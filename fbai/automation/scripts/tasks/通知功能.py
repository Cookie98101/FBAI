"""
通知功能任务
模拟真人查看 Facebook 通知消息

流程：
1. 点击通知图标
2. 等待通知面板加载
3. 逐个查看通知（模拟阅读）
4. 随机点击部分通知查看详情
5. 关闭通知面板

使用方法：
- 调试模式：修改 DEBUG_BROWSER_ID，直接运行此文件
- 正式调用：main.py 中调用 通知功能(driver, ...)
"""

import os
import sys
import time
import random
from typing import TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

# ==================== 调试配置 ====================

# 从环境变量读取浏览器ID
DEBUG_BROWSER_ID = os.environ.get('DEBUG_BROWSER_ID', "75fcd7cda44d4c97b7dc441e46525526")

# ==================== 配置 ====================

@dataclass
class 通知功能配置:
    """通知功能任务配置"""
    查看比例最小: float = 0.5  # 最少查看50%的通知
    查看比例最大: float = 0.8  # 最多查看80%的通知
    查看详情概率: float = 0.3  # 点击查看详情的概率
    每条通知最小阅读秒: float = 2  # 每条通知最少阅读时间
    每条通知最大阅读秒: float = 5  # 每条通知最多阅读时间

# ==================== 辅助函数 ====================

def 随机延迟(最小秒: float = 1, 最大秒: float = 3):
    """随机延迟，模拟真人操作"""
    time.sleep(random.uniform(最小秒, 最大秒))

def 平滑滚动(driver: "WebDriver", 滚动量: int = 300):
    """平滑滚动，模拟真人"""
    driver.execute_script(f"window.scrollBy({{top: {滚动量}, behavior: 'smooth'}});")
    随机延迟(0.5, 1.5)

def 人性化点击(driver: "WebDriver", 元素):
    """模拟真人点击，带鼠标移动"""
    from selenium.webdriver.common.action_chains import ActionChains
    
    try:
        actions = ActionChains(driver)
        # 移动到元素
        actions.move_to_element(元素).perform()
        随机延迟(0.3, 0.8)
        # 点击
        actions.click(元素).perform()
        return True
    except Exception as e:
        print(f"  人性化点击失败: {e}")
        # 备用方案：直接点击
        try:
            元素.click()
            return True
        except:
            return False

# ==================== 核心功能 ====================

def 点击通知图标(driver: "WebDriver", log_func=None, debug=False) -> bool:
    """点击通知图标"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        log("  查找通知图标...")
        
        # 多种选择器策略
        选择器列表 = [
            # 通过 aria-label（包含未读数量的情况）
            "//div[starts-with(@aria-label, 'Notifications') and @role='button']",
            # 通过 SVG 路径（通知铃铛图标）
            "//svg[contains(@class, 'x14rh7hd')]//path[contains(@d, 'M3 9.5a9 9 0 1 1 18 0v2.927')]/../..",
            # 通过父元素（包含未读数量）
            "//div[contains(@class, 'x1i10hfl') and starts-with(@aria-label, 'Notifications')]",
            # 备用：直接通过 SVG 图标的父元素
            "//div[@role='button' and .//svg//path[contains(@d, 'M3 9.5a9 9 0 1 1 18 0v2.927')]]",
        ]
        
        通知图标 = None
        for 选择器 in 选择器列表:
            try:
                通知图标 = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, 选择器))
                )
                if 通知图标:
                    log(f"    ✓ 找到通知图标")
                    break
            except TimeoutException:
                continue
        
        if not 通知图标:
            log("  ✗ 未找到通知图标")
            return False
        
        # 滚动到元素可见
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 通知图标)
        随机延迟(0.5, 1)
        
        # 模拟真人点击
        log("  点击通知图标...")
        if 人性化点击(driver, 通知图标):
            log("    ✓ 成功点击")
            随机延迟(1, 2)
            return True
        else:
            log("  ✗ 点击失败")
            return False
            
    except Exception as e:
        log(f"  ✗ 点击通知图标异常: {e}")
        return False

def 阅读通知列表(driver: "WebDriver", 配置: 通知功能配置, log_func=None, debug=False) -> bool:
    """阅读通知列表"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.common.exceptions import TimeoutException
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        log(f"  等待通知面板加载...")
        随机延迟(2, 3)  # 增加等待时间，模拟真人反应
        
        # 等待通知面板加载（增加等待时间）
        try:
            通知面板 = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.XPATH, "//div[@role='dialog' or @role='menu']"))
            )
            log("    ✓ 通知面板已加载")
        except TimeoutException:
            log("  ⚠ 通知面板加载超时")
            return False
        
        # 重要：等待通知内容加载完成
        log("  等待通知内容加载...")
        随机延迟(2, 3)
        
        # 模拟真人：先看一眼整体
        log("  浏览通知面板...")
        随机延迟(1, 2)
        
        # 调试：打印页面源码的一部分
        if debug:
            try:
                log("  [调试] 检查页面结构...")
                # 查找所有可能的通知相关元素
                all_roles = driver.find_elements(By.XPATH, "//*[@role]")
                role_counts = {}
                for elem in all_roles:
                    try:
                        if elem.is_displayed():
                            role = elem.get_attribute("role")
                            role_counts[role] = role_counts.get(role, 0) + 1
                    except:
                        pass
                log(f"  [调试] 页面中的 role 属性统计: {role_counts}")
            except Exception as e:
                log(f"  [调试] 检查页面结构失败: {e}")
        
        # 查找通知项（使用更准确的选择器）
        通知选择器列表 = [
            # 方法1: 查找通知面板内的所有链接（排除"See all"）
            "//div[@role='dialog']//a[@role='link' and not(contains(text(), 'See all')) and not(contains(text(), 'See All'))]",
            # 方法2: 查找包含通知内容的 div（通常有特定的 class）
            "//div[@role='dialog']//div[contains(@class, 'x1n2onr6')]//a[@role='link']",
            # 方法3: 查找 article 元素（通知通常是 article）
            "//div[@role='dialog']//article",
            "//div[@role='dialog']//div[@role='article']",
            # 方法4: 查找包含头像的通知项
            "//div[@role='dialog']//img[@alt]/ancestor::a[@role='link']",
            # 方法5: 通过 listitem
            "//div[@role='dialog']//div[@role='listitem']",
            # 方法6: 查找所有可点击的通知容器
            "//div[@role='dialog']//div[contains(@class, 'x1yztbdb')]",
            # 方法7: 更宽泛 - 通知面板内的所有链接
            "//div[@role='dialog']//a[@role='link']",
        ]
        
        通知列表 = []
        使用的选择器 = ""
        for i, 选择器 in enumerate(通知选择器列表, 1):
            try:
                log(f"    尝试选择器 {i}/{len(通知选择器列表)}: {选择器[:60]}...")
                候选列表 = driver.find_elements(By.XPATH, 选择器)
                log(f"      找到 {len(候选列表)} 个元素")
                
                # 过滤掉不可见的元素和"See all"链接
                可见通知 = []
                for n in 候选列表:
                    try:
                        if n.is_displayed():
                            # 排除"See all"和其他导航链接
                            文本 = n.text.strip().lower()
                            if 'see all' not in 文本 and 'see more' not in 文本 and len(文本) > 5:
                                可见通知.append(n)
                    except:
                        pass
                
                log(f"      其中可见且有效: {len(可见通知)} 个")
                
                if 可见通知 and len(可见通知) > 1:  # 至少要有2条通知才算成功
                    通知列表 = 可见通知
                    使用的选择器 = 选择器
                    log(f"    ✓ 成功！找到 {len(通知列表)} 条通知")
                    break
            except Exception as e:
                log(f"      异常: {e}")
                continue
        
        if not 通知列表:
            log("  ✗ 未找到通知项")
            log("  尝试截图调试...")
            try:
                # 保存截图用于调试
                screenshot_path = os.path.join(current_dir, "debug_notifications.png")
                driver.save_screenshot(screenshot_path)
                log(f"  截图已保存: {screenshot_path}")
                
                # 保存页面源码
                html_path = os.path.join(current_dir, "debug_notifications.html")
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                log(f"  页面源码已保存: {html_path}")
            except Exception as e:
                log(f"  保存调试信息失败: {e}")
            return False
        
        # 打印前3条通知的信息用于调试
        if debug:
            log(f"\n  前3条通知信息:")
            for i, 通知 in enumerate(通知列表[:3], 1):
                try:
                    文本 = 通知.text.strip()[:50] if 通知.text else "(无文本)"
                    log(f"    {i}. {文本}...")
                except:
                    log(f"    {i}. (无法获取文本)")
            log("")
        
        # 计算要查看的数量（50%-80%）
        总数量 = len(通知列表)
        查看比例 = random.uniform(配置.查看比例最小, 配置.查看比例最大)
        要查看数量 = max(1, int(总数量 * 查看比例))
        
        log(f"  计划查看 {要查看数量}/{总数量} 条通知 ({查看比例*100:.0f}%)")
        log(f"  每条通知阅读时间: {配置.每条通知最小阅读秒:.1f}-{配置.每条通知最大阅读秒:.1f}秒")
        
        # 限制阅读数量
        要阅读的通知 = 通知列表[:要查看数量]
        
        # 模拟真人：开始前先整体浏览一下（滚动查看）
        if len(通知列表) > 3:
            log("  先整体浏览通知列表...")
            try:
                # 慢速滚动查看
                for _ in range(2):
                    平滑滚动(driver, random.randint(100, 200))
                    随机延迟(0.8, 1.5)
                # 滚回顶部
                driver.execute_script("arguments[0].scrollIntoView({block: 'start', behavior: 'smooth'});", 通知列表[0])
                随机延迟(1, 2)
            except:
                pass
        
        # 逐个查看通知
        已查看数量 = 0
        for i, 通知 in enumerate(要阅读的通知, 1):
            try:
                log(f"\n  查看第 {i}/{len(要阅读的通知)} 条通知...")
                
                # 滚动到通知可见（慢速滚动）
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", 通知)
                随机延迟(0.8, 1.5)
                
                # 鼠标悬停，模拟阅读
                actions = ActionChains(driver)
                actions.move_to_element(通知).perform()
                
                # 模拟真人：先快速扫一眼
                随机延迟(0.5, 1)
                
                # 随机停留时间，模拟仔细阅读
                阅读时间 = random.uniform(配置.每条通知最小阅读秒, 配置.每条通知最大阅读秒)
                log(f"    阅读中... ({阅读时间:.1f}秒)")
                time.sleep(阅读时间)
                
                # 模拟真人：偶尔会稍微移动鼠标（10%概率）
                if random.random() < 0.1:
                    try:
                        # 在通知区域内随机移动鼠标
                        offset_x = random.randint(-20, 20)
                        offset_y = random.randint(-10, 10)
                        actions.move_to_element_with_offset(通知, offset_x, offset_y).perform()
                        随机延迟(0.3, 0.6)
                    except:
                        pass
                
                已查看数量 += 1
                
                # 随机决定是否点击查看详情
                if random.random() < 配置.查看详情概率:
                    log(f"    点击查看详情...")
                    
                    # 模拟真人：点击前犹豫一下
                    随机延迟(0.5, 1)
                    
                    if 人性化点击(driver, 通知):
                        log(f"      ✓ 已打开详情")
                        
                        # 查看详情页面（更长时间）
                        查看详情时间 = random.uniform(3, 6)
                        log(f"      查看详情 {查看详情时间:.1f}秒...")
                        time.sleep(查看详情时间)
                        
                        # 模拟真人：可能会滚动一下详情页
                        if random.random() < 0.5:
                            平滑滚动(driver, random.randint(100, 300))
                            随机延迟(1, 2)
                        
                        # 返回首页（不是返回通知列表）
                        log(f"      ← 返回首页")
                        driver.get('https://www.facebook.com')
                        随机延迟(2, 3)
                        
                        # 如果还有更多通知要查看，重新打开通知面板
                        if i < len(要阅读的通知):
                            log(f"      重新打开通知面板...")
                            if not 点击通知图标(driver, log_func, debug=False):
                                log(f"      ✗ 无法重新打开通知面板，停止查看")
                                break
                            
                            # 等待面板加载
                            随机延迟(2, 3)
                            
                            # 重新获取通知列表
                            try:
                                log(f"      重新获取通知列表...")
                                新通知列表 = driver.find_elements(By.XPATH, 使用的选择器)
                                可见新通知 = []
                                for n in 新通知列表:
                                    try:
                                        if n.is_displayed():
                                            文本 = n.text.strip().lower()
                                            if 'see all' not in 文本 and 'see more' not in 文本 and len(文本) > 5:
                                                可见新通知.append(n)
                                    except:
                                        pass
                                
                                if 可见新通知:
                                    # 更新通知列表（跳过已查看的）
                                    要阅读的通知 = 可见新通知[已查看数量:]
                                    log(f"      ✓ 找到 {len(可见新通知)} 条通知，继续查看剩余 {len(要阅读的通知)} 条")
                                    
                                    # 重置索引，因为列表已更新
                                    continue
                                else:
                                    log(f"      ⚠ 未找到通知，停止查看")
                                    break
                            except Exception as e:
                                log(f"      ⚠ 重新获取通知列表失败: {e}")
                                break
                else:
                    # 没有点击查看详情，继续查看下一条
                    # 模拟真人：查看完一条后，稍微停顿
                    if i < len(要阅读的通知):
                        停顿时间 = random.uniform(0.5, 1.5)
                        log(f"    停顿 {停顿时间:.1f}秒...")
                        time.sleep(停顿时间)
                
            except Exception as e:
                log(f"  ⚠ 处理第 {i} 条通知时出错: {e}")
                # 如果出错，尝试重新打开通知面板
                if i < len(要阅读的通知):
                    try:
                        log(f"  尝试恢复...")
                        driver.get('https://www.facebook.com')
                        随机延迟(2, 3)
                        if 点击通知图标(driver, log_func, debug=False):
                            随机延迟(2, 3)
                            log(f"  ✓ 已恢复，继续查看")
                        else:
                            log(f"  ✗ 无法恢复，停止查看")
                            break
                    except:
                        break
                continue
        
        log(f"\n  ✓ 完成阅读 {已查看数量} 条通知")
        
        # 模拟真人：看完后，可能会再浏览一下整体（30%概率）
        if random.random() < 0.3:
            log("  再浏览一下...")
            随机延迟(1, 2)
            # 随机滚动
            if random.random() < 0.5:
                平滑滚动(driver, random.randint(-200, 200))
                随机延迟(0.5, 1)
        
        return True
        
    except Exception as e:
        log(f"  ✗ 阅读通知异常: {e}")
        return False

def 关闭通知面板(driver: "WebDriver", log_func=None, debug=False) -> bool:
    """关闭通知面板"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        log("  准备关闭通知面板...")
        
        # 模拟真人：关闭前稍微停顿
        随机延迟(1, 2)
        
        # 尝试多种关闭方式
        # 1. 按 ESC 键（最自然的方式）
        try:
            log("    按 ESC 键...")
            actions = ActionChains(driver)
            actions.send_keys(Keys.ESCAPE).perform()
            log("    ✓ 通过 ESC 键关闭")
            随机延迟(0.8, 1.5)
            return True
        except:
            pass
        
        # 2. 点击关闭按钮
        try:
            关闭按钮 = driver.find_element(By.XPATH, "//div[@aria-label='Close' or @aria-label='关闭']")
            log("    点击关闭按钮...")
            人性化点击(driver, 关闭按钮)
            log("    ✓ 通过关闭按钮关闭")
            随机延迟(0.8, 1.5)
            return True
        except:
            pass
        
        # 3. 点击页面其他区域
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            actions = ActionChains(driver)
            # 点击左上角区域（远离通知面板）
            actions.move_to_element_with_offset(body, 100, 100).click().perform()
            log("    ✓ 通过点击外部区域关闭")
            随机延迟(0.8, 1.5)
            return True
        except:
            pass
        
        log("  ⚠ 无法关闭通知面板（可能已自动关闭）")
        return False
        
    except Exception as e:
        log(f"  ⚠ 关闭通知面板异常: {e}")
        return False

# ==================== 主函数 ====================

def 通知功能(driver: "WebDriver", 浏览器ID: str = None, log_func=None, 配置: 通知功能配置 = None) -> bool:
    """
    执行通知功能任务
    
    流程：
    1. 点击通知图标
    2. 阅读通知列表
    3. 关闭通知面板
    
    Args:
        driver: WebDriver实例
        浏览器ID: 浏览器ID（可选）
        log_func: 日志函数
        配置: 通知功能配置
    
    Returns:
        是否成功
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    if 配置 is None:
        配置 = 通知功能配置()
    
    log("=" * 60)
    log("开始通知功能任务")
    log("=" * 60)
    log(f"查看比例: {配置.查看比例最小*100:.0f}%-{配置.查看比例最大*100:.0f}%")
    log(f"每条通知阅读时间: {配置.每条通知最小阅读秒:.1f}-{配置.每条通知最大阅读秒:.1f}秒")
    log(f"查看详情概率: {配置.查看详情概率 * 100:.0f}%")
    
    try:
        # 确保在 Facebook 页面
        当前网址 = driver.current_url
        if 'facebook.com' not in 当前网址:
            log("\n⚠ 当前不在 Facebook 页面，正在跳转...")
            driver.get('https://www.facebook.com')
            随机延迟(2, 4)
        
        # 步骤1: 点击通知图标
        log("\n步骤1: 点击通知图标")
        log("-" * 60)
        
        # 模拟真人：点击前先看一眼
        随机延迟(0.5, 1)
        
        if not 点击通知图标(driver, log_func, debug=True):
            log("✗ 无法打开通知面板")
            return False
        
        # 步骤2: 阅读通知
        log("\n步骤2: 阅读通知")
        log("-" * 60)
        
        if not 阅读通知列表(driver, 配置, log_func, debug=True):
            log("⚠ 阅读通知失败")
        
        # 步骤3: 关闭通知面板
        log("\n步骤3: 关闭通知面板")
        log("-" * 60)
        
        关闭通知面板(driver, log_func, debug=True)
        
        # 模拟真人：关闭后稍微停留，不是立即离开
        随机延迟(1, 2)
        
        log("\n" + "=" * 60)
        log("✓ 通知功能任务完成")
        log("=" * 60)
        return True
        
    except Exception as e:
        log(f"\n✗ 通知功能任务异常: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==================== 调试模式 ====================

def _调试模式():
    """调试模式入口"""
    print("=" * 60)
    print("通知功能 - 调试模式")
    print("=" * 60)
    print(f"浏览器ID: {DEBUG_BROWSER_ID}")
    print()
    
    # 设置路径（调试模式需要）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    
    paths_to_add = [project_root]
    
    print("[路径设置]")
    for path in paths_to_add:
        if path not in sys.path:
            sys.path.insert(0, path)
            print(f"  已添加: {path}")
    print()
    
    try:
        from bitbrowser_api import BitBrowserAPI
        bit_browser = BitBrowserAPI()
    except ImportError as e:
        print(f"❌ 无法导入 bitbrowser_api: {e}")
        print(f"   当前路径: {sys.path[:3]}")
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
    
    测试配置 = 通知功能配置(
        查看比例最小=0.5,
        查看比例最大=0.8,
        查看详情概率=0.3,
        每条通知最小阅读秒=2,
        每条通知最大阅读秒=5
    )
    
    成功 = 通知功能(driver, 浏览器ID=DEBUG_BROWSER_ID, 配置=测试配置)
    
    print()
    if 成功:
        print("✓ 通知功能任务执行成功")
    else:
        print("✗ 通知功能任务执行失败")
    
    print()
    print("调试完成，浏览器保持打开状态")

# ==================== 入口 ====================

if __name__ == "__main__":
    _调试模式()
