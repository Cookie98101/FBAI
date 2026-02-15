"""
采集小组链接
从 Facebook 的"我的小组"页面采集已加入的小组链接

流程：
1. 进入"我的小组"页面
2. 滚动加载所有小组
3. 提取小组链接
4. 保存到配置文件

使用方法：
- 调试模式：修改 DEBUG_BROWSER_ID，直接运行此文件
"""

import os
import sys
import time
import random
import json
from typing import TYPE_CHECKING, List, Set

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

# 路径设置（供保存配置使用）
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(os.path.dirname(scripts_dir))
for path in [current_dir, scripts_dir, project_root]:
    if path not in sys.path:
        sys.path.insert(0, path)

# ==================== 调试配置 ====================

DEBUG_BROWSER_ID = "dd6c77a66dc74aea8c449207d55a3a87"
# 优先使用调试面板传入的浏览器ID（facebook_dashboard.py 会设置环境变量 DEBUG_BROWSER_ID）
DEBUG_BROWSER_ID = os.environ.get("DEBUG_BROWSER_ID") or DEBUG_BROWSER_ID

# 我的小组页面 URL
我的小组URL = "https://www.facebook.com/groups/feed/"

# ==================== 采集小组链接 ====================

def 采集小组链接(driver: "WebDriver", log_func=None, debug=False) -> List[str]:
    """
    采集已加入的小组链接
    
    Args:
        driver: WebDriver实例
        log_func: 日志函数
        debug: 是否开启调试模式
    
    Returns:
        小组链接列表
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        log("=" * 60)
        log("开始采集小组链接")
        log("=" * 60)
        
        # 1. 进入"我的小组"页面
        log("\n步骤1: 进入我的小组页面")
        log("-" * 60)
        
        driver.get(我的小组URL)
        
        # 等待页面加载
        加载时间 = random.uniform(3, 5)
        log(f"等待页面加载 {加载时间:.1f} 秒...")
        time.sleep(加载时间)
        
        log(f"✓ 已进入: {driver.title}")
        
        # 2. 滚动加载所有小组
        log("\n步骤2: 滚动加载小组")
        log("-" * 60)
        
        已采集链接 = set()
        小组信息列表 = []  # 保存 {name: 名称, url: 链接}
        上次数量 = 0
        无变化次数 = 0
        最大滚动次数 = 20
        
        for 滚动次数 in range(最大滚动次数):
            # 查找所有小组链接
            all_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/groups/']")
            
            for link in all_links:
                try:
                    href = link.get_attribute("href") or ""
                    
                    # 过滤：只保留小组主页链接
                    if "/groups/" in href and "?" not in href:
                        # 清理链接（移除尾部斜杠）
                        href = href.rstrip("/")
                        
                        # 排除特殊链接和无效链接
                        if any(x in href for x in ["/feed", "/create", "/discover", "/search"]):
                            continue
                        
                        # 排除只有 /groups 的链接（无小组ID）
                        小组ID = href.split("/groups/")[-1]
                        if not 小组ID or 小组ID == "groups":
                            continue
                        
                        # 如果已经采集过这个链接，跳过
                        if href in 已采集链接:
                            continue
                        
                        已采集链接.add(href)
                        
                        # 提取小组名称（从链接的文本或 aria-label）
                        小组名称 = None
                        
                        # 方法1: 从链接文本获取
                        try:
                            text = link.text.strip()
                            # 清理文本：移除 "Last active" 时间信息
                            if text and len(text) > 0 and len(text) < 100:
                                # 移除 "Last active X minutes/hours ago" 等时间信息
                                if "Last active" in text:
                                    text = text.split("Last active")[0].strip()
                                
                                # 如果清理后还有内容，使用它
                                if text:
                                    小组名称 = text
                        except:
                            pass
                        
                        # 方法2: 从 aria-label 获取
                        if not 小组名称:
                            try:
                                aria_label = link.get_attribute("aria-label") or ""
                                if aria_label and len(aria_label) < 100:
                                    # 清理 aria-label
                                    if "Last active" in aria_label:
                                        aria_label = aria_label.split("Last active")[0].strip()
                                    
                                    if aria_label:
                                        小组名称 = aria_label
                            except:
                                pass
                        
                        # 方法3: 从链接中的图片 alt 获取
                        if not 小组名称:
                            try:
                                imgs = link.find_elements(By.CSS_SELECTOR, "img")
                                for img in imgs:
                                    alt = img.get_attribute("alt") or ""
                                    if alt and len(alt) < 100:
                                        # 清理 alt
                                        if "Last active" in alt:
                                            alt = alt.split("Last active")[0].strip()
                                        
                                        if alt:
                                            小组名称 = alt
                                            break
                            except:
                                pass
                        
                        # 如果还是没有名称，使用链接ID
                        if not 小组名称:
                            小组名称 = 小组ID
                        
                        小组信息列表.append({
                            'name': 小组名称,
                            'url': href
                        })
                        
                except:
                    continue
            
            当前数量 = len(小组信息列表)
            
            if debug:
                log(f"  第 {滚动次数 + 1} 次滚动，已采集 {当前数量} 个小组")
            
            # 检查是否有新增
            if 当前数量 == 上次数量:
                无变化次数 += 1
                if 无变化次数 >= 3:
                    log(f"  连续 {无变化次数} 次无新增，停止滚动")
                    break
            else:
                无变化次数 = 0
                上次数量 = 当前数量
            
            # 继续滚动
            if 滚动次数 < 最大滚动次数 - 1:
                滚动距离 = random.randint(800, 1200)
                driver.execute_script(f"window.scrollBy(0, {滚动距离})")
                time.sleep(random.uniform(1, 2))
        
        log(f"\n✓ 采集完成，共找到 {len(小组信息列表)} 个小组")
        
        # 3. 显示前几个小组
        if 小组信息列表:
            log("\n前10个小组:")
            for i, 小组 in enumerate(小组信息列表[:10], 1):
                log(f"  {i}. {小组['name'][:40]}")
        
        return 小组信息列表
        
    except Exception as e:
        log(f"\n✗ 采集小组链接失败: {e}")
        import traceback
        traceback.print_exc()
        return []

def 保存小组链接到JSON(浏览器ID: str, 小组列表: List[dict]) -> bool:
    """
    保存小组信息到 JSON 配置文件
    
    Args:
        浏览器ID: 浏览器ID
        小组列表: 小组信息列表 [{name: 名称, url: 链接}, ...]
    
    Returns:
        是否成功
    """
    try:
        json配置文件 = os.path.join(scripts_dir, "脚本配置", "小组链接.json")
        
        # 读取现有配置（如果存在）
        配置数据 = {}
        if os.path.exists(json配置文件):
            try:
                with open(json配置文件, 'r', encoding='utf-8') as f:
                    配置数据 = json.load(f)
            except:
                配置数据 = {}
        
        # 更新该浏览器的小组列表
        配置数据[浏览器ID] = 小组列表
        
        # 保存配置
        with open(json配置文件, 'w', encoding='utf-8') as f:
            json.dump(配置数据, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 已保存 {len(小组列表)} 个小组到浏览器 {浏览器ID}")
        return True
        
    except Exception as e:
        print(f"\n✗ 保存小组信息失败: {e}")
        return False

# ==================== 调试模式 ====================

def _调试模式():
    """调试模式入口"""
    print("=" * 60)
    print("采集小组链接 - 调试模式")
    print("=" * 60)
    print(f"浏览器ID: {DEBUG_BROWSER_ID}")
    print()
    
    try:
        from bitbrowser_api import BitBrowserAPI
        bit_browser = BitBrowserAPI()
    except ImportError as e:
        print(f"❌ 无法导入 bitbrowser_api: {e}")
        return
    except Exception as e:
        print(f"❌ 初始化 BitBrowserAPI 失败: {e}")
        return
    
    print("正在打开浏览器...")
    result = bit_browser.open_browser(DEBUG_BROWSER_ID)
    
    if not result.get("success"):
        print(f"❌ 打开浏览器失败: {result}")
        return
    
    data = result.get("data", {})
    debug_port = data.get("http")
    driver_path = data.get("driver")
    
    print(f"✓ 浏览器已打开: {debug_port}")
    
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
        
        print(f"✓ Selenium 连接成功: {driver.title}")
        
    except Exception as e:
        print(f"❌ Selenium 连接失败: {e}")
        return
    
    print()
    
    # 采集小组链接
    小组列表 = 采集小组链接(driver, debug=True)
    
    if 小组列表:
        # 保存到配置文件
        保存小组链接到JSON(DEBUG_BROWSER_ID, 小组列表)
        print("\n✓ 采集任务完成")
    else:
        print("\n✗ 未采集到小组链接")
    
    print()
    print("调试完成，浏览器保持打开状态")

# ==================== 入口 ====================

if __name__ == "__main__":
    _调试模式()
