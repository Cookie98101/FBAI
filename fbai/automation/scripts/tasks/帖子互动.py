"""
帖子互动功能
功能：
1. 打开帖子
2. 点赞帖子
3. 评论帖子
4. 生成随机评论

作者：Kiro AI
日期：2024
"""

import time
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .自动化工具 import AI评论_不带帖子内容
from .辅助_进入公共主页 import 读取主页名称, 读取主页链接

# 尝试导入比特浏览器 API（用于根据账号ID打开浏览器）
try:
    from bitbrowser_api import bit_browser
except ImportError:
    bit_browser = None

def 打开帖子(driver: "WebDriver", 帖子URL: str):
    """
    打开帖子页面
    
    Args:
        driver: Selenium WebDriver
        帖子URL: 帖子链接
    """
    driver.get(帖子URL)
    time.sleep(random.randint(3, 6))

def 生成中英文选择器(中文关键词: str, 英文关键词: str, 属性: str = "aria-label") -> list:
    """
    生成同时支持中英文的选择器列表
    
    Args:
        中文关键词: 中文关键词
        英文关键词: 英文关键词
        属性: 属性名（默认 aria-label）
    
    Returns:
        选择器列表
    """
    选择器 = []
    
    # 精确匹配
    选择器.append(f"[{属性}='{中文关键词}']")
    选择器.append(f"[{属性}='{英文关键词}']")
    
    # 包含匹配
    选择器.append(f"[{属性}*='{中文关键词}']")
    选择器.append(f"[{属性}*='{英文关键词}']")
    
    # 带 role 的选择器
    选择器.append(f"div[role='button'][{属性}*='{中文关键词}']")
    选择器.append(f"div[role='button'][{属性}*='{英文关键词}']")
    选择器.append(f"button[{属性}*='{中文关键词}']")
    选择器.append(f"button[{属性}*='{英文关键词}']")
    
    return 选择器

def 点赞帖子(driver: "WebDriver") -> bool:
    """
    点赞帖子 - 支持普通帖子和 Reels 视频，兼容中英文
    
    Args:
        driver: Selenium WebDriver
    
    Returns:
        是否成功
    """
    try:
        # 查找点赞按钮候选 - 包括 Reels 特定选择器，兼容中英文
        选择器列表 = [
            # 精确匹配 - 中英文
            "[aria-label='赞']",
            "[aria-label='Like']",
            "[aria-label='点赞']",
            "[data-testid='like-button']",
            
            # 包含匹配 - 中英文
            "[aria-label*='赞']",
            "[aria-label*='Like']",
            "[aria-label*='like']",
            "[aria-label*='点赞']",
            
            # 带 role 的选择器 - 中英文
            "div[role='button'][aria-label*='赞']",
            "div[role='button'][aria-label*='Like']",
            "div[role='button'][aria-label*='like']",
            "button[aria-label*='赞']",
            "button[aria-label*='Like']",
            "button[aria-label*='like']",
            
            # Reels 视频特定选择器
            "[aria-label*='Like'][aria-label*='reaction']",
            "div[aria-label*='Like']",
            "button[aria-label*='Like']",
            
            # 通用选择器
            "div[role='button'][aria-pressed]",
            "button[aria-pressed]"
        ]

        # 收集候选
        候选 = []
        for sel in 选择器列表:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elems:
                    try:
                        if el.is_displayed() and el not in 候选:
                            候选.append(el)
                    except:
                        continue
            except:
                continue

        print(f"[点赞] 候选按钮数量: {len(候选)}")
        if not 候选:
            print("[点赞] 未找到点赞按钮")
            return False

        def 已点赞状态(el) -> bool:
            try:
                aria_pressed = (el.get_attribute("aria-pressed") or "").lower()
                aria_label = (el.get_attribute("aria-label") or "").lower()
                # 兼容中英文的已赞状态检查
                return aria_pressed == "true" or \
                       ("取消" in aria_label or "unlike" in aria_label or \
                        "已赞" in aria_label or "已点赞" in aria_label)
            except:
                return False

        # 逐个候选尝试点击并校验状态
        for idx, btn in enumerate(候选, start=1):
            try:
                lbl = btn.get_attribute("aria-label") or ""
                prs = btn.get_attribute("aria-pressed") or ""
                print(f"[点赞] 尝试候选#{idx}: aria-label='{lbl}', aria-pressed='{prs}'")

                if 已点赞状态(btn):
                    print("[点赞] 检测到已赞状态（当前账号），跳过点击")
                    return True

                # 滚动到可见后点击
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                except:
                    pass
                time.sleep(0.5)
                
                # 尝试 JavaScript 点击
                点击成功 = False
                try:
                    driver.execute_script("arguments[0].click();", btn)
                    点击成功 = True
                    print(f"[点赞] 候选#{idx} JavaScript点击成功")
                except Exception as e:
                    print(f"[点赞] 候选#{idx} JavaScript点击失败: {e}")
                    # 备选：直接点击
                    try:
                        btn.click()
                        点击成功 = True
                        print(f"[点赞] 候选#{idx} 直接点击成功")
                    except Exception as e2:
                        print(f"[点赞] 候选#{idx} 直接点击失败: {e2}")

                if not 点击成功:
                    print(f"[点赞] ⚠️ 候选#{idx} 点击失败，尝试下一个")
                    continue

                # 点击后校验状态
                time.sleep(2)
                if 已点赞状态(btn):
                    print("[点赞] ✅ 点赞成功")
                    return True
                else:
                    print("[点赞] ⚠️ 点击后状态未变，尝试下一个候选")
            except Exception as e:
                print(f"[点赞] 候选#{idx} 操作异常: {e}")
                continue

        print("[点赞] ❌ 所有候选均未能成功点赞")
        return False

    except Exception as e:
        print(f"[点赞] ❌ 点赞失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def 评论帖子(driver: "WebDriver", 评论内容: str) -> bool:
    """
    评论帖子 - 支持普通帖子和 Reels 视频，兼容中英文
    
    Args:
        driver: Selenium WebDriver
        评论内容: 评论文本
    
    Returns:
        是否成功
    """
    try:
        # 第一步：暂停视频，防止自动滑到下一条
        print("[评论] 尝试暂停视频...")
        try:
            driver.execute_script("""
                var videos = document.querySelectorAll('video');
                videos.forEach(v => {
                    if (v && v.play) {
                        v.pause();
                    }
                });
            """)
            print("[评论] ✓ 视频已暂停")
        except:
            print("[评论] ⚠️ 暂停视频失败")
        
        time.sleep(1)
        
        # 最多重试3次点击评论按钮
        已点击触发 = False
        for attempt in range(1, 4):
            try:
                所有按钮 = driver.find_elements(By.CSS_SELECTOR, "div[role='button'], button[role='button'], button")
                print(f"[评论-调试] (第{attempt}/3次) 本页可点击按钮数: {len(所有按钮)}")
                
                点击候选 = []
                for btn in 所有按钮:
                    try:
                        lbl = (btn.get_attribute("aria-label") or "").lower()
                        dt = (btn.get_attribute("data-testid") or "").lower()
                        txt = (btn.text or "").lower()
                        # 兼容中英文的评论按钮识别
                        if ("comment" in lbl or "评论" in lbl or "reply" in lbl or "回复" in lbl) or \
                           ("comment" in dt or "reply" in dt) or \
                           ("评论" in txt or "回复" in txt or "comment" in txt or "reply" in txt):
                            点击候选.append(btn)
                    except:
                        continue

                print(f"[评论] (第{attempt}/3次) 评论按钮候选数: {len(点击候选)}")
                for cand in 点击候选:
                    try:
                        if cand.is_displayed():
                            al = cand.get_attribute("aria-label") or ""
                            dt = cand.get_attribute("data-testid") or ""
                            print(f"[评论] 尝试点击评论按钮: aria-label='{al}', data-testid='{dt}'")
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cand)
                            time.sleep(0.3)
                            driver.execute_script("arguments[0].click();", cand)
                            time.sleep(2)  # 增加等待时间，等待评论输入框出现
                            已点击触发 = True
                            break
                    except Exception as e:
                        print(f"[评论] 点击评论按钮失败(跳过该候选): {e}")

                if 已点击触发:
                    break
                else:
                    print(f"[评论] (第{attempt}/3次) 未能点击到评论按钮，将重试...")
                    try:
                        driver.execute_script("window.scrollBy(0, 800);")
                    except:
                        pass
                    time.sleep(1)
            except Exception as e:
                print(f"[评论-调试] (第{attempt}/3次) 枚举/点击评论按钮时异常: {e}")

        if not 已点击触发:
            print("[评论] 未找到明确的评论按钮，将直接定位输入框")

        # 查找评论框 - 包括 Reels 特定选择器，兼容中英文
        评论框选择器列表 = [
            # 精确匹配 - 中英文
            "[aria-label='写评论']",
            "[aria-label='Write a comment']",
            "[aria-label='评论']",
            "[aria-label='Comment']",
            "[aria-placeholder='写评论']",
            "[aria-placeholder='Write a comment']",
            "[placeholder='写评论']",
            "[placeholder='Write a comment']",
            
            # 包含匹配 - 中英文
            "[aria-label*='写评论']",
            "[aria-label*='Write a comment']",
            "[aria-label*='评论']",
            "[aria-label*='comment' i]",
            "[aria-placeholder*='comment' i]",
            "[placeholder*='comment' i]",
            
            # Reels 视频特定选择器
            "div[contenteditable='true'][role='textbox']",
            "div[contenteditable='true'][data-lexical-editor='true']",
            
            # 通用选择器
            "textarea[placeholder*='comment' i]",
            "textarea[placeholder*='评论']",
            "input[placeholder*='comment' i]",
            "input[placeholder*='评论']",
            "div[contenteditable='true']"
        ]
        
        评论框 = None
        for 选择器 in 评论框选择器列表:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, 选择器)
                for el in elements:
                    if el.is_displayed():
                        评论框 = el
                        print(f"[评论] 找到评论框: {选择器}")
                        break
                if 评论框:
                    break
            except:
                continue
        
        if not 评论框:
            print("[评论] 未找到评论框")
            return False
        
        # 点击评论框激活
        print("[评论] 点击评论框...")
        driver.execute_script("arguments[0].click();", 评论框)
        time.sleep(2)  # 增加等待时间，等待输入框完全激活
        
        # 清空并输入评论
        print(f"[评论] 输入评论内容: {评论内容[:50]}...")
        
        # 方法1：使用 JavaScript 设置文本
        try:
            escaped_content = 评论内容.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            driver.execute_script(f'''
                var editor = arguments[0];
                editor.focus();
                editor.textContent = "{escaped_content}";
                editor.dispatchEvent(new InputEvent('input', {{bubbles: true, data: "{escaped_content}"}}));
                editor.dispatchEvent(new Event('change', {{bubbles: true}}));
            ''', 评论框)
        except Exception as e:
            print(f"[评论] JavaScript 输入失败: {e}，尝试直接输入...")
            # 方法2：直接输入
            评论框.clear()
            for char in 评论内容:
                评论框.send_keys(char)
                time.sleep(random.uniform(0.02, 0.05))
        
        time.sleep(random.randint(2, 4))  # 增加等待时间，让输入框稳定

        # 查找并点击发送按钮 - 兼容中英文
        print("[评论] 查找发送按钮...")
        发送按钮 = None
        发送按钮选择器 = [
            # 精确匹配 - 中英文
            "[aria-label='Post']",
            "[aria-label='发布']",
            "[aria-label='Send']",
            "[aria-label='发送']",
            "[aria-label='Comment']",
            "[aria-label='评论']",
            
            # 包含匹配 - 中英文
            "[aria-label*='Post']",
            "[aria-label*='发布']",
            "[aria-label*='Send']",
            "[aria-label*='发送']",
            "[aria-label*='Comment']",
            "[aria-label*='评论']",
            
            # 带 role 的选择器 - 中英文
            "button[aria-label*='Post']",
            "button[aria-label*='发布']",
            "button[aria-label*='Send']",
            "button[aria-label*='发送']",
            "button[aria-label*='Comment']",
            "button[aria-label*='评论']",
            
            "div[role='button'][aria-label*='Post']",
            "div[role='button'][aria-label*='发布']",
            "div[role='button'][aria-label*='Send']",
            "div[role='button'][aria-label*='发送']",
            "div[role='button'][aria-label*='Comment']",
            "div[role='button'][aria-label*='评论']"
        ]
        
        for 选择器 in 发送按钮选择器:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, 选择器)
                for btn in buttons:
                    if btn.is_displayed():
                        发送按钮 = btn
                        print(f"[评论] 找到发送按钮: {选择器}")
                        break
                if 发送按钮:
                    break
            except:
                continue
        
        # 如果找到发送按钮，点击它；否则尝试回车键
        if 发送按钮:
            print("[评论] 点击发送按钮...")
            try:
                driver.execute_script("arguments[0].click();", 发送按钮)
            except:
                发送按钮.click()
            
            # 增加等待时间，确保评论被提交
            等待秒数 = random.randint(4, 8)  # 增加到 4-8 秒
            print(f"[评论] ⏳ 等待评论提交（{等待秒数}秒）...")
            time.sleep(等待秒数)
            print(f"[评论] ✅ 通过发送按钮提交评论: {评论内容[:50]}...")
        else:
            # 备选：使用回车键提交
            print("[评论] 未找到发送按钮，尝试回车键提交...")
            try:
                评论框.send_keys(Keys.ENTER)
                # 增加等待时间，确保评论被提交
                等待秒数 = random.randint(4, 8)  # 增加到 4-8 秒
                print(f"[评论] ⏳ 等待评论提交（{等待秒数}秒）...")
                time.sleep(等待秒数)
                print(f"[评论] ✅ 通过回车键提交评论: {评论内容[:50]}...")
            except Exception as e:
                print(f"[评论] ❌ 回车键提交失败: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"[评论] ❌ 评论失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def 生成随机评论() -> str:
    """
    生成随机评论内容
    
    Returns:
        评论文本
    """
    评论模板 = [
        "👍",
        "不错！",
        "支持！",
        "赞一个",
        "很棒！",
        "❤️",
        "🔥",
        "太好了",
        "👏",
        "💯",
        "Nice!",
        "Great!",
        "Awesome!",
        "😊",
        "👌",
        "💪",
        "✨",
        "🎉",
        "好！",
        "棒！"
    ]
    
    return random.choice(评论模板)

def 执行帖子互动(账号: dict, 帖子URL: str, 点赞概率: float = 0.8, 评论概率: float = 1.0, log_func=None) -> bool:
    """
    执行帖子互动（点赞和评论）
    
    Args:
        账号: 账号信息字典
        帖子URL: 帖子链接
        点赞概率: 点赞的概率（0-1）
        评论概率: 评论的概率（0-1）
        log_func: 日志函数
    
    Returns:
        是否成功
    """
    log = log_func or print

    try:
        账号名称 = 账号.get("name", "未知")
        browser_id = 账号.get("browser_id")

        if not browser_id:
            log(f"[帖子互动] ❌ 账号 {账号名称} 缺少 browser_id，无法打开浏览器")
            return False

        if not 帖子URL:
            log(f"[帖子互动] ❌ 帖子URL为空，无法执行互动")
            return False

        if bit_browser is None:
            log(f"[帖子互动] ❌ 无法导入 bitbrowser_api，无法打开账号浏览器")
            return False

        log(f"[帖子互动] 🚀 账号 {账号名称} 开始互动")
        log(f"[帖子互动] 帖子URL: {帖子URL}")

        # 1. 通过 BitBrowser 打开对应账号浏览器并获取 driver 信息
        try:
            open_result = bit_browser.open_browser(browser_id)
        except Exception as e:
            log(f"[帖子互动] ❌ 调用 bit_browser.open_browser 失败: {e}")
            return False

        if not open_result or not open_result.get("success"):
            log(f"[帖子互动] ❌ 打开浏览器失败: {open_result}")
            return False

        # BitBrowser 返回结构通常为 {"success": True, "data": {"driver": ..., "http": ..., ...}}
        data = open_result.get("data") or open_result
        driver_path = data.get("driver")
        debug_port = data.get("http")  # 远程调试地址，如 "127.0.0.1:9222"

        if not driver_path or not debug_port:
            log(f"[帖子互动] ❌ 返回结果中缺少 driver/http 信息: {open_result}")
            return False

        # 2. 附着到已打开的浏览器，创建 Selenium WebDriver
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_experimental_option("debuggerAddress", debug_port)

        service = Service(driver_path)
        driver = None

        try:
            driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            log(f"[帖子互动] ❌ 创建 WebDriver 失败: {e}")
            return False

        原始窗口 = None
        新标签句柄 = None

        try:
            # 3. 在新标签页中打开帖子页面，避免干扰当前任务页面
            try:
                原始窗口 = driver.current_window_handle
                已有窗口 = set(driver.window_handles)
            except Exception:
                原始窗口 = None
                已有窗口 = set()

            try:
                driver.execute_script("window.open(arguments[0], '_blank');", "https://www.facebook.com/")
                time.sleep(3)
                当前窗口集合 = set(driver.window_handles)
                新窗口集合 = 当前窗口集合 - 已有窗口
                if 新窗口集合:
                    新标签句柄 = 新窗口集合.pop()
                    driver.switch_to.window(新标签句柄)
                else:
                    driver.get("https://www.facebook.com/")
            except Exception as e:
                log(f"[帖子互动] ⚠️ 打开新标签页失败，回退到当前窗口进入首页: {e}")
                driver.get("https://www.facebook.com/")

            # 自然导航：关闭“工作台”分页，确保首页根路径，然后搜索公共主页进入Pages再进入目标帖子
            try:
                # 关闭标题包含“- 工作台”的分页
                try:
                    所有句柄 = list(getattr(driver, "window_handles", []))
                    for h in 所有句柄:
                        try:
                            driver.switch_to.window(h)
                            标题 = driver.title or ""
                            if "- 工作台" in 标题:
                                driver.close()
                        except Exception:
                            pass
                    try:
                        driver.switch_to.window(driver.window_handles[-1])
                    except Exception:
                        pass
                except Exception:
                    pass

                # 确保位于首页根路径
                try:
                    当前URL = driver.current_url or ""
                    def _is_home(u: str) -> bool:
                        try:
                            base = (u or "").split("?")[0].rstrip("/")
                            return base.endswith("facebook.com")
                        except Exception:
                            return False
                    if "facebook.com" in 当前URL and not _is_home(当前URL):
                        logo_选择器 = [
                            "a[aria-label='Facebook']",
                            "a[aria-label='主页']",
                            "a[href='/']",
                            "a[href='https://www.facebook.com/']",
                        ]
                        点击成功 = False
                        for sel in logo_选择器:
                            try:
                                el = driver.find_element(By.CSS_SELECTOR, sel)
                                if el and el.is_displayed():
                                    driver.execute_script("arguments[0].click();", el)
                                    点击成功 = True
                                    break
                            except Exception:
                                continue
                        if not 点击成功:
                            driver.get("https://www.facebook.com/")
                        time.sleep(random.randint(2, 4))
                except Exception:
                    pass

                页面名称 = 读取主页名称() or ""
                页面链接 = 读取主页链接() or ""

                # 搜索公共主页
                搜索选择器 = [
                    "input[aria-label='Search Facebook']",
                    "input[placeholder='Search Facebook']",
                    "input[aria-label='搜索 Facebook']",
                    "input[placeholder*='搜索']",
                    "[role='combobox'] input",
                ]
                搜索框 = None
                for sel in 搜索选择器:
                    try:
                        el = WebDriverWait(driver, 5).until(lambda d: d.find_element(By.CSS_SELECTOR, sel))
                        if el and el.is_displayed():
                            搜索框 = el
                            break
                    except Exception:
                        continue
                if 搜索框:
                    try:
                        driver.execute_script("arguments[0].click();", 搜索框)
                    except Exception:
                        try:
                            搜索框.click()
                        except Exception:
                            pass
                    time.sleep(1)
                    try:
                        搜索框.clear()
                    except Exception:
                        pass
                    try:
                        搜索框.send_keys(Keys.CONTROL, 'a')
                        time.sleep(0.2)
                        搜索框.send_keys(Keys.BACKSPACE)
                    except Exception:
                        pass
                    查询词 = 页面名称 or 页面链接
                    if 查询词:
                        搜索框.send_keys(查询词)
                        time.sleep(0.5)
                        搜索框.send_keys(Keys.ENTER)
                        time.sleep(random.randint(3, 5))

                # 点击 Pages 标签
                try:
                    pages_clicked = False
                    xpath_list = [
                        "//span[text()='Pages']",
                        "//span[text()='主页']",
                        "//a[@role='tab']//span[text()='Pages']/..",
                        "//a[@role='tab' and contains(@href,'pages')]",
                        "//div[@role='tab']//span[text()='Pages']/..",
                    ]
                    for xp in xpath_list:
                        try:
                            el = driver.find_element(By.XPATH, xp)
                            if el and el.is_displayed():
                                driver.execute_script("arguments[0].click();", el)
                                pages_clicked = True
                                break
                        except Exception:
                            continue
                    if pages_clicked:
                        time.sleep(random.randint(2, 4))
                except Exception:
                    pass

                # 进入公共主页（优先链接匹配，其次名称匹配）
                主页已进入 = False
                if 页面链接:
                    try:
                        links = driver.find_elements(By.CSS_SELECTOR, f"a[href*='{页面链接}']")
                        if links:
                            driver.execute_script("arguments[0].click();", links[0])
                            主页已进入 = True
                    except Exception:
                        pass
                if not 主页已进入 and 页面名称:
                    try:
                        candidates = driver.find_elements(By.CSS_SELECTOR, "a[href]")
                        for a in candidates:
                            try:
                                if a.is_displayed():
                                    text = (a.text or "").strip()
                                    if text and 页面名称.lower() in text.lower():
                                        driver.execute_script("arguments[0].click();", a)
                                        主页已进入 = True
                                        break
                            except Exception:
                                continue
                    except Exception:
                        pass
                if 主页已进入:
                    time.sleep(random.randint(3, 5))
                else:
                    log("[帖子互动] ⚠️ 未能通过搜索进入公共主页，直接打开帖子链接")
                    打开帖子(driver, 帖子URL)

                # 在主页寻找目标帖子并进入
                def _norm(u: str) -> str:
                    try:
                        return (u or "").split("?")[0].rstrip("/").lower()
                    except Exception:
                        return u or ""
                目标 = _norm(帖子URL)
                已进入帖子 = False
                if 主页已进入:
                    for _ in range(8):
                        try:
                            anchors = driver.find_elements(By.CSS_SELECTOR, "a[href]")
                            命中 = None
                            for a in anchors:
                                try:
                                    href = a.get_attribute("href") or ""
                                    nh = _norm(href)
                                    if nh and (nh == 目标 or 目标 in nh):
                                        命中 = a
                                        break
                                except Exception:
                                    continue
                            if 命中:
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 命中)
                                time.sleep(0.5)
                                driver.execute_script("arguments[0].click();", 命中)
                                已进入帖子 = True
                                time.sleep(random.randint(3, 5))
                                break
                            driver.execute_script("window.scrollBy(0, 1400);")
                            time.sleep(1)
                        except Exception:
                            break
                if not 已进入帖子 and 主页已进入:
                    log("[帖子互动] ⚠️ 主页未找到目标帖子，直接打开帖子链接")
                    打开帖子(driver, 帖子URL)
            except Exception as e:
                log(f"[帖子互动] ⚠️ 自然导航异常，直接打开帖子链接: {e}")
                打开帖子(driver, 帖子URL)

            success = True

            # 4. 根据概率点赞
            do_like = random.random() < 点赞概率
            if do_like:
                try:
                    if 点赞帖子(driver):
                        log(f"[帖子互动] 👍 账号 {账号名称} 已点赞")
                    else:
                        log(f"[帖子互动] ⚠️ 账号 {账号名称} 点赞失败")
                except Exception as e:
                    log(f"[帖子互动] ❌ 点赞时异常: {e}")
                    success = False
            else:
                log(f"[帖子互动] ⏭️ 账号 {账号名称} 本次未参与点赞（概率控制）")

            # 5. 根据概率评论
            do_comment = random.random() < 评论概率
            if do_comment:
                # 优先使用自动化工具中的 AI 评论函数，失败或返回空时回退到本地随机评论
                评论内容 = ""
                try:
                    评论内容 = AI评论_不带帖子内容() or ""
                except Exception as e:
                    log(f"[帖子互动] ⚠️ 调用 AI评论_不带帖子内容 失败，使用本地随机评论: {e}")

                if not 评论内容.strip():
                    评论内容 = 生成随机评论()

                try:
                    if 评论帖子(driver, 评论内容):
                        log(f"[帖子互动] 💬 账号 {账号名称} 已评论: {评论内容}")
                    else:
                        log(f"[帖子互动] ⚠️ 账号 {账号名称} 评论失败")
                        success = False
                except Exception as e:
                    log(f"[帖子互动] ❌ 评论时异常: {e}")
                    success = False
            else:
                log(f"[帖子互动] ⏭️ 账号 {账号名称} 本次未参与评论（概率控制）")

            return success

        finally:
            # 6. 关闭我们自己打开的帖子标签，并尽量切回原始窗口
            try:
                if driver is not None:
                    if 新标签句柄 and 新标签句柄 in getattr(driver, "window_handles", []):
                        try:
                            driver.close()
                        except Exception:
                            pass

                    # 切回原始窗口（如果仍然存在）
                    try:
                        if 原始窗口 and 原始窗口 in getattr(driver, "window_handles", []):
                            driver.switch_to.window(原始窗口)
                    except Exception:
                        pass
            except Exception as e:
                log(f"[帖子互动] ⚠️ 关闭帖子标签或切回窗口时异常: {e}")

    except Exception as e:
        log(f"[帖子互动] ❌ 互动失败: {e}")
        return False
