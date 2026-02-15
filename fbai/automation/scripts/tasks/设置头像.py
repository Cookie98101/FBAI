"""
设置头像任务
检测是否已设置头像，如果没有则上传头像
"""

import os
import sys
import random
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

# ==================== 配置 ====================

# 头像目录
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(current_dir)
头像目录 = os.path.join(scripts_dir, "脚本配置", "头像")
评论图片目录 = os.path.join(scripts_dir, "脚本配置", "评论图片")

# ==================== 工具函数 ====================

def 获取随机头像() -> Optional[str]:
    """
    从头像目录随机获取一张头像
    
    Returns:
        头像完整路径，如果目录为空返回 None
    """
    if not os.path.exists(头像目录):
        return None
    
    支持格式 = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    
    头像列表 = []
    for 文件 in os.listdir(头像目录):
        后缀 = os.path.splitext(文件)[1].lower()
        if 后缀 in 支持格式:
            头像列表.append(os.path.join(头像目录, 文件))
    
    if not 头像列表:
        return None
    
    return random.choice(头像列表)


def 获取随机评论图片() -> Optional[str]:
    """
    从评论图片目录随机获取一张图片
    
    Returns:
        图片完整路径，如果目录为空返回 None
    """
    if not os.path.exists(评论图片目录):
        return None
    
    支持格式 = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    
    图片列表 = []
    for 文件 in os.listdir(评论图片目录):
        后缀 = os.path.splitext(文件)[1].lower()
        if 后缀 in 支持格式:
            图片列表.append(os.path.join(评论图片目录, 文件))
    
    if not 图片列表:
        return None
    
    return random.choice(图片列表)


def 检测是否有头像(driver: "WebDriver", log_func=None) -> bool:
    """
    检测用户是否已设置头像
    
    Args:
        driver: WebDriver实例
        log_func: 日志函数
    
    Returns:
        True 表示已有头像，False 表示使用默认头像
    """
    def log(msg):
        if log_func:
            log_func(msg)
    
    try:
        from selenium.webdriver.common.by import By
        
        # 查找头像元素（通常在导航栏或个人资料页面）
        # 这是一个简化的检测，实际可能需要根据页面结构调整
        try:
            # 方法1: 查找个人资料头像
            avatar_elements = driver.find_elements(By.CSS_SELECTOR, "img[alt*='profile'], img[alt*='avatar']")
            
            if avatar_elements:
                for elem in avatar_elements:
                    src = elem.get_attribute("src")
                    if src and "default" not in src.lower():
                        log("✓ 检测到自定义头像")
                        return True
        except:
            pass
        
        log("检测到默认头像")
        return False
        
    except Exception as e:
        log(f"检测头像异常: {e}")
        return False


def 设置头像(driver: "WebDriver", log_func=None) -> bool:
    """
    设置用户头像
    
    Args:
        driver: WebDriver实例
        log_func: 日志函数
    
    Returns:
        True 表示设置成功，False 表示设置失败
    """
    def log(msg):
        if log_func:
            log_func(msg)
    
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        
        # 获取随机头像
        头像路径 = 获取随机头像()
        if not 头像路径:
            log("⚠ 头像目录为空，无法设置头像")
            return False
        
        log(f"使用头像: {os.path.basename(头像路径)}")
        
        # 这是一个简化的实现，实际需要根据Facebook的UI结构调整
        # 通常需要：
        # 1. 点击个人资料
        # 2. 点击编辑头像
        # 3. 上传文件
        # 4. 确认
        
        log("⚠ 头像设置功能需要根据实际页面结构实现")
        return False
        
    except Exception as e:
        log(f"设置头像异常: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==================== 调试配置 ====================

DEBUG_BROWSER_ID = os.environ.get('DEBUG_BROWSER_ID', "7d9ecff84fef490987dcb58004fa2c82")


# ==================== 调试模式 ====================

def _调试模式():
    """调试模式入口"""
    print("=" * 60)
    print("设置头像 - 调试模式")
    print("=" * 60)
    print(f"浏览器ID: {DEBUG_BROWSER_ID}")
    print(f"头像目录: {头像目录}")
    print()
    
    # 检查头像目录
    if os.path.exists(头像目录):
        图片数量 = len([f for f in os.listdir(头像目录) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
        print(f"头像图片数量: {图片数量}")
    else:
        print("⚠ 头像目录不存在")
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
    print("开始检测头像...")
    print("-" * 60)
    
    # 先检测是否有头像
    有头像 = 检测是否有头像(driver, print)
    
    if 有头像:
        print("✓ 已有头像，无需设置")
    else:
        print("检测到默认头像，尝试设置...")
        成功 = 设置头像(driver, print)
        
        print("-" * 60)
        if 成功:
            print("✓ 头像设置成功")
        else:
            print("✗ 头像设置失败")
    
    print("-" * 60)
    print()
    print("调试完成，浏览器保持打开状态")


# ==================== 入口 ====================

if __name__ == "__main__":
    _调试模式()
