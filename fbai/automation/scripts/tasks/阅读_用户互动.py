"""
阅读模块 - 用户互动功能（统一接口）
包括对帖子发布者和评论用户的互动

这个文件整合了原来的 阅读_帖子互动.py 和 阅读_评论互动.py
提供统一的接口，避免混淆
"""

import time
import random
from typing import TYPE_CHECKING, Optional, Tuple, Dict, List

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.remote.webelement import WebElement

# 导入数据库
try:
    from database.db import Database
    _db = Database()
except:
    _db = None

# 导入AI工具
try:
    from tasks.自动化工具 import AI生成私信内容, AI生成回复内容
except ImportError:
    from 自动化工具 import AI生成私信内容, AI生成回复内容



# ==================== 帖子发布者互动 ====================

def 点击帖子发布者头像(driver: "WebDriver", 帖子元素: "WebElement", 浏览器ID: str = None, log_func=None, debug=False) -> Tuple[bool, Optional[str]]:
    """
    点击帖子发布者的名字，访问其主页
    
    策略：
    1. 在帖子顶部查找第一个有文本的用户链接（通常是发布者）
    2. 排除包含comment_id的链接（这些是评论者）
    3. 去重，避免重复链接
    4. 点击用户名链接进入主页
    
    Args:
        driver: WebDriver实例
        帖子元素: 帖子的DOM元素
        浏览器ID: 浏览器ID（用于数据库记录）
        log_func: 日志函数
        debug: 是否开启调试模式
    
    Returns:
        (是否成功, 用户ID)
    """
    from selenium.webdriver.common.by import By
    import re
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        # 查找用户名链接
        # 策略：第1个链接通常是头像（无文本），第2个链接是发布者名字
        # 适用于：帖子元素、评论弹窗
        用户链接元素 = None
        用户链接 = None
        
        try:
            # 在帖子元素中查找所有链接
            links = 帖子元素.find_elements(By.CSS_SELECTOR, "a[role='link']")
            
            if debug:
                log(f"[调试] 找到 {len(links)} 个链接")
            
            # 找第一个有文本的用户主页链接 = 发布者
            for idx, link in enumerate(links):
                if not link.is_displayed():
                    continue
                
                href = link.get_attribute("href") or ""
                text = link.text.strip()
                
                if debug:
                    log(f"[调试] 检查链接 #{idx + 1}: {text or '(无文本)'} -> {href[:80]}...")
                
                # 1. 必须有文本（用户名）
                if not text or len(text) < 2:
                    if debug:
                        log(f"[调试]   跳过：无文本")
                    continue
                
                # 2. 必须是Facebook用户主页链接（不包含 comment_id）
                if not ("facebook.com/" in href):
                    if debug:
                        log(f"[调试]   跳过：不是Facebook链接")
                    continue
                
                # 排除非用户主页链接
                if any(x in href for x in ["/photo/", "/posts/", "/videos/", "/watch/", "/groups/", "/events/", "/reel/", "/share/", "/hashtag/", "comment_id="]):
                    if debug:
                        log(f"[调试]   跳过：不是用户主页链接")
                    continue
                
                # 必须是用户主页格式
                if not ("/profile.php?id=" in href or re.search(r'facebook\.com/[^/\?]+$', href) or re.search(r'facebook\.com/[^/\?]+\?', href)):
                    if debug:
                        log(f"[调试]   跳过：不是用户主页格式")
                    continue
                
                # 3. 排除明显不是用户名的文本
                if any(keyword in text.lower() for keyword in [
                    'like', 'reply', 'share', 'comment', 'see more', 'show more',
                    '点赞', '回复', '分享', '评论', '查看更多', 'http', 'www',
                    'sponsored', '赞助'
                ]):
                    if debug:
                        log(f"[调试]   跳过：非用户名文本")
                    continue
                
                # 找到第一个有文本的用户链接 = 发布者
                用户链接元素 = link
                用户链接 = href
                
                if debug:
                    log(f"[调试] ✓ 找到发布者链接: {text}")
                break
                    
        except Exception as e:
            if debug:
                log(f"[调试] 查找用户链接失败: {e}")
        
        if not 用户链接元素:
            if debug:
                log("[调试] 未找到发布者链接")
            log("未找到发布者链接")
            return False, None
        
        # 提取用户ID
        用户ID = None
        用户名 = 用户链接元素.text.strip()
        
        if "/user/" in 用户链接:
            用户ID = 用户链接.split("/user/")[1].split("/")[0].split("?")[0]
        elif "id=" in 用户链接:
            用户ID = 用户链接.split("id=")[1].split("&")[0]
        else:
            # 从URL中提取用户名作为ID
            import re
            match = re.search(r'facebook\.com/([^/\?]+)', 用户链接)
            if match:
                用户ID = match.group(1)
        
        if debug:
            log(f"找到发布者: {用户名}")
            log(f"用户ID: {用户ID}")
            log(f"用户链接: {用户链接}")
        
        # 检查数据库去重（访问主页动作）
        if _db and 浏览器ID and 用户ID:
            try:
                # 使用用户ID作为URL进行去重检查
                if not _db.can_interact(浏览器ID, f"user_{用户ID}", "visit_profile"):
                    log("跳过（已访问过该用户主页）")
                    return False, 用户ID
            except Exception as e:
                if debug:
                    log(f"数据库检查失败: {e}")
        
        # 滚动到链接
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 用户链接元素)
        time.sleep(random.uniform(0.5, 1.5))
        
        # 记录当前URL
        当前URL = driver.current_url
        if debug:
            log(f"[调试] 点击前URL: {当前URL}")
        
        # 点击用户名链接
        if debug:
            log("点击用户名链接...")
        
        try:
            driver.execute_script("arguments[0].click();", 用户链接元素)
        except:
            用户链接元素.click()
        
        log("✓ 已点击发布者链接")
        
        # 等待页面加载
        time.sleep(random.uniform(3, 6))
        
        # 验证是否跳转成功
        新URL = driver.current_url
        if debug:
            log(f"[调试] 点击后URL: {新URL}")
        
        if 新URL == 当前URL:
            if debug:
                log(f"[调试] ⚠️ 点击后URL未变化，可能点击失败")
            log("点击链接失败（URL未变化）")
            return False, None
        
        # 检查是否被重定向到搜索页面
        if "/search/" in 新URL:
            if debug:
                log(f"[调试] ⚠️ 被重定向到搜索页面: {新URL}")
            log("点击链接失败（被重定向到搜索页面）")
            # 尝试返回
            driver.back()
            time.sleep(2)
            return False, None
        
        # 记录到数据库
        if _db and 浏览器ID and 用户ID:
            try:
                _db.record_interaction(
                    browser_id=浏览器ID,
                    post_url=f"user_{用户ID}",
                    action_type="visit_profile"
                )
                if debug:
                    log("✓ 已记录到数据库")
            except Exception as e:
                if debug:
                    log(f"数据库记录失败: {e}")
        
        # 模拟浏览主页（真人滚动）
        浏览时长 = random.uniform(5, 15)
        if debug:
            log(f"浏览主页 {浏览时长:.1f} 秒...")
        
        # 导入滚动工具
        try:
            from tasks.自动化工具 import 真人阅读式滚动, 鼠标滚轮滚动
        except ImportError:
            from 自动化工具 import 真人阅读式滚动, 鼠标滚轮滚动
        
        # 真人阅读式滚动（模拟浏览主页内容）
        try:
            滚动距离 = random.randint(300, 800)
            if debug:
                log(f"  真人滚动浏览 {滚动距离} 像素...")
            真人阅读式滚动(driver, 滚动距离)
        except Exception as e:
            if debug:
                log(f"  滚动失败: {e}")
            # 如果滚动失败，至少等待一下
            time.sleep(浏览时长)
        
        # 注意：不返回上一页，让调用者决定后续操作
        # （如果只是访问主页，调用者需要自己执行 driver.back()）
        
        return True, 用户ID
        
    except Exception as e:
        log(f"点击头像失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False, None

def 私信帖子发布者(driver: "WebDriver", 帖子元素: "WebElement", 帖子内容: str, 浏览器ID: str = None, log_func=None, debug=False) -> bool:
    """
    给帖子发布者发送私信
    
    流程：先访问主页，然后发送私信
    
    Args:
        driver: WebDriver实例
        帖子元素: 帖子的DOM元素
        帖子内容: 帖子的文本内容（用于AI生成私信）
        浏览器ID: 浏览器ID（用于数据库记录）
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
        # 1. 先访问用户主页
        成功, 用户ID = 点击帖子发布者头像(driver, 帖子元素, 浏览器ID, log_func, debug)
        
        if not 成功 or not 用户ID:
            log("访问发布者主页失败")
            return False
        
        # 记录访问主页后的URL
        主页URL = driver.current_url
        if debug:
            log(f"[调试] 主页URL: {主页URL}")
        
        # 2. 在主页上发送私信
        result = _在主页私信发布者(driver, 用户ID, 帖子内容, 浏览器ID, log_func, debug)
        
        # 记录私信后的URL
        私信后URL = driver.current_url
        if debug:
            log(f"[调试] 私信后URL: {私信后URL}")
            if 主页URL != 私信后URL:
                log(f"[调试] ⚠️ URL发生了变化！")
        
        # 3. 返回上一页
        if debug:
            log("[调试] 执行 driver.back()...")
        
        driver.back()
        time.sleep(random.uniform(2, 4))
        
        # 记录返回后的URL
        返回后URL = driver.current_url
        if debug:
            log(f"[调试] 返回后URL: {返回后URL}")
        
        return result
        
    except Exception as e:
        log(f"私信帖子发布者失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

def _在主页私信发布者(driver: "WebDriver", 用户ID: str, 帖子内容: str, 浏览器ID: str = None, log_func=None, debug=False) -> bool:
    """
    在用户主页上发送私信（假设已经在主页上）
    
    Args:
        driver: WebDriver实例
        用户ID: 用户ID
        帖子内容: 帖子的文本内容（用于AI生成私信）
        浏览器ID: 浏览器ID（用于数据库记录）
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
        # 检查数据库去重（私信动作）
        if _db and 浏览器ID and 用户ID:
            try:
                if not _db.can_interact(浏览器ID, f"user_{用户ID}", "message"):
                    log("跳过（已私信过该用户）")
                    return False
            except Exception as e:
                if debug:
                    log(f"数据库检查失败: {e}")
        
        # 1. 在主页上查找"Message"按钮
        message_selectors = [
            "[aria-label='Message']",  # 包括 div[role='button'] 和 a 标签
            "[aria-label='发消息']",
            "a[href*='/messages/']",
        ]
        
        message_button = None
        for selector in message_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if debug:
                    log(f"[调试] 选择器 '{selector}' 找到 {len(elements)} 个元素")
                for el in elements:
                    if el.is_displayed():
                        message_button = el
                        if debug:
                            log(f"[调试] ✓ 找到可见的私信按钮")
                        break
                if message_button:
                    break
            except Exception as e:
                if debug:
                    log(f"[调试] 选择器 '{selector}' 失败: {e}")
                continue
        
        if not message_button:
            log("未找到私信按钮")
            return False
        
        # 2. 点击私信按钮
        if debug:
            log("点击私信按钮...")
        
        try:
            driver.execute_script("arguments[0].click();", message_button)
        except:
            message_button.click()
        
        # 等待聊天窗口出现（用户说要等几秒才有聊天窗口）
        if debug:
            log("等待聊天窗口出现...")
        time.sleep(random.uniform(3, 5))
        
        # 3. 生成私信内容
        if debug:
            log("生成私信内容...")
        
        try:
            私信内容 = AI生成私信内容(帖子内容)
        except:
            私信内容 = ""
        
        if not 私信内容:
            log("AI生成私信失败")
            return False
        
        # 移除表情符号
        import re
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U00002600-\U000026FF"
            "]+",
            flags=re.UNICODE
        )
        私信内容 = emoji_pattern.sub('', 私信内容).strip()
        
        if not 私信内容:
            log("私信内容为空")
            return False
        
        log(f"私信内容: {私信内容[:50]}...")
        
        # 4. 查找输入框
        input_selectors = [
            "[aria-label='Message'][contenteditable='true'][role='textbox']",
            "[data-lexical-editor='true'][contenteditable='true']",
            "[aria-label='Message'][contenteditable='true']",
            "[aria-label='Message']",
            "[placeholder*='message' i]",
            "[contenteditable='true'][role='textbox']",
        ]
        
        input_box = None
        for selector in input_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        input_box = el
                        break
                if input_box:
                    break
            except:
                continue
        
        if not input_box:
            log("未找到私信输入框")
            return False
        
        # 5. 输入私信内容
        if debug:
            log("输入私信内容...")
        
        try:
            driver.execute_script("arguments[0].focus();", input_box)
        except:
            pass
        
        time.sleep(0.5)
        
        # 逐字输入
        for char in 私信内容:
            input_box.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        time.sleep(random.uniform(1, 2))
        
        # 6. 发送私信
        if debug:
            log("发送私信...")
        
        input_box.send_keys(Keys.RETURN)
        
        log("✓ 私信已发送")
        
        # 等待消息发送
        time.sleep(random.uniform(2, 3))
        
        # 关闭聊天窗口
        try:
            close_button = driver.find_element(By.CSS_SELECTOR, "[aria-label='Close chat']")
            if close_button.is_displayed():
                close_button.click()
                if debug:
                    log("✓ 已关闭聊天窗口")
                time.sleep(1)
        except:
            if debug:
                log("未找到关闭按钮，跳过")
        
        # 记录到数据库
        if _db and 浏览器ID and 用户ID:
            try:
                _db.record_interaction(
                    browser_id=浏览器ID,
                    post_url=f"user_{用户ID}",
                    action_type="message",
                    content=私信内容
                )
                if debug:
                    log("✓ 已记录到数据库")
            except Exception as e:
                if debug:
                    log(f"数据库记录失败: {e}")
        
        time.sleep(random.uniform(2, 4))
        
        return True
        
    except Exception as e:
        log(f"私信失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

def 加帖子发布者为好友(driver: "WebDriver", 帖子元素: "WebElement", 浏览器ID: str = None, log_func=None, debug=False) -> bool:
    """
    加帖子发布者为好友
    
    流程：先访问主页，然后加好友
    
    Args:
        driver: WebDriver实例
        帖子元素: 帖子的DOM元素
        浏览器ID: 浏览器ID（用于数据库记录）
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
        # 1. 先访问用户主页
        成功, 用户ID = 点击帖子发布者头像(driver, 帖子元素, 浏览器ID, log_func, debug)
        
        if not 成功 or not 用户ID:
            log("访问发布者主页失败")
            return False
        
        # 记录访问主页后的URL
        主页URL = driver.current_url
        if debug:
            log(f"[调试] 主页URL: {主页URL}")
        
        # 2. 在主页上加好友
        result = _在主页加发布者为好友(driver, 用户ID, 浏览器ID, log_func, debug)
        
        # 记录加好友后的URL
        加好友后URL = driver.current_url
        if debug:
            log(f"[调试] 加好友后URL: {加好友后URL}")
            if 主页URL != 加好友后URL:
                log(f"[调试] ⚠️ URL发生了变化！")
        
        # 3. 返回上一页
        if debug:
            log("[调试] 执行 driver.back()...")
        
        driver.back()
        time.sleep(random.uniform(2, 4))
        
        # 记录返回后的URL
        返回后URL = driver.current_url
        if debug:
            log(f"[调试] 返回后URL: {返回后URL}")
        
        return result
        
    except Exception as e:
        log(f"加帖子发布者为好友失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

def _在主页加发布者为好友(driver: "WebDriver", 用户ID: str, 浏览器ID: str = None, log_func=None, debug=False) -> bool:
    """
    在用户主页上加好友（假设已经在主页上）
    
    Args:
        driver: WebDriver实例
        用户ID: 用户ID
        浏览器ID: 浏览器ID（用于数据库记录）
        log_func: 日志函数
        debug: 是否开启调试模式
    
    Returns:
        是否成功
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        # 检查数据库去重（加好友动作）
        if _db and 浏览器ID and 用户ID:
            try:
                if not _db.can_interact(浏览器ID, f"user_{用户ID}", "add_friend"):
                    log("跳过（已加过该用户为好友）")
                    return False
            except Exception as e:
                if debug:
                    log(f"数据库检查失败: {e}")
        
        # 1. 在主页上查找"Add Friend"按钮
        add_friend_selectors = [
            "[aria-label='Add Friend']",
            "[aria-label='加为好友']",
            "[aria-label='添加好友']",
        ]
        
        add_friend_button = None
        for selector in add_friend_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        add_friend_button = el
                        break
                if add_friend_button:
                    break
            except:
                continue
        
        if not add_friend_button:
            log("未找到加好友按钮（可能已是好友）")
            return False
        
        # 2. 点击加好友按钮
        if debug:
            log("点击加好友按钮...")
        
        try:
            driver.execute_script("arguments[0].click();", add_friend_button)
        except:
            add_friend_button.click()
        
        log("✓ 已发送好友请求")
        
        # 等待2-3秒
        time.sleep(random.uniform(2, 3))
        
        # 尝试关闭可能出现的对话框
        try:
            close_selectors = [
                "[aria-label='Close']",
                "[aria-label='关闭']",
                "div[role='button'][aria-label*='Close' i]",
            ]
            
            for selector in close_selectors:
                try:
                    close_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in close_buttons:
                        if btn.is_displayed():
                            btn.click()
                            if debug:
                                log("✓ 已关闭对话框")
                            time.sleep(1)
                            break
                except:
                    continue
        except:
            if debug:
                log("未找到对话框，跳过")
        
        # 记录到数据库
        if _db and 浏览器ID and 用户ID:
            try:
                _db.record_interaction(
                    browser_id=浏览器ID,
                    post_url=f"user_{用户ID}",
                    action_type="add_friend"
                )
                if debug:
                    log("✓ 已记录到数据库")
            except Exception as e:
                if debug:
                    log(f"数据库记录失败: {e}")
        
        time.sleep(random.uniform(2, 4))
        
        return True
        
    except Exception as e:
        log(f"加好友失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False


# ==================== 评论互动功能 ====================

# ==================== 用户信息提取（参考评论区挖掘模块）====================

def _提取评论用户信息(driver: "WebDriver", 评论元素: "WebElement", log_func=None) -> Optional[Dict[str, str]]:
    """
    从评论元素提取用户信息（使用评论区挖掘的方法）
    
    Args:
        driver: WebDriver实例
        评论元素: 评论元素
        log_func: 日志函数
    
    Returns:
        用户信息字典 {user_id, user_name, profile_url}
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
    
    try:
        # 策略1：直接在评论元素内部查找用户链接
        user_links = _在元素内查找用户链接(评论元素)
        
        if user_links:
            最佳链接 = _选择最佳用户链接(user_links)
            if 最佳链接:
                return _从链接提取用户信息(最佳链接, log_func)
        
        # 策略2：在父容器中查找用户链接
        user_links = _在父容器查找用户链接(评论元素)
        
        if user_links:
            最佳链接 = _选择最佳用户链接(user_links)
            if 最佳链接:
                return _从链接提取用户信息(最佳链接, log_func)
        
        # 策略3：在评论弹窗中通过位置匹配查找用户链接
        user_links = _在弹窗中按位置查找用户链接(driver, 评论元素, log_func)
        
        if user_links:
            最佳链接 = _选择最佳用户链接(user_links)
            if 最佳链接:
                return _从链接提取用户信息(最佳链接, log_func)
        
        return None
        
    except Exception as e:
        if log_func:
            log(f"提取用户信息异常: {e}")
        return None

def _在元素内查找用户链接(元素: "WebElement") -> List["WebElement"]:
    """在元素内部查找用户链接"""
    from selenium.webdriver.common.by import By
    
    try:
        user_links = []
        user_links.extend(元素.find_elements(By.CSS_SELECTOR, "a[href*='/user/']"))
        user_links.extend(元素.find_elements(By.CSS_SELECTOR, "a[href*='/profile.php']"))
        
        # 查找所有可能的用户链接
        all_links = 元素.find_elements(By.CSS_SELECTOR, "a[role='link'], a[tabindex='0'], a[href^='https://www.facebook.com/']")
        for link in all_links:
            href = link.get_attribute("href") or ""
            if href and _是用户主页链接(href):
                user_links.append(link)
        
        # 如果没找到链接，尝试通过头像查找
        if not user_links:
            # 查找SVG image标签（Facebook新版头像）
            # 注意：xlink:href 需要转义冒号
            try:
                # 方法1：使用XPath查找SVG image标签
                images = 元素.find_elements(By.XPATH, ".//image[contains(@*[local-name()='href'], '_n.jpg')]")
                for img in images:
                    # 向上查找包含此图片的a标签
                    try:
                        parent = img
                        for _ in range(5):  # 最多向上5层
                            parent = parent.find_element(By.XPATH, "..")
                            if parent.tag_name == 'a':
                                href = parent.get_attribute("href") or ""
                                if href and _是用户主页链接(href):
                                    user_links.append(parent)
                                    break
                    except:
                        continue
            except:
                pass
            
            # 查找普通img标签
            try:
                imgs = 元素.find_elements(By.CSS_SELECTOR, "img[src*='fbcdn.net']")
                for img in imgs:
                    # 向上查找包含此图片的a标签
                    try:
                        parent = img
                        for _ in range(5):
                            parent = parent.find_element(By.XPATH, "..")
                            if parent.tag_name == 'a':
                                href = parent.get_attribute("href") or ""
                                if href and _是用户主页链接(href):
                                    user_links.append(parent)
                                    break
                    except:
                        continue
            except:
                pass
        
        return user_links
    except:
        return []

def _在父容器查找用户链接(元素: "WebElement") -> List["WebElement"]:
    """在父容器中查找用户链接"""
    from selenium.webdriver.common.by import By
    
    try:
        # 向上查找最多3层父容器
        current = 元素
        for level in range(3):
            try:
                parent = current.find_element(By.XPATH, "..")
                user_links = _在元素内查找用户链接(parent)
                if user_links:
                    return user_links
                current = parent
            except:
                break
        return []
    except:
        return []

def _在弹窗中按位置查找用户链接(driver: "WebDriver", 评论元素: "WebElement", log_func=None) -> List["WebElement"]:
    """在评论弹窗中通过位置匹配查找用户链接"""
    from selenium.webdriver.common.by import By
    
    try:
        # 获取评论元素的Y坐标
        评论Y坐标 = 评论元素.location['y']
        
        # 查找评论弹窗
        评论弹窗 = None
        dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog']")
        for dialog in dialogs:
            if dialog.is_displayed():
                评论弹窗 = dialog
                break
        
        if not 评论弹窗:
            return []
        
        # 在弹窗中查找所有用户链接
        all_links = []
        all_links.extend(评论弹窗.find_elements(By.CSS_SELECTOR, "a[href*='/user/']"))
        all_links.extend(评论弹窗.find_elements(By.CSS_SELECTOR, "a[href*='/profile.php']"))
        all_links.extend(评论弹窗.find_elements(By.CSS_SELECTOR, "a[role='link'][tabindex='0']"))
        
        # 去重
        seen_hrefs = set()
        unique_links = []
        for link in all_links:
            href = link.get_attribute("href") or ""
            if href and href not in seen_hrefs and _是用户主页链接(href):
                seen_hrefs.add(href)
                unique_links.append(link)
        
        # 查找距离评论最近的用户链接（Y坐标差距<150px）
        nearby_links = []
        for link in unique_links:
            try:
                链接Y坐标 = link.location['y']
                距离 = abs(链接Y坐标 - 评论Y坐标)
                
                # 链接必须在评论上方或同一行（±150px）
                if 距离 < 150:
                    user_name = link.text.strip()
                    if user_name and 2 <= len(user_name) <= 50:
                        nearby_links.append((距离, link))
            except:
                continue
        
        # 按距离排序，返回最近的链接
        if nearby_links:
            nearby_links.sort(key=lambda x: x[0])
            return [link for _, link in nearby_links]
        
        return []
    except:
        return []

def _选择最佳用户链接(user_links: List["WebElement"]) -> Optional["WebElement"]:
    """从用户链接列表中选择最佳的一个"""
    if not user_links:
        return None
    
    for link in user_links:
        try:
            user_name = link.text.strip()
            href = link.get_attribute("href") or ""
            
            # 检查用户名是否合理
            if not user_name or len(user_name) < 2 or len(user_name) > 50:
                continue
            
            # 排除明显不是用户名的文本
            if any(keyword in user_name.lower() for keyword in [
                'reply', 'like', 'share', 'comment', 'see more', 'show more',
                '回复', '点赞', '分享', '评论', '查看更多', '显示更多'
            ]):
                continue
            
            return link
        except:
            continue
    
    # 如果没有找到合适的，返回第一个
    return user_links[0] if user_links else None

def _从链接提取用户信息(链接: "WebElement", log_func=None) -> Optional[Dict[str, str]]:
    """从用户链接提取用户信息"""
    try:
        profile_url = 链接.get_attribute("href")
        user_name = 链接.text.strip()
        
        if log_func:
            log_func(f"找到用户: {user_name}")
            log_func(f"profile_url: {profile_url[:100] if profile_url else 'None'}")
        
        # 提取用户ID
        user_id = _提取用户ID(profile_url)
        
        if log_func:
            log_func(f"user_id: {user_id if user_id else '(提取失败)'}")
        
        if not user_id or not user_name:
            return None
        
        return {
            "user_id": user_id,
            "user_name": user_name,
            "profile_url": profile_url
        }
    except:
        return None

def _是用户主页链接(href: str) -> bool:
    """检查是否是用户主页链接"""
    if not href:
        return False
    
    # 明确的用户链接格式
    if "/user/" in href or "profile.php?id=" in href:
        return True
    
    # Facebook用户名格式
    if href.startswith("https://www.facebook.com/"):
        # 排除明显不是用户主页的链接
        if any(x in href for x in [
            "/reel/", "/photo/", "/posts/", "/videos/", "/watch/", 
            "/groups/", "/pages/", "/events/", "/marketplace/",
            "/search/",  # 排除搜索链接
            "/hashtag/"  # 排除hashtag链接
        ]):
            return False
        
        # 检查是否是简单的用户名格式
        path = href.replace("https://www.facebook.com/", "").split("/")[0].split("?")[0]
        if path and len(path) > 2 and not path.isdigit():
            return True
    
    return False

def _提取用户ID(profile_url: str) -> Optional[str]:
    """从profile URL提取用户ID"""
    if not profile_url:
        return None
    
    try:
        # 格式1: /user/123456789/
        if "/user/" in profile_url:
            user_id = profile_url.split("/user/")[1].split("/")[0].split("?")[0]
            if user_id:
                return user_id
        
        # 格式2: profile.php?id=123456789
        if "profile.php?id=" in profile_url:
            user_id = profile_url.split("id=")[1].split("&")[0]
            if user_id:
                return user_id
        
        # 格式3: /username
        if profile_url.startswith("https://www.facebook.com/"):
            username = profile_url.replace("https://www.facebook.com/", "").split("/")[0].split("?")[0]
            if username and len(username) > 2:
                return username
        
        return None
    except:
        return None

def _提取帖子作者(driver: "WebDriver", log_func=None) -> Optional[str]:
    """
    提取帖子作者名字（用于过滤作者自己的评论）
    
    Args:
        driver: WebDriver实例
        log_func: 日志函数
    
    Returns:
        作者名字，如果提取失败返回None
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
    
    try:
        # 查找评论弹窗
        评论弹窗 = None
        try:
            dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog']")
            for dialog in dialogs:
                if dialog.is_displayed():
                    评论弹窗 = dialog
                    break
        except:
            pass
        
        if not 评论弹窗:
            return None
        
        # 查找作者名字元素
        # 方法1: 通过h2标签查找
        try:
            h2_elements = 评论弹窗.find_elements(By.CSS_SELECTOR, "h2[dir='auto']")
            for h2 in h2_elements:
                text = h2.text.strip()
                # 检查是否包含 "'s Post" 或 "'s post"
                if "'s Post" in text or "'s post" in text:
                    # 提取作者名字（移除 "'s Post" 后缀）
                    作者名 = text.replace("'s Post", "").replace("'s post", "").strip()
                    if log_func:
                        log(f"[调试-作者] 找到作者: {作者名}")
                    return 作者名
        except:
            pass
        
        # 方法2: 通过span标签查找
        try:
            span_elements = 评论弹窗.find_elements(By.CSS_SELECTOR, "span[dir='auto']")
            for span in span_elements:
                text = span.text.strip()
                if "'s Post" in text or "'s post" in text:
                    作者名 = text.replace("'s Post", "").replace("'s post", "").strip()
                    if log_func:
                        log(f"[调试-作者] 找到作者: {作者名}")
                    return 作者名
        except:
            pass
        
        return None
        
    except Exception as e:
        if log_func:
            log(f"[调试-作者] 提取失败: {e}")
        return None

# ==================== 评论互动功能 ====================


def 回复评论(driver: "WebDriver", 评论元素: "WebElement", 评论内容: str, 浏览器ID: str = None, log_func=None, debug=False) -> bool:
    """
    回复评论
    
    Args:
        driver: WebDriver实例
        评论元素: 评论的DOM元素
        评论内容: 评论的文本内容（用于AI生成回复）
        浏览器ID: 浏览器ID（用于数据库记录）
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
        # 1. 查找"Reply"按钮
        reply_selectors = [
            "[aria-label='Reply']",
            "[aria-label='回复']",
            "a:has-text('Reply')",
            "span:has-text('Reply')",
        ]
        
        reply_button = None
        for selector in reply_selectors:
            try:
                elements = 评论元素.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        reply_button = el
                        break
                if reply_button:
                    break
            except:
                continue
        
        if not reply_button:
            log("未找到回复按钮")
            return False
        
        # 2. 点击回复按钮
        if debug:
            log("点击回复按钮...")
        
        try:
            driver.execute_script("arguments[0].click();", reply_button)
        except:
            reply_button.click()
        
        time.sleep(random.uniform(1, 2))
        
        # 3. 生成回复内容
        if debug:
            log("生成回复内容...")
        
        try:
            回复内容 = AI生成回复内容(评论内容)
        except:
            回复内容 = ""
        
        if not 回复内容:
            log("AI生成回复失败")
            return False
        
        # 移除表情符号
        import re
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U00002600-\U000026FF"
            "]+",
            flags=re.UNICODE
        )
        回复内容 = emoji_pattern.sub('', 回复内容).strip()
        
        if not 回复内容:
            log("回复内容为空")
            return False
        
        log(f"回复内容: {回复内容[:50]}...")
        
        # 4. 查找回复输入框（在评论元素附近）
        input_selectors = [
            "[aria-label='Write a reply']",
            "[aria-label='写回复']",
            "[placeholder*='reply' i]",
            "[contenteditable='true'][role='textbox']",
        ]
        
        input_box = None
        
        # 先在评论元素内查找
        for selector in input_selectors:
            try:
                elements = 评论元素.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        input_box = el
                        break
                if input_box:
                    break
            except:
                continue
        
        # 如果没找到，在整个页面查找最近的
        if not input_box:
            评论y = 评论元素.location['y']
            
            for selector in input_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    最近输入框 = None
                    最小距离 = float('inf')
                    
                    for el in elements:
                        if el.is_displayed():
                            el_y = el.location['y']
                            距离 = abs(el_y - 评论y)
                            if 距离 < 最小距离 and 距离 < 500:
                                最小距离 = 距离
                                最近输入框 = el
                    
                    if 最近输入框:
                        input_box = 最近输入框
                        break
                except:
                    continue
        
        if not input_box:
            log("未找到回复输入框")
            return False
        
        # 5. 滚动到输入框
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_box)
        time.sleep(0.5)
        
        # 6. 输入回复内容
        if debug:
            log("输入回复内容...")
        
        try:
            driver.execute_script("arguments[0].focus();", input_box)
        except:
            pass
        
        time.sleep(0.5)
        
        # 逐字输入
        for char in 回复内容:
            input_box.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        time.sleep(random.uniform(1, 2))
        
        # 7. 发送回复
        if debug:
            log("发送回复...")
        
        input_box.send_keys(Keys.RETURN)
        
        log("✓ 回复已发送")
        
        # 记录到数据库（使用评论内容的hash作为ID）
        if _db and 浏览器ID:
            try:
                import hashlib
                评论ID = hashlib.md5(评论内容.encode()).hexdigest()[:16]
                
                _db.record_interaction(
                    browser_id=浏览器ID,
                    post_url=f"comment_{评论ID}",
                    action_type="reply_comment",
                    content=回复内容
                )
                if debug:
                    log("✓ 已记录到数据库")
            except Exception as e:
                if debug:
                    log(f"数据库记录失败: {e}")
        
        time.sleep(random.uniform(2, 4))
        
        return True
        
    except Exception as e:
        log(f"回复评论失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

def 点击评论者头像(driver: "WebDriver", 评论元素: "WebElement", 浏览器ID: str = None, log_func=None, debug=False) -> Tuple[bool, Optional[str]]:
    """
    点击评论者的头像，访问其主页
    
    使用评论区挖掘模块的用户提取方法
    
    Args:
        driver: WebDriver实例
        评论元素: 评论的DOM元素
        浏览器ID: 浏览器ID（用于数据库记录）
        log_func: 日志函数
        debug: 是否开启调试模式
    
    Returns:
        (是否成功, 用户ID)
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        # 使用评论区挖掘的方法提取用户信息
        用户信息 = _提取评论用户信息(driver, 评论元素, log_func if debug else None)
        
        if not 用户信息:
            log("未找到评论者信息")
            return False, None
        
        用户ID = 用户信息.get('user_id')
        用户名 = 用户信息.get('user_name')
        用户链接 = 用户信息.get('profile_url')
        
        if debug:
            log(f"找到评论者: {用户名}")
            log(f"用户ID: {用户ID}")
            log(f"用户链接: {用户链接}")
        
        # 提取帖子作者并过滤（排除作者自己的评论）
        帖子作者 = _提取帖子作者(driver, log_func if debug else None)
        if 帖子作者 and 用户名:
            # 检查用户名是否与作者名字匹配
            用户名_清理 = 用户名.strip()
            作者名_清理 = 帖子作者.replace("'s Post", "").replace("'s post", "").strip()
            
            if debug:
                log(f"帖子作者: {作者名_清理}")
                log(f"评论者: {用户名_清理}")
            
            # 匹配检查
            if 用户名_清理 == 作者名_清理 or 作者名_清理 in 用户名_清理:
                log(f"跳过：这是帖子作者的评论（{用户名_清理}）")
                return False, None
        
        # 检查数据库去重
        if _db and 浏览器ID and 用户ID:
            try:
                if not _db.can_interact(浏览器ID, f"user_{用户ID}", "visit_profile"):
                    log("跳过（已访问过该用户主页）")
                    return False, 用户ID
            except Exception as e:
                if debug:
                    log(f"数据库检查失败: {e}")
        
        # 查找用户链接元素（包含comment_id的链接）
        if debug:
            log("查找用户链接元素...")
        
        用户链接元素 = None
        
        # 策略1：先在评论元素内查找（最精确）
        try:
            links = 评论元素.find_elements(By.CSS_SELECTOR, "a")
            
            if debug:
                log(f"  在评论元素内找到 {len(links)} 个链接")
            
            # 先尝试查找包含comment_id的链接
            候选链接_有comment_id = []
            候选链接_无comment_id = []
            
            for link in links:
                href = link.get_attribute("href") or ""
                text = link.text.strip()
                
                # 必须是Facebook链接
                if not href.startswith("https://www.facebook.com/"):
                    continue
                
                # 排除hashtag链接
                if "/hashtag/" in href:
                    continue
                
                # 排除其他非用户主页链接
                if any(x in href for x in [
                    "/reel/", "/photo/", "/posts/", "/videos/", "/watch/", 
                    "/groups/", "/pages/", "/events/", "/marketplace/", "/share/"
                ]):
                    continue
                
                # 必须有用户名文本（这是用户名链接的特征）
                if not text or len(text) < 2:
                    continue
                
                # 排除明显不是用户名的文本
                if any(keyword in text.lower() for keyword in [
                    'like', 'reply', 'share', 'comment', 'see more', 'show more',
                    '点赞', '回复', '分享', '评论', '查看更多', 'http', 'www', '1d', '2d', '3d', '1h', '2h'
                ]):
                    if debug:
                        log(f"  跳过非用户名文本: {text}")
                    continue
                
                # 排除以#开头的文本（hashtag）
                if text.startswith('#'):
                    if debug:
                        log(f"  跳过hashtag文本: {text}")
                    continue
                
                # 排除时间文本（如 "26w", "32w", "1d", "2h" 等）
                import re
                if re.match(r'^\d+[wdhms]$', text.lower()):
                    if debug:
                        log(f"  跳过时间文本: {text}")
                    continue
                
                # 分类：包含comment_id的和不包含的
                if "comment_id=" in href:
                    候选链接_有comment_id.append((link, href, text))
                    if debug:
                        log(f"  ✓ 找到用户名链接(有comment_id): {text} -> {href[:100]}...")
                else:
                    候选链接_无comment_id.append((link, href, text))
                    if debug:
                        log(f"  ✓ 找到用户名链接(无comment_id): {text} -> {href[:100]}...")
            
            # 优先选择包含comment_id的链接
            if 候选链接_有comment_id:
                候选链接 = 候选链接_有comment_id
                if debug:
                    log(f"  使用包含comment_id的链接")
            elif 候选链接_无comment_id:
                候选链接 = 候选链接_无comment_id
                if debug:
                    log(f"  使用不包含comment_id的链接（评论元素内唯一可用）")
            else:
                候选链接 = []
            
            # 选择第一个链接（评论元素内的链接就是当前评论者的）
            if 候选链接:
                用户链接元素 = 候选链接[0][0]
                if debug:
                    log(f"  选择评论元素内的链接: {候选链接[0][2]}")
        except Exception as e:
            if debug:
                log(f"  在评论元素内查找失败: {e}")
        
        # 策略2：如果在评论元素内找不到，扩大到评论弹窗
        if not 用户链接元素:
            try:
                if debug:
                    log("  在评论元素内未找到，扩大到评论弹窗...")
                
                # 先找到评论弹窗
                评论弹窗 = None
                dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog']")
                for dialog in dialogs:
                    if dialog.is_displayed():
                        评论弹窗 = dialog
                        break
                
                if not 评论弹窗:
                    if debug:
                        log("  未找到评论弹窗")
                else:
                    links = 评论弹窗.find_elements(By.CSS_SELECTOR, "a")
                    
                    if debug:
                        log(f"  在评论弹窗中找到 {len(links)} 个链接")
                    
                    # 过滤出包含comment_id的链接
                    候选链接 = []
                    
                    for link in links:
                        href = link.get_attribute("href") or ""
                        text = link.text.strip()
                        
                        # 必须包含comment_id参数
                        if "comment_id=" not in href:
                            continue
                        
                        # 必须是Facebook链接
                        if not href.startswith("https://www.facebook.com/"):
                            continue
                        
                        # 排除 reel 链接
                        if "/reel/" in href:
                            continue
                        
                        # 必须有用户名文本（不能是"无文本"或时间文本）
                        if not text or len(text) < 2:
                            continue
                        
                        # 排除时间文本（如 "26w", "32w", "1d", "2h" 等）
                        import re
                        if re.match(r'^\d+[wdhms]$', text.lower()):
                            continue
                        
                        # 排除非用户名文本
                        if any(keyword in text.lower() for keyword in [
                            'like', 'reply', 'share', 'comment', 'see more', 'show more',
                            '点赞', '回复', '分享', '评论', '查看更多', 'http', 'www'
                        ]):
                            continue
                        
                        # 这是一个包含comment_id的用户名链接
                        候选链接.append((link, href, text))
                        if debug:
                            log(f"  ✓ 找到用户名链接: {text} -> {href[:100]}...")
                    
                    # 选择最佳链接
                    if 候选链接:
                        # 优先选择用户名匹配的链接
                        匹配用户名的链接 = [l for l in 候选链接 if 用户名 and 用户名.lower() in l[2].lower()]
                        if 匹配用户名的链接:
                            用户链接元素 = 匹配用户名的链接[0][0]
                            if debug:
                                log(f"  选择匹配用户名的链接: {匹配用户名的链接[0][2]}")
                        else:
                            用户链接元素 = 候选链接[0][0]
                            if debug:
                                log(f"  选择第一个用户名链接: {候选链接[0][2]}")
            except Exception as e:
                if debug:
                    log(f"  在评论弹窗中查找失败: {e}")
                    import traceback
                    traceback.print_exc()
        
        # 如果还是找不到，输出调试信息
        if not 用户链接元素:
            if debug:
                log(f"  未找到包含comment_id的用户名链接")
                
                # 输出评论元素内所有包含comment_id的链接
                try:
                    log(f"  === 评论元素内的链接 ===")
                    all_comment_links = []
                    for link in 评论元素.find_elements(By.CSS_SELECTOR, "a"):
                        href = link.get_attribute("href") or ""
                        if "comment_id=" in href:
                            all_comment_links.append(link)
                    
                    log(f"  评论元素内包含comment_id的链接数: {len(all_comment_links)}")
                    for idx, link in enumerate(all_comment_links[:3]):
                        href = link.get_attribute("href") or ""
                        text = link.text.strip()
                        log(f"    链接 #{idx + 1}: {text or '(无文本)'}")
                        log(f"      href: {href[:120]}...")
                        log(f"      有文本: {bool(text)}")
                        log(f"      包含用户ID: {用户ID in href if 用户ID else False}")
                        log(f"      包含用户名: {用户名.lower() in href.lower() if 用户名 else False}")
                except:
                    pass
                
                # 输出评论弹窗内所有包含comment_id的链接
                try:
                    log(f"  === 评论弹窗内的链接 ===")
                    评论弹窗 = None
                    dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog']")
                    for dialog in dialogs:
                        if dialog.is_displayed():
                            评论弹窗 = dialog
                            break
                    
                    if 评论弹窗:
                        all_comment_links = []
                        for link in 评论弹窗.find_elements(By.CSS_SELECTOR, "a"):
                            href = link.get_attribute("href") or ""
                            if "comment_id=" in href:
                                all_comment_links.append(link)
                        
                        log(f"  评论弹窗内包含comment_id的链接数: {len(all_comment_links)}")
                        for idx, link in enumerate(all_comment_links[:10]):  # 显示前10个
                            href = link.get_attribute("href") or ""
                            text = link.text.strip()
                            log(f"    链接 #{idx + 1}: {text or '(无文本)'}")
                            log(f"      href: {href[:120]}...")
                            log(f"      有文本: {bool(text)}")
                            log(f"      包含用户ID '{用户ID}': {用户ID in href if 用户ID else False}")
                            log(f"      包含用户名 '{用户名}': {用户名.lower() in href.lower() if 用户名 else False}")
                            log(f"      包含用户名(文本): {用户名.lower() in text.lower() if 用户名 and text else False}")
                except:
                    pass
            
        # 如果找不到链接元素，报错（不使用URL访问）
        if not 用户链接元素:
            if debug:
                log(f"  未找到包含comment_id的用户名链接")
                log(f"  提取的用户信息：")
                log(f"    用户ID: {用户ID}")
                log(f"    用户名: {用户名}")
                
                # 输出评论元素内所有包含comment_id的链接
                try:
                    log(f"  === 评论元素内的链接 ===")
                    all_comment_links = []
                    for link in 评论元素.find_elements(By.CSS_SELECTOR, "a"):
                        href = link.get_attribute("href") or ""
                        if "comment_id=" in href:
                            all_comment_links.append(link)
                    
                    log(f"  评论元素内包含comment_id的链接数: {len(all_comment_links)}")
                    for idx, link in enumerate(all_comment_links[:3]):
                        href = link.get_attribute("href") or ""
                        text = link.text.strip()
                        log(f"    链接 #{idx + 1}: {text or '(无文本)'}")
                        log(f"      href: {href[:120]}...")
                        log(f"      有文本: {bool(text)}")
                        log(f"      包含用户ID: {用户ID in href if 用户ID else False}")
                        log(f"      包含用户名: {用户名.lower() in href.lower() if 用户名 else False}")
                except:
                    pass
                
                # 输出评论弹窗内所有包含comment_id的链接
                try:
                    log(f"  === 评论弹窗内的链接 ===")
                    评论弹窗 = None
                    dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog']")
                    for dialog in dialogs:
                        if dialog.is_displayed():
                            评论弹窗 = dialog
                            break
                    
                    if 评论弹窗:
                        all_comment_links = []
                        for link in 评论弹窗.find_elements(By.CSS_SELECTOR, "a"):
                            href = link.get_attribute("href") or ""
                            if "comment_id=" in href:
                                all_comment_links.append(link)
                        
                        log(f"  评论弹窗内包含comment_id的链接数: {len(all_comment_links)}")
                        for idx, link in enumerate(all_comment_links[:10]):  # 显示前10个
                            href = link.get_attribute("href") or ""
                            text = link.text.strip()
                            log(f"    链接 #{idx + 1}: {text or '(无文本)'}")
                            log(f"      href: {href[:120]}...")
                            log(f"      有文本: {bool(text)}")
                            log(f"      包含用户ID '{用户ID}': {用户ID in href if 用户ID else False}")
                            log(f"      包含用户名 '{用户名}': {用户名.lower() in href.lower() if 用户名 else False}")
                            log(f"      包含用户名(文本): {用户名.lower() in text.lower() if 用户名 and text else False}")
                except:
                    pass
            
            log("未找到可点击的用户名链接（需要包含comment_id参数且有用户名文本）")
            return False, None
        
        # 点击链接访问主页
        if debug:
            log("  点击链接访问主页...")
        
        # 记录当前URL
        当前URL = driver.current_url
        
        try:
            # 滚动到链接
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 用户链接元素)
            time.sleep(0.5)
            
            # 点击链接
            try:
                driver.execute_script("arguments[0].click();", 用户链接元素)
            except:
                用户链接元素.click()
            
            # 等待页面跳转
            time.sleep(random.uniform(3, 6))
            
            # 验证是否跳转成功
            新URL = driver.current_url
            if 新URL == 当前URL:
                if debug:
                    log(f"  点击后URL未变化，可能点击失败")
                    log(f"  当前URL: {当前URL}")
                log("点击链接失败（URL未变化）")
                return False, None
            
        except Exception as e:
            log(f"点击链接失败: {e}")
            return False, None
        
        log("✓ 已访问评论者主页")
        
        # 记录到数据库
        if _db and 浏览器ID and 用户ID:
            try:
                _db.record_interaction(
                    browser_id=浏览器ID,
                    post_url=f"user_{用户ID}",
                    action_type="visit_profile"
                )
                if debug:
                    log("✓ 已记录到数据库")
            except Exception as e:
                if debug:
                    log(f"数据库记录失败: {e}")
        
        # 模拟浏览主页（真人滚动）
        浏览时长 = random.uniform(5, 15)
        if debug:
            log(f"浏览主页 {浏览时长:.1f} 秒...")
        
        # 导入滚动工具
        try:
            from tasks.自动化工具 import 真人阅读式滚动, 鼠标滚轮滚动
        except ImportError:
            from 自动化工具 import 真人阅读式滚动, 鼠标滚轮滚动
        
        # 真人阅读式滚动（模拟浏览主页内容）
        try:
            滚动距离 = random.randint(300, 800)
            if debug:
                log(f"  真人滚动浏览 {滚动距离} 像素...")
            真人阅读式滚动(driver, 滚动距离)
        except Exception as e:
            if debug:
                log(f"  滚动失败: {e}")
            # 如果滚动失败，至少等待一下
            time.sleep(浏览时长)
        
        # 注意：不返回上一页，让调用者决定后续操作
        # 返回成功和用户ID
        return True, 用户ID
        
    except Exception as e:
        log(f"点击头像失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False, None

def _在主页私信用户(driver: "WebDriver", 用户ID: str, 评论内容: str, 浏览器ID: str = None, log_func=None, debug=False) -> bool:
    """
    在用户主页上发送私信（假设已经在主页上）
    
    Args:
        driver: WebDriver实例
        用户ID: 用户ID
        评论内容: 评论的文本内容（用于AI生成私信）
        浏览器ID: 浏览器ID（用于数据库记录）
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
        # 检查数据库去重（私信动作）
        if _db and 浏览器ID and 用户ID:
            try:
                if not _db.can_interact(浏览器ID, f"user_{用户ID}", "message"):
                    log("跳过（已私信过该用户）")
                    return False
            except Exception as e:
                if debug:
                    log(f"数据库检查失败: {e}")
        
        # 1. 在主页上查找"Message"按钮
        message_selectors = [
            "[aria-label='Message']",
            "[aria-label='发消息']",
            "a[href*='/messages/']",
        ]
        
        message_button = None
        for selector in message_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        message_button = el
                        break
                if message_button:
                    break
            except:
                continue
        
        if not message_button:
            log("未找到私信按钮")
            return False
        
        # 2. 点击私信按钮
        if debug:
            log("点击私信按钮...")
        
        try:
            driver.execute_script("arguments[0].click();", message_button)
        except:
            message_button.click()
        
        time.sleep(random.uniform(2, 4))
        
        # 3. 生成私信内容
        if debug:
            log("生成私信内容...")
        
        try:
            私信内容 = AI生成私信内容(评论内容)
        except:
            私信内容 = ""
        
        if not 私信内容:
            log("AI生成私信失败")
            return False
        
        # 移除表情符号
        import re
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U00002600-\U000026FF"
            "]+",
            flags=re.UNICODE
        )
        私信内容 = emoji_pattern.sub('', 私信内容).strip()
        
        if not 私信内容:
            log("私信内容为空")
            return False
        
        log(f"私信内容: {私信内容[:50]}...")
        
        # 4. 查找输入框
        input_selectors = [
            "[aria-label='Message'][contenteditable='true'][role='textbox']",
            "[data-lexical-editor='true'][contenteditable='true']",
            "[aria-label='Message'][contenteditable='true']",
            "[aria-label='Message']",
            "[placeholder*='message' i]",
            "[contenteditable='true'][role='textbox']",
        ]
        
        input_box = None
        for selector in input_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        input_box = el
                        break
                if input_box:
                    break
            except:
                continue
        
        if not input_box:
            log("未找到私信输入框")
            return False
        
        # 5. 输入私信内容
        if debug:
            log("输入私信内容...")
        
        try:
            driver.execute_script("arguments[0].focus();", input_box)
        except:
            pass
        
        time.sleep(0.5)
        
        # 逐字输入
        for char in 私信内容:
            input_box.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        time.sleep(random.uniform(1, 2))
        
        # 6. 发送私信
        if debug:
            log("发送私信...")
        
        input_box.send_keys(Keys.RETURN)
        
        log("✓ 私信已发送")
        
        # 等待消息发送
        time.sleep(random.uniform(2, 3))
        
        # 关闭聊天窗口
        try:
            close_button = driver.find_element(By.CSS_SELECTOR, "[aria-label='Close chat']")
            if close_button.is_displayed():
                close_button.click()
                if debug:
                    log("✓ 已关闭聊天窗口")
                time.sleep(1)
        except:
            if debug:
                log("未找到关闭按钮，跳过")
        
        # 记录到数据库
        if _db and 浏览器ID and 用户ID:
            try:
                _db.record_interaction(
                    browser_id=浏览器ID,
                    post_url=f"user_{用户ID}",
                    action_type="message",
                    content=私信内容
                )
                if debug:
                    log("✓ 已记录到数据库")
            except Exception as e:
                if debug:
                    log(f"数据库记录失败: {e}")
        
        time.sleep(random.uniform(2, 4))
        
        return True
        
    except Exception as e:
        log(f"私信失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

def _在主页加好友(driver: "WebDriver", 用户ID: str, 浏览器ID: str = None, log_func=None, debug=False) -> bool:
    """
    在用户主页上加好友（假设已经在主页上）
    
    Args:
        driver: WebDriver实例
        用户ID: 用户ID
        浏览器ID: 浏览器ID（用于数据库记录）
        log_func: 日志函数
        debug: 是否开启调试模式
    
    Returns:
        是否成功
    """
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        # 检查数据库去重（加好友动作）
        if _db and 浏览器ID and 用户ID:
            try:
                if not _db.can_interact(浏览器ID, f"user_{用户ID}", "add_friend"):
                    log("跳过（已加过该用户为好友）")
                    return False
            except Exception as e:
                if debug:
                    log(f"数据库检查失败: {e}")
        
        # 1. 在主页上查找"Add Friend"按钮
        add_friend_selectors = [
            "[aria-label*='Add Friend' i]",  # 包含 "Add Friend" 的 aria-label
            "[aria-label='加为好友']",
            "[aria-label='添加好友']",
        ]
        
        add_friend_button = None
        for selector in add_friend_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        add_friend_button = el
                        break
                if add_friend_button:
                    break
            except:
                continue
        
        if not add_friend_button:
            log("未找到加好友按钮（可能已是好友）")
            return False
        
        # 2. 点击加好友按钮
        if debug:
            log("点击加好友按钮...")
        
        try:
            driver.execute_script("arguments[0].click();", add_friend_button)
        except:
            add_friend_button.click()
        
        log("✓ 已发送好友请求")
        
        # 等待按钮状态变化
        time.sleep(random.uniform(2, 3))
        
        # 尝试关闭可能弹出的对话框或确认框
        try:
            # 查找并关闭可能的对话框
            close_selectors = [
                "[aria-label='Close']",
                "[aria-label='关闭']",
                "[role='button'][aria-label*='Close' i]",
                "div[role='dialog'] button[aria-label*='Close' i]",
            ]
            
            for selector in close_selectors:
                try:
                    close_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in close_buttons:
                        if btn.is_displayed():
                            btn.click()
                            if debug:
                                log("✓ 已关闭弹窗")
                            time.sleep(1)
                            break
                except:
                    continue
        except:
            pass
        
        # 记录到数据库（使用好友管理表，与加好友.py保持一致）
        if _db and 浏览器ID and 用户ID:
            try:
                # 提取用户名称
                用户名称 = None
                try:
                    # 方法1: 从页面标题提取
                    title = driver.title
                    if title and title != "Facebook":
                        # 去掉 "(数字)" 前缀和 " | Facebook" 后缀
                        import re
                        title = re.sub(r'^\(\d+\)\s*', '', title)
                        用户名称 = title.replace(" | Facebook", "").strip()
                except:
                    pass
                
                # 如果没提取到，使用用户ID
                if not 用户名称:
                    用户名称 = 用户ID
                
                # 添加到好友管理表（与加好友.py保持一致）
                success = _db.add_friend(
                    browser_id=浏览器ID,
                    friend_id=用户ID,
                    friend_name=用户名称,
                    friend_profile_url=f"https://www.facebook.com/{用户ID}",
                    notes="评论互动-自动添加"
                )
                if success:
                    if debug:
                        log("✓ 已记录到好友管理表")
                else:
                    if debug:
                        log("⚠ 好友已存在，数据库未记录")
            except Exception as e:
                if debug:
                    log(f"数据库记录失败: {e}")
        
        time.sleep(random.uniform(1, 2))
        
        return True
        
    except Exception as e:
        log(f"加好友失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

def 私信评论者(driver: "WebDriver", 评论元素: "WebElement", 评论内容: str, 浏览器ID: str = None, log_func=None, debug=False) -> bool:
    """
    给评论者发送私信
    
    流程：先访问主页，然后发送私信
    
    Args:
        driver: WebDriver实例
        评论元素: 评论的DOM元素
        评论内容: 评论的文本内容（用于AI生成私信）
        浏览器ID: 浏览器ID（用于数据库记录）
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
        # 1. 先访问用户主页
        success, 用户ID = 点击评论者头像(driver, 评论元素, 浏览器ID, log_func, debug)
        
        if not success or not 用户ID:
            log("访问用户主页失败")
            return False
        
        # 记录访问主页后的URL
        主页URL = driver.current_url
        if debug:
            log(f"[调试] 主页URL: {主页URL}")
        
        # 2. 在主页上发送私信
        result = _在主页私信用户(driver, 用户ID, 评论内容, 浏览器ID, log_func, debug)
        
        # 记录私信后的URL
        私信后URL = driver.current_url
        if debug:
            log(f"[调试] 私信后URL: {私信后URL}")
            if 主页URL != 私信后URL:
                log(f"[调试] ⚠️ URL发生了变化！")
        
        # 3. 返回上一页
        if debug:
            log("[调试] 执行 driver.back()...")
        
        driver.back()
        time.sleep(random.uniform(2, 4))
        
        # 记录返回后的URL
        返回后URL = driver.current_url
        if debug:
            log(f"[调试] 返回后URL: {返回后URL}")
        
        return result
        
    except Exception as e:
        log(f"私信评论者失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

def 加评论者为好友(driver: "WebDriver", 评论元素: "WebElement", 浏览器ID: str = None, log_func=None, debug=False) -> bool:
    """
    加评论者为好友
    
    流程：先访问主页，然后加好友
    
    Args:
        driver: WebDriver实例
        评论元素: 评论的DOM元素
        浏览器ID: 浏览器ID（用于数据库记录）
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
        # 1. 先访问用户主页
        success, 用户ID = 点击评论者头像(driver, 评论元素, 浏览器ID, log_func, debug)
        
        if not success or not 用户ID:
            log("访问用户主页失败")
            return False
        
        # 记录访问主页后的URL
        主页URL = driver.current_url
        if debug:
            log(f"[调试] 主页URL: {主页URL}")
        
        # 2. 在主页上加好友
        result = _在主页加好友(driver, 用户ID, 浏览器ID, log_func, debug)
        
        # 记录加好友后的URL
        加好友后URL = driver.current_url
        if debug:
            log(f"[调试] 加好友后URL: {加好友后URL}")
            if 主页URL != 加好友后URL:
                log(f"[调试] ⚠️ URL发生了变化！")
        
        # 3. 返回上一页
        if debug:
            log("[调试] 执行 driver.back()...")
        
        driver.back()
        time.sleep(random.uniform(2, 4))
        
        # 记录返回后的URL
        返回后URL = driver.current_url
        if debug:
            log(f"[调试] 返回后URL: {返回后URL}")
        
        return result
        
    except Exception as e:
        log(f"加好友失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

# 保留旧的实现作为备用（已废弃）
def 私信评论者_旧版(driver: "WebDriver", 评论元素: "WebElement", 评论内容: str, 浏览器ID: str = None, log_func=None, debug=False) -> bool:
    """
    给评论者发送私信（旧版 - 已废弃，请使用新版）
    
    Args:
        driver: WebDriver实例
        评论元素: 评论的DOM元素
        评论内容: 评论的文本内容（用于AI生成私信）
        浏览器ID: 浏览器ID（用于数据库记录）
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
        # 1. 提取用户信息
        用户信息 = _提取评论用户信息(driver, 评论元素, log_func if debug else None)
        
        if not 用户信息:
            log("无法提取评论者信息")
            return False
        
        用户ID = 用户信息.get('user_id')
        用户链接 = 用户信息.get('profile_url')
        
        # 检查数据库去重（私信动作）
        if _db and 浏览器ID and 用户ID:
            try:
                if not _db.can_interact(浏览器ID, f"user_{用户ID}", "message"):
                    log("跳过（已私信过该用户）")
                    return False
            except Exception as e:
                if debug:
                    log(f"数据库检查失败: {e}")
        
        # 2. 访问用户主页
        if debug:
            log("访问用户主页...")
        
        driver.get(用户链接)
        time.sleep(random.uniform(3, 6))
        
        # 3. 在主页上查找"Message"按钮
        message_selectors = [
            "[aria-label='Message']",
            "[aria-label='发消息']",
            "a[href*='/messages/']",
        ]
        
        message_button = None
        for selector in message_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        message_button = el
                        break
                if message_button:
                    break
            except:
                continue
        
        if not message_button:
            log("未找到私信按钮")
            return False
        
        # 4. 点击私信按钮
        if debug:
            log("点击私信按钮...")
        
        try:
            driver.execute_script("arguments[0].click();", message_button)
        except:
            message_button.click()
        
        time.sleep(random.uniform(2, 4))
        
        # 5. 生成私信内容
        if debug:
            log("生成私信内容...")
        
        try:
            私信内容 = AI生成私信内容(评论内容)
        except:
            私信内容 = ""
        
        if not 私信内容:
            log("AI生成私信失败")
            return False
        
        # 移除表情符号
        import re
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U00002600-\U000026FF"
            "]+",
            flags=re.UNICODE
        )
        私信内容 = emoji_pattern.sub('', 私信内容).strip()
        
        if not 私信内容:
            log("私信内容为空")
            return False
        
        log(f"私信内容: {私信内容[:50]}...")
        
        # 6. 查找输入框
        input_selectors = [
            "[aria-label='Message'][contenteditable='true'][role='textbox']",
            "[data-lexical-editor='true'][contenteditable='true']",
            "[aria-label='Message'][contenteditable='true']",
            "[aria-label='Message']",
            "[placeholder*='message' i]",
            "[contenteditable='true'][role='textbox']",
        ]
        
        input_box = None
        for selector in input_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        input_box = el
                        break
                if input_box:
                    break
            except:
                continue
        
        if not input_box:
            log("未找到私信输入框")
            return False
        
        # 7. 输入私信内容
        if debug:
            log("输入私信内容...")
        
        try:
            driver.execute_script("arguments[0].focus();", input_box)
        except:
            pass
        
        time.sleep(0.5)
        
        # 逐字输入
        for char in 私信内容:
            input_box.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        time.sleep(random.uniform(1, 2))
        
        # 8. 发送私信
        if debug:
            log("发送私信...")
        
        input_box.send_keys(Keys.RETURN)
        
        log("✓ 私信已发送")
        
        # 记录到数据库
        if _db and 浏览器ID and 用户ID:
            try:
                _db.record_interaction(
                    browser_id=浏览器ID,
                    post_url=f"user_{用户ID}",
                    action_type="message",
                    content=私信内容
                )
                if debug:
                    log("✓ 已记录到数据库")
            except Exception as e:
                if debug:
                    log(f"数据库记录失败: {e}")
        
        time.sleep(random.uniform(2, 4))
        
        # 返回
        driver.back()
        time.sleep(random.uniform(2, 4))
        
        return True
        
    except Exception as e:
        log(f"私信失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

