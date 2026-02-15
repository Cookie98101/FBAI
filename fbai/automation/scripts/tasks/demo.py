"""
任务模板示例 (demo.py)

这是一个任务脚本模板，展示如何编写可以：
1. 直接运行调试（修改下方 DEBUG_BROWSER_ID）
2. 被 main.py 调用

使用方法：
- 调试模式：直接运行此文件 `python demo.py`
- 正式调用：在 main.py 中 `from tasks import demo任务` 然后调用

编写新任务时，复制此文件并修改：
1. 文件名改为任务名（如：视频功能.py）
2. 修改主函数名（如：def 视频功能(...)）
3. 实现具体逻辑
4. 在 __init__.py 中导出
"""

import os
import sys
import time
import random
from typing import TYPE_CHECKING, Optional
from dataclasses import dataclass

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

# ==================== 路径设置 ====================
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(os.path.dirname(scripts_dir))

for path in [current_dir, scripts_dir, project_root]:
    if path not in sys.path:
        sys.path.insert(0, path)

# ==================== 导入自动化工具 ====================

from 自动化工具 import (
    # 等待
    随机等待, 短等待, 中等待, 长等待, 思考等待, 页面加载等待,
    # 元素查找
    查找元素, 查找所有元素, 查找可见元素, 查找可点击元素, 元素存在, 等待元素消失,
    # 点击
    点击元素, 点击选择器, 双击元素,
    # 鼠标
    移动到元素, 悬停元素, 鼠标微移动, 贝塞尔移动鼠标,
    # 滚动
    向下滚动, 向上滚动, 滚动到元素, 滚动到顶部, 真人滚动, 获取滚动位置,
    # 输入
    真人输入, 快速输入, 按键,
    # 页面
    打开网址, 刷新页面, 获取当前网址, 获取页面标题, 执行JS,
    # 截图
    截图,
)

# ==================== 调试配置 ====================

# 从环境变量读取浏览器ID
DEFAULT_BROWSER_ID = "f3d96f5a97a84a6c9c7e8b1d2e3f4a5b"
DEBUG_BROWSER_ID = os.environ.get('DEBUG_BROWSER_ID', DEFAULT_BROWSER_ID)

# ==================== 任务配置 ====================

@dataclass
class Demo配置:
    """任务配置（可选）"""
    执行时长秒: int = 60        # 执行时长
    某个数量: int = 5           # 某个参数

# ==================== 主任务函数 ====================

def demo任务(driver: "WebDriver", log_func=None, 配置: Demo配置 = None) -> bool:
    """
    Demo任务主函数
    
    这是被 main.py 调用的入口函数
    
    Args:
        driver: Selenium WebDriver（已连接的浏览器）
        log_func: 日志函数（可选）
        配置: 任务配置（可选）
    
    Returns:
        是否成功
    """
    # 日志函数
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(f"[Demo] {msg}")
    
    # 默认配置
    if 配置 is None:
        配置 = Demo配置()
    
    log("开始执行Demo任务...")
    开始时间 = time.time()
    
    try:
        # ========== 示例：获取页面信息 ==========
        当前网址 = 获取当前网址(driver)
        页面标题 = 获取页面标题(driver)
        log(f"当前页面: {页面标题}")
        log(f"网址: {当前网址}")
        
        # ========== 示例：滚动浏览 ==========
        log("开始滚动浏览...")
        for i in range(3):
            真人滚动(driver)
            随机等待(1, 3)
            
            已用时间 = time.time() - 开始时间
            log(f"已执行 {int(已用时间)} 秒...")
            
            # 检查时间限制
            if 已用时间 >= 配置.执行时长秒:
                break
        
        # ========== 示例：查找元素 ==========
        # 查找页面上的链接
        链接列表 = 查找所有元素(driver, "a[href]")
        log(f"找到 {len(链接列表)} 个链接")
        
        # ========== 示例：悬停元素 ==========
        if 链接列表:
            随机链接 = random.choice(链接列表[:10])  # 取前10个中的随机一个
            悬停元素(driver, 随机链接, 停留秒=1.5)
            log("悬停在随机链接上")
        
        # ========== 示例：点击元素 ==========
        # 某个按钮 = 查找可点击元素(driver, "button.some-class", 超时秒=3)
        # if 某个按钮:
        #     点击元素(driver, 某个按钮)
        #     log("点击了按钮")
        
        # ========== 示例：输入文本 ==========
        # 输入框 = 查找元素(driver, "input[type='text']")
        # if 输入框:
        #     真人输入(driver, 输入框, "Hello World")
        #     log("输入了文本")
        
        总用时 = time.time() - 开始时间
        log(f"✓ Demo任务完成，用时 {int(总用时)} 秒")
        return True
        
    except Exception as e:
        log(f"✗ Demo任务异常: {e}")
        return False

# ==================== 调试模式 ====================

def _调试模式():
    """
    调试模式入口
    直接运行此文件时执行
    """
    # 处理Windows控制台编码问题（仅在有buffer属性时才包装）
    import sys
    import io
    if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
        # 设置stdout为UTF-8编码
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    # 在函数执行时读取浏览器ID，而不是在模块导入时
    global DEFAULT_BROWSER_ID
    if get_debug_browser_id:
        _debug_browser_id = get_debug_browser_id()
        DEBUG_BROWSER_ID = _debug_browser_id if _debug_browser_id else DEFAULT_BROWSER_ID
    else:
        DEBUG_BROWSER_ID = DEFAULT_BROWSER_ID
    
    print("=" * 60)
    print("Demo任务 - 调试模式")
    print("=" * 60)
    print(f"浏览器ID: {DEBUG_BROWSER_ID}")
    print()
    
    # 导入比特浏览器API
    try:
        from bitbrowser_api import BitBrowserAPI
        bit_browser = BitBrowserAPI()
    except ImportError as e:
        print(f"❌ 无法导入 bitbrowser_api: {e}")
        print("请确保在项目根目录运行，或检查 bitbrowser_api.py 是否存在")
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
    
    # 获取 Selenium 连接信息
    data = result.get("data", {})
    debug_port = data.get("http")      # 调试端口，如 "127.0.0.1:9222"
    driver_path = data.get("driver")   # ChromeDriver 路径
    
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
        
        # 使用比特浏览器提供的 ChromeDriver
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
    print("开始执行任务...")
    print("-" * 60)
    
    # 可以修改配置进行测试
    测试配置 = Demo配置(
        执行时长秒=30,  # 调试时用较短时间
        某个数量=3
    )
    
    成功 = demo任务(driver, 配置=测试配置)
    
    print("-" * 60)
    if 成功:
        print("✓ 任务执行成功")
    else:
        print("✗ 任务执行失败")
    print("-" * 60)
    
    # 4. 调试模式下不关闭浏览器，方便查看结果
    print()
    print("调试完成，浏览器保持打开状态")
    print("如需关闭浏览器，请手动关闭或调用 bit_browser.close_browser()")

# ==================== 入口 ====================

if __name__ == "__main__":
    _调试模式()
