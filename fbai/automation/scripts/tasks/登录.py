"""
登录任务
处理新账号的登录流程

账号格式（一行一个）：
c_user----密码----2FA码----邮箱----cookie----token

登录方式：
1. Cookie 登录：如果有 c_user= 开头的 cookie，使用 cookie 方式
2. 账号密码登录：如果没有 cookie，使用账号密码方式

流程：
1. 解析账号文件
2. 解析 VPN 文件
3. 为每个账号创建浏览器（配置 VPN）
4. 打开浏览器并登录
5. 验证登录状态
6. 登录成功/失败后从账号文件删除该账号
"""

import os
import sys
import time
import random
import json
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import unquote

# 路径设置
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(os.path.dirname(scripts_dir))

for path in [current_dir, scripts_dir, project_root]:
    if path not in sys.path:
        sys.path.insert(0, path)

# 动态查找脚本配置目录（与 browser_monitor_server 保持一致）
def _find_scripts_config_dir():
    """查找脚本配置目录"""
    possible_dirs = [
        # 打包后的位置1：exe所在目录/_internal/automation/scripts/脚本配置/
        os.path.join(os.path.dirname(sys.executable), "_internal", "automation", "scripts", "脚本配置"),
        # 打包后的位置2：exe所在目录/automation/scripts/脚本配置/
        os.path.join(os.path.dirname(sys.executable), "automation", "scripts", "脚本配置"),
        # 开发时的位置
        os.path.join(scripts_dir, "脚本配置"),
        # 当前工作目录
        os.path.join(os.getcwd(), "automation", "scripts", "脚本配置"),
    ]
    
    for dir_path in possible_dirs:
        if os.path.exists(dir_path):
            return dir_path
    
    # 默认使用开发时的位置
    return os.path.join(scripts_dir, "脚本配置")

# 脚本配置目录
脚本配置目录 = _find_scripts_config_dir()

# VPN 索引记录文件（用于持久化记录当前分配到哪个 VPN）
VPN索引文件 = os.path.join(脚本配置目录, "vpn_index.json")

# 账号文件路径
账号文件路径 = os.path.join(脚本配置目录, "账号.txt")

# 运行配置文件路径
运行配置路径 = os.path.join(脚本配置目录, "运行配置.json")

# 文件操作锁（防止多线程同时读写文件）
文件锁 = threading.Lock()

# 导入比特浏览器 API
try:
    from bitbrowser_api import bit_browser
except ImportError:
    bit_browser = None
    print("[登录] 警告: 无法导入 bitbrowser_api")

# ==================== 运行配置 ====================

def 读取运行配置() -> dict:
    """
    读取运行配置文件
    
    Returns:
        配置字典
    """
    默认配置 = {
        "线程数": 1,
        "手动打码": False
    }
    
    try:
        if os.path.exists(运行配置路径):
            with open(运行配置路径, 'r', encoding='utf-8') as f:
                配置 = json.load(f)
                # 合并默认配置
                for key in 默认配置:
                    if key not in 配置:
                        配置[key] = 默认配置[key]
                return 配置
    except Exception as e:
        print(f"[登录] 读取运行配置失败: {e}")
    
    return 默认配置

def 是否手动打码() -> bool:
    """检查是否开启手动打码模式"""
    return 读取运行配置().get("手动打码", False)

# ==================== 文件安全操作 ====================

def 安全读取账号文件() -> List[str]:
    """
    线程安全地读取账号文件
    
    Returns:
        账号行列表
    """
    with 文件锁:
        try:
            if os.path.exists(账号文件路径):
                with open(账号文件路径, 'r', encoding='utf-8') as f:
                    return [line.strip() for line in f.readlines() if line.strip() and not line.strip().startswith('#')]
        except Exception as e:
            print(f"[登录] 读取账号文件失败: {e}")
    return []

def 安全删除账号(账号原始行: str) -> bool:
    """
    线程安全地从账号文件中删除指定账号
    
    Args:
        账号原始行: 要删除的账号原始文本行
    
    Returns:
        是否成功删除
    """
    with 文件锁:
        try:
            if not os.path.exists(账号文件路径):
                return False
            
            # 读取所有行
            with open(账号文件路径, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 过滤掉要删除的账号
            新内容 = []
            已删除 = False
            for line in lines:
                # 保留注释行和空行
                if line.strip().startswith('#') or not line.strip():
                    新内容.append(line)
                elif line.strip() != 账号原始行.strip():
                    新内容.append(line)
                else:
                    已删除 = True
            
            # 写回文件
            with open(账号文件路径, 'w', encoding='utf-8') as f:
                f.writelines(新内容)
            
            return 已删除
        except Exception as e:
            print(f"[登录] 删除账号失败: {e}")
            return False

def 获取并锁定下一个账号() -> Optional['账号数据']:
    """
    线程安全地获取下一个待处理的账号
    获取后立即从文件中删除，防止其他线程重复处理
    
    Returns:
        账号数据，如果没有账号返回 None
    """
    with 文件锁:
        try:
            if not os.path.exists(账号文件路径):
                return None
            
            # 读取所有行
            with open(账号文件路径, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 找到第一个有效账号
            账号行 = None
            新内容 = []
            
            for line in lines:
                stripped = line.strip()
                # 保留注释行和空行
                if stripped.startswith('#') or not stripped:
                    新内容.append(line)
                elif 账号行 is None:
                    # 第一个有效账号，取出来处理
                    账号行 = stripped
                    # 不添加到新内容中（相当于删除）
                else:
                    新内容.append(line)
            
            if 账号行 is None:
                return None
            
            # 写回文件（已删除第一个账号）
            with open(账号文件路径, 'w', encoding='utf-8') as f:
                f.writelines(新内容)
            
            # 解析账号
            return _解析单个账号(账号行)
            
        except Exception as e:
            print(f"[登录] 获取账号失败: {e}")
            return None

def _解析单个账号(line: str) -> '账号数据':
    """
    智能解析单行账号数据
    
    支持的格式：
    - 邮箱----密码----2FA码----cookie
    - c_user----密码----2FA码----邮箱----cookie----token
    
    智能识别规则：
    - 包含 c_user= 或 datr= 等的是 cookie
    - 包含 @ 且是有效邮箱格式的是邮箱
    - 大写字母+数字组成（16位以上）的是 2FA 码
    - 其他短字符串是密码
    """
    import re
    
    parts = line.split('----')
    
    账号 = 账号数据(原始行=line)
    
    # 智能识别各字段
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # 1. 识别 cookie（包含 Facebook cookie 特征字段）
        if 'c_user=' in part or ('datr=' in part and ';' in part) or ('xs=' in part and ';' in part):
            账号.cookie = part
            # 从 cookie 中提取 c_user ID
            if 'c_user=' in part:
                match = re.search(r'c_user=(\d+)', part)
                if match and not 账号.c_user:
                    账号.c_user = match.group(1)
            continue
        
        # 2. 识别 2FA 码（大写字母+数字，16位以上，可能有空格）
        clean_part = part.replace(' ', '')
        if len(clean_part) >= 16 and re.match(r'^[A-Z0-9]+$', clean_part):
            账号.二次验证码 = clean_part
            continue
        
        # 3. 识别邮箱（包含 @ 且有域名格式）
        if '@' in part and re.match(r'^[^@]+@[^@]+\.[^@]+$', part):
            账号.邮箱 = part
            # 如果还没有 c_user，用邮箱作为用户名
            if not 账号.c_user:
                账号.c_user = part
            continue
        
        # 4. 识别 token（以 EAA 开头的长字符串）
        if part.startswith('EAA') and len(part) > 50:
            账号.token = part
            continue
        
        # 5. 其他情况：如果还没有密码，当作密码处理
        if not 账号.密码 and len(part) < 100:
            账号.密码 = part
    
    return 账号

# ==================== VPN 索引管理 ====================

def 读取VPN索引() -> int:
    """
    读取上次分配的 VPN 索引
    
    Returns:
        上次分配的索引，如果文件不存在返回 0
    """
    with 文件锁:
        try:
            if os.path.exists(VPN索引文件):
                with open(VPN索引文件, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("index", 0)
        except:
            pass
    return 0

def 保存VPN索引(索引: int):
    """
    保存当前分配的 VPN 索引
    
    Args:
        索引: 当前分配的索引
    """
    with 文件锁:
        try:
            with open(VPN索引文件, 'w', encoding='utf-8') as f:
                json.dump({"index": 索引}, f)
        except Exception as e:
            print(f"[登录] 保存 VPN 索引失败: {e}")

def 获取下一个VPN(vpn列表: List) -> Tuple[Optional[any], int]:
    """
    获取下一个要分配的 VPN（轮询方式，持久化记录）
    
    Args:
        vpn列表: VPN 数据列表
    
    Returns:
        (VPN数据, 当前索引)，如果列表为空返回 (None, -1)
    """
    if not vpn列表:
        return None, -1
    
    with 文件锁:
        # 读取上次的索引
        当前索引 = 0
        try:
            if os.path.exists(VPN索引文件):
                with open(VPN索引文件, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    当前索引 = data.get("index", 0)
        except:
            pass
        
        # 确保索引在有效范围内
        if 当前索引 >= len(vpn列表):
            当前索引 = 0
        
        # 获取当前 VPN
        vpn = vpn列表[当前索引]
        
        # 计算下一个索引并保存
        下一个索引 = (当前索引 + 1) % len(vpn列表)
        try:
            with open(VPN索引文件, 'w', encoding='utf-8') as f:
                json.dump({"index": 下一个索引}, f)
        except:
            pass
        
        return vpn, 当前索引

# ==================== 数据类 ====================

@dataclass
class 账号数据:
    """账号信息"""
    c_user: str = ""           # Facebook c_user
    密码: str = ""             # 登录密码
    二次验证码: str = ""       # 2FA 密钥
    邮箱: str = ""             # 绑定邮箱
    cookie: str = ""           # Cookie 字符串
    token: str = ""            # Access Token
    原始行: str = ""           # 原始文本行
    
    def 有cookie(self) -> bool:
        """是否有有效的 cookie"""
        return bool(self.cookie and "c_user=" in self.cookie)
    
    def 有密码(self) -> bool:
        """是否有密码"""
        return bool(self.密码)
    
    def 获取JSON格式Cookie(self) -> str:
        """
        将 cookie 字符串转换为比特浏览器需要的 JSON 格式
        
        输入格式: c_user=xxx;xs=xxx;oo=xxx;datr=xxx
        输出格式: [{"name":"c_user","value":"xxx","domain":".facebook.com",...}, ...]
        """
        if not self.cookie:
            return ""
        
        # 如果已经是 JSON 格式，直接返回
        if self.cookie.strip().startswith('['):
            return self.cookie
        
        cookie_list = []
        
        # 解析 key=value 格式
        for part in self.cookie.split(';'):
            part = part.strip()
            if not part or '=' not in part:
                continue
            
            key, value = part.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            cookie_item = {
                "name": key,
                "value": value,
                "domain": ".facebook.com",
                "path": "/",
                "hostOnly": False,
                "httpOnly": False,
                "session": False,
                "secure": False
            }
            cookie_list.append(cookie_item)
        
        if cookie_list:
            return json.dumps(cookie_list, ensure_ascii=False)
        
        return ""

@dataclass
class VPN数据:
    """VPN 配置（V2Ray HTTP 代理）"""
    host: str = "127.0.0.1"    # 代理主机
    port: int = 20001          # 代理端口
    protocol: str = "http"     # 代理协议
    tag: str = ""              # 标签

# ==================== 文件解析 ====================

def 解析账号文件(文件路径: str = None) -> List[账号数据]:
    """
    解析账号文件
    
    优先级：
    1. 本地账号.txt文件
    2. 远程分配的账号
    
    支持的格式：
    - 邮箱----密码----2FA码----cookie
    - c_user----密码----2FA码----邮箱----cookie----token
    
    Returns:
        账号数据列表
    """
    if 文件路径 is None:
        文件路径 = os.path.join(脚本配置目录, "账号.txt")
    
    账号列表 = []
    
    # 1. 尝试读取本地账号文件
    if os.path.exists(文件路径):
        try:
            with open(文件路径, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # 使用智能解析函数
                账号 = _解析单个账号(line)
                
                # 只添加有效账号
                if 账号.c_user or 账号.有cookie():
                    账号列表.append(账号)
        
        except Exception as e:
            print(f"[登录] 解析本地账号文件失败: {e}")
    
    # 2. 如果本地没有账号，尝试从远程获取
    if len(账号列表) == 0:
        print(f"[登录] 本地账号文件为空，尝试从远程获取...")
        
        try:
            # 导入远程账号管理模块
            import sys
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from 远程账号管理 import 获取远程账号
            
            远程账号列表 = 获取远程账号()
            
            if 远程账号列表:
                print(f"[登录] ✓ 从远程获取到 {len(远程账号列表)} 个账号")
                
                for line in 远程账号列表:
                    # 使用智能解析函数
                    账号 = _解析单个账号(line)
                    
                    # 只添加有效账号
                    if 账号.c_user or 账号.有cookie():
                        账号列表.append(账号)
            else:
                print(f"[登录] 远程也没有可用账号")
        
        except ImportError:
            print(f"[登录] 无法导入远程账号管理模块")
        except Exception as e:
            print(f"[登录] 获取远程账号失败: {e}")
    else:
        print(f"[登录] 使用本地账号文件，共 {len(账号列表)} 个账号")
    
    return 账号列表

def 解析VPN文件(文件路径: str = None) -> List[VPN数据]:
    """
    解析 V2Ray JSON 配置文件
    
    从 inbounds 中提取 HTTP 代理端口
    格式：127.0.0.1:端口
    
    Returns:
        VPN数据列表
    """
    if 文件路径 is None:
        文件路径 = os.path.join(脚本配置目录, "vpn.txt")
    
    if not os.path.exists(文件路径):
        return []
    
    vpn列表 = []
    
    try:
        with open(文件路径, 'r', encoding='utf-8') as f:
            内容 = f.read()
        
        # 解析 JSON
        配置 = json.loads(内容)
        
        # 从 inbounds 提取 HTTP 代理
        inbounds = 配置.get("inbounds", [])
        
        for inbound in inbounds:
            protocol = inbound.get("protocol", "")
            if protocol == "http":
                host = inbound.get("listen", "127.0.0.1")
                port = inbound.get("port", 0)
                tag = inbound.get("tag", "")
                
                if port > 0:
                    vpn = VPN数据(
                        host=host,
                        port=port,
                        protocol="http",
                        tag=tag
                    )
                    vpn列表.append(vpn)
        
    except json.JSONDecodeError as e:
        print(f"[登录] VPN 配置不是有效的 JSON: {e}")
    except Exception as e:
        print(f"[登录] 解析VPN文件失败: {e}")
    
    return vpn列表

# ==================== 浏览器操作 ====================

def 创建浏览器(账号: 账号数据, vpn: VPN数据 = None, log_func=None) -> Optional[str]:
    """
    创建新浏览器窗口
    
    Args:
        账号: 账号数据
        vpn: VPN配置（V2Ray HTTP 代理）
        log_func: 日志函数
    
    Returns:
        浏览器ID，失败返回 None
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(f"[登录] {msg}")
    
    if not bit_browser:
        log("比特浏览器 API 不可用")
        return None
    
    # 浏览器名称
    名称 = 账号.c_user[:8] if 账号.c_user else f"新账号_{int(time.time())}"
    
    # 构建创建参数
    创建参数 = {
        "name": 名称,
        "remark": f"c_user: {账号.c_user}",
        "proxyMethod": 2,  # 自定义代理
        "workbench": "disable",  # 关闭工作台/导航页
        "disableNotifications": True,  # 禁止弹出消息通知弹窗
        "disableTranslatePopup": True,  # 禁止谷歌翻译弹窗
        "browserFingerPrint": {
            "coreVersion": "140",
            "isIpCreateLanguage": False,  # 不基于IP生成语言
            "languages": "en-US",  # 固定英文
            "isIpCreateDisplayLanguage": False,  # 不基于IP生成界面语言
            "displayLanguages": "en-US",  # 界面语言固定英文
            # 权限设置 - 0:询问 1:允许 2:禁止
            "notificationPermission": 2,  # 禁止通知
            "mediaPermission": 2,  # 禁止媒体（摄像头/麦克风）
        }
    }
    
    # 配置 HTTP 代理（V2Ray 本地代理）
    if vpn:
        创建参数["proxyType"] = "http"
        创建参数["host"] = vpn.host
        创建参数["port"] = str(vpn.port)
        log(f"配置代理: {vpn.host}:{vpn.port}")
    else:
        创建参数["proxyType"] = "noproxy"
    
    # 设置 Cookie（转换为 JSON 格式）
    if 账号.有cookie():
        json_cookie = 账号.获取JSON格式Cookie()
        if json_cookie:
            创建参数["cookie"] = json_cookie
            log(f"设置 Cookie: c_user={账号.c_user}")
        else:
            log("⚠ Cookie 格式转换失败")
    
    # 设置平台账号信息（比特浏览器账号管理功能）
    # 参考文档: platform, userName, password, faSecretKey
    创建参数["platform"] = "https://www.facebook.com"  # 账号平台 URL
    
    # 设置账号（邮箱优先，否则用 c_user）
    if 账号.邮箱:
        创建参数["userName"] = 账号.邮箱
        log(f"设置账号: {账号.邮箱}")
    elif 账号.c_user:
        创建参数["userName"] = 账号.c_user
        log(f"设置账号: {账号.c_user}")
    
    # 设置密码
    if 账号.密码:
        创建参数["password"] = 账号.密码
        log(f"设置密码: {账号.密码}")
    
    # 设置 2FA 密钥（去掉空格和横线，转大写）
    if 账号.二次验证码:
        清理后密钥 = 账号.二次验证码.replace(" ", "").replace("-", "").upper()
        创建参数["faSecretKey"] = 清理后密钥
        log(f"设置 2FA 密钥: {清理后密钥}")
    
    try:
        result = bit_browser._request("/browser/update", 创建参数)
        
        if result.get("success"):
            browser_id = result.get("data", {}).get("id")
            log(f"✓ 浏览器创建成功: {browser_id}")
            return browser_id
        else:
            log(f"✗ 创建失败: {result.get('msg', '未知错误')}")
            return None
            
    except Exception as e:
        log(f"✗ 创建异常: {e}")
        return None

def Cookie登录(browser_id: str, 账号: 账号数据, log_func=None) -> bool:
    """
    使用 Cookie 方式登录
    
    流程：
    1. 打开浏览器
    2. 访问 Facebook
    3. 验证登录状态
    
    Args:
        browser_id: 浏览器ID
        账号: 账号数据
        log_func: 日志函数
    
    Returns:
        是否成功
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(f"[登录] {msg}")
    
    if not bit_browser:
        return False
    
    log("开始 Cookie 登录...")
    
    try:
        # 打开浏览器前，先修改浏览器设置禁止通知弹窗
        log("修改浏览器设置：禁止通知弹窗...")
        update_params = {
            "ids": [browser_id],
            "disableNotifications": True,
            "disableTranslatePopup": True,
        }
        update_result = bit_browser._request("/browser/update/partial", update_params)
        if update_result.get("success"):
            log("✓ 浏览器设置已修改")
        else:
            log(f"⚠ 修改浏览器设置失败: {update_result.get('msg', '未知错误')}")
        
        # 打开浏览器
        result = bit_browser.open_browser(browser_id)
        if not result.get("success"):
            log(f"✗ 打开浏览器失败: {result}")
            return "browser_failed"
        
        data = result.get("data", {})
        debug_port = data.get("http")
        driver_path = data.get("driver")
        
        log(f"浏览器已打开: {debug_port}")
        
        # 连接 Selenium
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        
        options = Options()
        options.add_experimental_option("debuggerAddress", debug_port)
        
        if driver_path:
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=options)
        else:
            driver = webdriver.Chrome(options=options)
        
        # 访问 Facebook
        log("访问 Facebook...")
        driver.get("https://www.facebook.com")
        time.sleep(5)
        
        # 检查登录状态
        current_url = driver.current_url
        page_title = driver.title
        
        log(f"当前页面: {page_title}")
        log(f"当前URL: {current_url}")
        
        # 判断是否登录成功
        if "/login" in current_url or "log in" in page_title.lower():
            log("✗ Cookie 登录失败，需要重新登录")
            return False
        
        if "/checkpoint" in current_url:
            log("⚠ 需要验证，请手动处理")
            return False
        
        # 使用统一的登录成功检测函数（兼容中英文界面）
        if _检查登录成功(driver, log):
            log("✓ Cookie 登录成功，已进入首页")
            # 处理浏览器权限弹窗
            _处理浏览器权限弹窗(driver, log)
            # 修改语言为英文
            _修改语言为英文(driver, log)
            return True
        else:
            log("✗ 无法确认登录成功，页面中找不到首页特定元素")
            log(f"当前URL: {current_url}")
            log(f"页面标题: {page_title}")
            return False
        
    except Exception as e:
        log(f"✗ 登录异常: {e}")
        return False

def _查找输入框(driver, 框类型: str, log_func=None):
    """
    查找输入框（支持中英文界面）
    
    Args:
        driver: Selenium WebDriver
        框类型: "email" 或 "password"
        log_func: 日志函数
    
    Returns:
        输入框元素，找不到返回 None
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    def log(msg):
        if log_func:
            log_func(msg)
    
    if 框类型 == "email":
        selectors = [
            (By.ID, "email"),                                    # 英文界面
            (By.NAME, "email"),                                  # 备选
            (By.CSS_SELECTOR, "input[type='text'][name='email']"),  # 通用
            (By.CSS_SELECTOR, "input[placeholder*='email' i]"),  # 包含 email 的 placeholder
            (By.CSS_SELECTOR, "input[placeholder*='邮箱']"),     # 中文 placeholder
            (By.CSS_SELECTOR, "input[placeholder*='手机号']"),   # 中文 placeholder
            (By.CSS_SELECTOR, "input[aria-label*='email' i]"),   # aria-label
            (By.CSS_SELECTOR, "input[aria-label*='邮箱']"),      # 中文 aria-label
            (By.CSS_SELECTOR, "input[type='text']:first-of-type"),  # 第一个文本输入框
        ]
    elif 框类型 == "password":
        selectors = [
            (By.ID, "pass"),                                     # 英文界面
            (By.NAME, "pass"),                                   # 备选
            (By.CSS_SELECTOR, "input[type='password']"),         # 通用
            (By.CSS_SELECTOR, "input[placeholder*='password' i]"),  # 包含 password 的 placeholder
            (By.CSS_SELECTOR, "input[placeholder*='密码']"),     # 中文 placeholder
            (By.CSS_SELECTOR, "input[aria-label*='password' i]"),  # aria-label
            (By.CSS_SELECTOR, "input[aria-label*='密码']"),      # 中文 aria-label
        ]
    else:
        return None
    
    for selector in selectors:
        try:
            element = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located(selector)
            )
            if element and element.is_displayed():
                if log_func:
                    log(f"✓ 找到{框类型}输入框: {selector}")
                return element
        except:
            continue
    
    return None

def 账号密码登录(browser_id: str, 账号: 账号数据, log_func=None) -> bool:
    """
    使用账号密码方式登录
    
    流程：
    1. 打开浏览器
    2. 访问 Facebook 登录页
    3. 输入邮箱/手机号
    4. 输入密码
    5. 处理 2FA（如果需要）
    6. 验证登录状态
    
    Args:
        browser_id: 浏览器ID
        账号: 账号数据
        log_func: 日志函数
    
    Returns:
        是否成功
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(f"[登录] {msg}")
    
    if not bit_browser:
        return False
    
    if not 账号.有密码():
        log("✗ 没有密码，无法登录")
        return False
    
    log("开始账号密码登录...")
    
    try:
        # 打开浏览器前，先修改浏览器设置禁止通知弹窗
        log("修改浏览器设置：禁止通知弹窗...")
        update_params = {
            "ids": [browser_id],
            "disableNotifications": True,
            "disableTranslatePopup": True,
        }
        update_result = bit_browser._request("/browser/update/partial", update_params)
        if update_result.get("success"):
            log("✓ 浏览器设置已修改")
        else:
            log(f"⚠ 修改浏览器设置失败: {update_result.get('msg', '未知错误')}")
        
        # 打开浏览器
        result = bit_browser.open_browser(browser_id)
        if not result.get("success"):
            log(f"✗ 打开浏览器失败: {result}")
            return "browser_failed"
        
        data = result.get("data", {})
        debug_port = data.get("http")
        driver_path = data.get("driver")
        
        log(f"浏览器已打开: {debug_port}")
        
        # 连接 Selenium
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        options = Options()
        options.add_experimental_option("debuggerAddress", debug_port)
        
        if driver_path:
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=options)
        else:
            driver = webdriver.Chrome(options=options)
        
        # 访问 Facebook 登录页
        log("访问 Facebook 登录页...")
        driver.get("https://www.facebook.com/login")
        time.sleep(3)
        
        # 输入邮箱
        登录账号 = 账号.邮箱 if 账号.邮箱 else 账号.c_user
        log(f"输入账号: {登录账号}")
        
        try:
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email_input.clear()
            for char in 登录账号:
                email_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
        except Exception as e:
            log(f"✗ 找不到邮箱输入框: {e}")
            return False
        
        time.sleep(random.uniform(0.5, 1.5))
        
        # 输入密码
        log("输入密码...")
        try:
            pass_input = driver.find_element(By.ID, "pass")
            pass_input.clear()
            for char in 账号.密码:
                pass_input.send_keys(char)
                time.sleep(random.uniform(0.03, 0.1))
        except Exception as e:
            log(f"✗ 找不到密码输入框: {e}")
            return False
        
        time.sleep(random.uniform(0.5, 1.0))
        
        # 点击登录按钮
        log("点击登录...")
        try:
            login_btn = driver.find_element(By.NAME, "login")
            login_btn.click()
        except:
            # 备选方案
            try:
                login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_btn.click()
            except Exception as e:
                log(f"✗ 找不到登录按钮: {e}")
                return False
        
        # 等待页面跳转
        time.sleep(5)
        
        # 检查是否有 reCAPTCHA 图形验证（在 2FA 之前检测）
        if _检测图形验证(driver):
            if 是否手动打码():
                log("检测到图形验证，等待人工处理...")
                if _等待手动打码(driver, log):
                    log("✓ 图形验证已通过，继续登录流程")
                    
                    # 图形验证完成后，检查是否回到了登录页面
                    time.sleep(2)
                    current_url = driver.current_url
                    if "/login" in current_url:
                        log("图形验证后回到登录页面，重新输入账号密码...")
                        # 重新输入账号密码
                        try:
                            from selenium.webdriver.common.by import By
                            from selenium.webdriver.support.ui import WebDriverWait
                            from selenium.webdriver.support import expected_conditions as EC
                            
                            登录账号 = 账号.邮箱 if 账号.邮箱 else 账号.c_user
                            
                            # 输入邮箱
                            email_input = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.ID, "email"))
                            )
                            email_input.clear()
                            for char in 登录账号:
                                email_input.send_keys(char)
                                time.sleep(random.uniform(0.05, 0.15))
                            log(f"重新输入账号: {登录账号}")
                            
                            time.sleep(random.uniform(0.5, 1.5))
                            
                            # 输入密码
                            pass_input = driver.find_element(By.ID, "pass")
                            pass_input.clear()
                            for char in 账号.密码:
                                pass_input.send_keys(char)
                                time.sleep(random.uniform(0.03, 0.1))
                            log("重新输入密码...")
                            
                            time.sleep(random.uniform(0.5, 1.0))
                            
                            # 点击登录按钮
                            try:
                                login_btn = driver.find_element(By.NAME, "login")
                                login_btn.click()
                            except:
                                login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                                login_btn.click()
                            log("重新点击登录...")
                            
                            # 等待页面跳转
                            time.sleep(5)
                        except Exception as e:
                            log(f"重新输入账号密码失败: {e}")
                            return False
                else:
                    log("✗ 图形验证超时未完成")
                    return "captcha"
            else:
                log("✗ 检测到图形验证，需要人工处理")
                return "captcha"
        
        # 检查是否需要 2FA
        current_url = driver.current_url
        page_source = driver.page_source.lower()
        
        if "two-factor" in current_url or "checkpoint" in current_url or "验证码" in page_source or "code" in page_source:
            if 账号.二次验证码:
                log("需要 2FA 验证，正在处理...")
                成功 = _处理2FA(driver, 账号.二次验证码, log)
                if 成功 == "captcha":
                    return "captcha"
                if 成功 == "blocked":
                    return "blocked"
                if 成功 == "need_relogin":
                    # 需要重新登录，重新输入账号密码
                    log("需要重新登录，重新输入账号密码...")
                    try:
                        from selenium.webdriver.common.by import By
                        from selenium.webdriver.support.ui import WebDriverWait
                        from selenium.webdriver.support import expected_conditions as EC
                        
                        # 确保在登录页面
                        current_url = driver.current_url
                        if "/login" not in current_url:
                            driver.get("https://www.facebook.com/login")
                            time.sleep(3)
                        
                        登录账号 = 账号.邮箱 if 账号.邮箱 else 账号.c_user
                        
                        # 输入邮箱
                        email_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, "email"))
                        )
                        email_input.clear()
                        for char in 登录账号:
                            email_input.send_keys(char)
                            time.sleep(random.uniform(0.05, 0.15))
                        log(f"重新输入账号: {登录账号}")
                        
                        time.sleep(random.uniform(0.5, 1.5))
                        
                        # 输入密码
                        pass_input = driver.find_element(By.ID, "pass")
                        pass_input.clear()
                        for char in 账号.密码:
                            pass_input.send_keys(char)
                            time.sleep(random.uniform(0.03, 0.1))
                        log("重新输入密码...")
                        
                        time.sleep(random.uniform(0.5, 1.0))
                        
                        # 点击登录按钮
                        try:
                            login_btn = driver.find_element(By.NAME, "login")
                            login_btn.click()
                        except:
                            login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                            login_btn.click()
                        log("重新点击登录...")
                        
                        # 等待页面跳转
                        time.sleep(5)
                        
                        # 再次检查是否需要 2FA
                        current_url = driver.current_url
                        if "two-factor" in current_url or "checkpoint" in current_url:
                            log("重新进入 2FA 验证...")
                            成功 = _处理2FA(driver, 账号.二次验证码, log)
                            if 成功 == "captcha":
                                return "captcha"
                            if 成功 == "blocked":
                                return "blocked"
                            if not 成功:
                                return False
                    except Exception as e:
                        log(f"重新登录失败: {e}")
                        return False
                if not 成功:
                    return False
            else:
                log("⚠ 需要 2FA 但没有密钥，请手动处理")
                return False
        
        # 再次检查登录状态
        time.sleep(3)
        current_url = driver.current_url
        page_title = driver.title
        
        if "/login" in current_url or "log in" in page_title.lower():
            log("✗ 登录失败")
            return False
        
        if "facebook.com" in current_url and "/checkpoint" not in current_url:
            log("✓ 账号密码登录成功")
            # 处理浏览器权限弹窗
            _处理浏览器权限弹窗(driver, log)
            # 修改语言为英文
            _修改语言为英文(driver, log)
            return True
        
        log("? 登录状态未知")
        return False
        
    except Exception as e:
        log(f"✗ 登录异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def _检测图形验证(driver, 检测次数: int = 10, 间隔秒数: float = 3) -> bool:
    """
    检测页面是否有 reCAPTCHA 图形验证（多次检测，防止误判）
    
    因为页面可能在几秒后跳转到 2FA 页面，VPN 加载也会慢一些
    所以需要多次检测确认（默认 10 次，间隔 3 秒，共 30 秒）
    只有连续多次都检测到图形验证才返回 True
    
    检测元素：
    - .recaptcha-checkbox
    - #recaptcha-anchor
    - .g-recaptcha
    - iframe[src*='recaptcha']
    - iframe[title*='reCAPTCHA']
    
    Args:
        driver: Selenium WebDriver
        检测次数: 检测次数，默认 3 次
        间隔秒数: 每次检测间隔，默认 2 秒
    
    Returns:
        True: 确认是图形验证页面
        False: 不是图形验证页面（或已跳转）
    """
    from selenium.webdriver.common.by import By
    
    连续检测到次数 = 0
    
    for i in range(检测次数):
        本次检测到 = False
        
        try:
            # 检测 reCAPTCHA checkbox 元素
            recaptcha_selectors = [
                ".recaptcha-checkbox",
                "#recaptcha-anchor",
                ".g-recaptcha",
            ]
            
            for selector in recaptcha_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        if el.is_displayed():
                            本次检测到 = True
                            break
                except:
                    continue
                if 本次检测到:
                    break
            
            # 检测 reCAPTCHA iframe
            if not 本次检测到:
                iframe_selectors = [
                    "iframe[src*='recaptcha']",
                    "iframe[title*='reCAPTCHA']",
                ]
                
                for selector in iframe_selectors:
                    try:
                        iframes = driver.find_elements(By.CSS_SELECTOR, selector)
                        for iframe in iframes:
                            if iframe.is_displayed():
                                本次检测到 = True
                                break
                    except:
                        continue
                    if 本次检测到:
                        break
            
            # 检测 URL 中是否包含验证相关路径
            if not 本次检测到:
                try:
                    current_url = driver.current_url
                    if "/authentication/" in current_url or "pre_authentication" in current_url:
                        本次检测到 = True
                except:
                    pass
            
        except Exception:
            本次检测到 = False
        
        if 本次检测到:
            连续检测到次数 += 1
        else:
            # 没检测到，说明页面已跳转，重置计数
            连续检测到次数 = 0
        
        # 如果不是最后一次检测，等待一下
        if i < 检测次数 - 1:
            time.sleep(间隔秒数)
    
    # 只有连续检测到才返回 True
    return 连续检测到次数 >= 检测次数

def _等待手动打码(driver, log_func=None, 超时秒数: int = 300) -> bool:
    """
    等待人工完成图形验证
    
    检测逻辑：
    1. 每 3 秒检测一次是否还有图形验证
    2. 如果图形验证消失，说明人工已完成，返回 True
    3. 如果超时（默认 5 分钟），返回 False
    
    Args:
        driver: Selenium WebDriver
        log_func: 日志函数
        超时秒数: 超时时间，默认 300 秒（5分钟）
    
    Returns:
        True: 人工已完成验证
        False: 超时未完成
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(f"[登录] {msg}")
    
    log(f"⏳ 等待人工完成图形验证（超时: {超时秒数}秒）...")
    
    开始时间 = time.time()
    检测间隔 = 3
    
    while time.time() - 开始时间 < 超时秒数:
        # 检测是否还有图形验证
        有验证 = False
        
        try:
            # 检测 reCAPTCHA 元素
            recaptcha_selectors = [
                ".recaptcha-checkbox",
                "#recaptcha-anchor",
                ".g-recaptcha",
            ]
            
            for selector in recaptcha_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        if el.is_displayed():
                            有验证 = True
                            break
                except:
                    continue
                if 有验证:
                    break
            
            # 检测 reCAPTCHA iframe
            if not 有验证:
                iframe_selectors = [
                    "iframe[src*='recaptcha']",
                    "iframe[title*='reCAPTCHA']",
                ]
                
                for selector in iframe_selectors:
                    try:
                        iframes = driver.find_elements(By.CSS_SELECTOR, selector)
                        for iframe in iframes:
                            if iframe.is_displayed():
                                有验证 = True
                                break
                    except:
                        continue
                    if 有验证:
                        break
            
            # 检测 URL
            if not 有验证:
                try:
                    current_url = driver.current_url
                    if "/authentication/" in current_url or "pre_authentication" in current_url:
                        有验证 = True
                except:
                    pass
            
        except Exception:
            pass
        
        if not 有验证:
            log("✓ 图形验证已完成")
            return True
        
        # 显示剩余时间
        已等待 = int(time.time() - 开始时间)
        剩余 = 超时秒数 - 已等待
        if 已等待 % 30 == 0 and 已等待 > 0:  # 每 30 秒提示一次
            log(f"⏳ 等待人工打码中... 剩余 {剩余} 秒")
        
        time.sleep(检测间隔)
    
    log("✗ 等待超时，人工未完成验证")
    return False

def _检查登录成功(driver, log_func=None) -> bool:
    """
    检查是否登录成功（通过检测 Facebook 首页图标）
    
    Facebook 首页图标是一个 SVG path 元素，登录成功后会显示在页面左上角
    
    Args:
        driver: Selenium WebDriver
        log_func: 日志函数（可选，用于输出调试信息）
    
    Returns:
        是否登录成功
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
    
    try:
        # 检查 URL 是否是 Facebook 首页或个人页面
        current_url = driver.current_url
        
        # 排除验证/登录相关页面
        排除页面 = ["/checkpoint", "/login", "two-factor", "two_step_verification", "/authentication/"]
        for 页面 in 排除页面:
            if 页面 in current_url:
                return False
        
        # 方式1: 检查首页图标 SVG path（Facebook logo）
        # 首页图标的 SVG path 特征
        try:
            # 方式1a: 通过 Facebook logo 的 SVG path d 属性检测（最可靠，兼容中英文）
            # Facebook logo 的 path d 属性包含特征字符串
            all_paths = driver.find_elements(By.TAG_NAME, "path")
            for path in all_paths:
                try:
                    d_attr = path.get_attribute("d")
                    if d_attr and "M13.651 35.471v-11.97H9.936V18h3.715v-2.37c0-6.127" in d_attr:
                        if path.is_displayed():
                            # 找到了 Facebook logo，说明已登录
                            if log_func:
                                log("[检测] ✓ 通过 Facebook logo SVG path 检测到登录成功")
                            return True
                except:
                    continue
        except:
            pass
        
        try:
            # 方式1b: 检查搜索框（登录后才有，兼容中英文）
            # 中文：aria-label="搜索 Facebook"
            # 英文：aria-label="Search Facebook"
            search_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='search'][role='combobox']")
            for search_input in search_inputs:
                if search_input.is_displayed():
                    aria_label = search_input.get_attribute("aria-label") or ""
                    # 检查是否包含 "搜索" 或 "Search" 和 "Facebook"
                    if ("搜索" in aria_label or "Search" in aria_label) and "Facebook" in aria_label:
                        # 找到了搜索框，说明已登录
                        if log_func:
                            log(f"[检测] ✓ 通过搜索框检测到登录成功 (aria-label: {aria_label})")
                        return True
        except:
            pass
        
        try:
            # 方式1c: Facebook 首页图标通常在 aria-label="Facebook" 的链接中
            home_links = driver.find_elements(By.CSS_SELECTOR, "a[aria-label='Facebook']")
            for link in home_links:
                if link.is_displayed():
                    # 找到了首页链接，说明已登录
                    if log_func:
                        log("[检测] ✓ 通过首页链接检测到登录成功")
                    return True
        except:
            pass
        
        # 方式2: 检查是否有用户头像/个人资料入口
        try:
            # 登录后会有用户头像
            avatar_selectors = [
                "svg[aria-label='Your profile']",
                "image[style*='border-radius']",  # 圆形头像
                "[data-visualcompletion='media-vc-image']",  # 头像图片
            ]
            for selector in avatar_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        if log_func:
                            log(f"[检测] ✓ 通过用户头像检测到登录成功 (selector: {selector})")
                        return True
        except:
            pass
        
        # 方式3: 检查导航栏中的首页/Home 链接
        try:
            nav_items = driver.find_elements(By.CSS_SELECTOR, "[role='navigation'] a[href='/']")
            for item in nav_items:
                if item.is_displayed():
                    if log_func:
                        log("[检测] ✓ 通过导航栏首页链接检测到登录成功")
                    return True
        except:
            pass
        
        # 方式4: 检查是否有 Messenger 图标（登录后才有）
        try:
            messenger_icons = driver.find_elements(By.CSS_SELECTOR, "a[aria-label='Messenger']")
            for icon in messenger_icons:
                if icon.is_displayed():
                    if log_func:
                        log("[检测] ✓ 通过 Messenger 图标检测到登录成功")
                    return True
        except:
            pass
        
        # 方式5: 检查页面标题（登录后标题通常是 "Facebook"）
        try:
            title = driver.title.lower()
            if title == "facebook" and "log in" not in title:
                # 再确认 URL 是 facebook.com 首页
                if "facebook.com" in current_url and current_url.rstrip('/').endswith('facebook.com'):
                    if log_func:
                        log("[检测] ✓ 通过页面标题检测到登录成功")
                    return True
        except:
            pass
        
        return False
        
    except Exception:
        return False

def _处理浏览器权限弹窗(driver, log_func=None) -> bool:
    """
    处理浏览器权限弹窗（通知权限、位置权限等）
    
    这个弹窗是浏览器级别的权限请求，不是 DOM 元素，所以无法通过 Selenium 直接点击。
    解决方案：
    1. 使用 Chrome DevTools Protocol (CDP) 通过 send_command 处理权限
    2. 或者通过 Chrome 启动参数预先禁用权限请求
    
    Args:
        driver: Selenium WebDriver
        log_func: 日志函数
    
    Returns:
        是否成功处理
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(f"[登录] {msg}")
    
    try:
        # 方法1: 使用 Chrome DevTools Protocol 处理权限
        # 这需要 Selenium 4.x 支持
        try:
            # 获取 Chrome DevTools Protocol 连接
            # 拒绝所有权限请求（包括通知、位置、麦克风等）
            driver.execute_cdp_cmd('Browser.grantPermissions', {
                "origin": "https://www.facebook.com",
                "permissions": []  # 空列表表示拒绝所有权限
            })
            log("✓ 已通过 CDP 拒绝权限请求")
            time.sleep(1)
            return True
        except Exception as e:
            log(f"⚠️ CDP 方法失败: {e}")
        
        # 方法2: 尝试按 Escape 键关闭弹窗
        try:
            log("尝试按 Escape 键关闭弹窗...")
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            log("✓ 已按 Escape 键关闭弹窗")
            time.sleep(1)
            return True
        except Exception as e:
            log(f"⚠️ Escape 键方法失败: {e}")
        
        # 方法3: 尝试找到并点击 Block 按钮（如果弹窗还在）
        try:
            log("尝试查找并点击 Block 按钮...")
            # 尝试多种方式查找 Block 按钮
            block_selectors = [
                (By.XPATH, "//button[contains(text(), 'Block')]"),
                (By.XPATH, "//button[contains(text(), 'block')]"),
                (By.CSS_SELECTOR, "button:contains('Block')"),
                (By.XPATH, "//div[@role='dialog']//button[2]"),  # 通常 Block 是第二个按钮
            ]
            
            for selector in block_selectors:
                try:
                    block_button = driver.find_element(*selector)
                    if block_button and block_button.is_displayed():
                        block_button.click()
                        log("✓ 已点击 Block 按钮")
                        time.sleep(1)
                        return True
                except:
                    continue
        except Exception as e:
            log(f"⚠️ 点击 Block 按钮失败: {e}")
        
        # 方法4: 等待弹窗自动消失（某些情况下弹窗会自动关闭）
        log("⏳ 等待权限弹窗自动处理...")
        time.sleep(3)
        return True
        
    except Exception as e:
        log(f"⚠️ 处理权限弹窗异常: {e}")
        return False

def _修改语言为英文(driver, log_func=None) -> bool:
    """
    登录成功后将 Facebook 界面语言修改为英文
    
    流程：
    1. 先检查当前是否已经是英文（多种方式检测）
    2. 如果不是英文，访问语言设置页面修改
    
    Args:
        driver: Selenium WebDriver
        log_func: 日志函数
    
    Returns:
        是否成功
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(f"[登录] {msg}")
    
    try:
        # 先确保在首页
        current_url = driver.current_url
        if "facebook.com" not in current_url or "/settings" in current_url:
            driver.get("https://www.facebook.com")
            time.sleep(3)
        
        # 检查当前是否已经是英文界面
        # 核心判断：只要找到 aria-label="Search Facebook" 的搜索框，就是英文界面
        是英文 = False
        
        try:
            # 查找所有搜索框
            search_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='search'][role='combobox']")
            
            找到英文搜索框 = False
            找到中文搜索框 = False
            
            for search_input in search_inputs:
                if search_input.is_displayed():
                    aria_label = search_input.get_attribute("aria-label") or ""
                    placeholder = search_input.get_attribute("placeholder") or ""
                    
                    # 精确匹配：aria-label 或 placeholder 是 "Search Facebook"
                    if aria_label == "Search Facebook" or placeholder == "Search Facebook":
                        找到英文搜索框 = True
                        log(f"[语言检测] ✓ 找到英文搜索框 (aria-label: {aria_label}, placeholder: {placeholder})")
                    # 中文搜索框
                    elif "搜索" in aria_label or "搜索" in placeholder:
                        找到中文搜索框 = True
                        log(f"[语言检测] 找到中文搜索框 (aria-label: {aria_label}, placeholder: {placeholder})")
            
            # 判断逻辑：只有找到英文搜索框才算英文界面
            if 找到英文搜索框:
                是英文 = True
                log("[语言检测] 结论：英文界面（找到英文搜索框）")
            else:
                是英文 = False
                if 找到中文搜索框:
                    log("[语言检测] 结论：中文界面（只找到中文搜索框，没有英文搜索框）")
                else:
                    log("[语言检测] 结论：非英文界面（未找到英文搜索框）")
        except Exception as e:
            log(f"[语言检测] 检测异常: {e}")
            是英文 = False
        
        if 是英文:
            log("当前已是英文界面，跳过语言设置")
            return True
        
        log("检测到非英文界面，修改语言为英文...")
        
        # 访问语言和地区设置页面
        driver.get("https://www.facebook.com/settings/?tab=language_and_region")
        time.sleep(4)
        
        # 点击语言设置区域
        语言设置文本 = [
            "使用你的首选语言查看按钮",
            "使用你的首选语言",
            "首选语言",
            "Language for buttons",
            "preferred language",
            "Facebook language"
        ]
        
        已点击设置 = False
        for 文本 in 语言设置文本:
            if 已点击设置:
                break
            try:
                elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{文本}')]")
                for el in elements:
                    if el.is_displayed():
                        # 点击这个元素或其父元素
                        driver.execute_script("arguments[0].click();", el)
                        log(f"已点击语言设置: {文本[:20]}...")
                        已点击设置 = True
                        time.sleep(3)
                        break
            except:
                continue
        
        if not 已点击设置:
            # 尝试点击第一个可点击的设置项
            try:
                # 查找设置页面中的可点击区域
                clickable_divs = driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
                for div in clickable_divs:
                    if div.is_displayed():
                        text = div.text
                        if "语言" in text or "language" in text.lower():
                            driver.execute_script("arguments[0].click();", div)
                            log("已点击语言设置区域")
                            已点击设置 = True
                            time.sleep(3)
                            break
            except:
                pass
        
        # 等待弹窗出现
        time.sleep(2)
        
        # 在弹窗中查找并选择 English (US)
        英文选项文本 = ["English (US)", "English(US)", "英语（美国）", "英语(美国)"]
        已选择英文 = False
        
        for 文本 in 英文选项文本:
            if 已选择英文:
                break
            try:
                # 查找包含该文本的元素
                options = driver.find_elements(By.XPATH, f"//*[contains(text(), '{文本}')]")
                for opt in options:
                    if opt.is_displayed():
                        driver.execute_script("arguments[0].click();", opt)
                        log(f"已选择: {文本}")
                        已选择英文 = True
                        time.sleep(2)
                        break
            except:
                continue
        
        if not 已选择英文:
            # 尝试在下拉列表或单选按钮中查找
            try:
                # 查找 radio 或 checkbox
                inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='radio'], input[type='checkbox']")
                for inp in inputs:
                    try:
                        # 获取关联的 label 文本
                        parent = inp.find_element(By.XPATH, "./ancestor::div[1]")
                        if "English" in parent.text:
                            driver.execute_script("arguments[0].click();", inp)
                            log("已选择 English 选项")
                            已选择英文 = True
                            time.sleep(2)
                            break
                    except:
                        continue
            except:
                pass
        
        # 点击确定/保存按钮
        确定按钮文本 = ["确定", "确认", "Save", "保存", "OK", "Done", "Submit", "Apply"]
        已确定 = False
        
        for 文本 in 确定按钮文本:
            if 已确定:
                break
            try:
                # 方式1: 查找 role="button" 的元素
                buttons = driver.find_elements(By.XPATH, f"//*[@role='button']//*[contains(text(), '{文本}')]")
                for btn in buttons:
                    if btn.is_displayed():
                        # 向上找到 role="button" 的父元素
                        parent = btn
                        for _ in range(5):
                            parent = parent.find_element(By.XPATH, "./..")
                            if parent.get_attribute("role") == "button":
                                break
                        driver.execute_script("arguments[0].click();", parent)
                        log(f"已点击: {文本}")
                        已确定 = True
                        time.sleep(3)
                        break
                
                # 方式2: 直接查找包含文本的元素
                if not 已确定:
                    elements = driver.find_elements(By.XPATH, f"//*[text()='{文本}']")
                    for el in elements:
                        if el.is_displayed():
                            driver.execute_script("arguments[0].click();", el)
                            log(f"已点击: {文本}")
                            已确定 = True
                            time.sleep(3)
                            break
            except:
                continue
        
        # 回到首页
        driver.get("https://www.facebook.com")
        time.sleep(3)
        
        # 验证是否成功
        try:
            home_elements = driver.find_elements(By.XPATH, "//span[text()='Home']")
            for el in home_elements:
                if el.is_displayed():
                    log("✓ 语言已成功修改为英文")
                    return True
        except:
            pass
        
        log("语言设置完成")
        return True
        
    except Exception as e:
        log(f"修改语言失败: {e}")
        # 确保回到首页
        try:
            driver.get("https://www.facebook.com")
            time.sleep(2)
        except:
            pass
        return False

def _处理2FA(driver, 密钥: str, log_func, 最大重试次数: int = 5) -> bool:
    """
    处理 2FA 验证（支持重试）
    
    Args:
        driver: Selenium WebDriver
        密钥: 2FA 密钥
        log_func: 日志函数
        最大重试次数: 最大重试次数，默认5次
    
    Returns:
        True: 成功
        False: 失败
        "blocked": 账号被封禁
        "captcha": 需要图形验证
        "need_relogin": 需要重新登录（回到了登录页面或首页）
    """
    def log(msg):
        if log_func:
            log_func(msg)
    
    try:
        import pyotp
    except ImportError:
        log("✗ 需要安装 pyotp: pip install pyotp")
        return False
    
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    
    # 清理密钥格式（去掉空格，转大写）
    密钥 = 密钥.replace(" ", "").replace("-", "").upper()
    
    # 验证密钥格式
    try:
        totp = pyotp.TOTP(密钥)
        # 测试生成验证码
        totp.now()
    except Exception as e:
        log(f"✗ 2FA 密钥格式无效: {e}")
        return False
    
    上次验证码 = ""
    
    for 尝试次数 in range(最大重试次数):
        try:
            # 先检查当前页面类型
            current_url = driver.current_url
            
            # 检查是否回到了登录页面或首页（不是 2FA 页面）
            if "/login" in current_url and "two" not in current_url and "checkpoint" not in current_url:
                log("⚠ 检测到回到登录页面，需要重新登录")
                return "need_relogin"
            
            # 检查是否已经在首页（登录成功了）
            if current_url.rstrip('/').endswith('facebook.com') or current_url == "https://www.facebook.com/":
                # 再确认一下是否真的登录成功
                if _检查登录成功(driver):
                    log("✓ 已登录成功")
                    return True
                else:
                    # 可能是首页但未登录，需要重新登录
                    log("⚠ 在首页但未检测到登录状态，需要重新登录")
                    return "need_relogin"
            
            # 检查是否有 reCAPTCHA 图形验证
            try:
                # 检测 reCAPTCHA checkbox
                recaptcha_elements = driver.find_elements(By.CSS_SELECTOR, ".recaptcha-checkbox, #recaptcha-anchor, .g-recaptcha")
                for el in recaptcha_elements:
                    if el.is_displayed():
                        log("✗ 检测到 reCAPTCHA 图形验证")
                        return "captcha"
                
                # 检测 reCAPTCHA iframe
                recaptcha_iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha'], iframe[title*='reCAPTCHA']")
                for iframe in recaptcha_iframes:
                    if iframe.is_displayed():
                        log("✗ 检测到 reCAPTCHA 图形验证")
                        return "captcha"
            except:
                pass
            
            # 检查是否需要人脸验证（封号）
            try:
                人脸验证文本 = [
                    "通过自拍视频验证", 
                    "Verify your identity", 
                    "selfie video", 
                    "自拍视频",
                    "confirm you're human",
                    "Confirm you're human",
                    "confirm you're human to use your account",
                    "Confirm you're human to use your account"
                ]
                for 文本 in 人脸验证文本:
                    elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{文本}')]")
                    for el in elements:
                        if el.is_displayed():
                            log(f"✗ 检测到封号提示: {文本}")
                            return "blocked"
            except:
                pass
            
            # 检查是否有"信任这台设备"按钮（2FA 成功后的页面）
            try:
                信任设备文本 = ["信任这台设备", "Trust this device", "Trust this browser", "信任此浏览器"]
                for 文本 in 信任设备文本:
                    elements = driver.find_elements(By.XPATH, f"//span[contains(text(), '{文本}')]")
                    for el in elements:
                        if el.is_displayed():
                            log(f"检测到信任设备按钮，点击: {文本}")
                            # 向上找到可点击的父元素
                            parent = el
                            for _ in range(5):
                                parent = parent.find_element(By.XPATH, "./..")
                                role = parent.get_attribute("role")
                                if role == "button":
                                    break
                            driver.execute_script("arguments[0].click();", parent)
                            time.sleep(3)
                            
                            # 检查是否登录成功（首页图标）
                            if _检查登录成功(driver):
                                log("✓ 2FA 验证成功，已登录")
                                return True
                            break
            except:
                pass
            
            # 检查是否已经登录成功
            if _检查登录成功(driver):
                log("✓ 2FA 验证成功，已登录")
                return True
            
            log(f"2FA 验证尝试 [{尝试次数 + 1}/{最大重试次数}]...")
            
            # 等待新验证码（TOTP 每30秒更新，需要等到新的验证码）
            if 尝试次数 > 0:
                log("等待新验证码...")
                # 等待直到验证码变化（最多等35秒）
                等待开始 = time.time()
                while time.time() - 等待开始 < 35:
                    新验证码 = totp.now()
                    if 新验证码 != 上次验证码:
                        break
                    time.sleep(2)
            
            # 生成验证码
            验证码 = totp.now()
            上次验证码 = 验证码
            log(f"生成 2FA 验证码: {验证码}")
            
            # 查找验证码输入框
            time.sleep(2)
            
            输入框 = None
            输入框选择器 = [
                "input[name='approvals_code']",
                "input[type='text']",
                "input[autocomplete='one-time-code']",
            ]
            
            for 选择器 in 输入框选择器:
                try:
                    inputs = driver.find_elements(By.CSS_SELECTOR, 选择器)
                    for input_el in inputs:
                        if input_el.is_displayed():
                            输入框 = input_el
                            break
                    if 输入框:
                        break
                except:
                    continue
            
            # 如果没找到输入框，尝试点击"试试其他方式" / "Try another way"
            if not 输入框:
                log("未找到输入框，尝试切换验证方式...")
                
                # 先检查并点击"Dismiss"按钮（如果存在）
                try:
                    dismiss_texts = ["Dismiss", "dismiss", "关闭", "取消"]
                    for text in dismiss_texts:
                        # 方式1: 查找包含文本的按钮
                        buttons = driver.find_elements(By.XPATH, f"//button[contains(., '{text}')]")
                        for btn in buttons:
                            if btn.is_displayed():
                                driver.execute_script("arguments[0].click();", btn)
                                log(f"✓ 已点击Dismiss按钮: {text}")
                                time.sleep(2)
                                break
                        
                        # 方式2: 查找role="button"包含文本的元素
                        if not buttons:
                            spans = driver.find_elements(By.XPATH, f"//*[@role='button']//span[contains(text(), '{text}')]")
                            for span in spans:
                                if span.is_displayed():
                                    # 向上找到role="button"的父元素
                                    parent = span
                                    for _ in range(5):
                                        parent = parent.find_element(By.XPATH, "./..")
                                        if parent.get_attribute("role") == "button":
                                            break
                                    driver.execute_script("arguments[0].click();", parent)
                                    log(f"✓ 已点击Dismiss按钮: {text}")
                                    time.sleep(2)
                                    break
                except Exception as e:
                    log(f"检查Dismiss按钮时出错: {e}")
                
                # 点击"试试其他方式" / "Try another way"
                其他方式文本 = ["试试其他方式", "Try another way", "try another way", "Try Another Way"]
                已点击其他方式 = False
                
                # 增强识别：尝试多种方式查找
                for 文本 in 其他方式文本:
                    if 已点击其他方式:
                        break
                    
                    try:
                        # 方式1: 精确匹配文本的span
                        spans = driver.find_elements(By.XPATH, f"//span[text()='{文本}']")
                        for span in spans:
                            if span.is_displayed():
                                driver.execute_script("arguments[0].click();", span)
                                log(f"✓ 已点击: {文本} (精确匹配)")
                                已点击其他方式 = True
                                time.sleep(2)
                                break
                    except:
                        pass
                    
                    if not 已点击其他方式:
                        try:
                            # 方式2: 包含文本的span
                            spans = driver.find_elements(By.XPATH, f"//span[contains(text(), '{文本}')]")
                            for span in spans:
                                if span.is_displayed():
                                    driver.execute_script("arguments[0].click();", span)
                                    log(f"✓ 已点击: {文本} (包含匹配)")
                                    已点击其他方式 = True
                                    time.sleep(2)
                                    break
                        except:
                            pass
                    
                    if not 已点击其他方式:
                        try:
                            # 方式3: 查找role="button"包含该文本的元素
                            buttons = driver.find_elements(By.XPATH, f"//*[@role='button']//span[contains(text(), '{文本}')]")
                            for btn in buttons:
                                if btn.is_displayed():
                                    # 向上找到role="button"的父元素
                                    parent = btn
                                    for _ in range(5):
                                        parent = parent.find_element(By.XPATH, "./..")
                                        if parent.get_attribute("role") == "button":
                                            break
                                    driver.execute_script("arguments[0].click();", parent)
                                    log(f"✓ 已点击: {文本} (按钮匹配)")
                                    已点击其他方式 = True
                                    time.sleep(2)
                                    break
                        except:
                            pass
                    
                    if not 已点击其他方式:
                        try:
                            # 方式4: 查找a标签包含该文本
                            links = driver.find_elements(By.XPATH, f"//a[contains(text(), '{文本}')]")
                            for link in links:
                                if link.is_displayed():
                                    driver.execute_script("arguments[0].click();", link)
                                    log(f"✓ 已点击: {文本} (链接匹配)")
                                    已点击其他方式 = True
                                    time.sleep(2)
                                    break
                        except:
                            pass
                
                if not 已点击其他方式:
                    log("⚠ 未找到'Try another way'按钮")
                
                if 已点击其他方式:
                    # 选择"身份验证应用" / "Authentication app"
                    验证应用文本 = ["身份验证应用", "Authentication app", "authentication app", "Authenticator app"]
                    已选择验证应用 = False
                    
                    for 文本 in 验证应用文本:
                        try:
                            divs = driver.find_elements(By.XPATH, f"//*[contains(text(), '{文本}')]")
                            for div in divs:
                                if div.is_displayed():
                                    # 点击包含该文本的元素或其父元素
                                    driver.execute_script("arguments[0].click();", div)
                                    log(f"已选择: {文本}")
                                    已选择验证应用 = True
                                    time.sleep(2)
                                    break
                            if 已选择验证应用:
                                break
                        except:
                            continue
                    
                    if 已选择验证应用:
                        # 点击"继续" / "Continue" 按钮
                        继续文本 = ["继续", "Continue", "continue"]
                        已点击继续 = False
                        
                        for 文本 in 继续文本:
                            if 已点击继续:
                                break
                            try:
                                # 方式1: 查找 role="button" 包含该文本的元素
                                btns = driver.find_elements(By.XPATH, f"//*[@role='button']//span[contains(text(), '{文本}')]")
                                for btn in btns:
                                    if btn.is_displayed():
                                        # 向上找到 role="button" 的父元素
                                        parent = btn
                                        for _ in range(5):
                                            parent = parent.find_element(By.XPATH, "./..")
                                            if parent.get_attribute("role") == "button":
                                                break
                                        driver.execute_script("arguments[0].click();", parent)
                                        log(f"已点击: {文本}")
                                        已点击继续 = True
                                        break
                            except:
                                pass
                            
                            if not 已点击继续:
                                try:
                                    # 方式2: 直接查找包含文本的 span 并点击
                                    spans = driver.find_elements(By.XPATH, f"//span[contains(text(), '{文本}')]")
                                    for span in spans:
                                        if span.is_displayed():
                                            driver.execute_script("arguments[0].click();", span)
                                            log(f"已点击: {文本}")
                                            已点击继续 = True
                                            break
                                except:
                                    pass
                        
                        if 已点击继续:
                            # 等待页面加载（这一步需要时间）
                            log("等待页面加载...")
                            time.sleep(5)
                            
                            # 等待输入框出现（最多等10秒）
                            for _ in range(10):
                                for 选择器 in 输入框选择器:
                                    try:
                                        inputs = driver.find_elements(By.CSS_SELECTOR, 选择器)
                                        for input_el in inputs:
                                            if input_el.is_displayed():
                                                输入框 = input_el
                                                break
                                        if 输入框:
                                            break
                                    except:
                                        continue
                                if 输入框:
                                    break
                                time.sleep(1)
            
            if not 输入框:
                # 再次检查是否有 reCAPTCHA（可能在尝试切换验证方式后出现）
                try:
                    recaptcha_elements = driver.find_elements(By.CSS_SELECTOR, ".recaptcha-checkbox, #recaptcha-anchor, .g-recaptcha")
                    for el in recaptcha_elements:
                        if el.is_displayed():
                            log("✗ 检测到 reCAPTCHA 图形验证")
                            return "captcha"
                    
                    recaptcha_iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha'], iframe[title*='reCAPTCHA']")
                    for iframe in recaptcha_iframes:
                        if iframe.is_displayed():
                            log("✗ 检测到 reCAPTCHA 图形验证")
                            return "captcha"
                except:
                    pass
                
                log("✗ 找不到验证码输入框")
                continue
            
            # 彻底清除输入框内容
            输入框.click()
            time.sleep(0.2)
            # 全选并删除
            输入框.send_keys(Keys.CONTROL + "a")
            time.sleep(0.1)
            输入框.send_keys(Keys.DELETE)
            time.sleep(0.1)
            输入框.clear()
            time.sleep(0.3)
            
            # 输入新验证码
            for char in 验证码:
                输入框.send_keys(char)
                time.sleep(0.1)
            log("已输入验证码")
            
            time.sleep(1)
            
            # 点击确认按钮（支持中英文）
            已点击 = False
            
            # 方式1: CSS 选择器
            确认按钮选择器 = [
                "button[type='submit']",
                "button[name='submit']",
                "#checkpointSubmitButton",
            ]
            
            for 选择器 in 确认按钮选择器:
                try:
                    btns = driver.find_elements(By.CSS_SELECTOR, 选择器)
                    for btn in btns:
                        if btn.is_displayed():
                            btn.click()
                            log("已点击确认按钮")
                            已点击 = True
                            break
                    if 已点击:
                        break
                except:
                    continue
            
            # 方式2: 查找包含 "Continue" 或 "继续" 文本的按钮
            确认文本列表 = ["Continue", "continue", "继续"]
            
            for 确认文本 in 确认文本列表:
                if 已点击:
                    break
                    
                # 方式2a: 查找 role="button" 包含文本
                try:
                    btns = driver.find_elements(By.XPATH, f"//*[@role='button']//span[contains(text(), '{确认文本}')]")
                    for btn in btns:
                        if btn.is_displayed():
                            # 向上找到 role="button" 的父元素
                            parent = btn
                            for _ in range(5):
                                parent = parent.find_element(By.XPATH, "./..")
                                if parent.get_attribute("role") == "button":
                                    break
                            driver.execute_script("arguments[0].click();", parent)
                            log(f"已点击: {确认文本}")
                            已点击 = True
                            break
                except:
                    pass
                
                # 方式2b: 直接查找包含文本的 span 并点击
                if not 已点击:
                    try:
                        spans = driver.find_elements(By.XPATH, f"//span[contains(text(), '{确认文本}')]")
                        for span in spans:
                            if span.is_displayed():
                                driver.execute_script("arguments[0].click();", span)
                                log(f"已点击: {确认文本}")
                                已点击 = True
                                break
                    except:
                        pass
            
            if not 已点击:
                log("⚠ 未找到确认按钮")
                continue
            
            # 等待页面响应（延长等待时间）
            log("等待页面响应...")
            time.sleep(5)
            
            # 多次检查是否有错误提示（红字）
            有错误 = False
            for _ in range(3):
                try:
                    # 检测中英文错误提示
                    错误提示 = driver.find_elements(By.XPATH, 
                        "//span[contains(text(), 'doesn\\'t match') or contains(text(), 'try again') or contains(text(), '不匹配') or contains(text(), '重试') or contains(text(), 'incorrect') or contains(text(), 'wrong') or contains(text(), '验证码') or contains(text(), '请检查')]")
                    for 提示 in 错误提示:
                        if 提示.is_displayed():
                            提示文本 = 提示.text[:80] if 提示.text else ""
                            # 排除正常的提示文本
                            if "输入" in 提示文本 and "验证码" in 提示文本 and "不匹配" not in 提示文本 and "请检查" not in 提示文本:
                                continue
                            log(f"⚠ 验证码错误: {提示文本}...")
                            有错误 = True
                            break
                except:
                    pass
                
                if 有错误:
                    break
                time.sleep(1)
            
            if 有错误:
                # 验证码错误，继续重试
                continue
            
            # 再等待一下，确保页面完全加载
            time.sleep(3)
            
            # 获取当前 URL
            current_url = driver.current_url
            log(f"当前 URL: {current_url}")
            
            # 检查 URL 是否还在 2FA 页面
            if "two_step_verification" in current_url or "two_factor" in current_url or "two-factor" in current_url:
                log("⚠ 仍在 2FA 验证页面，继续重试...")
                continue
            
            # 检查是否还有 Continue/继续 按钮（说明还在验证页面）
            try:
                continue_btns = driver.find_elements(By.XPATH, "//span[contains(text(), 'Continue') or contains(text(), '继续')]")
                for btn in continue_btns:
                    if btn.is_displayed():
                        log("⚠ 仍有确认按钮，继续重试...")
                        有错误 = True
                        break
            except:
                pass
            
            if 有错误:
                continue
            
            # 检查是否还有验证码输入框
            try:
                输入框列表 = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                for inp in 输入框列表:
                    if inp.is_displayed():
                        # 检查是否是验证码输入框
                        placeholder = inp.get_attribute("placeholder") or ""
                        if "code" in placeholder.lower() or "验证" in placeholder:
                            log("⚠ 仍有验证码输入框，继续重试...")
                            有错误 = True
                            break
            except:
                pass
            
            if 有错误:
                continue
            
            # 使用首页图标检测登录成功
            if _检查登录成功(driver):
                log("✓ 2FA 验证成功")
                return True
            
            # 严格判断：URL 必须是 Facebook 首页或个人页面
            if "facebook.com" in current_url:
                # 排除所有验证/登录相关页面
                if "/checkpoint" in current_url or "/login" in current_url or "two-factor" in current_url:
                    log("⚠ 仍在验证/登录页面，继续重试...")
                    continue
                else:
                    # URL 看起来正常，再次确认
                    log("✓ 2FA 验证成功")
                    return True
            
            # 如果 URL 不是 Facebook，可能出错了
            log("⚠ URL 异常，继续重试...")
            continue
                
        except Exception as e:
            log(f"2FA 尝试失败: {e}")
            continue
    
    log(f"✗ 2FA 验证失败，已尝试 {最大重试次数} 次")
    return False

def 账号密码登录_已打开浏览器(browser_id: str, 账号: 账号数据, log_func=None) -> bool:
    """
    在已打开的浏览器中使用账号密码登录（Cookie 登录失败后调用）
    
    Args:
        browser_id: 浏览器ID
        账号: 账号数据
        log_func: 日志函数
    
    Returns:
        是否成功
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(f"[登录] {msg}")
    
    if not bit_browser:
        return False
    
    if not 账号.有密码():
        log("✗ 没有密码，无法登录")
        return False
    
    log("开始账号密码登录（浏览器已打开）...")
    
    try:
        # 获取已打开浏览器的连接信息
        result = bit_browser.open_browser(browser_id)
        if not result.get("success"):
            log(f"✗ 获取浏览器连接失败: {result}")
            return "browser_failed"
        
        data = result.get("data", {})
        debug_port = data.get("http")
        driver_path = data.get("driver")
        
        # 连接 Selenium
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        options = Options()
        options.add_experimental_option("debuggerAddress", debug_port)
        
        if driver_path:
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=options)
        else:
            driver = webdriver.Chrome(options=options)
        
        # 检查当前页面，如果不在登录页则跳转
        current_url = driver.current_url
        if "/login" not in current_url:
            log("跳转到登录页...")
            driver.get("https://www.facebook.com/login")
            time.sleep(3)
        
        # 输入邮箱
        登录账号 = 账号.邮箱 if 账号.邮箱 else 账号.c_user
        log(f"输入账号: {登录账号}")
        
        try:
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email_input.clear()
            for char in 登录账号:
                email_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
        except Exception as e:
            log(f"✗ 找不到邮箱输入框: {e}")
            return False
        
        time.sleep(random.uniform(0.5, 1.5))
        
        # 输入密码
        log("输入密码...")
        try:
            pass_input = driver.find_element(By.ID, "pass")
            pass_input.clear()
            for char in 账号.密码:
                pass_input.send_keys(char)
                time.sleep(random.uniform(0.03, 0.1))
        except Exception as e:
            log(f"✗ 找不到密码输入框: {e}")
            return False
        
        time.sleep(random.uniform(0.5, 1.0))
        
        # 点击登录按钮
        log("点击登录...")
        try:
            login_btn = driver.find_element(By.NAME, "login")
            login_btn.click()
        except:
            try:
                login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_btn.click()
            except Exception as e:
                log(f"✗ 找不到登录按钮: {e}")
                return False
        
        # 等待页面跳转
        time.sleep(5)
        
        # 检查是否有 reCAPTCHA 图形验证（在 2FA 之前检测）
        if _检测图形验证(driver):
            if 是否手动打码():
                log("检测到图形验证，等待人工处理...")
                if _等待手动打码(driver, log):
                    log("✓ 图形验证已通过，继续登录流程")
                    
                    # 图形验证完成后，检查是否回到了登录页面
                    time.sleep(2)
                    current_url = driver.current_url
                    if "/login" in current_url:
                        log("图形验证后回到登录页面，重新输入账号密码...")
                        # 重新输入账号密码
                        try:
                            登录账号 = 账号.邮箱 if 账号.邮箱 else 账号.c_user
                            
                            # 输入邮箱
                            email_input = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.ID, "email"))
                            )
                            email_input.clear()
                            for char in 登录账号:
                                email_input.send_keys(char)
                                time.sleep(random.uniform(0.05, 0.15))
                            log(f"重新输入账号: {登录账号}")
                            
                            time.sleep(random.uniform(0.5, 1.5))
                            
                            # 输入密码
                            pass_input = driver.find_element(By.ID, "pass")
                            pass_input.clear()
                            for char in 账号.密码:
                                pass_input.send_keys(char)
                                time.sleep(random.uniform(0.03, 0.1))
                            log("重新输入密码...")
                            
                            time.sleep(random.uniform(0.5, 1.0))
                            
                            # 点击登录按钮
                            try:
                                login_btn = driver.find_element(By.NAME, "login")
                                login_btn.click()
                            except:
                                login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                                login_btn.click()
                            log("重新点击登录...")
                            
                            # 等待页面跳转
                            time.sleep(5)
                        except Exception as e:
                            log(f"重新输入账号密码失败: {e}")
                            return False
                else:
                    log("✗ 图形验证超时未完成")
                    return "captcha"
            else:
                log("✗ 检测到图形验证，需要人工处理")
                return "captcha"
        
        # 检查当前页面类型
        current_url = driver.current_url
        page_source = driver.page_source.lower()
        
        # 检查是否需要 2FA
        if "two_step_verification" in current_url or "two-factor" in current_url:
            # 区分是 2FA 验证码页面还是图形验证
            if "/authentication/" in current_url:
                log("⚠ 检测到图形验证页面，需要手动处理")
                return "captcha"
            
            if 账号.二次验证码:
                log("需要 2FA 验证，正在处理...")
                结果 = _处理2FA(driver, 账号.二次验证码, log)
                if 结果 == "blocked":
                    return "blocked"
                if 结果 == "captcha":
                    return "captcha"
                if 结果 == "need_relogin":
                    # 需要重新登录，重新输入账号密码
                    log("需要重新登录，重新输入账号密码...")
                    try:
                        # 确保在登录页面
                        current_url = driver.current_url
                        if "/login" not in current_url:
                            driver.get("https://www.facebook.com/login")
                            time.sleep(3)
                        
                        登录账号 = 账号.邮箱 if 账号.邮箱 else 账号.c_user
                        
                        # 输入邮箱
                        email_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, "email"))
                        )
                        email_input.clear()
                        for char in 登录账号:
                            email_input.send_keys(char)
                            time.sleep(random.uniform(0.05, 0.15))
                        log(f"重新输入账号: {登录账号}")
                        
                        time.sleep(random.uniform(0.5, 1.5))
                        
                        # 输入密码
                        pass_input = driver.find_element(By.ID, "pass")
                        pass_input.clear()
                        for char in 账号.密码:
                            pass_input.send_keys(char)
                            time.sleep(random.uniform(0.03, 0.1))
                        log("重新输入密码...")
                        
                        time.sleep(random.uniform(0.5, 1.0))
                        
                        # 点击登录按钮
                        try:
                            login_btn = driver.find_element(By.NAME, "login")
                            login_btn.click()
                        except:
                            login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                            login_btn.click()
                        log("重新点击登录...")
                        
                        # 等待页面跳转
                        time.sleep(5)
                        
                        # 再次检查是否需要 2FA
                        current_url = driver.current_url
                        if "two-factor" in current_url or "two_step_verification" in current_url:
                            log("重新进入 2FA 验证...")
                            结果 = _处理2FA(driver, 账号.二次验证码, log)
                            if 结果 == "captcha":
                                return "captcha"
                            if 结果 == "blocked":
                                return "blocked"
                            if not 结果:
                                return False
                    except Exception as e:
                        log(f"重新登录失败: {e}")
                        return False
                if not 结果:
                    return False
            else:
                log("⚠ 需要 2FA 但没有密钥，请手动处理")
                return False
        
        # 再次检查登录状态
        time.sleep(3)
        current_url = driver.current_url
        page_title = driver.title
        
        # 检查是否需要人脸验证（封号）
        try:
            from selenium.webdriver.common.by import By
            人脸验证文本 = [
                "通过自拍视频验证", 
                "Verify your identity", 
                "selfie video", 
                "自拍视频",
                "confirm you're human",
                "Confirm you're human",
                "confirm you're human to use your account",
                "Confirm you're human to use your account"
            ]
            for 文本 in 人脸验证文本:
                elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{文本}')]")
                for el in elements:
                    if el.is_displayed():
                        log(f"✗ 检测到封号提示: {文本}")
                        return "blocked"
        except:
            pass
        
        # 检查是否封号（URL 包含 /checkpoint/）
        if "/checkpoint/" in current_url:
            log("✗ 账号已被封禁（checkpoint）")
            return "blocked"
        
        # 检查是否是图形验证
        if "/authentication/" in current_url:
            log("⚠ 检测到图形验证页面，需要手动处理")
            return "captcha"
        
        if "/login" in current_url or "log in" in page_title.lower():
            log("✗ 登录失败")
            return False
        
        # 使用首页图标检测登录成功
        if _检查登录成功(driver):
            log("✓ 账号密码登录成功")
            # 处理浏览器权限弹窗
            _处理浏览器权限弹窗(driver, log)
            # 修改语言为英文
            _修改语言为英文(driver, log)
            return True
        
        if "facebook.com" in current_url:
            log("✓ 账号密码登录成功")
            # 处理浏览器权限弹窗
            _处理浏览器权限弹窗(driver, log)
            # 修改语言为英文
            _修改语言为英文(driver, log)
            return True
        
        log("? 登录状态未知")
        return False
        
    except Exception as e:
        log(f"✗ 登录异常: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==================== 主函数 ====================

def 批量登录(log_func=None, client=None, auth_client=None) -> Dict:
    """
    批量登录账号（线程安全版本，支持 UI 嵌入）
    
    流程：
    1. 逐个获取账号（获取时立即从文件删除，防止重复处理）
    2. 读取 VPN 文件
    3. 为每个账号创建浏览器并登录（VPN 轮询分配，持久化记录）
    4. 登录过程中将浏览器嵌入到 UI（如果提供了 client）
    5. 登录失败/图形验证的账号记录到对应文件并删除浏览器
    
    Args:
        log_func: 日志函数
        client: BrowserClient 实例，用于将浏览器嵌入到 UI
        auth_client: AuthClient 实例（保留参数，向后兼容）
    
    Returns:
        统计结果，包含失败账号列表
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(f"[登录] {msg}")
    
    统计 = {
        "总数": 0,
        "成功": 0,
        "失败": 0,
        "跳过": 0,
        "图形验证": 0,
        "失败账号": []
    }
    
    # 先统计待处理账号数量
    待处理账号列表 = 安全读取账号文件()
    待处理数 = len(待处理账号列表)
    if 待处理数 == 0:
        log("没有找到待登录的账号")
        return 统计
    
    log(f"找到 {待处理数} 个待登录账号")
    
    # 读取 VPN
    vpn列表 = 解析VPN文件()
    log(f"找到 {len(vpn列表)} 个 VPN 配置")
    
    # 显示当前 VPN 索引
    当前vpn索引 = 读取VPN索引()
    if vpn列表:
        log(f"当前 VPN 索引: {当前vpn索引} (端口: {vpn列表[当前vpn索引 % len(vpn列表)].port})")
    
    # 逐个处理（每次获取一个账号，获取时自动从文件删除）
    处理序号 = 0
    while True:
        # 获取下一个账号（线程安全，获取后自动从文件删除）
        账号 = 获取并锁定下一个账号()
        if 账号 is None:
            break
        
        处理序号 += 1
        统计["总数"] += 1
        
        显示名称 = f"登录#{处理序号} {账号.c_user or 账号.邮箱}"
        
        log(f"\n{'='*50}")
        log(f"处理账号 [{处理序号}]: {账号.c_user or 账号.邮箱}")
        log(f"{'='*50}")
        
        # 分配 VPN（轮询，持久化记录）
        vpn, vpn索引 = 获取下一个VPN(vpn列表)
        if vpn:
            log(f"分配 VPN [{vpn索引 + 1}/{len(vpn列表)}]: 端口 {vpn.port}")
        
        # 创建浏览器
        browser_id = 创建浏览器(账号, vpn, log)
        if not browser_id:
            统计["失败"] += 1
            统计["失败账号"].append(账号.原始行)
            _记录登录错误(账号.原始行, "创建浏览器失败")
            continue
        
        # 将浏览器嵌入到 UI（如果提供了 client）
        if client:
            try:
                client.add_browser(browser_id, 显示名称, wait=True)
                client.set_status(browser_id, "登录中...")
                time.sleep(1)
            except Exception as e:
                log(f"⚠ 嵌入浏览器到 UI 失败: {e}")
        
        # 登录（Cookie 失败后尝试账号密码）
        结果 = False
        
        if 账号.有cookie():
            结果 = Cookie登录(browser_id, 账号, log)
            
            # Cookie 登录失败，尝试账号密码登录
            if not 结果 and 账号.有密码():
                log("Cookie 登录失败，尝试账号密码登录...")
                结果 = 账号密码登录_已打开浏览器(browser_id, 账号, log)
        
        elif 账号.有密码():
            结果 = 账号密码登录(browser_id, 账号, log)
        
        else:
            log("✗ 没有 Cookie 也没有密码，跳过")
            统计["跳过"] += 1
            _关闭并移除浏览器(browser_id, client, log)
            _记录登录错误(账号.原始行, "没有Cookie也没有密码")
            continue
        
        # 处理登录结果
        if 结果 == "browser_failed":
            # 浏览器打开失败，账号放回文件，删除浏览器
            log("浏览器打开失败，账号放回文件，删除浏览器...")
            if client:
                client.set_status(browser_id, "⚠ 浏览器失败")
            _关闭并移除浏览器(browser_id, client, log)
            _删除浏览器(browser_id, log)
            _放回账号(账号.原始行)
            统计["总数"] -= 1  # 不计入总数，因为账号放回了
        elif 结果 == "blocked":
            # 封号，删除浏览器，记录错误
            log("账号被封禁，删除浏览器...")
            if client:
                client.set_status(browser_id, "✗ 封号")
            _关闭并移除浏览器(browser_id, client, log)
            _删除浏览器(browser_id, log)
            统计["失败"] += 1
            统计["失败账号"].append(账号.原始行)
            _记录登录错误(账号.原始行, "账号被封禁")
        elif 结果 == "captcha":
            # 图形验证，记录到单独文件，删除浏览器
            log("⚠ 需要图形验证，记录账号并删除浏览器...")
            if client:
                client.set_status(browser_id, "⚠ 图形验证")
            _关闭并移除浏览器(browser_id, client, log)
            _删除浏览器(browser_id, log)
            统计["图形验证"] += 1
            _记录图形验证账号(账号.原始行)
        elif 结果 == True:
            统计["成功"] += 1
            if client:
                client.set_status(browser_id, "✓ 登录成功")
            log("✓ 登录成功，浏览器保留")
            # 登录成功后从 UI 移除（但不关闭浏览器）
            if client:
                try:
                    time.sleep(1)
                    client.remove_browser(browser_id, close=False)
                except:
                    pass
            # 异步关闭浏览器窗口（保留浏览器配置，下次任务执行时再打开）
            if bit_browser:
                import threading
                def close_async():
                    try:
                        bit_browser.close_browser(browser_id)
                    except:
                        pass
                threading.Thread(target=close_async, daemon=True).start()
        else:
            # 登录失败，删除浏览器，记录错误
            log("登录失败，删除浏览器...")
            if client:
                client.set_status(browser_id, "✗ 失败")
            _关闭并移除浏览器(browser_id, client, log)
            _删除浏览器(browser_id, log)
            统计["失败"] += 1
            统计["失败账号"].append(账号.原始行)
            _记录登录错误(账号.原始行, "登录失败")
        
        # 间隔一下
        time.sleep(random.uniform(2, 5))
    
    # 输出统计
    log(f"\n{'='*50}")
    log("登录完成 - 统计")
    log(f"{'='*50}")
    log(f"  总数: {统计['总数']}")
    log(f"  成功: {统计['成功']}")
    log(f"  失败: {统计['失败']}")
    log(f"  图形验证: {统计['图形验证']}")
    log(f"  跳过: {统计['跳过']}")
    
    if 统计["失败账号"]:
        log(f"  失败账号已记录到: 登录错误.txt")
    if 统计["图形验证"] > 0:
        log(f"  图形验证账号已记录到: 图形验证.txt")
    
    if 统计["失败账号"]:
        log(f"  失败账号已记录到: 登录错误.txt")
    
    return 统计

def _关闭并移除浏览器(browser_id: str, client, log_func=None):
    """
    关闭浏览器窗口并从 UI 中移除（异步执行，不阻塞）
    
    Args:
        browser_id: 浏览器 ID
        client: BrowserClient 实例
        log_func: 日志函数
    """
    import threading
    
    def remove_async():
        # 从 UI 中移除
        if client:
            try:
                client.remove_browser(browser_id, close=True)
            except:
                pass
        else:
            # 如果没有 client，直接关闭浏览器
            if bit_browser:
                try:
                    bit_browser.close_browser(browser_id)
                except:
                    pass
    
    # 异步执行，避免阻塞
    threading.Thread(target=remove_async, daemon=True).start()

def _删除浏览器(browser_id: str, log_func=None):
    """删除浏览器（从比特浏览器中彻底删除，异步执行）"""
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(f"[登录] {msg}")
    
    if not bit_browser:
        return
    
    import threading
    
    def delete_async():
        try:
            bit_browser.delete_browser(browser_id)
            log("✓ 浏览器已删除")
        except Exception as e:
            log(f"删除浏览器失败: {e}")
    
    # 异步执行，避免阻塞
    threading.Thread(target=delete_async, daemon=True).start()

def _记录登录错误(账号原始行: str, 错误原因: str = ""):
    """
    记录登录失败的账号到 登录错误.txt
    
    Args:
        账号原始行: 账号的原始文本行
        错误原因: 失败原因
    """
    错误文件 = os.path.join(脚本配置目录, "登录错误.txt")
    
    with 文件锁:
        try:
            with open(错误文件, 'a', encoding='utf-8') as f:
                时间戳 = time.strftime("%Y-%m-%d %H:%M:%S")
                if 错误原因:
                    f.write(f"# {时间戳} - {错误原因}\n")
                f.write(f"{账号原始行}\n")
        except Exception as e:
            print(f"[登录] 记录错误失败: {e}")

def _放回账号(账号原始行: str):
    """
    将账号放回账号文件（用于浏览器打开失败等情况）
    
    Args:
        账号原始行: 账号的原始文本行
    """
    with 文件锁:
        try:
            with open(账号文件路径, 'a', encoding='utf-8') as f:
                f.write(f"{账号原始行}\n")
            print(f"[登录] 账号已放回文件")
        except Exception as e:
            print(f"[登录] 放回账号失败: {e}")

def _记录图形验证账号(账号原始行: str):
    """
    记录需要图形验证的账号到 图形验证.txt
    这些账号需要人工登录处理
    
    Args:
        账号原始行: 账号的原始文本行
    """
    验证文件 = os.path.join(脚本配置目录, "图形验证.txt")
    
    with 文件锁:
        try:
            with open(验证文件, 'a', encoding='utf-8') as f:
                时间戳 = time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"# {时间戳} - 需要图形验证\n")
                f.write(f"{账号原始行}\n")
        except Exception as e:
            print(f"[登录] 记录图形验证账号失败: {e}")

def 检查待登录账号() -> int:
    """
    检查是否有待登录的账号（线程安全）
    
    Returns:
        待登录账号数量
    """
    return len(安全读取账号文件())

# ==================== 调试入口 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("登录功能 - 调试模式")
    print("=" * 60)
    
    # 检查账号
    账号数 = 检查待登录账号()
    print(f"待登录账号: {账号数} 个")
    
    if 账号数 > 0:
        确认 = input("是否开始登录？(y/n): ")
        if 确认.lower() == 'y':
            批量登录()
    else:
        print("没有待登录的账号")
#测试更新