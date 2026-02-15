"""
到首页任务
导航到 Facebook 首页并检测页面状态
"""

import os
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

# ==================== 页面状态枚举 ====================

class 页面状态:
    """Facebook 页面状态"""
    首页正常 = "首页正常"           # 成功进入首页
    需要登录 = "需要登录"           # 账号退登，需要重新登录
    需要验证码 = "需要验证码"       # 需要邮箱/手机验证码
    账号被封 = "账号被封"           # 账号被封禁
    账号受限 = "账号受限"           # 账号功能受限
    需要确认身份 = "需要确认身份"   # 需要身份验证
    网络错误 = "网络错误"           # 页面加载失败
    未知状态 = "未知状态"           # 无法识别的状态

@dataclass
class 页面检测结果:
    """页面检测结果"""
    状态: str                       # 页面状态
    当前URL: str = ""               # 当前页面 URL
    页面标题: str = ""              # 页面标题
    详细信息: str = ""              # 详细描述
    可继续: bool = False            # 是否可以继续执行任务

# ==================== 主函数 ====================

def 到首页(driver: "WebDriver", log_func=None) -> 页面检测结果:
    """
    导航到 Facebook 首页并检测页面状态
    
    优化策略：
    1. 先检查是否已在首页（www.facebook.com）
    2. 如果不在首页，尝试点击Logo返回首页
    3. 最后才使用URL跳转
    
    Args:
        driver: Selenium WebDriver
        log_func: 日志函数（可选）
    
    Returns:
        页面检测结果，包含状态和详细信息
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    try:
        # 先关闭多余的标签页
        log("清理多余的标签页...")
        _关闭多余标签页(driver, log)
        
        # 先检查当前是否已经在首页
        current_url = driver.current_url
        
        # 检查是否在www.facebook.com域名下且不是登录/检查点页面
        # 关键：必须检查路径，确保是首页而不是其他页面（如 /friends, /messages）
        parsed = urlparse(current_url)
        path = parsed.path
        
        if ("www.facebook.com" in current_url and 
            "/login" not in current_url and 
            "/checkpoint" not in current_url and
            (not path or path == "/")):  # 路径必须为空或只有 /
            # 可能已经在首页，检测一下
            if _是否在首页(driver):
                log("✓ 已在首页")
                
                # 检测并修改语言为英文
                log("检测页面语言...")
                if not _是否英文界面(driver):
                    log("检测到非英文界面，修改语言为英文...")
                    if _修改语言为英文(driver, log):
                        log("✓ 语言已修改为英文")
                        # 重新验证首页状态
                        time.sleep(2)
                        driver.get("https://www.facebook.com")
                        time.sleep(3)
                        if not _是否在首页(driver):
                            log("⚠ 语言修改后首页检测失败，重新导航...")
                            driver.get("https://www.facebook.com")
                            time.sleep(3)
                    else:
                        log("⚠ 语言修改失败，但继续执行")
                else:
                    log("✓ 已是英文界面")
                
                return 页面检测结果(
                    状态=页面状态.首页正常,
                    当前URL=current_url,
                    页面标题=driver.title,
                    详细信息="已在首页",
                    可继续=True
                )
        
        log("正在进入 Facebook 首页...")
        
        # 策略1: 如果在facebook.com域名下但不在首页，尝试点击Logo返回
        if "facebook.com" in current_url and "/login" not in current_url and "/checkpoint" not in current_url:
            log("尝试点击Logo返回首页...")
            if _点击Logo返回首页(driver, log):
                # 等待页面加载
                time.sleep(2)
                current_url = driver.current_url
                
                # 检查是否成功到达www.facebook.com
                if "www.facebook.com" in current_url and _是否在首页(driver):
                    log("✓ 通过Logo成功返回首页")
                    return 页面检测结果(
                        状态=页面状态.首页正常,
                        当前URL=current_url,
                        页面标题=driver.title,
                        详细信息="通过Logo返回首页",
                        可继续=True
                    )
                else:
                    log("点击Logo后未到达首页，尝试URL跳转...")
        
        # 策略2: 直接URL跳转（最后的办法）
        log("使用URL跳转到首页...")
        driver.get("https://www.facebook.com")
        time.sleep(3)  # 等待页面加载
        
        # 获取当前页面信息
        current_url = driver.current_url
        page_title = driver.title
        
        log(f"当前URL: {current_url}")
        log(f"页面标题: {page_title}")
        
        # 刷新浏览器
        log("刷新浏览器...")
        driver.refresh()
        time.sleep(3)
        
        # 检测页面状态（带重试机制）
        result = _检测页面状态(driver, current_url, page_title)
        
        # 如果未能识别页面状态，进行重试
        if result.状态 == 页面状态.未知状态:
            log("首次检测失败，进行重试...")
            for retry in range(3):
                log(f"重试 {retry + 1}/3...")
                time.sleep(2)
                driver.refresh()
                time.sleep(2)
                result = _检测页面状态(driver, current_url, page_title)
                if result.状态 != 页面状态.未知状态:
                    log(f"✓ 第 {retry + 1} 次重试成功")
                    break
        
        # 记录结果
        if result.可继续:
            log(f"✓ {result.状态}")
            
            # 检测并修改语言为英文
            log("检测页面语言...")
            if not _是否英文界面(driver):
                log("检测到非英文界面，修改语言为英文...")
                if _修改语言为英文(driver, log):
                    log("✓ 语言已修改为英文")
                    # 重新执行到首页过程，确保既是首页又是英文
                    log("重新验证首页状态...")
                    time.sleep(2)
                    driver.get("https://www.facebook.com")
                    time.sleep(3)
                    result = _检测页面状态(driver, driver.current_url, driver.title)
                    if result.状态 != 页面状态.未知状态:
                        log(f"✓ 最终状态: {result.状态}")
                else:
                    log("⚠ 语言修改失败，但继续执行")
            else:
                log("✓ 已是英文界面")
        else:
            log(f"✗ {result.状态}: {result.详细信息}")
        
        return result
        
    except Exception as e:
        log(f"✗ 页面加载异常: {e}")
        return 页面检测结果(
            状态=页面状态.网络错误,
            详细信息=str(e),
            可继续=False
        )

# ==================== 内部函数 ====================

def _关闭多余标签页(driver, log_func=None) -> bool:
    """
    关闭多余的标签页，保留只有一个标签页
    
    策略：
    1. 获取所有标签页
    2. 如果只有1个标签页，不关闭（避免关闭整个浏览器）
    3. 优先关闭包含"-工作台"的标签页
    4. 然后关闭其他非Facebook首页的标签页
    5. 最后保证只留下1个标签页
    
    Args:
        driver: Selenium WebDriver
        log_func: 日志函数
    
    Returns:
        是否成功
    """
    def log(msg):
        if log_func:
            log_func(msg)
    
    try:
        # 获取所有标签页
        all_handles = driver.window_handles
        tab_count = len(all_handles)
        
        log(f"当前标签页数: {tab_count}")
        
        # 如果只有1个标签页，不关闭
        if tab_count <= 1:
            log("只有1个标签页，不关闭")
            return True
        
        # 收集要关闭的标签页
        tabs_to_close = []
        workbench_tab = None
        facebook_home_tab = None
        
        # 遍历所有标签页，识别它们
        for handle in all_handles:
            try:
                driver.switch_to.window(handle)
                time.sleep(0.3)
                
                title = driver.title
                url = driver.current_url
                
                log(f"  标签页: {title} | {url}")
                
                # 检查是否是工作台标签页
                if "工作台" in title or "-工作台" in title:
                    workbench_tab = handle
                    log(f"    → 识别为工作台标签页")
                
                # 检查是否是Facebook首页
                elif "facebook.com" in url and (not url.split('/')[-1] or url.endswith('/')):
                    facebook_home_tab = handle
                    log(f"    → 识别为Facebook首页标签页")
                
                else:
                    # 其他标签页，标记为待关闭
                    tabs_to_close.append(handle)
                    log(f"    → 标记为待关闭")
                    
            except Exception as e:
                log(f"  获取标签页信息失败: {e}")
                tabs_to_close.append(handle)
        
        # 决定要保留的标签页
        keep_handle = None
        if facebook_home_tab:
            keep_handle = facebook_home_tab
            log(f"将保留Facebook首页标签页")
        else:
            # 找到第一个不是工作台也不在待关闭列表中的标签页
            for handle in all_handles:
                if handle != workbench_tab and handle not in tabs_to_close:
                    keep_handle = handle
                    break
            
            # 如果没找到，就保留第一个非工作台标签页
            if not keep_handle:
                for handle in all_handles:
                    if handle != workbench_tab:
                        keep_handle = handle
                        break
            
            if keep_handle:
                log(f"将保留第一个可用标签页")
        
        # 先切换到要保留的标签页（关键！）
        if keep_handle:
            try:
                driver.switch_to.window(keep_handle)
                time.sleep(0.3)
                log(f"已切换到保留的标签页")
            except Exception as e:
                log(f"切换到保留标签页失败: {e}")
                return False
        
        # 现在可以安全地关闭工作台标签页
        if workbench_tab and workbench_tab != keep_handle:
            log(f"关闭工作台标签页...")
            try:
                driver.switch_to.window(workbench_tab)
                driver.close()
                time.sleep(0.3)
                # 立即切回保留的标签页
                driver.switch_to.window(keep_handle)
                time.sleep(0.2)
                log(f"已关闭工作台标签页")
            except Exception as e:
                log(f"关闭工作台标签页失败: {e}")
                # 确保切回保留的标签页
                try:
                    driver.switch_to.window(keep_handle)
                except:
                    pass
            
            if workbench_tab in tabs_to_close:
                tabs_to_close.remove(workbench_tab)
        
        # 关闭其他多余标签页
        for handle in tabs_to_close:
            if handle != keep_handle:
                try:
                    driver.switch_to.window(handle)
                    time.sleep(0.2)
                    driver.close()
                    time.sleep(0.2)
                    # 立即切回保留的标签页
                    driver.switch_to.window(keep_handle)
                    time.sleep(0.2)
                    log(f"已关闭标签页")
                except Exception as e:
                    log(f"关闭标签页失败: {e}")
                    # 确保切回保留的标签页
                    try:
                        driver.switch_to.window(keep_handle)
                    except:
                        pass
        
        # 获取剩余的标签页
        remaining_handles = driver.window_handles
        log(f"剩余标签页数: {len(remaining_handles)}")
        
        # 确保我们在正确的标签页上
        if remaining_handles:
            try:
                current_handle = driver.current_window_handle
                if current_handle not in remaining_handles:
                    # 当前句柄无效，切换到第一个可用的
                    driver.switch_to.window(remaining_handles[0])
                    time.sleep(0.3)
            except Exception as e:
                log(f"验证当前标签页失败: {e}")
                # 尝试切换到第一个可用的标签页
                try:
                    driver.switch_to.window(remaining_handles[0])
                    time.sleep(0.3)
                except:
                    pass
        
        final_count = len(driver.window_handles)
        log(f"✓ 标签页清理完成，最终标签页数: {final_count}")
        return True
        
    except Exception as e:
        log(f"⚠ 关闭标签页异常: {e}")
        # 尝试恢复到任何可用的窗口
        try:
            handles = driver.window_handles
            if handles:
                driver.switch_to.window(handles[0])
        except:
            pass
        return False

def _点击Logo返回首页(driver, log_func=None) -> bool:
    """
    尝试点击Facebook Logo返回首页
    
    Args:
        driver: Selenium WebDriver
        log_func: 日志函数
    
    Returns:
        是否成功点击Logo
    """
    def log(msg):
        if log_func:
            log_func(msg)
    
    try:
        # Facebook Logo的常见选择器
        logo_selectors = [
            "a[aria-label='Facebook']",  # 主Logo
            "a[href='/']",  # 首页链接
            "a[href='https://www.facebook.com/']",  # 完整首页链接
            "svg[aria-label='Facebook']",  # SVG Logo
            "img[alt='Facebook']",  # 图片Logo
        ]
        
        for selector in logo_selectors:
            try:
                elements = driver.find_elements("css selector", selector)
                if elements:
                    # 找到第一个可见的Logo元素
                    for element in elements:
                        if element.is_displayed():
                            element.click()
                            if log_func:
                                log(f"✓ 点击Logo成功 (选择器: {selector})")
                            return True
            except Exception as e:
                continue
        
        if log_func:
            log("未找到可点击的Logo")
        return False
        
    except Exception as e:
        if log_func:
            log(f"点击Logo失败: {e}")
        return False

def _检测页面状态(driver, current_url: str, page_title: str) -> 页面检测结果:
    """
    检测当前页面状态
    根据 URL、标题和页面元素判断账号状态
    """
    url_lower = current_url.lower()
    title_lower = page_title.lower()
    
    # ========== 根据标题判断 ==========
    
    # 标题包含 "log in" 或 "sign up" 表示未登录
    if "log in" in title_lower or "sign up" in title_lower or "登录" in title_lower:
        return 页面检测结果(
            状态=页面状态.需要登录,
            当前URL=current_url,
            页面标题=page_title,
            详细信息="页面标题显示需要登录",
            可继续=False
        )
    
    # ========== 根据 URL 判断 ==========
    
    # 登录页面 - 账号退登
    if "/login" in url_lower or "login.php" in url_lower:
        return 页面检测结果(
            状态=页面状态.需要登录,
            当前URL=current_url,
            页面标题=page_title,
            详细信息="账号已退出登录",
            可继续=False
        )
    
    # 检查点/验证页面
    if "/checkpoint" in url_lower:
        return _检测检查点类型(driver, current_url, page_title)
    
    # 账号被禁用
    if "/disabled" in url_lower or "account_disabled" in url_lower:
        return 页面检测结果(
            状态=页面状态.账号被封,
            当前URL=current_url,
            页面标题=page_title,
            详细信息="账号已被禁用",
            可继续=False
        )
    
    # 账号受限
    if "/restricted" in url_lower:
        return 页面检测结果(
            状态=页面状态.账号受限,
            当前URL=current_url,
            页面标题=page_title,
            详细信息="账号功能受限",
            可继续=False
        )
    
    # ========== 检测首页元素 ==========
    
    if _是否在首页(driver):
        return 页面检测结果(
            状态=页面状态.首页正常,
            当前URL=current_url,
            页面标题=page_title,
            详细信息="成功进入首页",
            可继续=True
        )
    
    # 无法识别的状态
    return 页面检测结果(
        状态=页面状态.未知状态,
        当前URL=current_url,
        页面标题=page_title,
        详细信息="无法识别当前页面状态",
        可继续=False
    )

def _检测检查点类型(driver, current_url: str, page_title: str) -> 页面检测结果:
    """
    检测检查点页面的具体类型
    """
    try:
        page_source = driver.page_source.lower()
        
        # 检测验证码相关关键词
        验证码关键词 = ["验证码", "verification code", "enter code", "输入代码", 
                     "发送代码", "send code", "确认你的身份"]
        if any(kw in page_source for kw in 验证码关键词):
            return 页面检测结果(
                状态=页面状态.需要验证码,
                当前URL=current_url,
                页面标题=page_title,
                详细信息="需要输入验证码",
                可继续=False
            )
        
        # 检测身份验证关键词
        身份验证关键词 = ["上传照片", "upload photo", "身份证", "id card", 
                      "confirm your identity", "确认身份"]
        if any(kw in page_source for kw in 身份验证关键词):
            return 页面检测结果(
                状态=页面状态.需要确认身份,
                当前URL=current_url,
                页面标题=page_title,
                详细信息="需要身份验证",
                可继续=False
            )
        
        # 检测封号关键词
        封号关键词 = ["disabled", "suspended", "违反", "violation", 
                   "permanently", "无法使用", "被停用"]
        if any(kw in page_source for kw in 封号关键词):
            return 页面检测结果(
                状态=页面状态.账号被封,
                当前URL=current_url,
                页面标题=page_title,
                详细信息="账号被封禁",
                可继续=False
            )
        
        # 默认返回需要验证码
        return 页面检测结果(
            状态=页面状态.需要验证码,
            当前URL=current_url,
            页面标题=page_title,
            详细信息="检查点页面，可能需要验证",
            可继续=False
        )
        
    except Exception as e:
        return 页面检测结果(
            状态=页面状态.未知状态,
            当前URL=current_url,
            页面标题=page_title,
            详细信息=f"检测检查点失败: {e}",
            可继续=False
        )

def _是否在首页(driver) -> bool:
    """
    检测是否成功进入 Facebook 首页
    
    要求：
    1. 必须在 www.facebook.com 域名下
    2. URL 必须是 www.facebook.com 或 www.facebook.com/（不能有其他路径如 /friends, /messages 等）
    3. 不能是登录页或检查点页面
    4. 页面包含首页特征元素（Feed 或特定的 img 元素）
    """
    try:
        current_url = driver.current_url
        
        # 必须在 www.facebook.com 域名下
        if "www.facebook.com" not in current_url:
            return False
        
        # 不能是登录页或检查点页面
        if "/login" in current_url or "/checkpoint" in current_url:
            return False
        
        # 关键：URL 必须是首页，不能有其他路径
        parsed = urlparse(current_url)
        path = parsed.path
        
        # 路径应该是空或只有 /
        if path and path != "/":
            return False
        
        # 检查是否有首页特征元素
        # 优先检查特定的 img 元素
        home_selectors = [
            "img[src*='rsrc.php/v4/y7/r/Ivw7nhRtXyo.png']",  # 特定的首页 img 元素
            "[data-testid='feed']",  # Feed 元素
            "[data-pagelet='FeedComposer']",  # Feed Composer
            "[aria-label*='Feed']",
            "[aria-label*='动态']"
        ]
        
        for selector in home_selectors:
            try:
                elements = driver.find_elements("css selector", selector)
                if elements and any(e.is_displayed() for e in elements):
                    return True
            except:
                continue
        
        return False
        
    except Exception:
        return False

# ==================== 调试配置 ====================

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(os.path.dirname(scripts_dir))

# 添加项目根目录到 sys.path（用于导入 bitbrowser_api 等模块）
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 打包环境检测：如果脚本路径包含 _internal，说明在打包环境中
if '_internal' in current_dir:
    internal_idx = current_dir.find('_internal')
    internal_dir = current_dir[:internal_idx + len('_internal')]
    if internal_dir not in sys.path:
        sys.path.insert(0, internal_dir)

# 默认浏览器ID
DEFAULT_BROWSER_ID = "dd6c77a66dc74aea8c449207d55a3a87"

def _get_debug_browser_id():
    """从环境变量获取调试浏览器ID"""
    return os.environ.get('DEBUG_BROWSER_ID', DEFAULT_BROWSER_ID)

# ==================== 调试模式 ====================

def _调试模式():
    """调试模式入口"""
    # 处理Windows控制台编码问题（仅在有buffer属性时才包装）
    import sys
    import io
    if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    # 从环境变量读取浏览器ID
    DEBUG_BROWSER_ID = _get_debug_browser_id()
    
    print("=" * 60)
    print("到首页 - 调试模式")
    print("=" * 60)
    print(f"浏览器ID: {DEBUG_BROWSER_ID}")
    print()
    
    # 导入比特浏览器API
    try:
        from bitbrowser_api import BitBrowserAPI
        bit_browser = BitBrowserAPI()
    except ImportError as e:
        print(f"❌ 无法导入 bitbrowser_api: {e}")
        return
    except Exception as e:
        print(f"❌ 初始化 BitBrowserAPI 失败: {e}")
        return
    
    # 1. 打开浏览器
    print("正在打开浏览器...")
    result = bit_browser.open_browser(DEBUG_BROWSER_ID)
    
    if not result.get("success"):
        print(f"❌ 打开浏览器失败: {result}")
        return
    
    data = result.get("data", {})
    debug_port = data.get("http")
    driver_path = data.get("driver")
    
    if not debug_port:
        print("❌ 未获取到调试端口")
        return
    
    print(f"✓ 浏览器已打开")
    print(f"  调试端口: {debug_port}")
    print(f"  驱动路径: {driver_path}")
    
    # 2. 连接 Selenium
    print("正在连接 Selenium...")
    try:
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
        
        print(f"✓ Selenium 连接成功")
        print(f"  当前页面: {driver.title}")
        print()
        
    except Exception as e:
        print(f"❌ Selenium 连接失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. 执行任务
    print("-" * 60)
    print("开始执行到首页...")
    print("-" * 60)
    
    结果 = 到首页(driver, print)
    
    print("-" * 60)
    print(f"状态: {结果.状态}")
    print(f"当前URL: {结果.当前URL}")
    print(f"页面标题: {结果.页面标题}")
    print(f"详细信息: {结果.详细信息}")
    print(f"可继续: {结果.可继续}")
    print("-" * 60)
    
    print()
    print("调试完成，浏览器保持打开状态")

# ==================== 语言检测和修改 ====================

def _是否英文界面(driver) -> bool:
    """
    检测当前是否是英文界面
    
    Args:
        driver: Selenium WebDriver
    
    Returns:
        是否是英文界面
    """
    from selenium.webdriver.common.by import By
    import re
    
    try:
        # 首先检查是否有中文特征（如果有中文，则不是英文）
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
            # 检查是否包含中文字符
            if re.search(r'[\u4e00-\u9fff]', page_text):
                # 页面中有中文，检查是否是导航栏中的中文（表示界面语言是中文）
                中文导航词 = ["首页", "视频", "朋友", "群组", "好友", "动态", "消息"]
                for 词 in 中文导航词:
                    if 词 in page_text[:500]:  # 检查页面前500个字符（通常是导航栏）
                        return False  # 界面是中文
        except:
            pass
        
        # 检查英文特征词（导航栏）
        英文特征词 = ["Home", "Watch", "Marketplace", "Groups", "Friends"]
        
        for 词 in 英文特征词:
            try:
                elements = driver.find_elements(By.XPATH, f"//span[text()='{词}']")
                for el in elements:
                    if el.is_displayed():
                        return True
            except:
                continue
        
        # 检查页面中是否有英文特征文字
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
            英文特征 = ["What's on your mind", "News Feed", "Create post", "Friend requests"]
            for 特征 in 英文特征:
                if 特征 in page_text:
                    return True
        except:
            pass
        
        return False
        
    except Exception:
        return False

def _修改语言为英文(driver, log_func=None) -> bool:
    """
    将 Facebook 界面语言修改为英文
    
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
            print(f"[到首页] {msg}")
    
    try:
        # 访问语言和地区设置页面
        log("访问语言设置页面...")
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
                        driver.execute_script("arguments[0].click();", el)
                        log(f"已点击语言设置")
                        已点击设置 = True
                        time.sleep(3)
                        break
            except:
                continue
        
        if not 已点击设置:
            # 尝试点击第一个可点击的设置项
            try:
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
                inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='radio'], input[type='checkbox']")
                for inp in inputs:
                    try:
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
                buttons = driver.find_elements(By.XPATH, f"//*[@role='button']//*[contains(text(), '{文本}')]")
                for btn in buttons:
                    if btn.is_displayed():
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
        
        log("✓ 语言设置完成")
        return True
        
    except Exception as e:
        log(f"修改语言失败: {e}")
        try:
            driver.get("https://www.facebook.com")
            time.sleep(2)
        except:
            pass
        return False

# ==================== 入口 ====================

if __name__ == "__main__":
    _调试模式()
