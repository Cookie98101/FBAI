"""
进入公共主页
通过在个人首页查找主页名称来进入，更自然地模拟真人行为

特性：
- 优先在个人首页查找主页链接（模拟真人）
- 降级使用URL直接访问
- 随机等待时间

使用方法：
- 调试模式：修改 DEBUG_BROWSER_ID，直接运行此文件
- 正式调用：from tasks.进入公共主页 import 进入公共主页
"""

import os
import sys
import time
import random
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

# ==================== 路径设置 ====================
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(os.path.dirname(scripts_dir))
脚本配置目录 = os.path.join(scripts_dir, "脚本配置")

for path in [current_dir, scripts_dir, project_root]:
    if path not in sys.path:
        sys.path.insert(0, path)

# ==================== 调试配置 ====================

DEBUG_BROWSER_ID = "dd6c77a66dc74aea8c449207d55a3a87"
# 优先使用调试面板传入的浏览器ID（facebook_dashboard.py 会设置环境变量 DEBUG_BROWSER_ID）
DEBUG_BROWSER_ID = os.environ.get("DEBUG_BROWSER_ID") or DEBUG_BROWSER_ID

# ==================== 读取配置 ====================

def 读取主页名称() -> Optional[str]:
    """从主页名称.txt读取主页名称"""
    名称文件 = os.path.join(脚本配置目录, "主页名称.txt")
    
    if not os.path.exists(名称文件):
        return None
    
    try:
        with open(名称文件, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                return line
        
        return None
    except Exception:
        return None

def 读取主页链接() -> Optional[str]:
    """从公共主页链接文件读取URL"""
    链接文件 = os.path.join(脚本配置目录, "公共主页链接")
    
    if not os.path.exists(链接文件):
        return None
    
    try:
        with open(链接文件, 'r', encoding='utf-8') as f:
            链接 = f.read().strip()
        return 链接 if 链接 else None
    except Exception:
        return None

# ==================== 主要功能 ====================

def 点击头像进入个人主页(driver: "WebDriver", log_func=None, debug=False) -> bool:
    """
    点击自己的头像进入个人主页
    
    Args:
        driver: WebDriver实例
        log_func: 日志函数
        debug: 是否开启调试模式
    
    Returns:
        是否成功进入个人主页
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        log("点击头像进入个人主页...")
        
        # 1. 先确保在首页
        当前URL = driver.current_url
        if "facebook.com" not in 当前URL:
            if debug:
                log("  不在 Facebook，先进入首页...")
            driver.get("https://www.facebook.com/")
            time.sleep(random.uniform(2, 3))
        
        # 2. 查找头像元素
        # Facebook 头像通常在顶部导航栏，可能是 circle SVG 元素或包含 profile.php 的链接
        头像元素 = None
        
        # 方法1: 查找包含 circle 的顶部链接（头像通常是圆形）
        try:
            circles = driver.find_elements(By.CSS_SELECTOR, "circle")
            if debug:
                log(f"  找到 {len(circles)} 个 circle 元素")
            
            for circle in circles:
                try:
                    if not circle.is_displayed():
                        continue
                    
                    location = circle.location
                    if location['y'] > 100:  # 不在顶部
                        continue
                    
                    # 向上查找父链接（最多5层）
                    parent = circle
                    for level in range(6):  # 增加到6层
                        try:
                            parent = parent.find_element(By.XPATH, "..")
                            
                            if parent.tag_name == 'a':
                                href = parent.get_attribute("href") or ""
                                aria_label = parent.get_attribute("aria-label") or ""
                                
                                # 检查是否是个人主页链接
                                if "profile.php" in href or "/me" in href or "timeline" in aria_label.lower():
                                    头像元素 = parent
                                    if debug:
                                        log(f"  ✓ 通过 circle 找到头像链接（第{level}层）")
                                        log(f"    href: {href[:60]}...")
                                        log(f"    aria-label: {aria_label[:60] if aria_label else '(无)'}")
                                    break
                        except:
                            break
                    
                    if 头像元素:
                        break
                except:
                    continue
        except Exception as e:
            if debug:
                log(f"  方法1异常: {e}")
        
        # 方法2: 直接查找包含 profile.php 的顶部链接
        if not 头像元素:
            try:
                all_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='profile.php']")
                if debug:
                    log(f"  找到 {len(all_links)} 个 profile.php 链接")
                
                for link in all_links:
                    try:
                        if link.is_displayed():
                            location = link.location
                            if location['y'] < 100:  # 在顶部
                                href = link.get_attribute("href") or ""
                                text = link.text.strip()
                                
                                # 优先选择有文本的（通常是用户名）
                                if text:
                                    头像元素 = link
                                    if debug:
                                        log(f"  ✓ 找到 profile.php 链接（有文本）")
                                        log(f"    text: {text}")
                                        log(f"    href: {href[:60]}...")
                                    break
                                elif not 头像元素:  # 如果还没找到，先记录这个
                                    头像元素 = link
                    except:
                        continue
                
                if 头像元素 and debug:
                    log(f"  ✓ 使用 profile.php 链接")
            except Exception as e:
                if debug:
                    log(f"  方法2异常: {e}")
        
        # 方法3: 查找 aria-label 包含 Timeline 的链接
        if not 头像元素:
            try:
                all_links = driver.find_elements(By.CSS_SELECTOR, "a[aria-label*='Timeline']")
                for link in all_links:
                    if link.is_displayed():
                        location = link.location
                        if location['y'] < 100:
                            头像元素 = link
                            if debug:
                                log(f"  ✓ 找到 Timeline 链接")
                            break
            except Exception as e:
                if debug:
                    log(f"  方法3异常: {e}")
        
        if not 头像元素:
            log("  未找到头像元素")
            return False
        
        if debug:
            log("  找到头像元素")
        
        # 模拟真人：思考一下
        思考时间 = random.uniform(0.5, 1)
        if debug:
            log(f"  思考 {思考时间:.1f} 秒...")
        time.sleep(思考时间)
        
        # 3. 点击头像
        if debug:
            log("  点击头像...")
        
        try:
            driver.execute_script("arguments[0].click();", 头像元素)
        except:
            头像元素.click()
        
        # 等待页面加载
        加载时间 = random.uniform(3, 5)
        if debug:
            log(f"  等待页面加载 {加载时间:.1f} 秒...")
        time.sleep(加载时间)
        
        log("✓ 已进入个人主页")
        return True
        
    except Exception as e:
        log(f"进入个人主页失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

def 在个人主页搜索主页帖子(driver: "WebDriver", 主页名称: str, log_func=None, debug=False) -> bool:
    """
    在个人主页中搜索包含主页名称的帖子或链接，随机选择一个进入
    
    策略：
    1. 优先查找直接指向公共主页的链接（aria-label="See Owner Profile"）
    2. 其次查找包含主页名称的帖子链接
    
    Args:
        driver: WebDriver实例
        主页名称: 要搜索的主页名称
        log_func: 日志函数
        debug: 是否开启调试模式
    
    Returns:
        是否成功找到并进入
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        log(f"在个人主页搜索: {主页名称}")
        
        # 读取目标公共主页ID（用于验证链接）
        目标主页ID = None
        try:
            主页链接 = 读取主页链接()
            if 主页链接 and "id=" in 主页链接:
                import re
                match = re.search(r'id=(\d+)', 主页链接)
                if match:
                    目标主页ID = match.group(1)
                    if debug:
                        log(f"  目标主页ID: {目标主页ID}")
        except:
            pass
        
        # 提取主页名称的关键词（用于部分匹配）
        关键词列表 = 主页名称.split()
        if debug:
            log(f"  关键词: {关键词列表}")
        
        # 1. 滚动页面，收集所有符合的链接
        符合的主页链接列表 = []  # 直接指向公共主页的链接
        符合的帖子列表 = []  # 包含主页名称的帖子
        最大滚动次数 = 10
        
        for 滚动次数 in range(最大滚动次数):
            if debug:
                log(f"  第 {滚动次数 + 1} 次滚动...")
            
            # 查找包含主页名称的文本元素
            # 只查找包含文本的元素
            text_elements = driver.find_elements(By.CSS_SELECTOR, "span, div[dir='auto'], a")
            
            for element in text_elements:
                try:
                    if not element.is_displayed():
                        continue
                    
                    text = element.text.strip()
                    
                    if not text or len(text) < 5:
                        continue
                    
                    # 检查是否包含主页名称（完整匹配）
                    匹配 = False
                    if 主页名称.lower() in text.lower():
                        匹配 = True
                    else:
                        # 部分匹配：至少包含2个关键词
                        匹配数 = 0
                        for 关键词 in 关键词列表:
                            if len(关键词) > 2 and 关键词.lower() in text.lower():
                                匹配数 += 1
                        
                        if 匹配数 >= min(2, len(关键词列表)):
                            匹配 = True
                    
                    if not 匹配:
                        continue
                    
                    # 向上查找父元素中的链接
                    parent = element
                    找到链接 = False
                    
                    for level in range(15):
                        try:
                            # 在当前层级查找链接
                            links = parent.find_elements(By.CSS_SELECTOR, "a[href]")
                            
                            for link in links:
                                href = link.get_attribute("href") or ""
                                
                                # 优先：检查是否是公共主页链接
                                if "profile.php?id=" in href:
                                    # 验证是否指向目标主页
                                    if 目标主页ID and 目标主页ID in href:
                                        已存在 = False
                                        for 已有链接 in 符合的主页链接列表:
                                            if 已有链接['href'] == href:
                                                已存在 = True
                                                break
                                        
                                        if not 已存在:
                                            符合的主页链接列表.append({
                                                'element': link,
                                                'href': href,
                                                'text': text[:50],
                                                'type': 'profile_link'
                                            })
                                            找到链接 = True
                                            if debug:
                                                log(f"    ✓ 找到目标公共主页链接: {text[:30]}...")
                                            break
                                
                                # 其次：检查是否是帖子链接
                                elif "/posts/" in href or "/photo" in href or "fbid=" in href or "/permalink/" in href or "story_fbid=" in href:
                                    已存在 = False
                                    for 已有帖子 in 符合的帖子列表:
                                        if 已有帖子['href'] == href:
                                            已存在 = True
                                            break
                                    
                                    if not 已存在:
                                        符合的帖子列表.append({
                                            'element': link,
                                            'href': href,
                                            'text': text[:50]
                                        })
                                        找到链接 = True
                                        if debug:
                                            log(f"    ✓ 找到帖子链接: {text[:30]}...")
                                        break
                            
                            if 找到链接:
                                break
                            
                            # 向上一层
                            parent = parent.find_element(By.XPATH, "..")
                        except:
                            break
                    
                except:
                    continue
            
            if debug:
                log(f"    当前找到 {len(符合的主页链接列表)} 个公共主页链接，{len(符合的帖子列表)} 个帖子")
            
            # 如果已经找到公共主页链接，优先使用
            if len(符合的主页链接列表) >= 2:
                log(f"  已找到 {len(符合的主页链接列表)} 个公共主页链接，停止滚动")
                break
            
            # 或者找到足够多的帖子
            if len(符合的帖子列表) >= 5:
                log(f"  已找到 {len(符合的帖子列表)} 个帖子，停止滚动")
                break
            
            # 继续滚动
            if 滚动次数 < 最大滚动次数 - 1:
                滚动距离 = random.randint(2500, 3500)
                driver.execute_script(f"window.scrollBy(0, {滚动距离})")
                
                # 模拟真人：滚动后浏览一下
                浏览时间 = random.uniform(0.5, 1)
                time.sleep(浏览时间)
        
        # 2. 优先使用公共主页链接
        if 符合的主页链接列表:
            log(f"✓ 找到 {len(符合的主页链接列表)} 个目标公共主页链接（优先使用）")
            
            选中的链接 = random.choice(符合的主页链接列表)
            
            log(f"随机选择公共主页链接: {选中的链接['text'][:30]}...")
            if debug:
                log(f"  类型: {选中的链接['type']}")
                log(f"  链接: {选中的链接['href'][:80]}...")
            
            # 模拟真人：选择前思考一下
            思考时间 = random.uniform(2, 4)
            if debug:
                log(f"  思考 {思考时间:.1f} 秒...")
            time.sleep(思考时间)
            
            # 点击进入
            log("点击进入公共主页...")
            
            try:
                # 记录当前标签数量
                原标签数 = len(driver.window_handles)
                
                # 滚动到元素可见
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 选中的链接['element'])
                time.sleep(random.uniform(0.5, 1))
                
                # 移除 target 属性（防止打开新标签）
                driver.execute_script("arguments[0].removeAttribute('target');", 选中的链接['element'])
                
                # 点击
                driver.execute_script("arguments[0].click();", 选中的链接['element'])
            except:
                选中的链接['element'].click()
            
            # 等待页面加载
            加载时间 = random.uniform(3, 5)
            if debug:
                log(f"  等待页面加载 {加载时间:.1f} 秒...")
            time.sleep(加载时间)
            
            # 检查是否打开了新标签
            try:
                新标签数 = len(driver.window_handles)
                if 新标签数 > 原标签数:
                    if debug:
                        log("  检测到新标签，切换到新标签...")
                    # 切换到最新的标签
                    driver.switch_to.window(driver.window_handles[-1])
            except:
                pass
            
            log(f"✓ 成功进入公共主页")
            return True
        
        # 3. 降级：使用帖子链接
        elif 符合的帖子列表:
            log(f"✓ 找到 {len(符合的帖子列表)} 个帖子")
            
            选中的帖子 = random.choice(符合的帖子列表)
            
            log(f"随机选择帖子: {选中的帖子['text']}...")
            if debug:
                log(f"  链接: {选中的帖子['href'][:80]}...")
            
            思考时间 = random.uniform(2, 4)
            if debug:
                log(f"  思考 {思考时间:.1f} 秒...")
            time.sleep(思考时间)
            
            log("点击进入帖子...")
            
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 选中的帖子['element'])
                time.sleep(random.uniform(0.5, 1))
                driver.execute_script("arguments[0].click();", 选中的帖子['element'])
            except:
                选中的帖子['element'].click()
            
            加载时间 = random.uniform(3, 5)
            if debug:
                log(f"  等待页面加载 {加载时间:.1f} 秒...")
            time.sleep(加载时间)
            
            log(f"✓ 成功进入公共主页帖子")
            return True
        
        else:
            log(f"未找到包含'{主页名称}'的链接或帖子")
            return False
        
    except Exception as e:
        log(f"搜索主页帖子失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False
    """
    在个人主页中搜索包含主页名称的帖子或链接，随机选择一个进入
    
    策略：
    1. 优先查找直接指向公共主页的链接（aria-label="See Owner Profile"）
    2. 其次查找包含主页名称的帖子链接
    
    Args:
        driver: WebDriver实例
        主页名称: 要搜索的主页名称
        log_func: 日志函数
        debug: 是否开启调试模式
    
    Returns:
        是否成功找到并进入
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        log(f"在个人主页搜索: {主页名称}")
        
        # 提取主页名称的关键词（用于部分匹配）
        关键词列表 = 主页名称.split()
        if debug:
            log(f"  关键词: {关键词列表}")
        
        # 1. 滚动页面，收集所有符合的链接
        符合的主页链接列表 = []  # 直接指向公共主页的链接
        符合的帖子列表 = []  # 包含主页名称的帖子
        最大滚动次数 = 10
        
        for 滚动次数 in range(最大滚动次数):
            if debug:
                log(f"  第 {滚动次数 + 1} 次滚动...")
            
            # 策略1: 查找直接指向公共主页的链接
            # 这些链接通常在视频或帖子中，aria-label="See Owner Profile"
            try:
                owner_links = driver.find_elements(By.CSS_SELECTOR, "a[aria-label='See Owner Profile']")
                for link in owner_links:
                    try:
                        if not link.is_displayed():
                            continue
                        
                        # 检查链接文本是否包含主页名称
                        link_text = link.text.strip()
                        href = link.get_attribute("href") or ""
                        
                        if 主页名称.lower() in link_text.lower():
                            # 检查是否已添加
                            已存在 = False
                            for 已有链接 in 符合的主页链接列表:
                                if 已有链接['href'] == href:
                                    已存在 = True
                                    break
                            
                            if not 已存在:
                                符合的主页链接列表.append({
                                    'element': link,
                                    'href': href,
                                    'text': link_text,
                                    'type': 'owner_profile'
                                })
                                if debug:
                                    log(f"    ✓ 找到公共主页链接: {link_text}")
                    except:
                        continue
            except:
                pass
            
            # 策略2: 查找包含主页名称的文本元素
            # 只查找包含文本的元素
            text_elements = driver.find_elements(By.CSS_SELECTOR, "span, div[dir='auto'], a")
            
            for element in text_elements:
                try:
                    if not element.is_displayed():
                        continue
                    
                    text = element.text.strip()
                    
                    if not text or len(text) < 5:
                        continue
                    
                    # 检查是否包含主页名称（完整匹配）
                    匹配 = False
                    if 主页名称.lower() in text.lower():
                        匹配 = True
                    else:
                        # 部分匹配：至少包含2个关键词
                        匹配数 = 0
                        for 关键词 in 关键词列表:
                            if len(关键词) > 2 and 关键词.lower() in text.lower():
                                匹配数 += 1
                        
                        if 匹配数 >= min(2, len(关键词列表)):
                            匹配 = True
                    
                    if not 匹配:
                        continue
                    
                    # 如果元素本身就是链接
                    if element.tag_name == 'a':
                        href = element.get_attribute("href") or ""
                        
                        # 检查是否是公共主页链接
                        if "profile.php?id=" in href:
                            已存在 = False
                            for 已有链接 in 符合的主页链接列表:
                                if 已有链接['href'] == href:
                                    已存在 = True
                                    break
                            
                            if not 已存在:
                                符合的主页链接列表.append({
                                    'element': element,
                                    'href': href,
                                    'text': text[:50],
                                    'type': 'direct_link'
                                })
                                if debug:
                                    log(f"    ✓ 找到公共主页直接链接: {text[:30]}...")
                            continue
                    
                    # 向上查找父元素中的链接
                    parent = element
                    找到链接 = False
                    
                    for level in range(15):
                        try:
                            # 在当前层级查找链接
                            links = parent.find_elements(By.CSS_SELECTOR, "a[href]")
                            
                            for link in links:
                                href = link.get_attribute("href") or ""
                                
                                # 优先：检查是否是公共主页链接
                                if "profile.php?id=" in href:
                                    已存在 = False
                                    for 已有链接 in 符合的主页链接列表:
                                        if 已有链接['href'] == href:
                                            已存在 = True
                                            break
                                    
                                    if not 已存在:
                                        符合的主页链接列表.append({
                                            'element': link,
                                            'href': href,
                                            'text': text[:50],
                                            'type': 'profile_link'
                                        })
                                        找到链接 = True
                                        if debug:
                                            log(f"    ✓ 找到公共主页链接: {text[:30]}...")
                                        break
                                
                                # 其次：检查是否是帖子链接
                                elif "/posts/" in href or "/photo" in href or "fbid=" in href or "/permalink/" in href or "story_fbid=" in href:
                                    已存在 = False
                                    for 已有帖子 in 符合的帖子列表:
                                        if 已有帖子['href'] == href:
                                            已存在 = True
                                            break
                                    
                                    if not 已存在:
                                        符合的帖子列表.append({
                                            'element': link,
                                            'href': href,
                                            'text': text[:50]
                                        })
                                        找到链接 = True
                                        if debug:
                                            log(f"    ✓ 找到帖子链接: {text[:30]}...")
                                        break
                            
                            if 找到链接:
                                break
                            
                            # 向上一层
                            parent = parent.find_element(By.XPATH, "..")
                        except:
                            break
                    
                except:
                    continue
            
            if debug:
                log(f"    当前找到 {len(符合的主页链接列表)} 个公共主页链接，{len(符合的帖子列表)} 个帖子")
            
            # 如果已经找到公共主页链接，优先使用
            if len(符合的主页链接列表) >= 2:
                log(f"  已找到 {len(符合的主页链接列表)} 个公共主页链接，停止滚动")
                break
            
            # 或者找到足够多的帖子
            if len(符合的帖子列表) >= 5:
                log(f"  已找到 {len(符合的帖子列表)} 个帖子，停止滚动")
                break
            
            # 继续滚动
            if 滚动次数 < 最大滚动次数 - 1:
                滚动距离 = random.randint(2500, 3500)
                driver.execute_script(f"window.scrollBy(0, {滚动距离})")
                
                # 模拟真人：滚动后浏览一下
                浏览时间 = random.uniform(0.5, 1)
                time.sleep(浏览时间)
        
        # 2. 优先使用公共主页链接
        if 符合的主页链接列表:
            log(f"✓ 找到 {len(符合的主页链接列表)} 个公共主页链接（优先使用）")
            
            选中的链接 = random.choice(符合的主页链接列表)
            
            log(f"随机选择公共主页链接: {选中的链接['text'][:30]}...")
            if debug:
                log(f"  类型: {选中的链接['type']}")
                log(f"  链接: {选中的链接['href'][:80]}...")
            
            # 模拟真人：选择前思考一下
            思考时间 = random.uniform(2, 4)
            if debug:
                log(f"  思考 {思考时间:.1f} 秒...")
            time.sleep(思考时间)
            
            # 点击进入
            log("点击进入公共主页...")
            
            try:
                # 记录当前标签数量
                原标签数 = len(driver.window_handles)
                
                # 滚动到元素可见
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 选中的链接['element'])
                time.sleep(random.uniform(0.5, 1))
                
                # 移除 target 属性（防止打开新标签）
                driver.execute_script("arguments[0].removeAttribute('target');", 选中的链接['element'])
                
                # 点击
                driver.execute_script("arguments[0].click();", 选中的链接['element'])
            except:
                选中的链接['element'].click()
            
            # 等待页面加载
            加载时间 = random.uniform(3, 5)
            if debug:
                log(f"  等待页面加载 {加载时间:.1f} 秒...")
            time.sleep(加载时间)
            
            # 检查是否打开了新标签
            try:
                新标签数 = len(driver.window_handles)
                if 新标签数 > 原标签数:
                    if debug:
                        log("  检测到新标签，切换到新标签...")
                    # 切换到最新的标签
                    driver.switch_to.window(driver.window_handles[-1])
            except:
                pass
            
            log(f"✓ 成功进入公共主页")
            return True
        
        # 3. 降级：使用帖子链接
        elif 符合的帖子列表:
            log(f"✓ 找到 {len(符合的帖子列表)} 个帖子")
            
            选中的帖子 = random.choice(符合的帖子列表)
            
            log(f"随机选择帖子: {选中的帖子['text']}...")
            if debug:
                log(f"  链接: {选中的帖子['href'][:80]}...")
            
            思考时间 = random.uniform(2, 4)
            if debug:
                log(f"  思考 {思考时间:.1f} 秒...")
            time.sleep(思考时间)
            
            log("点击进入帖子...")
            
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 选中的帖子['element'])
                time.sleep(random.uniform(0.5, 1))
                driver.execute_script("arguments[0].click();", 选中的帖子['element'])
            except:
                选中的帖子['element'].click()
            
            加载时间 = random.uniform(3, 5)
            if debug:
                log(f"  等待页面加载 {加载时间:.1f} 秒...")
            time.sleep(加载时间)
            
            log(f"✓ 成功进入公共主页帖子")
            return True
        
        else:
            log(f"未找到包含'{主页名称}'的链接或帖子")
            return False
        
    except Exception as e:
        log(f"搜索主页帖子失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

def 直接访问主页(driver: "WebDriver", 主页链接: str, log_func=None, debug=False) -> bool:
    """
    直接通过URL访问主页（降级方案）
    
    Args:
        driver: WebDriver实例
        主页链接: 主页URL
        log_func: 日志函数
        debug: 是否开启调试模式
    
    Returns:
        是否成功
    """
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        log(f"直接访问主页URL...")
        
        driver.get(主页链接)
        
        # 等待页面加载
        加载时间 = random.uniform(3, 5)
        if debug:
            log(f"等待页面加载 {加载时间:.1f} 秒...")
        time.sleep(加载时间)
        
        log("✓ 已进入主页（URL方式）")
        return True
        
    except Exception as e:
        log(f"访问主页失败: {e}")
        return False

def 进入公共主页(driver: "WebDriver", log_func=None, debug=False) -> bool:
    """
    进入公共主页（智能选择方式）
    
    流程：
    1. 点击头像进入个人主页
    2. 在个人主页搜索包含主页名称的帖子
    3. 随机选择一个帖子进入
    4. 降级：直接访问URL
    
    Args:
        driver: WebDriver实例
        log_func: 日志函数
        debug: 是否开启调试模式
    
    Returns:
        是否成功进入
    """
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    # 1. 读取配置
    主页名称 = 读取主页名称()
    主页链接 = 读取主页链接()
    
    if not 主页名称 and not 主页链接:
        log("❌ 未配置主页名称或链接")
        log("请在以下文件中配置：")
        log("  - 脚本配置/主页名称.txt")
        log("  - 脚本配置/公共主页链接")
        return False
    
    if debug:
        log(f"主页名称: {主页名称 or '(未配置)'}")
        log(f"主页链接: {主页链接 or '(未配置)'}")
    
    # 2. 优先尝试：点击头像进入个人主页，然后搜索帖子
    if 主页名称:
        log("尝试方式1: 通过个人主页搜索帖子（模拟真人）")
        
        # 2.1 点击头像进入个人主页
        if 点击头像进入个人主页(driver, log_func, debug):
            # 2.2 在个人主页搜索主页帖子
            if 在个人主页搜索主页帖子(driver, 主页名称, log_func, debug):
                return True
            else:
                log("在个人主页未找到帖子")
        else:
            log("进入个人主页失败")
        
        log("方式1失败，尝试方式2...")
    
    # 3. 降级：直接访问URL
    if 主页链接:
        log("尝试方式2: 直接访问URL（降级方案）")
        if 直接访问主页(driver, 主页链接, log_func, debug):
            return True
    
    log("❌ 所有方式都失败了")
    return False

# ==================== 调试模式 ====================

def _调试模式():
    """调试模式入口"""
    print("=" * 60)
    print("进入公共主页 - 调试模式")
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
    print("=" * 60)
    print("功能说明：")
    print("1. 点击头像进入个人主页")
    print("2. 在个人主页搜索包含主页名称的帖子")
    print("3. 随机选择一个帖子进入")
    print("4. 降级：直接访问URL")
    print("=" * 60)
    print()
    print("-" * 60)
    print("开始进入公共主页...")
    print("-" * 60)
    
    成功 = 进入公共主页(driver, debug=True)
    
    print("-" * 60)
    if 成功:
        print("✓ 成功进入公共主页")
        print(f"当前页面: {driver.title}")
    else:
        print("✗ 进入公共主页失败")
    print("-" * 60)
    
    print()
    print("调试完成，浏览器保持打开状态")

# ==================== 入口 ====================

if __name__ == "__main__":
    _调试模式()
