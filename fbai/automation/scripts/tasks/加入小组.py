"""
加入小组任务
通过关键词搜索 Facebook 小组并加入

特性：
- 支持多个关键词搜索
- 全局去重（避免重复加入同一小组）
- 模拟真人操作
- 随机等待时间
- 数据上报

使用方法：
- 调试模式：修改 DEBUG_BROWSER_ID，直接运行此文件
- 正式调用：main.py 中调用 加入小组(driver, ...)
"""

import os
import sys
import time
import random
import re
import requests
from typing import TYPE_CHECKING, List, Optional
from dataclasses import dataclass

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.remote.webelement import WebElement

# ==================== 路径设置 ====================
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(os.path.dirname(scripts_dir))
脚本配置目录 = os.path.join(scripts_dir, "脚本配置")

for path in [current_dir, scripts_dir, project_root]:
    if path not in sys.path:
        sys.path.insert(0, path)

from tasks.去重管理 import 检查是否已操作, 记录操作

# 数据上报 API
数据上报API = "http://localhost:8805/add_data"

# ==================== 调试配置 ====================

DEBUG_BROWSER_ID = "dd6c77a66dc74aea8c449207d55a3a87"
# 优先使用调试面板传入的浏览器ID（facebook_dashboard.py 会设置环境变量 DEBUG_BROWSER_ID）
DEBUG_BROWSER_ID = os.environ.get("DEBUG_BROWSER_ID") or DEBUG_BROWSER_ID

# ==================== 配置 ====================

@dataclass
class 加入小组配置:
    """加入小组任务配置"""
    关键词列表: List[str] = None  # 搜索关键词列表
    每个关键词加入数量: int = 3  # 每个关键词加入多少个小组
    总加入数量限制: int = 10  # 总共加入多少个小组

# ==================== 关键词读取 ====================

def 读取小组关键词() -> List[str]:
    """从小组关键词.txt读取关键词列表"""
    关键词文件 = os.path.join(脚本配置目录, "小组关键词.txt")
    
    if not os.path.exists(关键词文件):
        # 如果文件不存在，创建示例文件
        try:
            with open(关键词文件, 'w', encoding='utf-8') as f:
                f.write("# Facebook 小组搜索关键词\n")
                f.write("# 每行一个关键词\n")
                f.write("# 以 # 开头的行为注释\n\n")
                f.write("motorcycle\n")
                f.write("bike\n")
                f.write("cycling\n")
        except:
            pass
        return []
    
    try:
        with open(关键词文件, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        关键词列表 = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                关键词列表.append(line)
        
        return 关键词列表
    except Exception:
        return []

# ==================== 小组ID提取 ====================

def 提取小组ID(链接或元素) -> Optional[str]:
    """
    从链接或元素中提取 Facebook 小组ID
    
    支持的格式：
    - /groups/数字
    - /groups/字符串
    - groups_id=数字
    
    Args:
        链接或元素: URL字符串或 WebElement
    
    Returns:
        小组ID，如果提取失败返回 None
    """
    try:
        # 如果是 WebElement，获取 href
        if hasattr(链接或元素, 'get_attribute'):
            链接 = 链接或元素.get_attribute('href') or ""
        else:
            链接 = str(链接或元素)
        
        if not 链接:
            return None
        
        # 方法1: 提取 /groups/数字或字符串
        match = re.search(r'/groups/([^/?&#]+)', 链接)
        if match:
            return match.group(1)
        
        # 方法2: 提取 groups_id=数字
        match = re.search(r'groups_id=(\d+)', 链接)
        if match:
            return match.group(1)
        
        return None
        
    except:
        return None

# ==================== 搜索小组 ====================

def 搜索小组(driver: "WebDriver", 关键词: str, log_func=None, debug=False) -> bool:
    """
    在 Facebook 中搜索小组（模拟真人操作）
    
    流程：
    1. 点击搜索框
    2. 输入关键词
    3. 按回车搜索
    4. 点击"Groups"标签
    
    Args:
        driver: WebDriver实例
        关键词: 搜索关键词
        log_func: 日志函数
        debug: 是否开启调试模式
    
    Returns:
        是否成功
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        log(f"搜索小组关键词: {关键词}")
        
        # 1. 查找搜索框
        搜索框选择器列表 = [
            "input[placeholder*='Search' i]",
            "input[aria-label*='Search' i]",
            "input[type='search']",
            "[role='search'] input",
        ]
        
        搜索框 = None
        for 选择器 in 搜索框选择器列表:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, 选择器)
                for el in elements:
                    if el.is_displayed():
                        搜索框 = el
                        break
                if 搜索框:
                    break
            except:
                continue
        
        if not 搜索框:
            if debug:
                log("未找到搜索框，尝试点击搜索按钮...")
            
            # 尝试点击搜索按钮
            try:
                search_buttons = driver.find_elements(By.CSS_SELECTOR, "[aria-label*='Search' i]")
                for btn in search_buttons:
                    if btn.is_displayed() and btn.tag_name in ['div', 'button', 'a']:
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(random.uniform(1, 2))
                        
                        # 再次查找搜索框
                        for 选择器 in 搜索框选择器列表:
                            elements = driver.find_elements(By.CSS_SELECTOR, 选择器)
                            for el in elements:
                                if el.is_displayed():
                                    搜索框 = el
                                    break
                            if 搜索框:
                                break
                        if 搜索框:
                            break
            except:
                pass
        
        if not 搜索框:
            log("找不到搜索框，使用直接URL方式")
            # 降级：直接访问搜索URL
            搜索URL = f"https://www.facebook.com/search/groups/?q={关键词}"
            driver.get(搜索URL)
            time.sleep(random.uniform(3, 5))
            log("已进入小组搜索页面（URL方式）")
            return True
        
        # 2. 点击搜索框
        if debug:
            log("点击搜索框...")
        
        try:
            driver.execute_script("arguments[0].click();", 搜索框)
        except:
            搜索框.click()
        
        time.sleep(random.uniform(0.5, 1))
        
        # 3. 清空搜索框（模拟真人操作）
        if debug:
            log("清空搜索框...")
        
        try:
            # 方法1: 全选后删除
            搜索框.click()
            time.sleep(0.2)
            
            # 使用 Ctrl+A 全选
            from selenium.webdriver.common.keys import Keys
            搜索框.send_keys(Keys.CONTROL + "a")
            time.sleep(0.1)
            
            # 删除
            搜索框.send_keys(Keys.BACKSPACE)
            time.sleep(0.2)
        except:
            # 方法2: 使用 clear()
            try:
                搜索框.clear()
                time.sleep(0.2)
            except:
                pass
        
        time.sleep(random.uniform(0.3, 0.5))
        
        # 4. 逐字输入关键词（模拟真人）
        if debug:
            log(f"输入关键词: {关键词}")
        
        for char in 关键词:
            搜索框.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        time.sleep(random.uniform(0.5, 1))
        
        # 5. 按回车搜索
        if debug:
            log("按回车搜索...")
        
        搜索框.send_keys(Keys.RETURN)
        time.sleep(random.uniform(3, 5))
        
        # 6. 点击"Groups"标签
        if debug:
            log("查找并点击 Groups 标签...")
        
        groups_tab_selectors = [
            "a[href*='/search/groups']",
            "[role='tab']:has-text('Groups')",
            "[role='tab']:has-text('小组')",
            "a:has-text('Groups')",
            "a:has-text('小组')",
        ]
        
        groups_tab = None
        for selector in groups_tab_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        text = el.text.strip().lower()
                        if 'group' in text or '小组' in text:
                            groups_tab = el
                            break
                if groups_tab:
                    break
            except:
                continue
        
        # 如果没找到标签，尝试通过文本查找
        if not groups_tab:
            all_links = driver.find_elements(By.CSS_SELECTOR, "a")
            for link in all_links:
                try:
                    if link.is_displayed():
                        text = link.text.strip().lower()
                        href = link.get_attribute("href") or ""
                        if ('group' in text or '小组' in text) and '/search/groups' in href:
                            groups_tab = link
                            break
                except:
                    continue
        
        if groups_tab:
            if debug:
                log("点击 Groups 标签...")
            
            try:
                driver.execute_script("arguments[0].click();", groups_tab)
            except:
                groups_tab.click()
            
            time.sleep(random.uniform(2, 3))
            log("已进入小组搜索结果页面")
        else:
            if debug:
                log("未找到 Groups 标签，可能已在小组搜索页面")
            log("已进入搜索结果页面")
        
        return True
        
    except Exception as e:
        log(f"搜索失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

# ==================== 加入小组 ====================

def 加入单个小组(driver: "WebDriver", log_func=None, debug=False) -> bool:
    """
    加入当前页面上的一个小组
    
    Args:
        driver: WebDriver实例
        log_func: 日志函数
        debug: 是否开启调试模式
    
    Returns:
        是否成功加入
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        # 1. 查找所有小组链接
        group_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/groups/']")
        
        if debug:
            log(f"找到 {len(group_links)} 个小组链接")
        
        # 过滤出有效的小组链接
        有效小组 = []
        for link in group_links:
            try:
                href = link.get_attribute("href") or ""
                if "/groups/" in href and link.is_displayed():
                    小组ID = 提取小组ID(href)
                    if 小组ID:
                        # 检查是否已加入过
                        if 检查是否已操作(小组ID, "join_group"):
                            if debug:
                                log(f"  小组 {小组ID} 已加入过，跳过")
                            continue
                        
                        有效小组.append({
                            'link': link,
                            'href': href,
                            'id': 小组ID
                        })
            except:
                continue
        
        if debug:
            log(f"有效小组（未加入过）: {len(有效小组)} 个")
        
        if not 有效小组:
            log("未找到可加入的小组")
            return False
        
        # 2. 随机选择一个小组
        小组信息 = random.choice(有效小组)
        小组ID = 小组信息['id']
        小组链接 = 小组信息['href']
        
        if debug:
            log(f"\n选择小组: {小组ID}")
            log(f"链接: {小组链接[:80]}...")
        
        # 模拟真人：浏览小组列表，思考一下
        思考时间 = random.uniform(2, 5)
        if debug:
            log(f"浏览小组列表，思考 {思考时间:.1f} 秒...")
        time.sleep(思考时间)
        
        # 3. 点击进入小组页面
        try:
            driver.execute_script("arguments[0].click();", 小组信息['link'])
        except:
            小组信息['link'].click()
        
        # 模拟真人：等待页面加载，查看小组信息
        加载等待 = random.uniform(3, 6)
        if debug:
            log(f"页面加载中，查看小组信息 {加载等待:.1f} 秒...")
        time.sleep(加载等待)
        
        # 4. 查找"加入"按钮
        加入按钮选择器列表 = [
            "[aria-label='Join']",
            "[aria-label='Join group']",
            "[aria-label='加入']",
            "[aria-label='加入小组']",
            "div[role='button']:has-text('Join')",
            "div[role='button']:has-text('加入')",
        ]
        
        加入按钮 = None
        for 选择器 in 加入按钮选择器列表:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, 选择器)
                for btn in buttons:
                    if btn.is_displayed():
                        btn_text = btn.text.strip().lower()
                        if 'join' in btn_text or '加入' in btn_text:
                            加入按钮 = btn
                            break
                if 加入按钮:
                    break
            except:
                continue
        
        if not 加入按钮:
            # 尝试通过文本查找
            all_buttons = driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
            for btn in all_buttons:
                try:
                    if btn.is_displayed():
                        text = btn.text.strip().lower()
                        if text in ['join', 'join group', '加入', '加入小组']:
                            加入按钮 = btn
                            break
                except:
                    continue
        
        if not 加入按钮:
            log("未找到加入按钮（可能已是成员）")
            # 记录为已操作，避免重复尝试
            记录操作(小组ID, "join_group")
            # 返回搜索页面
            if debug:
                log("返回搜索结果页面...")
            driver.back()
            time.sleep(random.uniform(1, 2))
            return False
        
        # 5. 点击加入按钮
        if debug:
            log("找到加入按钮，准备加入...")
        
        # 模拟真人：考虑一下是否加入
        考虑时间 = random.uniform(1, 3)
        if debug:
            log(f"考虑是否加入 {考虑时间:.1f} 秒...")
        time.sleep(考虑时间)
        
        if debug:
            log("点击加入按钮...")
        
        try:
            driver.execute_script("arguments[0].click();", 加入按钮)
        except:
            加入按钮.click()
        
        # 模拟真人：等待加入处理
        处理等待 = random.uniform(2, 4)
        if debug:
            log(f"等待加入处理 {处理等待:.1f} 秒...")
        time.sleep(处理等待)
        
        # 6. 处理可能的确认弹窗或问题
        # 有些小组需要回答问题，这里先跳过
        try:
            # 查找"Skip"或"跳过"按钮
            skip_buttons = driver.find_elements(By.CSS_SELECTOR, "[aria-label*='Skip'], [aria-label*='跳过']")
            for btn in skip_buttons:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
                    break
        except:
            pass
        
        log(f"✓ 已加入小组: {小组ID}")
        
        # 7. 记录操作
        记录操作(小组ID, "join_group")
        
        # 8. 上报数据
        try:
            requests.get(f"{数据上报API}?groups=1", timeout=5)
            if debug:
                log("  已上报数据")
        except Exception as e:
            if debug:
                log(f"  上报数据失败: {e}")
        
        # 9. 模拟真人：加入后查看一下小组
        查看时间 = random.uniform(2, 5)
        if debug:
            log(f"加入成功，查看小组 {查看时间:.1f} 秒...")
        time.sleep(查看时间)
        
        # 10. 返回上一页（返回搜索结果）
        if debug:
            log("返回搜索结果页面...")
        driver.back()
        
        # 模拟真人：等待页面加载
        返回等待 = random.uniform(2, 4)
        if debug:
            log(f"页面加载中 {返回等待:.1f} 秒...")
        time.sleep(返回等待)
        
        return True
        
    except Exception as e:
        log(f"加入小组失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        
        # 尝试返回搜索页面
        try:
            driver.back()
            time.sleep(1)
        except:
            pass
        
        return False

# ==================== 主函数 ====================

def 加入小组(driver: "WebDriver", log_func=None, 配置: 加入小组配置 = None) -> bool:
    """
    执行加入小组任务
    
    Args:
        driver: WebDriver实例
        log_func: 日志函数
        配置: 加入小组配置
    
    Returns:
        是否成功
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    if 配置 is None:
        配置 = 加入小组配置()
    
    # 读取关键词
    if 配置.关键词列表 is None:
        配置.关键词列表 = 读取小组关键词()
    
    if not 配置.关键词列表:
        log("没有搜索关键词，请在 脚本配置/小组关键词.txt 中添加")
        return False
    
    log(f"开始加入小组任务...")
    log(f"关键词数量: {len(配置.关键词列表)}")
    log(f"每个关键词加入: {配置.每个关键词加入数量} 个")
    log(f"总加入限制: {配置.总加入数量限制} 个")
    
    已加入数量 = 0
    
    try:
        # 随机打乱关键词顺序
        关键词列表 = 配置.关键词列表.copy()
        random.shuffle(关键词列表)
        
        for 关键词 in 关键词列表:
            if 已加入数量 >= 配置.总加入数量限制:
                log(f"已达到总加入数量限制: {配置.总加入数量限制}")
                break
            
            log(f"\n处理关键词: {关键词}")
            
            # 搜索小组（模拟真人操作）
            if not 搜索小组(driver, 关键词, log, debug=False):
                continue
            
            # 模拟真人：搜索后等待页面完全加载，浏览搜索结果
            加载浏览时间 = random.uniform(5, 8)
            log(f"等待页面加载，浏览搜索结果 {加载浏览时间:.1f} 秒...")
            time.sleep(加载浏览时间)
            
            # 加入小组
            本关键词已加入 = 0
            尝试次数 = 0
            最大尝试次数 = 配置.每个关键词加入数量 * 3  # 允许失败
            
            while 本关键词已加入 < 配置.每个关键词加入数量 and 尝试次数 < 最大尝试次数:
                if 已加入数量 >= 配置.总加入数量限制:
                    break
                
                尝试次数 += 1
                
                # 尝试加入小组
                加入成功 = 加入单个小组(driver, log)
                
                if 加入成功:
                    本关键词已加入 += 1
                    已加入数量 += 1
                    log(f"进度: {已加入数量}/{配置.总加入数量限制}")
                    
                    # 模拟真人：加入成功后休息一下
                    if 本关键词已加入 < 配置.每个关键词加入数量:
                        休息时间 = random.uniform(5, 10)
                        log(f"休息 {休息时间:.1f} 秒后继续...")
                        time.sleep(休息时间)
                else:
                    # 如果加入失败，滚动页面加载更多小组
                    if debug:
                        log("滚动页面，加载更多小组...")
                    driver.execute_script("window.scrollBy(0, 800)")
                    
                    # 模拟真人：滚动后浏览一下
                    浏览时间 = random.uniform(2, 4)
                    time.sleep(浏览时间)
            
            log(f"关键词 '{关键词}' 完成，加入了 {本关键词已加入} 个小组")
            
            # 模拟真人：切换关键词前休息一下
            if 已加入数量 < 配置.总加入数量限制:
                切换休息 = random.uniform(10, 20)
                log(f"准备搜索下一个关键词，休息 {切换休息:.1f} 秒...")
                time.sleep(切换休息)
        
        log(f"\n✓ 加入小组任务完成，共加入 {已加入数量} 个小组")
        return True
        
    except Exception as e:
        log(f"✗ 加入小组任务异常: {e}")
        return False

# ==================== 调试模式 ====================

def _调试模式():
    """调试模式入口"""
    print("=" * 60)
    print("加入小组 - 调试模式")
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
    print("-" * 60)
    print("开始执行加入小组任务...")
    print("-" * 60)
    
    测试配置 = 加入小组配置(
        每个关键词加入数量=2,
        总加入数量限制=5
    )
    
    成功 = 加入小组(driver, 配置=测试配置)
    
    print("-" * 60)
    if 成功:
        print("✓ 加入小组任务执行成功")
    else:
        print("✗ 加入小组任务执行失败")
    print("-" * 60)
    
    print()
    print("调试完成，浏览器保持打开状态")

# ==================== 入口 ====================

if __name__ == "__main__":
    _调试模式()
