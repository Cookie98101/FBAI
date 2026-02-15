"""
分享动态任务
从公共主页获取帖子并分享到自己的动态（Timeline）

流程：
1. 调用辅助功能进入公共主页
2. 模拟真人浏览（滚动、停留）
3. 随机选择一个帖子
4. 分享到自己的动态
5. 全局去重（避免重复分享同一帖子）
6. 数据上报

使用方法：
- 调试模式：修改 DEBUG_BROWSER_ID，直接运行此文件
- 正式调用：main.py 中调用 分享动态(driver, ...)
"""

import os
import sys
import time
import random
import requests
from typing import TYPE_CHECKING, List
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

from tasks.辅助_进入公共主页 import 进入公共主页
from tasks.去重管理 import 检查是否已操作, 记录操作, 提取帖子ID

# 数据上报 API
数据上报API = "http://localhost:8805/add_data"

# ==================== 调试配置 ====================

DEBUG_BROWSER_ID = "dd6c77a66dc74aea8c449207d55a3a87"
# 优先使用调试面板传入的浏览器ID（facebook_dashboard.py 会设置环境变量 DEBUG_BROWSER_ID）
DEBUG_BROWSER_ID = os.environ.get("DEBUG_BROWSER_ID") or DEBUG_BROWSER_ID

# ==================== 配置 ====================

@dataclass
class 分享动态配置:
    """分享动态任务配置"""
    分享数量: int = 1  # 每次运行只分享1个帖子
    浏览时长秒: int = 30  # 浏览多长时间（秒）

# ==================== 真人模拟浏览 ====================

def 模拟真人浏览(driver: "WebDriver", 浏览时长秒: int, log_func=None, debug=False):
    """
    模拟真人浏览公共主页（类似阅读.py的逻辑）
    
    Args:
        driver: WebDriver实例
        浏览时长秒: 浏览时长（秒）
        log_func: 日志函数
        debug: 是否开启调试模式
    """
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    log(f"开始浏览公共主页（{浏览时长秒}秒）...")
    
    开始时间 = time.time()
    
    while True:
        已用时间 = time.time() - 开始时间
        if 已用时间 >= 浏览时长秒:
            break
        
        # 随机行为
        行为 = random.random()
        
        if 行为 < 0.7:
            # 滚动
            滚动距离 = random.randint(500, 1000)
            driver.execute_script(f"window.scrollBy(0, {滚动距离})")
            time.sleep(random.uniform(1, 3))
        elif 行为 < 0.85:
            # 回滚
            滚动距离 = random.randint(200, 400)
            driver.execute_script(f"window.scrollBy(0, -{滚动距离})")
            time.sleep(random.uniform(1, 2))
        else:
            # 停留
            time.sleep(random.uniform(2, 5))
    
    log(f"✓ 浏览完成（{int(已用时间)}秒）")

# ==================== 获取帖子列表 ====================

def 获取公共主页帖子列表(driver: "WebDriver", log_func=None, debug=False) -> List[dict]:
    """
    获取当前公共主页上的帖子列表
    
    通过查找包含 Like、Comment、Share 三个按钮的帖子容器来识别真实帖子
    
    Returns:
        帖子信息列表，每个元素包含：
        - share_button: 分享按钮元素
        - post_id: 帖子ID（从帖子内链接提取）
        - container: 帖子容器元素
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        log("收集公共主页帖子（通过 Like/Comment/Share 按钮识别）...")
        
        # 滚动页面，加载更多帖子
        for i in range(3):
            driver.execute_script("window.scrollBy(0, 800)")
            time.sleep(random.uniform(1, 2))
        
        # 查找所有分享按钮（每个帖子都有一个）
        share_buttons = driver.find_elements(
            By.CSS_SELECTOR, 
            "[aria-label='Send this to friends or post it on your profile.']"
        )
        
        if debug:
            log(f"  找到 {len(share_buttons)} 个分享按钮")
        
        帖子列表 = []
        已添加ID = set()
        
        for share_button in share_buttons:
            try:
                if not share_button.is_displayed():
                    continue
                
                # 向上查找帖子容器（包含 Like、Comment、Share 的父元素）
                # 通常需要向上查找 5-10 层
                当前元素 = share_button
                帖子容器 = None
                
                for level in range(15):
                    try:
                        当前元素 = 当前元素.find_element(By.XPATH, "..")
                        
                        # 检查是否同时包含 Like 和 Comment 按钮
                        try:
                            like_buttons = 当前元素.find_elements(By.CSS_SELECTOR, "[aria-label='Like']")
                            comment_buttons = 当前元素.find_elements(By.CSS_SELECTOR, "[aria-label='Leave a comment']")
                            
                            if like_buttons and comment_buttons:
                                帖子容器 = 当前元素
                                if debug and len(帖子列表) < 3:
                                    log(f"    找到帖子容器（第{level}层）")
                                break
                        except:
                            pass
                    except:
                        break
                
                if not 帖子容器:
                    continue
                
                # 从帖子容器中提取帖子ID
                帖子ID = None
                try:
                    # 查找帖子容器内的所有链接
                    links = 帖子容器.find_elements(By.CSS_SELECTOR, "a[href]")
                    
                    for link in links:
                        href = link.get_attribute("href") or ""
                        
                        # 尝试提取帖子ID
                        temp_id = 提取帖子ID(href)
                        if temp_id:
                            帖子ID = temp_id
                            if debug and len(帖子列表) < 3:
                                log(f"    提取到帖子ID: {帖子ID[:16]}...")
                            break
                except:
                    pass
                
                # 如果没有提取到ID，使用分享按钮的位置作为唯一标识
                if not 帖子ID:
                    try:
                        location = share_button.location
                        帖子ID = f"pos_{int(location['y'])}_{int(location['x'])}"
                        if debug and len(帖子列表) < 3:
                            log(f"    使用位置作为ID: {帖子ID}")
                    except:
                        continue
                
                # 去重
                if 帖子ID in 已添加ID:
                    continue
                
                已添加ID.add(帖子ID)
                
                帖子信息 = {
                    'share_button': share_button,
                    'post_id': 帖子ID,
                    'container': 帖子容器
                }
                
                帖子列表.append(帖子信息)
                
            except:
                continue
        
        log(f"✓ 找到 {len(帖子列表)} 个帖子")
        
        return 帖子列表
        
    except Exception as e:
        if debug:
            log(f"获取帖子列表失败: {e}")
            import traceback
            traceback.print_exc()
        return []

# ==================== 分享帖子到动态 ====================

def 分享帖子到动态(driver: "WebDriver", 帖子ID: str, 分享按钮, 
                  log_func=None, debug=False) -> bool:
    """
    将帖子分享到自己的动态（直接点击 Share 按钮）
    
    流程：
    1. 点击 Share 按钮（aria-label="Send this to friends or post it on your profile."）
    2. 等待分享菜单出现
    3. 选择"Share now (Public)"或类似选项
    
    Args:
        driver: WebDriver实例
        帖子ID: 帖子ID（用于去重）
        分享按钮: Share 按钮元素
        log_func: 日志函数
        debug: 是否开启调试模式
    
    Returns:
        是否成功分享
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        # 检查是否已分享过（全局去重）
        if 检查是否已操作(帖子ID, "share_to_timeline", 去重天数=15):
            if debug:
                log(f"  跳过（15天内已分享过）")
            return False
        
        # 1. 滚动到分享按钮可见
        if debug:
            log("  滚动到帖子...")
        
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 分享按钮)
        time.sleep(random.uniform(1, 2))
        
        # 模拟真人：思考一下
        思考时间 = random.uniform(1, 2)
        if debug:
            log(f"  思考 {思考时间:.1f} 秒...")
        time.sleep(思考时间)
        
        # 2. 点击 Share 按钮
        if debug:
            log("  点击 Share 按钮...")
        
        try:
            driver.execute_script("arguments[0].click();", 分享按钮)
        except:
            分享按钮.click()
        
        # 等待分享菜单完全加载（需要更长时间）
        等待时间 = random.uniform(5, 10)
        if debug:
            log(f"  等待菜单加载 {等待时间:.1f} 秒...")
        time.sleep(等待时间)
        
        # 3. 修改分享权限：从 "Friends" 改为 "Public"
        if debug:
            log("  修改分享权限为 Public...")
        
        try:
            # 查找包含 "Friends" 文本的 span 元素
            friends_spans = driver.find_elements(By.XPATH, "//span[contains(text(), 'Friends')]")
            
            if debug:
                log(f"    找到 {len(friends_spans)} 个包含 'Friends' 的 span")
            
            friends_button = None
            for span in friends_spans:
                try:
                    if not span.is_displayed():
                        continue
                    
                    # 向上查找可点击的父元素（最多5层）
                    current = span
                    for level in range(6):
                        try:
                            parent = current.find_element(By.XPATH, "..")
                            role = parent.get_attribute("role")
                            
                            # 检查是否是可点击的元素
                            if role == "button" or parent.tag_name == "button":
                                friends_button = parent
                                if debug:
                                    log(f"    找到 Friends 按钮（第{level}层父元素）")
                                break
                            
                            current = parent
                        except:
                            break
                    
                    if friends_button:
                        break
                except:
                    continue
            
            if friends_button:
                # 点击 Friends 按钮打开权限菜单
                if debug:
                    log("  点击 Friends 按钮...")
                
                try:
                    driver.execute_script("arguments[0].click();", friends_button)
                except:
                    friends_button.click()
                
                # 等待权限菜单加载（Public 出现很慢）
                等待时间2 = random.uniform(3, 5)
                if debug:
                    log(f"  等待权限菜单加载 {等待时间2:.1f} 秒...")
                time.sleep(等待时间2)
                
                # 查找包含 "Public" 文本的 span 元素
                public_spans = driver.find_elements(By.XPATH, "//span[contains(text(), 'Public')]")
                
                if debug:
                    log(f"    找到 {len(public_spans)} 个包含 'Public' 的 span")
                
                public_option = None
                for span in public_spans:
                    try:
                        if not span.is_displayed():
                            continue
                        
                        # 向上查找可点击的父元素（最多8层，因为可能嵌套较深）
                        current = span
                        for level in range(9):
                            try:
                                parent = current.find_element(By.XPATH, "..")
                                role = parent.get_attribute("role")
                                tag = parent.tag_name
                                
                                # 检查是否是可点击的元素
                                # Public 选项可能没有 role，但可以点击
                                if role in ["menuitem", "option", "button"] or tag == "button" or tag == "div":
                                    # 尝试点击，如果可以点击就是正确的元素
                                    public_option = parent
                                    if debug:
                                        log(f"    找到 Public 选项（第{level}层父元素，tag={tag}, role={role}）")
                                    break
                                
                                current = parent
                            except:
                                break
                        
                        if public_option:
                            break
                    except:
                        continue
                
                if public_option:
                    if debug:
                        log("  点击 Public 选项...")
                    
                    try:
                        driver.execute_script("arguments[0].click();", public_option)
                    except:
                        public_option.click()
                    
                    # 等待选择生效
                    time.sleep(random.uniform(1, 2))
                    
                    # 查找并点击 "Done" 按钮
                    if debug:
                        log("  查找 Done 按钮...")
                    
                    done_buttons = driver.find_elements(By.CSS_SELECTOR, "[aria-label='Done']")
                    
                    if debug:
                        log(f"    找到 {len(done_buttons)} 个 Done 按钮")
                    
                    done_button = None
                    for btn in done_buttons:
                        if btn.is_displayed():
                            done_button = btn
                            if debug:
                                log("    找到可见的 Done 按钮")
                            break
                    
                    if done_button:
                        if debug:
                            log("  点击 Done 按钮...")
                        
                        try:
                            driver.execute_script("arguments[0].click();", done_button)
                        except:
                            done_button.click()
                        
                        # 等待菜单关闭
                        time.sleep(random.uniform(1, 2))
                        
                        if debug:
                            log("  ✓ 已设置为 Public")
                    else:
                        if debug:
                            log("  ⚠ 未找到 Done 按钮")
                else:
                    if debug:
                        log("  ⚠ 未找到 Public 选项，使用默认设置")
            else:
                if debug:
                    log("  ⚠ 未找到 Friends 按钮，使用默认设置")
        except Exception as e:
            if debug:
                log(f"  ⚠ 修改权限异常: {e}，使用默认设置")
            import traceback
            traceback.print_exc()
        
        # 4. 添加评论（在分享菜单中）
        if debug:
            log("  添加分享评论...")
        
        try:
            # 导入 AI 评论函数
            from tasks.自动化工具 import AI评论_不带帖子内容
            
            # 生成评论内容
            评论内容 = AI评论_不带帖子内容()
            
            if debug:
                log(f"  生成评论: {评论内容[:50]}...")
            
            # 查找分享菜单中的评论输入框
            # 必须同时满足：role="textbox" 且 contenteditable="true"
            # 并且在分享菜单弹窗内（z-index 较高或在特定父元素内）
            评论输入框 = None
            
            try:
                # 查找所有 role="textbox" 的元素
                textboxes = driver.find_elements(By.CSS_SELECTOR, "[role='textbox'][contenteditable='true']")
                
                if debug:
                    log(f"    找到 {len(textboxes)} 个 textbox")
                
                # 遍历所有 textbox，找到在分享菜单内的那个
                候选输入框列表 = []
                
                for textbox in textboxes:
                    try:
                        if not textbox.is_displayed():
                            continue
                        
                        # 获取元素信息
                        location = textbox.location
                        z_index = textbox.value_of_css_property("z-index")
                        
                        # 检查位置（不在顶部导航栏）
                        if location['y'] < 100:
                            continue
                        
                        # 检查 placeholder 或 aria-placeholder
                        placeholder = textbox.get_attribute("aria-placeholder") or ""
                        
                        # 分享菜单中的输入框通常有 "Say something about this..." 的 placeholder
                        if "say something" in placeholder.lower():
                            候选输入框列表.append({
                                'element': textbox,
                                'y': location['y'],
                                'z_index': z_index,
                                'placeholder': placeholder
                            })
                            if debug:
                                log(f"    候选输入框: Y={location['y']}, z-index={z_index}, placeholder={placeholder[:30]}")
                    except:
                        continue
                
                # 如果找到候选输入框，选择 z-index 最高的（在最上层）
                if 候选输入框列表:
                    # 按 z-index 排序（降序）
                    候选输入框列表.sort(key=lambda x: (
                        int(x['z_index']) if x['z_index'] != 'auto' else 0
                    ), reverse=True)
                    
                    评论输入框 = 候选输入框列表[0]['element']
                    
                    if debug:
                        log(f"    ✓ 选择输入框: Y={候选输入框列表[0]['y']}, z-index={候选输入框列表[0]['z_index']}")
                
                # 如果还没找到，降级：选择 Y 坐标最大的（最下面的，通常是弹窗）
                if not 评论输入框 and textboxes:
                    最大Y = 0
                    for textbox in textboxes:
                        try:
                            if textbox.is_displayed():
                                location = textbox.location
                                if location['y'] > 最大Y:
                                    最大Y = location['y']
                                    评论输入框 = textbox
                        except:
                            continue
                    
                    if debug and 评论输入框:
                        log(f"    降级：选择 Y 坐标最大的输入框（Y={最大Y}）")
                
            except Exception as e:
                if debug:
                    log(f"    查找输入框异常: {e}")
            
            if 评论输入框:
                # 先滚动到输入框可见
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 评论输入框)
                    time.sleep(random.uniform(0.3, 0.5))
                except:
                    pass
                
                # 点击输入框获得焦点（重要！）
                if debug:
                    log("  点击输入框...")
                
                try:
                    driver.execute_script("arguments[0].click();", 评论输入框)
                    time.sleep(random.uniform(0.5, 1))
                except:
                    try:
                        评论输入框.click()
                        time.sleep(random.uniform(0.5, 1))
                    except:
                        pass
                
                # 再次聚焦
                try:
                    driver.execute_script("arguments[0].focus();", 评论输入框)
                    time.sleep(random.uniform(0.3, 0.5))
                except:
                    pass
                
                # 输入评论（模拟真人逐字输入）
                try:
                    # 对于 contenteditable 的 div，也可以使用 send_keys
                    # 先清空（如果有内容）
                    try:
                        from selenium.webdriver.common.keys import Keys
                        评论输入框.send_keys(Keys.CONTROL + "a")
                        time.sleep(random.uniform(0.1, 0.2))
                        评论输入框.send_keys(Keys.DELETE)
                        time.sleep(random.uniform(0.2, 0.4))
                    except:
                        pass
                    
                    if debug:
                        log(f"  开始逐字输入评论...")
                    
                    # 逐字输入
                    for i, 字符 in enumerate(评论内容):
                        评论输入框.send_keys(字符)
                        
                        # 随机输入速度
                        if random.random() < 0.1:  # 10% 稍长停顿
                            time.sleep(random.uniform(0.2, 0.5))
                        else:
                            time.sleep(random.uniform(0.05, 0.15))
                        
                        # 每输入10个字符显示一次进度
                        if debug and (i + 1) % 10 == 0:
                            log(f"    已输入 {i + 1}/{len(评论内容)} 字符")
                    
                    if debug:
                        log(f"  ✓ 已添加评论（逐字输入，共 {len(评论内容)} 字符）")
                    
                    # 输入完成后等待一下
                    time.sleep(random.uniform(1, 2))
                    
                except Exception as e:
                    if debug:
                        log(f"  ⚠ 输入评论失败: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                if debug:
                    log("  ⚠ 未找到评论输入框，跳过评论")
        except Exception as e:
            if debug:
                log(f"  ⚠ 添加评论异常: {e}")
            import traceback
            traceback.print_exc()
        
        # 5. 查找分享选项
        if debug:
            log("  查找分享选项...")
        
        分享选项 = None
        
        # 方法1: 直接查找 aria-label="Share now" 的按钮
        try:
            share_now_buttons = driver.find_elements(By.CSS_SELECTOR, "[aria-label='Share now']")
            
            if debug:
                log(f"    找到 {len(share_now_buttons)} 个 'Share now' 按钮")
            
            for btn in share_now_buttons:
                if btn.is_displayed():
                    分享选项 = btn
                    if debug:
                        log(f"    ✓ 找到 Share now 按钮")
                    break
        except Exception as e:
            if debug:
                log(f"    方法1异常: {e}")
        
        # 方法2: 查找 role='button' 且包含 "Share now" 文本的元素
        if not 分享选项:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, "[role='button']")
                
                if debug:
                    log(f"    找到 {len(buttons)} 个按钮，查找包含 'Share now' 的...")
                
                for btn in buttons:
                    try:
                        if not btn.is_displayed():
                            continue
                        
                        aria_label = btn.get_attribute("aria-label") or ""
                        text = btn.text.strip()
                        
                        if 'share now' in aria_label.lower() or 'share now' in text.lower():
                            分享选项 = btn
                            if debug:
                                log(f"    ✓ 找到分享按钮: {text or aria_label}")
                            break
                    except:
                        continue
            except Exception as e:
                if debug:
                    log(f"    方法2异常: {e}")
        
        # 方法3: 查找 menuitem
        if not 分享选项:
            try:
                menu_items = driver.find_elements(By.CSS_SELECTOR, "[role='menuitem']")
                
                if debug:
                    log(f"    找到 {len(menu_items)} 个菜单项")
                
                for item in menu_items:
                    try:
                        if not item.is_displayed():
                            continue
                        
                        aria_label = item.get_attribute("aria-label") or ""
                        text = item.text.strip()
                        
                        if debug and (text or aria_label):
                            log(f"    菜单项: {text[:50]} | aria-label: {aria_label[:50]}")
                        
                        # 匹配 "Share now"
                        if 'share now' in text.lower() or 'share now' in aria_label.lower():
                            分享选项 = item
                            if debug:
                                log(f"    ✓ 找到分享选项: {text or aria_label}")
                            break
                    except:
                        continue
            except Exception as e:
                if debug:
                    log(f"    方法3异常: {e}")
        
        if not 分享选项:
            if debug:
                log("  ✗ 未找到分享选项")
            return False
        
        # 5. 点击分享选项（Share now）
        if debug:
            log("  点击 Share now...")
        
        try:
            driver.execute_script("arguments[0].click();", 分享选项)
        except:
            分享选项.click()
        
        # 等待分享完成
        time.sleep(random.uniform(2, 3))
        
        log(f"  ✓ 已分享到动态（Public）")
        
        # 6. 记录操作（全局去重）
        记录操作(帖子ID, "share_to_timeline")
        
        # 7. 上报数据
        try:
            requests.get(f"{数据上报API}?shares=1", timeout=5)
        except:
            pass
        
        return True
        
    except Exception as e:
        if debug:
            log(f"  分享失败: {e}")
            import traceback
            traceback.print_exc()
        return False

# ==================== 主函数 ====================

def 分享动态(driver: "WebDriver", log_func=None, 配置: 分享动态配置 = None) -> bool:
    """
    执行分享动态任务
    
    流程：
    1. 进入公共主页
    2. 模拟真人浏览
    3. 获取帖子列表
    4. 随机选择帖子并分享到动态
    
    Args:
        driver: WebDriver实例
        log_func: 日志函数
        配置: 分享动态配置
    
    Returns:
        是否成功
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    if 配置 is None:
        配置 = 分享动态配置()
    
    log("=" * 60)
    log("开始分享动态任务")
    log("=" * 60)
    log(f"目标分享数量: {配置.分享数量}")
    log(f"浏览时长: {配置.浏览时长秒}秒")
    
    try:
        # 1. 进入公共主页
        log("\n步骤1: 进入公共主页")
        log("-" * 60)
        
        if not 进入公共主页(driver, log_func, debug=False):
            log("✗ 进入公共主页失败")
            return False
        
        log("✓ 已进入公共主页")
        
        # 2. 模拟真人浏览
        log("\n步骤2: 模拟真人浏览")
        log("-" * 60)
        
        模拟真人浏览(driver, 配置.浏览时长秒, log_func, debug=False)
        
        # 3. 获取帖子列表
        log("\n步骤3: 获取帖子列表")
        log("-" * 60)
        
        帖子列表 = 获取公共主页帖子列表(driver, log_func, debug=True)  # 开启debug
        
        if not 帖子列表:
            log("✗ 未找到帖子")
            return False
        
        # 显示前几个帖子的信息
        log("\n前5个帖子:")
        for i, 帖子 in enumerate(帖子列表[:5], 1):
            log(f"  {i}. ID:{帖子['post_id'][:20]}...")
        
        # 4. 随机打乱帖子顺序
        random.shuffle(帖子列表)
        
        # 5. 分享帖子
        log("\n步骤4: 分享帖子到动态")
        log("-" * 60)
        
        已分享数量 = 0
        
        for 帖子信息 in 帖子列表:
            if 已分享数量 >= 配置.分享数量:
                log(f"\n已达到目标分享数量: {配置.分享数量}")
                break
            
            帖子ID = 帖子信息['post_id']
            分享按钮 = 帖子信息['share_button']
            
            log(f"\n处理帖子 {已分享数量 + 1}/{配置.分享数量}")
            log(f"帖子ID: {帖子ID[:20]}...")
            
            # 模拟真人：浏览帖子列表，思考一下
            浏览时间 = random.uniform(2, 4)
            log(f"浏览帖子 {浏览时间:.1f} 秒...")
            time.sleep(浏览时间)
            
            # 分享帖子
            分享成功 = 分享帖子到动态(driver, 帖子ID, 分享按钮, log_func, debug=True)  # 开启debug查看详情
            
            if 分享成功:
                已分享数量 += 1
                log(f"✓ 分享成功 ({已分享数量}/{配置.分享数量})")
                
                # 模拟真人：分享后休息一下
                if 已分享数量 < 配置.分享数量:
                    休息时间 = random.uniform(5, 10)
                    log(f"休息 {休息时间:.1f} 秒...")
                    time.sleep(休息时间)
            else:
                log(f"✗ 分享失败，尝试下一个帖子")
        
        log("\n" + "=" * 60)
        log(f"✓ 分享动态任务完成，共分享 {已分享数量} 个帖子")
        log("=" * 60)
        return True
        
    except Exception as e:
        log(f"\n✗ 分享动态任务异常: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==================== 调试模式 ====================

def _调试模式():
    """调试模式入口"""
    print("=" * 60)
    print("分享动态 - 调试模式")
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
    
    测试配置 = 分享动态配置(
        分享数量=1,
        浏览时长秒=30
    )
    
    成功 = 分享动态(driver, 配置=测试配置)
    
    print()
    if 成功:
        print("✓ 分享动态任务执行成功")
    else:
        print("✗ 分享动态任务执行失败")
    
    print()
    print("调试完成，浏览器保持打开状态")

# ==================== 入口 ====================

if __name__ == "__main__":
    _调试模式()
