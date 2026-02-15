"""
自动化主控制器 (可热更新)
由 bootstrap.py 加载执行

主要流程：
1. 连接监控服务器
2. 获取所有浏览器
3. 对每个浏览器执行：账号检测 -> 账号预检 -> 打开浏览器 -> 执行任务
4. 多线程并行执行（可配置并发数）

代码结构：
- VPN 数据解析
- 账号数据管理
- 单账号流程函数（账号检测、账号预检、执行任务等）
- AutomationMain 主控制器类
"""

import os
import sys
import json
import time
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from urllib.parse import unquote

# 确保可以导入项目模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 脚本配置目录
脚本配置目录 = os.path.join(current_dir, "脚本配置")

# 导入浏览器监控客户端
try:
    from browser_client import BrowserClient
except ImportError:
    BrowserClient = None
    print("[Main] 警告: 无法导入 browser_client")

# 导入比特浏览器 API
try:
    from bitbrowser_api import bit_browser
except ImportError:
    bit_browser = None
    print("[Main] 警告: 无法导入 bitbrowser_api")

# 导入子任务
from tasks import 到首页, 页面状态, 页面检测结果, 阅读, 阅读配置
from tasks import 设置头像, 检测是否有头像
from tasks import 视频功能, 视频配置
from tasks.登录 import 检查待登录账号, 批量登录
from tasks.通知功能 import 通知功能, 通知功能配置
from tasks.随机点击首页 import 随机点击首页, 随机点击首页配置
from tasks.加好友 import 加好友, 加好友配置
from tasks.加入小组 import 加入小组, 加入小组配置
from tasks.小组转发 import 小组转发, 小组转发配置
from tasks.分享动态 import 分享动态, 分享动态配置


# ==================== 常量配置 ====================

FB_CHECK_API = "https://check.fb.tools/api/check/account"
VERSION = "3.4.0"


# ==================== 运行配置 ====================

def 读取运行配置() -> Dict:
    """
    读取运行配置文件
    
    Returns:
        配置字典，包含线程数等参数
    """
    配置文件 = os.path.join(脚本配置目录, "运行配置.json")
    默认配置 = {
        "线程数": 4
    }
    
    try:
        if os.path.exists(配置文件):
            with open(配置文件, 'r', encoding='utf-8') as f:
                配置 = json.load(f)
                # 合并默认配置
                for key in 默认配置:
                    if key not in 配置:
                        配置[key] = 默认配置[key]
                return 配置
    except Exception as e:
        print(f"[Main] 读取运行配置失败: {e}")
    
    return 默认配置


def 获取线程数() -> int:
    """获取配置的线程数"""
    配置 = 读取运行配置()
    线程数 = 配置.get("线程数", 4)
    # 确保线程数在合理范围内
    return max(1, min(线程数, 20))


# ==================== 轮次控制配置 ====================

def 读取轮次配置() -> Dict:
    """
    读取轮次控制配置
    
    Returns:
        配置字典，包含轮次控制参数
    """
    配置文件 = os.path.join(脚本配置目录, "轮次配置.json")
    默认配置 = {
        "启用轮次控制": True,
        "每日轮次": 3,
        "轮次间隔策略": "平均分配",
        "轮次间隔小时": 8,
        "允许跨天补偿": False,
        "打乱账号顺序": True
    }
    
    try:
        if os.path.exists(配置文件):
            with open(配置文件, 'r', encoding='utf-8') as f:
                配置 = json.load(f)
                # 合并默认配置
                for key in 默认配置:
                    if key not in 配置:
                        配置[key] = 默认配置[key]
                return 配置
    except Exception as e:
        print(f"[Main] 读取轮次配置失败: {e}")
    
    return 默认配置


# ==================== 数据类 ====================

@dataclass
class 账号信息:
    """浏览器账号信息"""
    browser_id: str          # 浏览器ID
    显示名称: str = ""       # 显示名称（带序号）
    原名称: str = ""         # 原始名称
    c_user: str = ""         # Facebook c_user
    状态: str = ""           # Active / Blocked / NoLogin / Unknown
    状态消息: str = ""       # 状态详细信息
    运行天数: int = 0        # 在本项目运行的天数
    运行次数: int = 0        # 运行次数


@dataclass
class 任务统计:
    """任务统计（线程安全）"""
    total: int = 0
    active: int = 0
    blocked: int = 0
    no_login: int = 0
    success: int = 0
    failed: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def increment(self, field_name: str):
        with self._lock:
            setattr(self, field_name, getattr(self, field_name) + 1)


# ==================== VPN 数据解析 ====================

# 脚本配置目录
脚本配置目录 = os.path.join(current_dir, "脚本配置")

def 解析VPN数据(vpn_file: str = None) -> List[Dict]:
    """解析 VPN 数据文件"""
    if vpn_file is None:
        vpn_file = os.path.join(脚本配置目录, "vpn.txt")
    
    if not os.path.exists(vpn_file):
        return []
    
    result = []
    with open(vpn_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        if not line or not line.startswith('vless://'):
            continue
        try:
            url_part = line[8:]
            name = ""
            if '#' in url_part:
                url_part, fragment = url_part.rsplit('#', 1)
                name = unquote(fragment)
            
            params = {}
            if '?' in url_part:
                url_part, query_str = url_part.split('?', 1)
                for param in query_str.split('&'):
                    if '=' in param:
                        k, v = param.split('=', 1)
                        params[k] = unquote(v)
            
            if '@' not in url_part:
                continue
            uuid, host_port = url_part.split('@', 1)
            
            if ':' in host_port:
                host, port_str = host_port.rsplit(':', 1)
                port = int(port_str)
            else:
                host = host_port
                port = 443
            
            result.append({
                'name': name, 'uuid': uuid, 'host': host,
                'port': port, 'protocol': 'vless',
                'params': params, 'raw_url': line
            })
        except:
            continue
    
    return result


# ==================== 账号数据管理 ====================

_账号文件 = os.path.join(current_dir, "账号.json")
_账号缓存: Dict = None
_账号锁 = threading.Lock()


def _加载账号数据() -> Dict:
    global _账号缓存
    if _账号缓存 is not None:
        return _账号缓存
    if os.path.exists(_账号文件):
        try:
            with open(_账号文件, 'r', encoding='utf-8') as f:
                _账号缓存 = json.load(f)
        except:
            _账号缓存 = {}
    else:
        _账号缓存 = {}
    return _账号缓存


def _保存账号数据(data: Dict):
    global _账号缓存
    _账号缓存 = data
    try:
        with open(_账号文件, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass


def 取账号信息(browser_id: str) -> Optional[Dict]:
    """获取账号完整信息"""
    with _账号锁:
        return _加载账号数据().get(browser_id)


def 更新账号信息(browser_id: str, **kwargs) -> bool:
    """更新账号信息"""
    with _账号锁:
        accounts = _加载账号数据()
        if browser_id not in accounts:
            return False
        for key, value in kwargs.items():
            accounts[browser_id][key] = value
        _保存账号数据(accounts)
        return True


def 获取所有账号() -> Dict:
    """获取所有账号数据"""
    with _账号锁:
        return _加载账号数据().copy()


# ==================== 轮次管理函数 ====================

def 检查账号轮次(browser_id: str, 当前轮数: int) -> tuple:
    """
    检查账号今日轮次，决定是否可以执行
    
    Args:
        browser_id: 浏览器ID
        当前轮数: 当前是第几轮 (1-3)
    
    Returns:
        (是否可执行: bool, 已完成轮次: int)
    """
    with _账号锁:
        accounts = _加载账号数据()
        今天 = time.strftime("%Y-%m-%d")
        
        if browser_id not in accounts:
            # 新账号，可以执行
            return (True, 0)
        
        账号 = accounts[browser_id]
        最后日期 = 账号.get("最后执行日期", "")
        
        # 如果是新的一天，重置轮次
        if 最后日期 != 今天:
            return (True, 0)
        
        # 检查今日已执行轮次
        已执行轮次 = 账号.get("今日执行轮次", 0)
        
        # 如果已完成3轮，不能再执行
        轮次配置 = 读取轮次配置()
        每日轮次 = 轮次配置.get("每日轮次", 3)
        
        if 已执行轮次 >= 每日轮次:
            return (False, 已执行轮次)
        
        # 如果当前轮数 <= 已执行轮次，说明这一轮已经执行过了
        if 当前轮数 <= 已执行轮次:
            return (False, 已执行轮次)
        
        return (True, 已执行轮次)


def 更新账号执行状态(browser_id: str, 轮数: int, 状态: str = "completed"):
    """
    更新账号的执行状态
    
    Args:
        browser_id: 浏览器ID
        轮数: 第几轮
        状态: completed/failed/running
    """
    with _账号锁:
        accounts = _加载账号数据()
        今天 = time.strftime("%Y-%m-%d")
        现在 = int(time.time())
        
        if browser_id not in accounts:
            accounts[browser_id] = {
                "名称": "", "c_user": "",
                "首次运行": 现在, "密码": "", "2fa码": "",
                "已上传头像": False, "已设置资料": False,
                "上次运行": 现在, "运行次数": 0, "备注": ""
            }
        
        账号 = accounts[browser_id]
        最后日期 = 账号.get("最后执行日期", "")
        
        # 如果是新的一天，重置轮次
        if 最后日期 != 今天:
            账号["今日执行轮次"] = 0
            账号["最后执行日期"] = 今天
        
        # 更新状态
        if 状态 == "completed":
            # 只有成功完成才增加轮次
            账号["今日执行轮次"] = 轮数
            账号["最后执行时间"] = 现在
            账号["最后执行轮数"] = 轮数
            账号["最后执行状态"] = "completed"
        elif 状态 == "running":
            账号["最后执行时间"] = 现在
            账号["最后执行轮数"] = 轮数
            账号["最后执行状态"] = "running"
        elif 状态 == "failed":
            账号["最后执行时间"] = 现在
            账号["最后执行轮数"] = 轮数
            账号["最后执行状态"] = "failed"
        
        _保存账号数据(accounts)


def 启动时分析执行状态(browsers: List[Dict]) -> Dict:
    """
    软件启动时，分析所有账号的执行状态
    
    Args:
        browsers: 浏览器列表
    
    Returns:
        执行状态分析结果
    """
    今天 = time.strftime("%Y-%m-%d")
    轮次配置 = 读取轮次配置()
    每日轮次 = 轮次配置.get("每日轮次", 3)
    
    轮次统计 = {}
    for i in range(每日轮次 + 1):
        轮次统计[i] = 0
    
    for browser in browsers:
        bid = browser.get("id", "")
        账号信息 = 取账号信息(bid)
        
        if not 账号信息:
            轮次统计[0] += 1
            continue
        
        最后日期 = 账号信息.get("最后执行日期", "")
        
        # 如果是新的一天，重置为0轮
        if 最后日期 != 今天:
            轮次统计[0] += 1
        else:
            已执行轮次 = 账号信息.get("今日执行轮次", 0)
            if 已执行轮次 in 轮次统计:
                轮次统计[已执行轮次] += 1
            else:
                轮次统计[0] += 1
    
    # 分析应该执行哪一轮
    总账号数 = len(browsers)
    
    # 策略：找出大多数账号所处的轮次
    最多账号的轮次 = max(轮次统计, key=轮次统计.get)
    
    # 如果大部分账号都完成了所有轮次
    if 轮次统计.get(每日轮次, 0) > 总账号数 * 0.7:
        return {
            "应执行轮数": None,
            "今日已完成账号": 轮次统计.get(每日轮次, 0),
            "今日未完成账号": 总账号数 - 轮次统计.get(每日轮次, 0),
            "需要继续执行": False,
            "建议": f"今日任务已基本完成（{轮次统计.get(每日轮次, 0)}/{总账号数}），建议等待明天",
            "轮次分布": 轮次统计
        }
    
    # 否则，执行下一轮
    应执行轮数 = 最多账号的轮次 + 1
    
    return {
        "应执行轮数": 应执行轮数,
        "今日已完成账号": 轮次统计.get(每日轮次, 0),
        "今日未完成账号": 总账号数 - 轮次统计.get(每日轮次, 0),
        "需要继续执行": True,
        "建议": f"继续执行第 {应执行轮数} 轮",
        "轮次分布": 轮次统计
    }


def 启动时分析执行状态(browsers: List[Dict]) -> Dict:
    """
    软件启动时，分析所有账号的执行状态
    
    Args:
        browsers: 浏览器列表
    
    Returns:
        执行状态分析结果
    """
    今天 = time.strftime("%Y-%m-%d")
    轮次配置 = 读取轮次配置()
    每日轮次 = 轮次配置.get("每日轮次", 3)
    
    轮次统计 = {}
    for i in range(每日轮次 + 1):
        轮次统计[i] = 0
    
    for browser in browsers:
        bid = browser.get("id", "")
        账号信息 = 取账号信息(bid)
        
        if not 账号信息:
            轮次统计[0] += 1
            continue
        
        最后日期 = 账号信息.get("最后执行日期", "")
        
        # 如果是新的一天，重置为0轮
        if 最后日期 != 今天:
            轮次统计[0] += 1
        else:
            已执行轮次 = 账号信息.get("今日执行轮次", 0)
            if 已执行轮次 in 轮次统计:
                轮次统计[已执行轮次] += 1
            else:
                轮次统计[0] += 1
    
    # 分析应该执行哪一轮
    总账号数 = len(browsers)
    
    # 策略：找出大多数账号所处的轮次
    最多账号的轮次 = max(轮次统计, key=轮次统计.get)
    
    # 如果大部分账号都完成了所有轮次
    if 轮次统计.get(每日轮次, 0) > 总账号数 * 0.7:
        return {
            "应执行轮数": None,
            "今日已完成账号": 轮次统计.get(每日轮次, 0),
            "今日未完成账号": 总账号数 - 轮次统计.get(每日轮次, 0),
            "需要继续执行": False,
            "建议": f"今日任务已基本完成（{轮次统计.get(每日轮次, 0)}/{总账号数}），等待明天",
            "轮次分布": 轮次统计
        }
    
    # 否则，执行下一轮
    应执行轮数 = 最多账号的轮次 + 1
    
    return {
        "应执行轮数": 应执行轮数,
        "今日已完成账号": 轮次统计.get(每日轮次, 0),
        "今日未完成账号": 总账号数 - 轮次统计.get(每日轮次, 0),
        "需要继续执行": True,
        "建议": f"继续执行第 {应执行轮数} 轮",
        "轮次分布": 轮次统计
    }


def 计算轮次等待时间(当前轮数: int, 每日轮次: int) -> int:
    """
    计算当前轮次结束后需要等待的时间（秒）
    
    Args:
        当前轮数: 当前是第几轮
        每日轮次: 每天总轮次数
    
    Returns:
        等待秒数
    """
    轮次配置 = 读取轮次配置()
    策略 = 轮次配置.get("轮次间隔策略", "平均分配")
    
    if 策略 == "平均分配":
        # 24小时平均分配
        间隔小时 = 24 / 每日轮次
        return int(间隔小时 * 3600)
    
    elif 策略 == "固定间隔":
        # 使用配置的固定间隔
        间隔小时 = 轮次配置.get("轮次间隔小时", 8)
        return int(间隔小时 * 3600)
    
    elif 策略 == "随机间隔":
        # 随机6-10小时
        间隔小时 = random.randint(6, 10)
        return int(间隔小时 * 3600)
    
    else:
        # 默认8小时
        return 8 * 3600


def 计算到明天的秒数() -> int:
    """
    计算到明天0点的秒数
    
    Returns:
        到明天0点的秒数
    """
    现在 = time.time()
    今天结束 = time.mktime(time.strptime(time.strftime("%Y-%m-%d 23:59:59"), "%Y-%m-%d %H:%M:%S"))
    到明天秒数 = int(今天结束 - 现在) + 1
    return max(到明天秒数, 0)


# ==================== 阶段任务配置 ====================

import random

@dataclass
class 任务配置:
    """单个账号的任务配置"""
    阶段: int = 1                    # 当前阶段 1-6
    阶段名称: str = ""               # 阶段名称
    
    # 抽取的任务列表
    任务列表: List[str] = field(default_factory=list)
    
    # 各项参数
    阅读时长: int = 60               # 阅读时长（秒）
    点赞数量: int = 0                # 点赞数量
    评论数量: int = 0                # 评论数量
    加小组数量: int = 0              # 加小组数量
    加好友数量: int = 0              # 加好友数量
    通过好友数量: int = 0            # 通过好友请求数量
    转发小组数量: int = 0            # 转发到小组数量
    转发动态数量: int = 0            # 转发到动态数量
    邀请好友数量: int = 0            # 邀请好友数量
    视频观看时长: int = 0            # 视频观看时长（秒）
    删除好友数量: int = 0            # 删除好友数量


def 计算阶段(运行天数: int) -> int:
    """
    根据运行天数计算当前阶段
    
    阶段划分：
    - 阶段1: 0-3天   (注册期)
    - 阶段2: 4-7天   (轻浏览期)
    - 阶段3: 8-15天  (轻互动期)
    - 阶段4: 16-25天 (小组融入期)
    - 阶段5: 26-45天 (初步引流期)
    - 阶段6: 45天+   (成熟期)
    """
    if 运行天数 <= 3:
        return 1
    elif 运行天数 <= 7:
        return 2
    elif 运行天数 <= 15:
        return 3
    elif 运行天数 <= 25:
        return 4
    elif 运行天数 <= 45:
        return 5
    else:
        return 6


def 生成任务配置(运行天数: int) -> 任务配置:
    """
    根据运行天数生成任务配置
    
    功能：
    1. 计算当前阶段
    2. 根据阶段配置任务池和权重
    3. 按权重随机抽取任务
    4. 设置各项参数
    
    Args:
        运行天数: 账号在本项目运行的天数
    
    Returns:
        任务配置对象
    """
    阶段 = 计算阶段(运行天数)
    配置 = 任务配置(阶段=阶段)
    
    # ==================== 阶段1: 注册期 (0-3天) - 纯养号 ====================
    if 阶段 == 1:
        配置.阶段名称 = "注册期"
        任务池 = ["阅读", "设置头像", "通知功能"]
        权重池 = [100, 50, 50]
        抽取数量 = random.randint(2, 3)
        
        配置.阅读时长 = random.randint(300, 600)   # 5-10分钟
        配置.点赞数量 = random.randint(0, 1)       # 偶尔点一下
        配置.评论数量 = 0                          # 禁止评论
        配置.加好友数量 = 0                        # 禁止加好友
        配置.加小组数量 = 0                        # 禁止加小组
        配置.转发小组数量 = 0                      # 禁止转发
    
    # ==================== 阶段2: 轻浏览期 (4-7天) - 继续养号 ====================
    elif 阶段 == 2:
        配置.阶段名称 = "轻浏览期"
        任务池 = ["阅读", "随机点击首页", "通知功能", "视频功能"]
        权重池 = [100, 90, 80, 70]
        抽取数量 = random.randint(2, 4)
        
        配置.阅读时长 = random.randint(480, 900)   # 8-15分钟
        配置.点赞数量 = random.randint(2, 4)
        配置.视频观看时长 = random.randint(120, 300)  # 2-5分钟
        配置.评论数量 = 0                          # 仍禁止评论
        配置.加好友数量 = 0                        # 仍禁止加好友
        配置.加小组数量 = 0                        # 仍禁止加小组
        配置.转发小组数量 = 0                      # 仍禁止转发
    
    # ==================== 阶段3: 轻互动期 (8-15天) - 开始互动 ====================
    elif 阶段 == 3:
        配置.阶段名称 = "轻互动期"
        任务池 = ["阅读", "随机点击首页", "通知功能", "视频功能",
                 "个人主页评论帖子", "加好友", "加入小组"]
        权重池 = [100, 85, 75, 80, 50, 40, 30]
        抽取数量 = random.randint(3, 5)
        
        配置.阅读时长 = random.randint(600, 1200)  # 10-20分钟
        配置.点赞数量 = random.randint(3, 6)
        配置.评论数量 = random.randint(0, 2)       # 开始少量评论
        配置.加好友数量 = random.randint(1, 2)     # 开始少量加好友
        配置.加小组数量 = random.randint(0, 1)     # 开始少量加小组
        配置.视频观看时长 = random.randint(180, 480)  # 3-8分钟
        配置.转发小组数量 = 0                      # 仍禁止转发
    
    # ==================== 阶段4: 小组融入期 (16-25天) - 融入社区 ====================
    elif 阶段 == 4:
        配置.阶段名称 = "小组融入期"
        任务池 = ["阅读", "随机点击首页", "通知功能", "视频功能",
                 "个人主页评论帖子", "加好友", "加入小组",
                 "通过好友请求", "小组转发", "通过链接加好友"]
        权重池 = [100, 70, 80, 75, 85, 60, 80, 70, 60, 50]
        抽取数量 = random.randint(4, 6)
        
        配置.阅读时长 = random.randint(720, 1500)  # 12-25分钟
        配置.点赞数量 = random.randint(4, 8)
        配置.评论数量 = random.randint(2, 5)
        配置.加好友数量 = random.randint(2, 5)
        配置.加小组数量 = random.randint(1, 3)
        配置.通过好友数量 = random.randint(3, 8)
        配置.转发小组数量 = random.randint(1, 2)   # 开始少量转发
        配置.视频观看时长 = random.randint(240, 600)  # 4-10分钟
    
    # ==================== 阶段5: 初步引流期 (26-45天) - 开始引流 ====================
    elif 阶段 == 5:
        配置.阶段名称 = "初步引流期"
        任务池 = ["阅读", "随机点击首页", "通知功能", "视频功能",
                 "个人主页评论帖子", "加好友", "加入小组",
                 "通过好友请求", "小组转发", "通过链接加好友",
                 "小组邀请好友", "分享动态"]
        权重池 = [100, 60, 70, 70, 90, 70, 60, 75, 95, 65, 70, 60]
        抽取数量 = random.randint(5, 7)
        
        配置.阅读时长 = random.randint(900, 1800)  # 15-30分钟
        配置.点赞数量 = random.randint(5, 10)
        配置.评论数量 = random.randint(3, 6)       # 可以带软广
        配置.加好友数量 = random.randint(3, 8)
        配置.加小组数量 = random.randint(1, 2)
        配置.通过好友数量 = random.randint(5, 12)
        配置.转发小组数量 = random.randint(3, 5)   # 增加转发
        配置.转发动态数量 = random.randint(1, 2)   # 开始转发动态
        配置.邀请好友数量 = random.randint(2, 5)
        配置.视频观看时长 = random.randint(300, 720)  # 5-12分钟
    
    # ==================== 阶段6: 成熟期 (45天+) - 正式引流/发广告 ====================
    else:
        配置.阶段名称 = "成熟期"
        任务池 = ["阅读", "随机点击首页", "通知功能", "视频功能",
                 "个人主页评论帖子", "加好友", "加入小组",
                 "通过好友请求", "小组转发", "通过链接加好友",
                 "小组邀请好友", "分享动态", "发布广告"]
        权重池 = [100, 50, 60, 65, 95, 80, 70, 80, 100, 70, 75, 70, 90]
        抽取数量 = random.randint(5, 8)
        
        配置.阅读时长 = random.randint(900, 2100)  # 15-35分钟
        配置.点赞数量 = random.randint(5, 12)
        配置.评论数量 = random.randint(4, 8)       # 可以带广告
        配置.加好友数量 = random.randint(5, 15)
        配置.加小组数量 = random.randint(2, 3)
        配置.通过好友数量 = random.randint(8, 20)
        配置.转发小组数量 = random.randint(4, 8)   # 主要引流手段
        配置.转发动态数量 = random.randint(2, 4)   # 增加转发动态
        配置.邀请好友数量 = random.randint(3, 8)
        配置.删除好友数量 = random.randint(1, 3)
        配置.视频观看时长 = random.randint(360, 900)  # 6-15分钟
    
    # 按权重抽取任务
    配置.任务列表 = _按权重抽取任务(任务池, 权重池, 抽取数量)
    
    return 配置


def _按权重抽取任务(任务池: List[str], 权重池: List[int], 抽取数量: int) -> List[str]:
    """
    按权重随机抽取任务（不重复）
    
    算法：
    1. 根据权重展开任务池（权重100的任务出现100次）
    2. 打乱顺序
    3. 依次抽取不重复的任务
    """
    # 展开任务池
    展开池 = []
    for i, 任务 in enumerate(任务池):
        权重 = 权重池[i] if i < len(权重池) else 50
        展开池.extend([任务] * 权重)
    
    # 打乱
    random.shuffle(展开池)
    
    # 抽取不重复的任务
    已抽取 = []
    for 任务 in 展开池:
        if 任务 not in 已抽取:
            已抽取.append(任务)
            if len(已抽取) >= 抽取数量:
                break
    
    return 已抽取


def 打印任务配置(配置: 任务配置, log_func=None):
    """打印任务配置信息"""
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    log(f"【阶段{配置.阶段}-{配置.阶段名称}】任务: {', '.join(配置.任务列表)}")
    
    # 构建参数列表
    参数列表 = []
    参数列表.append(f"阅读{配置.阅读时长}秒")
    
    if 配置.视频观看时长 > 0:
        参数列表.append(f"视频{配置.视频观看时长}秒")
    if 配置.点赞数量 > 0:
        参数列表.append(f"点赞{配置.点赞数量}")
    if 配置.评论数量 > 0:
        参数列表.append(f"评论{配置.评论数量}")
    if 配置.加小组数量 > 0:
        参数列表.append(f"加组{配置.加小组数量}")
    if 配置.加好友数量 > 0:
        参数列表.append(f"加友{配置.加好友数量}")
    if 配置.通过好友数量 > 0:
        参数列表.append(f"通过{配置.通过好友数量}")
    if 配置.转发小组数量 > 0:
        参数列表.append(f"转发小组{配置.转发小组数量}")
    if 配置.转发动态数量 > 0:
        参数列表.append(f"转发动态{配置.转发动态数量}")
    if 配置.邀请好友数量 > 0:
        参数列表.append(f"邀请{配置.邀请好友数量}")
    if 配置.删除好友数量 > 0:
        参数列表.append(f"删友{配置.删除好友数量}")
    
    log(f"  参数: {', '.join(参数列表)}")



# ==================== 单账号流程函数 ====================

def 账号检测(browser_id: str, browser_name: str = "") -> 账号信息:
    """
    检测账号状态
    
    流程：
    1. 获取浏览器详情（Cookie）
    2. 提取 c_user
    3. 调用 API 检测账号状态
    
    Returns:
        账号信息对象
    """
    账号 = 账号信息(browser_id=browser_id, 原名称=browser_name)
    
    if not bit_browser:
        账号.状态 = "Unknown"
        账号.状态消息 = "API不可用"
        return 账号
    
    # 获取浏览器详情
    detail = bit_browser.get_browser_detail(browser_id)
    if not detail or not detail.get("success"):
        账号.状态 = "Unknown"
        账号.状态消息 = "获取详情失败"
        return 账号
    
    # 提取 c_user
    data = detail.get("data", {})
    cookies = data.get("cookie", "") or data.get("cookies", "")
    c_user = _提取c_user(cookies)
    账号.c_user = c_user or ""
    
    if not c_user:
        账号.状态 = "NoLogin"
        账号.状态消息 = "未登录Facebook"
        return 账号
    
    # 调用 API 检测
    try:
        response = requests.post(
            FB_CHECK_API,
            json={"inputData": [c_user], "checkFriends": False, "userLang": "zh"},
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            data_list = result.get("data", [])
            if data_list:
                status_msg = data_list[0].get("status", {}).get("message", "")
                if status_msg == "Active":
                    账号.状态 = "Active"
                    账号.状态消息 = "正常"
                elif status_msg == "Blocked":
                    账号.状态 = "Blocked"
                    账号.状态消息 = "已封号"
                else:
                    账号.状态 = "Unknown"
                    账号.状态消息 = status_msg
                return 账号
    except:
        pass
    
    账号.状态 = "Unknown"
    账号.状态消息 = "检测失败"
    return 账号


def _提取c_user(cookies: str) -> Optional[str]:
    """从 Cookie 中提取 c_user"""
    if not cookies:
        return None
    try:
        if cookies.strip().startswith('['):
            cookie_list = json.loads(cookies)
            for cookie in cookie_list:
                if cookie.get("name") == "c_user":
                    return cookie.get("value")
        else:
            for part in cookies.split(';'):
                part = part.strip()
                if part.startswith('c_user='):
                    return part.split('=', 1)[1]
    except:
        pass
    return None


def 账号预检(browser_id: str) -> bool:
    """
    账号预检 - 在打开浏览器之前进行配置
    
    功能：
    1. 禁止通知弹窗
    2. 关闭比特浏览器导航页（避免多标签问题）
    
    后续可扩展：
    - 检查/设置代理
    - 设置启动参数
    - 预加载 Cookie
    """
    if not bit_browser:
        return False
    
    try:
        # 修改浏览器设置：禁止通知弹窗
        update_params = {
            "ids": [browser_id],
            "disableNotifications": True,
            "disableTranslatePopup": True,
            "openguide": False  # 关闭导航页
        }
        result = bit_browser._request("/browser/update/partial", update_params)
        return result.get("success", False)
    except:
        return False


def 记录运行信息(browser_id: str, 显示名称: str = "", c_user: str = "") -> Dict:
    """
    记录账号运行信息
    
    Returns:
        Dict: 首次运行时间戳, 运行天数, 是否新增, 运行次数
    """
    with _账号锁:
        accounts = _加载账号数据()
        now = time.time()
        is_new = False
        
        if browser_id not in accounts:
            accounts[browser_id] = {
                "名称": 显示名称, "c_user": c_user,
                "首次运行": int(now), "密码": "", "2fa码": "",
                "已上传头像": False, "已设置资料": False,
                "上次运行": int(now), "运行次数": 1, "备注": ""
            }
            is_new = True
        else:
            accounts[browser_id]["上次运行"] = int(now)
            accounts[browser_id]["运行次数"] = accounts[browser_id].get("运行次数", 0) + 1
            if 显示名称:
                accounts[browser_id]["名称"] = 显示名称
            if c_user:
                accounts[browser_id]["c_user"] = c_user
        
        _保存账号数据(accounts)
        
        record = accounts[browser_id]
        首次运行 = record.get("首次运行", int(now))
        运行天数 = int((now - 首次运行) / 86400)
        
        return {
            "首次运行": 首次运行,
            "运行天数": 运行天数,
            "是否新增": is_new,
            "运行次数": record.get("运行次数", 1)
        }


def 执行任务(账号: 账号信息, driver, log_func=None, 互动协调器=None) -> bool:
    """
    执行主任务（单个账号）
    
    流程：
    1. 生成任务配置（根据运行天数）
    2. 进入首页
    3. 按任务列表执行各项任务
    4. 在任务执行过程中检查暂停标志（用于互动协调）
    
    Args:
        账号: 账号信息对象
        driver: Selenium WebDriver
        log_func: 日志函数
        互动协调器: 互动协调器实例（用于检查暂停标志）
    
    Returns:
        是否成功
    """
    def log(msg):
        if log_func:
            log_func(f"[{账号.显示名称}] {msg}")
    
    log("执行主任务...")
    
    # 第一步：生成任务配置
    配置 = 生成任务配置(账号.运行天数)
    
    # 打印完整配置（方便调试）
    打印任务配置(配置, log_func=lambda msg: log(msg))
    
    # 第二步：进入首页
    首页结果 = 到首页(driver, log_func=lambda msg: log(msg))
    
    if not 首页结果.可继续:
        _处理异常状态(账号, 首页结果, log_func)
        return False
    
    log("✓ 已进入首页，开始执行任务...")
    
    # 第三步：按任务列表执行
    for 任务名 in 配置.任务列表:
        # ========== 检查暂停标志（用于互动协调）==========
        if 互动协调器 and 账号.browser_id in 互动协调器.暂停标志:
            暂停事件 = 互动协调器.暂停标志[账号.browser_id]
            if not 暂停事件.is_set():
                log("⏸️ 收到暂停信号，等待恢复...")
                暂停事件.wait()  # 阻塞等待恢复信号
                log("▶️ 收到恢复信号，继续执行任务")
        
        try:
            _执行单个任务(任务名, 配置, driver, 账号.browser_id, log)
        except Exception as e:
            log(f"✗ 任务[{任务名}]异常: {e}")
    
    return True


def _执行单个任务(任务名: str, 配置: 任务配置, driver, 浏览器ID: str, log_func):
    """
    执行单个任务
    
    根据任务名称调用对应的任务函数
    每个任务执行前都会先确保回到首页
    
    Args:
        任务名: 任务名称
        配置: 任务配置对象
        driver: Selenium WebDriver
        浏览器ID: 浏览器ID（用于某些需要读取配置的任务）
        log_func: 日志函数
    """
    def log(msg):
        if log_func:
            log_func(msg)
    
    # ========== 每个任务执行前都先回到首页 ==========
    log(f"[{任务名}] 确保在首页...")
    首页结果 = 到首页(driver, log_func=log)
    
    if not 首页结果.可继续:
        log(f"[{任务名}] ✗ 无法到达首页，跳过任务: {首页结果.详细信息}")
        return
    
    # ========== 执行具体任务 ==========
    if 任务名 == "阅读":
        log(f"开始阅读（{配置.阅读时长}秒，点赞{配置.点赞数量}个，评论{配置.评论数量}个）...")
        自定义配置 = 阅读配置(
            总时长限制秒=配置.阅读时长,
            点赞数量=配置.点赞数量,
            评论数量=配置.评论数量
        )
        阅读(driver, log_func=log, 配置=自定义配置)
    
    elif 任务名 == "设置头像":
        log("检查头像...")
        if not 检测是否有头像(driver, log):
            设置头像(driver, log_func=log)
        else:
            log("已有头像，跳过")
    
    elif 任务名 == "通知功能":
        log("执行: 通知功能")
        通知任务配置 = 通知功能配置()
        通知功能(driver, log_func=log, 配置=通知任务配置)
    
    elif 任务名 == "随机点击首页":
        log("执行: 随机点击首页")
        随机点击配置 = 随机点击首页配置(
            探索板块数量=4,
            查看自己首页=True
        )
        随机点击首页(driver, log_func=log, 配置=随机点击配置)
    
    elif 任务名 == "视频功能":
        log(f"执行: 视频功能（{配置.视频观看时长}秒）")
        视频任务配置 = 视频配置(观看时长秒=配置.视频观看时长)
        视频功能(driver, log_func=log, 配置=视频任务配置)
    
    elif 任务名 == "加入小组":
        log(f"执行: 加入小组（{配置.加小组数量}个）")
        加小组配置 = 加入小组配置(
            每个关键词加入数量=max(1, 配置.加小组数量 // 2),  # 每个关键词加入数量减半
            总加入数量限制=配置.加小组数量
        )
        加入小组(driver, log_func=log, 配置=加小组配置)
    
    elif 任务名 == "个人主页评论帖子":
        log(f"执行: 评论帖子（{配置.评论数量}个）（TODO）")
        # TODO: 需要实现个人主页评论功能
    
    elif 任务名 == "加好友":
        log(f"执行: 加好友（{配置.加好友数量}个）")
        加好友任务配置 = 加好友配置(
            每个关键词添加数量=max(1, 配置.加好友数量 // 2),  # 每个关键词添加数量减半
            总添加数量限制=配置.加好友数量
        )
        加好友(driver, log_func=log, 配置=加好友任务配置)
    
    elif 任务名 == "通过好友请求":
        log(f"执行: 通过好友请求（{配置.通过好友数量}个）（TODO）")
        # TODO: 需要实现通过好友请求功能
    
    elif 任务名 == "小组转发":
        log(f"执行: 小组转发（{配置.转发小组数量}个）")
        小组转发任务配置 = 小组转发配置(转发数量=配置.转发小组数量)
        小组转发(driver, 浏览器ID=浏览器ID, log_func=log, 配置=小组转发任务配置)
    
    elif 任务名 == "通过链接加好友":
        log(f"执行: 通过链接加好友（TODO）")
        # TODO: 需要实现通过链接加好友功能
    
    elif 任务名 == "小组邀请好友":
        log(f"执行: 小组邀请好友（{配置.邀请好友数量}个）（TODO）")
        # TODO: 需要实现小组邀请好友功能
    
    elif 任务名 == "分享动态":
        log(f"执行: 分享动态（{配置.转发动态数量}个）")
        分享任务配置 = 分享动态配置(分享数量=配置.转发动态数量 if 配置.转发动态数量 > 0 else 1)
        分享动态(driver, log_func=log, 配置=分享任务配置)
    
    elif 任务名 == "发布广告":
        log("执行: 发布广告（TODO）")
        # TODO: 需要实现发布广告功能
    
    else:
        log(f"未知任务: {任务名}")


def _处理异常状态(账号: 账号信息, 结果: 页面检测结果, log_func=None):
    """处理各种异常状态"""
    def log(msg):
        if log_func:
            log_func(f"[{账号.显示名称}] {msg}")
    
    状态 = 结果.状态
    
    if 状态 == 页面状态.需要登录:
        log("处理: 账号需要重新登录")
    elif 状态 == 页面状态.需要验证码:
        log("处理: 需要验证码，等待人工处理")
    elif 状态 == 页面状态.账号被封:
        log("处理: 账号已被封禁")
    elif 状态 == 页面状态.账号受限:
        log("处理: 账号功能受限")
    elif 状态 == 页面状态.需要确认身份:
        log("处理: 需要身份验证")
    elif 状态 == 页面状态.网络错误:
        log("处理: 网络错误，稍后重试")
    else:
        log(f"处理: 未知状态 - {结果.详细信息}")



# ==================== 主控制器类 ====================

class AutomationMain:
    """
    自动化主控制器
    
    职责：
    - 连接监控服务器
    - 获取浏览器列表
    - 多线程调度
    - 日志输出
    - 管理自动发帖和账号互动
    """
    
    def __init__(self, max_workers: int = 4):
        self.client: Optional[BrowserClient] = None
        self.auth_client = None  # 新增：认证客户端
        self.stats = 任务统计()
        self.max_workers = max_workers
        self._log_lock = threading.Lock()
        self._running = False
        self._run_thread: Optional[threading.Thread] = None
        self.on_log: Optional[callable] = None  # 外部日志回调
        
        # 新增：自动发帖管理器和互动协调器
        self.发帖管理器 = None
        self.互动协调器 = None
        self._初始化自动发帖系统()
    
    def _初始化自动发帖系统(self):
        """初始化自动发帖管理器和互动协调器"""
        print("[Init] 🔧 开始初始化自动发帖系统...")
        
        try:
            # 导入自动发帖管理器和互动协调器
            # 使用绝对路径导入，避免中文文件名问题
            import importlib.util
            
            print(f"[Init] 📂 当前目录: {current_dir}")
            
            # 自动发帖管理器路径
            发帖管理器路径 = os.path.join(current_dir, "自动发帖管理器.py")
            互动协调器路径 = os.path.join(current_dir, "互动协调器.py")
            
            print(f"[Init] 📄 发帖管理器路径: {发帖管理器路径}")
            print(f"[Init] 📄 互动协调器路径: {互动协调器路径}")
            
            # 检查文件是否存在
            if not os.path.exists(发帖管理器路径):
                print(f"[Init] ❌ 文件不存在: {发帖管理器路径}")
                self.发帖管理器 = None
                self.互动协调器 = None
                return
            
            if not os.path.exists(互动协调器路径):
                print(f"[Init] ❌ 文件不存在: {互动协调器路径}")
                self.发帖管理器 = None
                self.互动协调器 = None
                return
            
            print("[Init] ✓ 文件检查通过")
            
            # 加载自动发帖管理器模块
            print("[Init] 📦 加载自动发帖管理器模块...")
            spec1 = importlib.util.spec_from_file_location("自动发帖管理器", 发帖管理器路径)
            发帖模块 = importlib.util.module_from_spec(spec1)
            spec1.loader.exec_module(发帖模块)
            print("[Init] ✓ 自动发帖管理器模块加载成功")
            
            # 加载互动协调器模块
            print("[Init] 📦 加载互动协调器模块...")
            spec2 = importlib.util.spec_from_file_location("互动协调器", 互动协调器路径)
            互动模块 = importlib.util.module_from_spec(spec2)
            spec2.loader.exec_module(互动模块)
            print("[Init] ✓ 互动协调器模块加载成功")
            
            # 创建实例
            print("[Init] 🏗️ 创建自动发帖管理器实例...")
            self.发帖管理器 = 发帖模块.自动发帖管理器(log_func=self.log, main_controller=self)
            print("[Init] ✓ 自动发帖管理器实例创建成功")
            
            print("[Init] 🏗️ 创建互动协调器实例...")
            self.互动协调器 = 互动模块.互动协调器(self, log_func=self.log)
            print("[Init] ✓ 互动协调器实例创建成功")
            
            # 设置互动协调器
            print("[Init] 🔗 设置互动协调器...")
            self.发帖管理器.设置互动协调器(self.互动协调器)
            print("[Init] ✓ 互动协调器设置成功")
            
            print("[Init] ✅ 自动发帖系统已初始化")
            print(f"[Init] 🔍 验证: 发帖管理器 = {self.发帖管理器}")
            print(f"[Init] 🔍 验证: 互动协调器 = {self.互动协调器}")
            
        except Exception as e:
            print("=" * 60)
            print(f"[Init] ❌ 自动发帖系统初始化失败")
            print(f"[Init] 错误类型: {type(e).__name__}")
            print(f"[Init] 错误信息: {str(e)}")
            print("=" * 60)
            
            import traceback
            错误详情 = traceback.format_exc()
            print("[Init] 详细错误堆栈:")
            for line in 错误详情.split('\n'):
                if line.strip():
                    print(f"[Init]   {line}")
            
            print("=" * 60)
            
            self.发帖管理器 = None
            self.互动协调器 = None
    
    def set_auth_client(self, auth_client):
        """设置认证客户端（用于账号数量检查）"""
        self.auth_client = auth_client
    
    def log(self, msg: str):
        """输出日志（线程安全）"""
        with self._log_lock:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {msg}")
            
            if self.on_log:
                try:
                    self.on_log(msg)
                except:
                    pass
            
            if self.client:
                try:
                    threading.Thread(
                        target=lambda: self.client.log(msg),
                        daemon=True
                    ).start()
                except:
                    pass
    
    # ==================== 连接与获取 ====================
    
    def connect(self, host: str = "localhost", port: int = 5678) -> bool:
        """连接监控服务器"""
        if BrowserClient is None:
            self.log("❌ BrowserClient 未加载")
            return False
        
        self.client = BrowserClient(host, port)
        
        if self.client.check_server():
            self.log("✓ 已连接监控服务器")
            return True
        else:
            self.log("❌ 无法连接监控服务器")
            return False
    
    def get_all_browsers(self) -> List[Dict]:
        """获取所有浏览器列表"""
        if self.client:
            return self.client.get_browser_list()
        elif bit_browser:
            result = bit_browser.get_browser_list()
            if result.get("success"):
                return result.get("data", {}).get("list", [])
        return []
    
    # ==================== 单账号完整流程 ====================
    
    def 处理单个账号(self, browser: Dict, 序号: int = 0, 当前轮数: int = None) -> bool:
        """
        处理单个账号的完整流程
        
        流程：
        1. 账号检测 - 检测账号状态（封号/正常/未登录）
        2. 轮次检查 - 检查今日轮次是否允许执行
        3. 账号预检 - 关闭导航页等配置
        4. 记录运行 - 记录首次运行时间等
        5. 打开浏览器 - 添加到监控窗口
        6. 获取Driver - 连接 Selenium
        7. 执行任务 - 进入首页、阅读等
        
        Args:
            browser: 浏览器信息字典
            序号: 浏览器序号（用于显示）
            当前轮数: 当前是第几轮（1-3），None表示不启用轮次控制
        
        Returns:
            是否成功
        """
        bid = browser.get("id", "")
        原名称 = browser.get("name", "")
        显示名称 = f"#{序号} {原名称}" if 原名称 else f"#{序号} {bid[:6]}"
        
        self.log(f"[{显示名称}] 开始处理...")
        self.stats.increment("total")
        
        # ========== 1. 账号检测 ==========
        账号 = 账号检测(bid, 原名称)
        账号.显示名称 = 显示名称
        
        # 根据状态决定是否继续
        if 账号.状态 == "Blocked":
            self.log(f"[{显示名称}] ✗ 账号已封号，删除浏览器...")
            self.stats.increment("blocked")
            # 删除封号的浏览器
            if bit_browser:
                try:
                    result = bit_browser.delete_browser(bid)
                    if result.get("success"):
                        self.log(f"[{显示名称}] ✓ 浏览器已删除")
                    else:
                        self.log(f"[{显示名称}] ✗ 删除失败: {result}")
                except Exception as e:
                    self.log(f"[{显示名称}] ✗ 删除异常: {e}")
            return False
        
        if 账号.状态 == "NoLogin":
            self.log(f"[{显示名称}] - 未登录Facebook，删除浏览器...")
            self.stats.increment("no_login")
            # 删除未登录的浏览器
            if bit_browser:
                try:
                    result = bit_browser.delete_browser(bid)
                    if result.get("success"):
                        self.log(f"[{显示名称}] ✓ 浏览器已删除")
                    else:
                        self.log(f"[{显示名称}] ✗ 删除失败: {result}")
                except Exception as e:
                    self.log(f"[{显示名称}] ✗ 删除异常: {e}")
            return False
        
        if 账号.状态 == "Active":
            self.log(f"[{显示名称}] ✓ 账号正常")
            self.stats.increment("active")
        else:
            self.log(f"[{显示名称}] ? 状态未知，尝试执行")
        
        # ========== 2. 轮次检查 ==========
        if 当前轮数 is not None:
            可执行, 已完成轮次 = 检查账号轮次(bid, 当前轮数)
            
            if not 可执行:
                self.log(f"[{显示名称}] ⏭ 已完成 {已完成轮次} 轮，跳过第 {当前轮数} 轮")
                return False
            
            self.log(f"[{显示名称}] 📋 开始第 {当前轮数} 轮（已完成 {已完成轮次} 轮）")
            
            # 更新状态为"执行中"
            更新账号执行状态(bid, 当前轮数, "running")
        
        # ========== 3. 账号预检 ==========
        账号预检(bid)
        
        # ========== 4. 记录运行信息 ==========
        运行信息 = 记录运行信息(bid, 显示名称, 账号.c_user)
        账号.运行天数 = 运行信息["运行天数"]
        账号.运行次数 = 运行信息["运行次数"]
        
        if 运行信息["是否新增"]:
            self.log(f"[{显示名称}] 📝 首次运行，已记录")
        else:
            self.log(f"[{显示名称}] 📅 已运行 {账号.运行天数} 天，第 {账号.运行次数} 次执行")
        
        # ========== 5. 打开浏览器 ==========
        if not self.client.add_browser(bid, 显示名称, wait=True):
            self.log(f"[{显示名称}] ✗ 打开浏览器失败，跳过")
            self.stats.increment("failed")
            if 当前轮数 is not None:
                更新账号执行状态(bid, 当前轮数, "failed")
            return False
        time.sleep(3)  # 等待窗口嵌入稳定
        
        # ========== 6. 获取 Driver ==========
        self.client.set_status(bid, "运行中...")
        driver = self.client.get_driver(bid, retry=3)
        
        if not driver:
            self.log(f"[{显示名称}] ✗ 获取 driver 失败")
            self.client.set_status(bid, "✗ 无driver")
            self.stats.increment("failed")
            # 关闭浏览器并从 UI 移除
            try:
                self.client.remove_browser(bid, close=True)
            except:
                pass
            if 当前轮数 is not None:
                更新账号执行状态(bid, 当前轮数, "failed")
            return False
        
        # 切换到最后一个标签
        try:
            handles = driver.window_handles
            if len(handles) > 1:
                driver.switch_to.window(handles[-1])
        except:
            pass
        
        # ========== 7. 执行任务 ==========
        try:
            # 传递互动协调器，以便任务执行时能检查暂停标志
            success = 执行任务(账号, driver, log_func=self.log, 互动协调器=self.互动协调器)
            
            if success:
                self.client.set_status(bid, "✓ 完成")
                if 当前轮数 is not None:
                    self.log(f"[{显示名称}] ✓ 第 {当前轮数} 轮任务完成")
                    更新账号执行状态(bid, 当前轮数, "completed")
                else:
                    self.log(f"[{显示名称}] ✓ 任务完成")
                self.stats.increment("success")
            else:
                self.client.set_status(bid, "✗ 失败")
                if 当前轮数 is not None:
                    self.log(f"[{显示名称}] ✗ 第 {当前轮数} 轮任务失败")
                    更新账号执行状态(bid, 当前轮数, "failed")
                else:
                    self.log(f"[{显示名称}] ✗ 任务失败")
                self.stats.increment("failed")
                
        except Exception as e:
            self.client.set_status(bid, "✗ 异常")
            if 当前轮数 is not None:
                self.log(f"[{显示名称}] ✗ 第 {当前轮数} 轮异常: {e}")
                更新账号执行状态(bid, 当前轮数, "failed")
            else:
                self.log(f"[{显示名称}] ✗ 异常: {e}")
            self.stats.increment("failed")
            success = False
        
        # ========== 8. 关闭浏览器并从 UI 移除 ==========
        try:
            self.log(f"[{显示名称}] 关闭浏览器...")
            # 从 UI 中移除浏览器并关闭
            self.client.remove_browser(bid, close=True)
            self.log(f"[{显示名称}] ✓ 浏览器已关闭")
        except Exception as e:
            self.log(f"[{显示名称}] ⚠ 关闭浏览器失败: {e}")
        
        return success
    
    # ==================== 主流程 ====================
    
    def run(self, max_workers: int = None):
        """运行主流程（支持每日3轮循环和断点续传）"""
        # 优先使用认证服务器的窗口数量配置
        if self.auth_client and hasattr(self.auth_client, 'user_info') and self.auth_client.user_info:
            auth_workers = self.auth_client.user_info.get('max_windows', 4)
            workers = max_workers or auth_workers
        else:
            workers = max_workers or self.max_workers
        
        self.log("=" * 60)
        self.log(f"自动化主控制器 v{VERSION}")
        self.log(f"并发数: {workers}")
        self.log("=" * 60)
        
        # 连接服务器（需要先连接，登录时才能嵌入浏览器到 UI）
        if not self.connect():
            return
        
        # ========== 启动自动发帖管理器（后台运行，不阻塞账号任务）==========
        if self.发帖管理器:
            try:
                self.log("")
                self.log("=" * 60)
                self.log("🚀 启动自动发帖系统")
                self.log("=" * 60)
                self.发帖管理器.启动()
                self.log("✅ 自动发帖系统已在后台运行")
                self.log("   - 定时发帖：每天早中晚随机时间")
                self.log("   - 发帖成功后：80%账号暂停任务去互动")
                self.log("   - 互动完成后：账号任务自动恢复")
                self.log("=" * 60)
                self.log("")
            except Exception as e:
                self.log(f"⚠️ 启动自动发帖系统失败: {e}")
        
        # ========== 检查待登录账号 ==========
        待登录数 = 检查待登录账号()
        if 待登录数 > 0:
            self.log(f"发现 {待登录数} 个待登录账号，开始登录...")
            # 传入 client 以便登录时嵌入浏览器到 UI，传入 auth_client 用于账号数量检查
            批量登录(log_func=self.log, client=self.client, auth_client=self.auth_client)
            self.log("")
        
        # 获取浏览器列表
        all_browsers = self.get_all_browsers()
        if not all_browsers:
            self.log("没有找到浏览器")
            return
        
        # 排除"公共主页"浏览器（专门用于发帖，不执行账号任务）
        browsers = [b for b in all_browsers if b.get("name") != "公共主页"]
        
        排除数量 = len(all_browsers) - len(browsers)
        if 排除数量 > 0:
            self.log(f"已排除 {排除数量} 个专用浏览器（公共主页）")
        
        if not browsers:
            self.log("没有找到可用的账号浏览器（已排除公共主页）")
            return
        
        self.log(f"找到 {len(browsers)} 个账号浏览器")
        
        # ========== 检查浏览器数量限制 ==========
        if self.auth_client and hasattr(self.auth_client, 'user_info') and self.auth_client.user_info:
            max_browsers = self.auth_client.user_info.get('max_simulators', 5)
            actual_count = len(browsers)  # 只计算账号浏览器，不包括公共主页
            
            self.log(f"账号浏览器数量检查: {actual_count}/{max_browsers}")
            
            if actual_count > max_browsers:
                self.log("")
                self.log("=" * 60)
                self.log(f"❌ 账号浏览器数量超过限制！")
                self.log(f"   当前账号浏览器数: {actual_count}")
                self.log(f"   最大允许数: {max_browsers}")
                self.log(f"   超出数量: {actual_count - max_browsers}")
                self.log(f"   注：「公共主页」浏览器不计入限制")
                self.log("")
                self.log("程序将退出，请联系管理员增加浏览器配额")
                self.log("=" * 60)
                self.log("")
                
                # 显示弹窗提示
                try:
                    from PyQt5.QtWidgets import QMessageBox, QApplication
                    app = QApplication.instance()
                    if app:
                        msg = QMessageBox()
                        msg.setIcon(QMessageBox.Warning)
                        msg.setWindowTitle("浏览器数量超限")
                        msg.setText(f"账号浏览器数量超过限制！\n\n当前账号浏览器数: {actual_count}\n最大允许数: {max_browsers}\n超出数量: {actual_count - max_browsers}\n\n注：「公共主页」浏览器不计入限制")
                        msg.setInformativeText("程序将退出，请联系管理员增加浏览器配额。")
                        msg.setStandardButtons(QMessageBox.Ok)
                        msg.exec_()
                except:
                    pass
                
                # 退出程序
                import sys
                sys.exit(1)
            
            self.log(f"✓ 账号浏览器数量检查通过")
        
        
        # ========== 读取轮次配置 ==========
        轮次配置 = 读取轮次配置()
        启用轮次控制 = 轮次配置.get("启用轮次控制", True)
        每日轮次 = 轮次配置.get("每日轮次", 3)
        打乱顺序 = 轮次配置.get("打乱账号顺序", True)
        
        if not 启用轮次控制:
            # 不启用轮次控制，直接执行一次
            self.log("轮次控制未启用，执行单次任务...")
            self._执行单轮(browsers, workers, None, 打乱顺序)
            return
        
        # ========== 启动时分析执行状态 ==========
        执行状态 = 启动时分析执行状态(browsers)
        
        self.log(f"\n📊 执行状态分析：")
        self.log(f"  总账号数: {len(browsers)}")
        self.log(f"  今日已完成{每日轮次}轮: {执行状态['今日已完成账号']} 个")
        self.log(f"  今日未完成{每日轮次}轮: {执行状态['今日未完成账号']} 个")
        
        if "轮次分布" in 执行状态:
            分布文本 = ", ".join([f"{i}轮={执行状态['轮次分布'][i]}" for i in sorted(执行状态['轮次分布'].keys())])
            self.log(f"  轮次分布: {分布文本}")
        
        self.log(f"  💡 {执行状态['建议']}\n")
        
        if not 执行状态['需要继续执行']:
            self.log("今日任务已完成，程序退出")
            return
        
        # ========== 确定起始轮数 ==========
        起始轮数 = 执行状态['应执行轮数']
        
        # ========== 从起始轮数开始执行到最后一轮 ==========
        for 轮数 in range(起始轮数, 每日轮次 + 1):
            self.log(f"\n{'='*60}")
            self.log(f"开始第 {轮数} 轮执行")
            self.log(f"{'='*60}\n")
            
            # 执行本轮
            本轮执行数, 本轮跳过数 = self._执行单轮(browsers, workers, 轮数, 打乱顺序)
            
            # 本轮统计
            self.log(f"\n第 {轮数} 轮完成统计：")
            self.log(f"  执行: {本轮执行数} 个")
            self.log(f"  跳过: {本轮跳过数} 个")
            
            # 计算等待时间
            if 轮数 < 每日轮次:
                等待秒数 = 计算轮次等待时间(轮数, 每日轮次)
                等待小时 = 等待秒数 / 3600
                预计时间 = time.strftime("%H:%M:%S", time.localtime(time.time() + 等待秒数))
                
                self.log(f"\n⏰ 第 {轮数} 轮完成，等待 {等待小时:.1f} 小时后开始第 {轮数+1} 轮")
                self.log(f"   预计开始时间: {预计时间}")
                
                # 可中断的等待（带倒计时）
                self._等待下一轮(等待秒数, 轮数+1)
        
        # 所有轮次完成，等待到第二天
        self.log(f"\n✅ 今日所有 {每日轮次} 轮已全部完成！")
        self._等待到明天()
        
        # 递归调用，继续执行
        self.log("\n" + "="*60)
        self.log("新的一天开始，重新执行任务...")
        self.log("="*60)
        self.run(max_workers)
        
        # 输出最终统计
        self.log("")
        self.log("=" * 60)
        self.log("执行完毕 - 统计")
        self.log("=" * 60)
        self.log(f"  总浏览器数: {self.stats.total}")
        self.log(f"  正常账号: {self.stats.active}")
        self.log(f"  封号账号: {self.stats.blocked}")
        self.log(f"  未登录: {self.stats.no_login}")
        self.log(f"  任务成功: {self.stats.success}")
        self.log(f"  任务失败: {self.stats.failed}")
    
    def _执行单轮(self, browsers: List[Dict], workers: int, 轮数: int = None, 打乱顺序: bool = True) -> tuple:
        """
        执行单轮任务
        
        Args:
            browsers: 浏览器列表
            workers: 并发数
            轮数: 第几轮（None表示不启用轮次控制）
            打乱顺序: 是否打乱账号顺序
        
        Returns:
            (执行数, 跳过数)
        """
        # 打乱账号顺序（模拟真实用户行为）
        if 打乱顺序:
            browsers_copy = browsers.copy()
            random.shuffle(browsers_copy)
        else:
            browsers_copy = browsers
        
        # 设置监控窗口列数
        self.client.set_columns(min(workers, 4))
        
        # 统计本轮执行情况
        本轮执行数 = 0
        本轮跳过数 = 0
        
        # 多线程执行本轮任务
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for 序号, browser in enumerate(browsers_copy, 1):
                future = executor.submit(self.处理单个账号, browser, 序号, 轮数)
                futures[future] = (browser, 序号)
            
            for future in as_completed(futures):
                browser, 序号 = futures[future]
                try:
                    result = future.result()
                    if result:
                        本轮执行数 += 1
                    else:
                        本轮跳过数 += 1
                except Exception as e:
                    bid = browser.get("id", "")[:6]
                    self.log(f"[#{序号} {bid}] 线程异常: {e}")
                    本轮跳过数 += 1
        
        total_time = time.time() - start_time
        if 轮数 is not None:
            self.log(f"\n第 {轮数} 轮耗时: {total_time:.1f}秒")
        else:
            self.log(f"\n总耗时: {total_time:.1f}秒")
        
        return (本轮执行数, 本轮跳过数)
    
    def _等待下一轮(self, 等待秒数: int, 下一轮数: int):
        """
        等待到下一轮（带倒计时显示）
        
        Args:
            等待秒数: 需要等待的总秒数
            下一轮数: 下一轮的轮数
        """
        已等待 = 0
        更新间隔 = 60  # 每60秒更新一次显示
        
        while 已等待 < 等待秒数:
            if not self._running:
                self.log("收到停止信号，中断等待")
                break
            
            剩余秒数 = 等待秒数 - 已等待
            剩余小时 = 剩余秒数 / 3600
            剩余分钟 = (剩余秒数 % 3600) / 60
            
            # 格式化显示
            if 剩余小时 >= 1:
                时间显示 = f"{剩余小时:.1f}小时"
            else:
                时间显示 = f"{int(剩余分钟)}分钟"
            
            预计时间 = time.strftime("%H:%M:%S", time.localtime(time.time() + 剩余秒数))
            
            self.log(f"⏳ 等待第 {下一轮数} 轮... 剩余: {时间显示} (预计 {预计时间} 开始)")
            
            # 等待
            本次等待 = min(更新间隔, 剩余秒数)
            time.sleep(本次等待)
            已等待 += 本次等待
    
    def _等待到明天(self):
        """
        等待到明天0点（带倒计时显示）
        """
        等待秒数 = 计算到明天的秒数()
        
        self.log(f"\n🌙 今日所有轮次已完成，等待到明天...")
        self.log(f"   距离明天还有: {等待秒数/3600:.1f} 小时")
        
        已等待 = 0
        更新间隔 = 300  # 每5分钟更新一次显示
        
        while 已等待 < 等待秒数:
            if not self._running:
                self.log("收到停止信号，中断等待")
                break
            
            剩余秒数 = 等待秒数 - 已等待
            剩余小时 = 剩余秒数 / 3600
            剩余分钟 = (剩余秒数 % 3600) / 60
            
            # 格式化显示
            if 剩余小时 >= 1:
                时间显示 = f"{剩余小时:.1f}小时"
            else:
                时间显示 = f"{int(剩余分钟)}分钟"
            
            明天时间 = time.strftime("%Y-%m-%d 00:00:00", time.localtime(time.time() + 剩余秒数))
            
            self.log(f"🌙 等待新的一天... 剩余: {时间显示} (明天: {明天时间})")
            
            # 等待
            本次等待 = min(更新间隔, 剩余秒数)
            time.sleep(本次等待)
            已等待 += 本次等待
    
    def run_async(self, max_workers: int = None, on_complete: callable = None):
        """异步运行（不阻塞）"""
        if self._running:
            self.log("⚠️ 任务正在运行中")
            return False
        
        def _run_wrapper():
            self._running = True
            try:
                self.run(max_workers)
            finally:
                self._running = False
                if on_complete:
                    try:
                        on_complete()
                    except:
                        pass
        
        self._run_thread = threading.Thread(target=_run_wrapper, daemon=True)
        self._run_thread.start()
        return True
    
    def is_running(self) -> bool:
        return self._running
    
    def stop(self):
        self._running = False
        self.log("⚠️ 收到停止请求")
        
        # 停止自动发帖管理器
        if self.发帖管理器:
            try:
                self.发帖管理器.停止()
                self.log("✅ 自动发帖系统已停止")
            except Exception as e:
                self.log(f"⚠️ 停止自动发帖系统失败: {e}")


# ==================== 入口 ====================

# 全局控制器实例（用于 bootstrap 获取）
_controller_instance = None

def get_controller():
    """
    获取控制器实例（用于 bootstrap）
    如果控制器不存在，则创建一个新的
    """
    global _controller_instance
    if _controller_instance is None:
        线程数 = 获取线程数()
        _controller_instance = AutomationMain(max_workers=线程数)
    return _controller_instance

def main():
    # 从配置文件读取线程数
    线程数 = 获取线程数()
    print(f"[Main] 配置线程数: {线程数}")
    
    # 初始化调试模式（启用快捷键监听）
    try:
        from debug_integration import init_debug_mode
        print("[Main] 🔧 初始化调试模式...")
        if init_debug_mode(enable_hotkey=True):
            print("[Main] ✓ 调试模式已启动 (Ctrl+Shift+D)")
        else:
            print("[Main] ⚠️ 调试模式启动失败（pynput可能未安装）")
    except Exception as e:
        print(f"[Main] ⚠️ 调试模式初始化异常: {e}")
    
    # 检测开发环境
    main_py_exists = os.path.exists(os.path.join(current_dir, "main.py"))
    main_pyc_exists = os.path.exists(os.path.join(current_dir, "main.pyc"))
    is_dev = main_py_exists  # 如果 main.py 存在，说明是开发环境
    
    if is_dev:
        print("[Main] 🔧 检测到开发环境，跳过热更新守护进程")
        print("[Main] ✓ 使用本地 .py 源文件")
    else:
        # 启动热更新守护进程（后台定期检查更新）
        # 注意：启动时的更新检查已由 bootstrap.py 完成
        try:
            from 热更新守护进程 import 启动热更新守护进程
            
            启动热更新守护进程(
                检查间隔=300,  # 5 分钟检查一次
                日志回调=print,
                启动时检查=False  # 禁用启动时检查，因为 bootstrap 已经检查过了
            )
            print("[Main] ✓ 热更新守护进程已启动（定期检查）")
        except Exception as e:
            print(f"[Main] 启动热更新守护进程失败: {e}")
    
    controller = get_controller()
    controller.run()


if __name__ == "__main__":
    main()
