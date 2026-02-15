"""
阅读模块 - 查看评论功能
根据阶段配置展开和查看评论区
"""

import time
import random
from typing import TYPE_CHECKING, Optional, List, Dict, Any

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.remote.webelement import WebElement


class 评论查看器:
    """评论查看器类"""
    
    def __init__(self, driver: "WebDriver", 阶段配置数据: Optional[Dict[str, Any]] = None):
        self.driver = driver
        self.阶段配置 = 阶段配置数据 or {}
        
        # 从阶段配置读取参数
        self.查看评论概率 = self.阶段配置.get('查看评论概率', 0.35)
        self.查看评论数范围 = (
            self.阶段配置.get('查看评论数', 2),
            self.阶段配置.get('查看评论数', 6)
        )
        self.点赞评论数范围 = (
            self.阶段配置.get('点赞评论数', 0),
            self.阶段配置.get('点赞评论数', 2)
        )
        self.回复评论数范围 = (
            self.阶段配置.get('回复评论数', 0),
            self.阶段配置.get('回复评论数', 1)
        )
        self.访问主页数范围 = (
            self.阶段配置.get('访问主页数', 0),
            self.阶段配置.get('访问主页数', 1)
        )
        
        # 统计
        self.已查看评论数 = 0
        self.已点赞评论数 = 0
        self.已回复评论数 = 0
        self.已访问主页数 = 0
    
    def 是否查看评论(self) -> bool:
        """
        根据概率决定是否查看评论
        
        Returns:
            是否查看评论
        """
        return random.random() < self.查看评论概率
    
    def 查找评论按钮(self) -> Optional["WebElement"]:
        """
        查找"查看评论"按钮
        
        Returns:
            评论按钮元素，如果未找到返回None
        """
        try:
            # 方法1: 通过 aria-label 查找
            评论按钮选择器 = [
                "[aria-label*='Comment' i]",
                "[aria-label*='comment' i]",
                "[aria-label*='View comment' i]",
                "[aria-label*='See comment' i]",
            ]
            
            for 选择器 in 评论按钮选择器:
                buttons = self.driver.find_elements("css selector", 选择器)
                for btn in buttons:
                    if btn.is_displayed():
                        return btn
            
            # 方法2: 通过文本查找
            all_elements = self.driver.find_elements("css selector", "[role='button']")
            for el in all_elements:
                try:
                    text = el.text.lower()
                    if 'comment' in text and el.is_displayed():
                        return el
                except:
                    continue
            
            return None
            
        except Exception:
            return None
    
    def 展开评论区(self, log_func=None) -> bool:
        """
        展开评论区
        
        Args:
            log_func: 日志函数
        
        Returns:
            是否成功展开
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        try:
            # 查找评论按钮
            评论按钮 = self.查找评论按钮()
            
            if not 评论按钮:
                log("  未找到评论按钮")
                return False
            
            # 滚动到按钮
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 评论按钮)
            time.sleep(random.uniform(0.5, 1.5))
            
            # 点击按钮
            try:
                self.driver.execute_script("arguments[0].click();", 评论按钮)
            except:
                评论按钮.click()
            
            log("  成功: 已展开评论区")
            
            # 等待评论加载
            time.sleep(random.uniform(2, 4))
            return True
            
        except Exception as e:
            log(f"  展开评论区失败: {e}")
            return False
    
    def 获取可见评论(self, log_func=None) -> List["WebElement"]:
        """
        获取当前可见的评论元素（只在评论弹窗内查找）
        
        Args:
            log_func: 日志函数
        
        Returns:
            评论元素列表
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        try:
            # 先找到评论弹窗
            评论弹窗 = None
            try:
                dialogs = self.driver.find_elements("css selector", "[role='dialog']")
                
                for idx, dialog in enumerate(dialogs, 1):
                    if dialog.is_displayed():
                        评论弹窗 = dialog
                        break
            except:
                pass
            
            if not 评论弹窗:
                return []
            
            # 等待评论加载
            import time
            time.sleep(2)
            
            # 在弹窗内查找评论元素
            评论列表 = []
            
            try:
                # 策略：查找包含用户链接的 div[dir='auto']（这些更可能是真实评论）
                # 先找所有用户链接
                user_links = 评论弹窗.find_elements("css selector", "a[href*='/user/'], a[href*='/profile.php']")
                
                # 对每个用户链接，查找其附近的评论文本
                已处理位置 = set()
                
                for link in user_links:
                    try:
                        # 获取链接的父元素
                        parent = link.find_element("xpath", "..")
                        
                        # 在父元素及其兄弟元素中查找 div[dir='auto']
                        # 这些通常是评论文本
                        nearby_divs = []
                        
                        # 方法1: 查找父元素的父元素下的所有 div[dir='auto']
                        try:
                            grandparent = parent.find_element("xpath", "..")
                            nearby_divs.extend(grandparent.find_elements("css selector", "div[dir='auto']"))
                        except:
                            pass
                        
                        # 方法2: 查找父元素下的 div[dir='auto']
                        try:
                            nearby_divs.extend(parent.find_elements("css selector", "div[dir='auto']"))
                        except:
                            pass
                        
                        # 筛选出有效的评论文本
                        for div in nearby_divs:
                            try:
                                text = div.text.strip()
                                location = div.location
                                位置key = (location['x'], location['y'])
                                
                                # 跳过已处理的位置
                                if 位置key in 已处理位置:
                                    continue
                                
                                # 检查文本长度和内容
                                if 5 <= len(text) <= 500:
                                    # 排除用户名（通常很短且在链接内）
                                    if text != link.text.strip():
                                        评论列表.append(div)
                                        已处理位置.add(位置key)
                            except:
                                continue
                    except:
                        continue
                
                # 如果通过用户链接没找到足够的评论，使用备用方案
                if len(评论列表) < 3:
                    if log_func:
                        log(f"  评论数量不足，使用备用方案...")
                    
                    # 备用方案：使用"Most relevant"元素作为分界线
                    # 这个元素在帖子内容和评论区之间
                    
                    # 第一步：查找分界元素
                    分界元素 = None
                    
                    # 优先查找"Most relevant"或类似的排序选择器
                    try:
                        elements = 评论弹窗.find_elements("css selector", "span[dir='auto']")
                        for el in elements:
                            text = el.text.strip()
                            if text in ["Most relevant", "最相关", "All comments", "所有评论", "Newest", "最新"]:
                                分界元素 = el
                                if log_func:
                                    log(f"  ✓ 找到分界元素: {text}")
                                break
                    except:
                        pass
                    
                    # 如果没找到，尝试使用Like按钮
                    if 分界元素 is None:
                        try:
                            like_buttons = []
                            like_buttons.extend(评论弹窗.find_elements("css selector", "[aria-label='Like']"))
                            like_buttons.extend(评论弹窗.find_elements("css selector", "[aria-label='Remove Like']"))
                            
                            for btn in like_buttons:
                                try:
                                    if btn.is_displayed():
                                        btn_text = btn.text.strip().lower()
                                        aria_label = (btn.get_attribute("aria-label") or "").lower()
                                        
                                        if "like" in btn_text or "like" in aria_label:
                                            分界元素 = btn
                                            if log_func:
                                                log(f"  ✓ 找到分界元素: Like按钮")
                                            break
                                except:
                                    continue
                        except:
                            pass
                    
                    if 分界元素 is None:
                        if log_func:
                            log(f"  ⚠️ 未找到分界元素，无法区分帖子和评论")
                        return []
                    
                    # 第二步：获取所有div[dir='auto']
                    all_divs = 评论弹窗.find_elements("css selector", "div[dir='auto']")
                    
                    # 第三步：使用compareDocumentPosition判断位置
                    帖子内容列表 = []
                    评论内容列表 = []
                    
                    for div in all_divs:
                        try:
                            text = div.text.strip()
                            if not text or len(text) < 5 or len(text) > 500:
                                continue
                            
                            # 判断div是否在分界元素之后
                            position = self.driver.execute_script(
                                "return arguments[0].compareDocumentPosition(arguments[1]);",
                                分界元素, div
                            )
                            
                            # position & 4 表示div在分界元素之后（评论区）
                            if position & 4:
                                评论内容列表.append({'element': div, 'text': text})
                            else:
                                帖子内容列表.append(text)
                        except:
                            continue
                    
                    # 输出帖子内容
                    if log_func and 帖子内容列表:
                        log(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        log(f"  📄 帖子内容:")
                        完整帖子内容 = " ".join(帖子内容列表)
                        if len(完整帖子内容) > 200:
                            log(f"  {完整帖子内容[:200]}...")
                        else:
                            log(f"  {完整帖子内容}")
                        log(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    
                    # 第四步：收集所有用户链接和用户名
                    用户名集合 = set()
                    用户链接位置 = []  # [(y坐标, 用户名), ...]
                    
                    try:
                        # 扩展用户链接选择器，包含更多可能的格式
                        all_links = []
                        all_links.extend(评论弹窗.find_elements("css selector", "a[href*='/user/']"))
                        all_links.extend(评论弹窗.find_elements("css selector", "a[href*='/profile.php']"))
                        all_links.extend(评论弹窗.find_elements("css selector", "a[role='link'][tabindex='0']"))
                        
                        # 去重
                        seen_hrefs = set()
                        unique_links = []
                        for link in all_links:
                            href = link.get_attribute("href") or ""
                            if href and href not in seen_hrefs:
                                seen_hrefs.add(href)
                                unique_links.append(link)
                        
                        for link in unique_links:
                            try:
                                用户名 = link.text.strip()
                                if 用户名 and len(用户名) > 0:
                                    用户名集合.add(用户名)
                                    # 记录用户链接的Y坐标
                                    try:
                                        y = link.location['y']
                                        用户链接位置.append((y, 用户名))
                                    except:
                                        pass
                            except:
                                pass
                    except:
                        pass
                    
                    # 第五步：按父容器分组评论
                    # 策略：查找包含 div[dir='auto'] 的父容器，合并同一容器内的所有div
                    
                    评论分组 = {}  # {容器id: {'divs': [...], 'y': 最小y坐标, 'element': 容器元素}}
                    
                    for item in 评论内容列表:
                        text = item['text']
                        element = item['element']
                        
                        # 排除用户名
                        if text in 用户名集合:
                            continue
                        
                        # 检查是否在用户链接附近
                        if 用户链接位置:  # 如果有用户链接
                            try:
                                div_y = element.location['y']
                                在用户附近 = False
                                最近距离 = float('inf')
                                
                                for user_y, user_name in 用户链接位置:
                                    距离 = abs(div_y - user_y)
                                    if 距离 < 最近距离:
                                        最近距离 = 距离
                                    
                                    # div必须在用户链接下方或附近（±200px）
                                    if 距离 < 200:
                                        在用户附近 = True
                                        break
                                
                                # 如果不在用户附近，跳过
                                if not 在用户附近:
                                    continue
                            except Exception as e:
                                pass
                        
                        # 查找包含 div[dir='auto'] 的父容器
                        # 策略：向上查找，直到找到一个包含多个 div[dir='auto'] 的容器
                        try:
                            div_y = element.location['y']
                            
                            # 从当前元素开始，向上查找最多5层
                            current = element
                            container = None
                            
                            for level in range(5):
                                try:
                                    parent = current.find_element("xpath", "..")
                                    
                                    # 检查这个父容器是否包含多个 div[dir='auto']
                                    child_divs = parent.find_elements("css selector", "div[dir='auto']")
                                    
                                    # 如果包含2个或更多div，这就是我们要找的容器
                                    if len(child_divs) >= 2:
                                        container = parent
                                        break
                                    
                                    current = parent
                                except:
                                    break
                            
                            # 如果没找到合适的容器，使用父容器
                            if container is None:
                                try:
                                    container = element.find_element("xpath", "..")
                                except:
                                    container = element
                            
                            container_id = container.id  # 使用Selenium元素的内部ID，而不是Python的id()
                            
                            if container_id not in 评论分组:
                                评论分组[container_id] = {
                                    'divs': [],
                                    'y': div_y,
                                    'element': container
                                }
                            
                            评论分组[container_id]['divs'].append({
                                'element': element,
                                'text': text,
                                'y': div_y
                            })
                            
                            # 更新最小Y坐标
                            if div_y < 评论分组[container_id]['y']:
                                评论分组[container_id]['y'] = div_y
                                
                        except:
                            # 如果无法获取位置，单独作为一条评论
                            container_id = element.id
                            评论分组[container_id] = {
                                'divs': [{
                                    'element': element,
                                    'text': text,
                                    'y': 0
                                }],
                                'y': 0,
                                'element': element
                            }
                    
                    # 第六步：按Y坐标排序，合并同一容器的div
                    评论计数 = 0
                    
                    # 按Y坐标排序
                    sorted_groups = sorted(评论分组.items(), key=lambda x: x[1]['y'])
                    
                    for container_id, group_data in sorted_groups:
                        divs = group_data['divs']
                        if not divs:
                            continue
                        
                        # 合并文本
                        合并文本 = " ".join([d['text'] for d in divs])
                        
                        # 使用第一个元素作为代表
                        评论列表.append(divs[0]['element'])
                        已处理位置.add(id(divs[0]['element']))
                        评论计数 += 1
                        
                        # 输出评论（前10条）
                        if log_func and 评论计数 <= 10:
                            if len(divs) > 1:
                                log(f"  💬 评论{评论计数} (合并{len(divs)}行): {合并文本[:100]}")
                            else:
                                log(f"  💬 评论{评论计数}: {合并文本[:100]}")
                    
                    if log_func:
                        if 评论计数 > 10:
                            log(f"  ... 还有 {评论计数 - 10} 条评论")
                        log(f"  ✓ 共找到 {len(评论列表)} 条评论")
                    
            except Exception as e:
                if log_func:
                    log(f"  [调试-获取评论] 查找评论失败: {e}")
            
            # 返回前20个评论
            return 评论列表[:20]
            
        except Exception as e:
            if log_func:
                log(f"  [调试-获取评论] 异常: {e}")
            return []
    
    def 滚动查看评论(self, 目标数量: int, log_func=None) -> tuple[int, List["WebElement"]]:
        """
        滚动查看评论
        
        Args:
            目标数量: 目标查看数量
            log_func: 日志函数
        
        Returns:
            (实际查看数量, 评论列表)
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        try:
            已查看 = 0
            滚动次数 = 0
            最大滚动次数 = 10
            
            # 尝试找到评论区容器（弹窗）
            评论区容器 = None
            try:
                # 查找评论弹窗容器
                containers = self.driver.find_elements("css selector", "[role='dialog']")
                for container in containers:
                    if container.is_displayed():
                        评论区容器 = container
                        break
            except:
                pass
            
            # 第一次获取评论列表
            评论列表 = self.获取可见评论(log)
            
            # 如果第一次就找到评论，直接使用
            if 评论列表:
                # 随机选择一些评论查看
                查看数量 = min(len(评论列表), 目标数量, random.randint(2, 5))
                
                for i in range(查看数量):
                    if i < len(评论列表):
                        评论 = 评论列表[i]
                        
                        # 滚动到评论
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 评论)
                        
                        # 模拟阅读（增加阅读时间）
                        阅读时间 = random.uniform(2, 5)
                        time.sleep(阅读时间)
                        
                        已查看 += 1
                        self.已查看评论数 += 1
                
                log(f"  查看了 {已查看} 条评论")
                return (已查看, 评论列表)
            
            # 如果第一次没找到评论，尝试滚动加载
            while 已查看 < 目标数量 and 滚动次数 < 最大滚动次数:
                # 滚动尝试加载更多
                if 评论区容器:
                    self.driver.execute_script("arguments[0].scrollTop += 300", 评论区容器)
                else:
                    self.driver.execute_script("window.scrollBy(0, 300)")
                time.sleep(random.uniform(1, 2))
                滚动次数 += 1
                
                # 再次获取评论
                评论列表 = self.获取可见评论()  # 不输出日志，避免重复
                
                if not 评论列表:
                    # 如果连续3次都找不到评论，退出
                    if 滚动次数 >= 3:
                        log(f"  连续{滚动次数}次未找到评论，停止滚动")
                        break
                    continue
                
                # 随机选择一些评论查看
                查看数量 = min(len(评论列表), 目标数量 - 已查看, random.randint(2, 5))
                
                for i in range(查看数量):
                    if i < len(评论列表):
                        评论 = 评论列表[i]
                        
                        # 滚动到评论
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 评论)
                        
                        # 模拟阅读（增加阅读时间）
                        阅读时间 = random.uniform(2, 5)  # 从1-3秒增加到2-5秒
                        time.sleep(阅读时间)
                        
                        已查看 += 1
                        self.已查看评论数 += 1
                
                # 继续滚动（在评论区容器内滚动）
                if 已查看 < 目标数量:
                    if 评论区容器:
                        # 在弹窗内滚动
                        self.driver.execute_script("arguments[0].scrollTop += 300", 评论区容器)
                    else:
                        # 在页面滚动
                        self.driver.execute_script("window.scrollBy(0, 300)")
                    time.sleep(random.uniform(1, 2))
                    滚动次数 += 1
            
            log(f"  查看了 {已查看} 条评论")
            return (已查看, 评论列表)
            
        except Exception as e:
            log(f"  滚动查看评论失败: {e}")
            return (0, [])
    
    def 点赞评论(self, 评论元素: "WebElement", log_func=None) -> bool:
        """
        点赞评论
        
        Args:
            评论元素: 评论元素
            log_func: 日志函数
        
        Returns:
            是否成功点赞
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        try:
            # 查找点赞按钮（在评论元素内部或附近）
            点赞按钮 = None
            
            # 方法1: 在评论元素内查找
            try:
                buttons = 评论元素.find_elements("css selector", "[aria-label='Like' i]")
                for btn in buttons:
                    if btn.is_displayed():
                        点赞按钮 = btn
                        break
            except:
                pass
            
            if not 点赞按钮:
                return False
            
            # 检查是否已点赞
            try:
                pressed = 点赞按钮.get_attribute("aria-pressed")
                if pressed == "true":
                    return False
            except:
                pass
            
            # 点击点赞
            try:
                self.driver.execute_script("arguments[0].click();", 点赞按钮)
            except:
                点赞按钮.click()
            
            self.已点赞评论数 += 1
            log("    成功: 点赞评论")
            
            time.sleep(random.uniform(1, 2))
            return True
            
        except Exception as e:
            log(f"    点赞评论失败: {e}")
            return False
    
    def 点击评论者头像(self, 评论元素: "WebElement", log_func=None) -> bool:
        """
        点击评论者头像（访问主页）
        
        Args:
            评论元素: 评论元素
            log_func: 日志函数
        
        Returns:
            是否成功点击
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        try:
            # 查找头像或用户名链接
            links = 评论元素.find_elements("css selector", "a[href*='/user/'], a[href*='/profile.php']")
            
            if not links:
                return False
            
            # 选择第一个链接（通常是用户名或头像）
            链接 = links[0]
            
            # 滚动到链接
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 链接)
            time.sleep(random.uniform(0.5, 1))
            
            # 点击链接
            try:
                self.driver.execute_script("arguments[0].click();", 链接)
            except:
                链接.click()
            
            self.已访问主页数 += 1
            log("    成功: 访问评论者主页")
            
            # 等待页面加载
            time.sleep(random.uniform(3, 5))
            
            # 返回上一页
            self.driver.back()
            time.sleep(random.uniform(2, 3))
            
            return True
            
        except Exception as e:
            log(f"    访问主页失败: {e}")
            return False
    
    def 执行查看评论(self, log_func=None, 不关闭弹窗=False) -> tuple[bool, List["WebElement"]]:
        """
        执行完整的查看评论流程
        
        Args:
            log_func: 日志函数
            不关闭弹窗: 是否不关闭评论弹窗（用于后续分析评论）
        
        Returns:
            (是否成功执行, 评论列表)
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        # 1. 检查是否查看评论
        概率检查 = self.是否查看评论()
        
        if not 概率检查:
            return (False, [])
        
        log("[查看评论] 开始查看评论...")
        
        # 2. 展开评论区
        展开成功 = self.展开评论区(log)
        
        if not 展开成功:
            return (False, [])
        
        # 3. 确定查看数量
        目标查看数 = random.randint(*self.查看评论数范围)
        目标点赞数 = random.randint(*self.点赞评论数范围)
        目标访问数 = random.randint(*self.访问主页数范围)
        
        log(f"  目标: 查看{目标查看数}条, 点赞{目标点赞数}条, 访问{目标访问数}个主页")
        
        # 4. 滚动查看评论
        实际查看数, 评论列表 = self.滚动查看评论(目标查看数, log)
        
        if 实际查看数 == 0:
            # 没有评论，关闭弹窗
            if not 不关闭弹窗:
                self.关闭评论弹窗(log)
            return (False, [])
        
        # 5. 使用已获取的评论列表（不再重复调用获取）
        if not 评论列表:
            # 即使没有评论列表，也要关闭弹窗
            if not 不关闭弹窗:
                self.关闭评论弹窗(log)
            return (True, [])
        
        # 随机打乱
        random.shuffle(评论列表)
        
        # 6. 点赞评论
        已点赞 = 0
        for 评论 in 评论列表:
            if 已点赞 >= 目标点赞数:
                break
            
            if self.点赞评论(评论, log):
                已点赞 += 1
                time.sleep(random.uniform(2, 4))
        
        # 7. 访问主页
        已访问 = 0
        for 评论 in 评论列表:
            if 已访问 >= 目标访问数:
                break
            
            if self.点击评论者头像(评论, log):
                已访问 += 1
                time.sleep(random.uniform(3, 5))
        
        # 8. 关闭评论弹窗（如果需要）
        if not 不关闭弹窗:
            self.关闭评论弹窗(log)
        
        log(f"[查看评论] 完成: 查看{实际查看数}条, 点赞{已点赞}条, 访问{已访问}个主页")
        return (True, 评论列表)
    
    def 关闭评论弹窗(self, log_func=None):
        """
        关闭评论弹窗
        
        Args:
            log_func: 日志函数
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        try:
            # 查找关闭按钮（aria-label="Close"）
            关闭按钮 = self.driver.find_elements("css selector", "[aria-label='Close']")
            for btn in 关闭按钮:
                if btn.is_displayed():
                    try:
                        self.driver.execute_script("arguments[0].click();", btn)
                        log("  成功: 已关闭评论弹窗")
                        time.sleep(random.uniform(0.5, 1))
                        break
                    except:
                        continue
        except Exception as e:
            log(f"  关闭评论弹窗失败: {e}")
    
    def 获取统计(self) -> Dict[str, int]:
        """
        获取统计信息
        
        Returns:
            统计字典
        """
        return {
            "已查看评论数": self.已查看评论数,
            "已点赞评论数": self.已点赞评论数,
            "已回复评论数": self.已回复评论数,
            "已访问主页数": self.已访问主页数,
        }


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("查看评论模块 - 测试")
    print("=" * 60)
    
    # 模拟阶段配置
    阶段配置 = {
        '查看评论概率': 0.35,
        '查看评论数': 5,
        '点赞评论数': 2,
        '回复评论数': 1,
        '访问主页数': 1,
    }
    
    # 模拟driver
    class MockDriver:
        def find_elements(self, by, value):
            return []
        
        def execute_script(self, script, *args):
            pass
    
    driver = MockDriver()
    查看器 = 评论查看器(driver, 阶段配置)
    
    print("\n[测试1] 检查查看评论概率...")
    查看次数 = 0
    总次数 = 100
    for _ in range(总次数):
        if 查看器.是否查看评论():
            查看次数 += 1
    
    实际概率 = 查看次数 / 总次数
    print(f"  配置概率: {阶段配置['查看评论概率']*100:.0f}%")
    print(f"  实际概率: {实际概率*100:.0f}%")
    print(f"  {'成功' if abs(实际概率 - 阶段配置['查看评论概率']) < 0.1 else '失败'}")
    
    print("\n[测试2] 获取统计信息...")
    统计 = 查看器.获取统计()
    print(f"  已查看评论数: {统计['已查看评论数']}")
    print(f"  已点赞评论数: {统计['已点赞评论数']}")
    print(f"  已回复评论数: {统计['已回复评论数']}")
    print(f"  已访问主页数: {统计['已访问主页数']}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
