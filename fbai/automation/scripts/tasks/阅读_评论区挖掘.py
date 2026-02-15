"""
阅读模块 - 评论区挖掘（AI识别意向）
从评论区识别高意向用户，记录到潜在用户池

优化策略：
1. 先用关键词预筛选（节省AI调用）
2. 命中关键词后再调用AI精确判断
3. 支持多语言关键词库
"""

import time
import random
import requests
import os
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.remote.webelement import WebElement

# 导入数据库
try:
    from database.db import Database
    _db = Database()
except Exception as e:
    try:
        import sys
        import os
        # 添加父目录到路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        from database.db import Database
        _db = Database()
    except Exception as e2:
        _db = None
        print(f"[评论区挖掘] 警告: 数据库初始化失败: {e2}")

# AI配置（从自动化工具导入）
try:
    from tasks.自动化工具 import 获取产品类目, 转义特殊字符
    AI工具可用 = True
except ImportError:
    try:
        from 自动化工具 import 获取产品类目, 转义特殊字符
        AI工具可用 = True
    except ImportError:
        AI工具可用 = False
        print("[评论区挖掘] 警告: AI工具不可用")

# AI API配置
_AI_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
_AI_MODEL = "qwen-plus"
_AI_TIMEOUT = 30

# 关键词库缓存
_意向关键词列表 = None


def _加载意向关键词() -> List[str]:
    """加载意向关键词库"""
    global _意向关键词列表
    
    if _意向关键词列表 is not None:
        return _意向关键词列表
    
    关键词列表 = []
    
    try:
        # 查找关键词文件
        current_dir = os.path.dirname(os.path.abspath(__file__))
        scripts_dir = os.path.dirname(current_dir)
        关键词文件 = os.path.join(scripts_dir, "脚本配置", "意向关键词.txt")
        
        print(f"[评论区挖掘] 尝试加载关键词文件: {关键词文件}")
        
        if not os.path.exists(关键词文件):
            print(f"[评论区挖掘] 警告: 关键词文件不存在: {关键词文件}")
            _意向关键词列表 = []
            return []
        
        with open(关键词文件, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if line and not line.startswith('#'):
                    关键词列表.append(line.lower())
        
        _意向关键词列表 = 关键词列表
        print(f"[评论区挖掘] 成功加载 {len(关键词列表)} 个意向关键词")
        
    except Exception as e:
        print(f"[评论区挖掘] 警告: 加载关键词失败: {e}")
        import traceback
        print(f"[评论区挖掘] 错误详情: {traceback.format_exc()}")
        _意向关键词列表 = []
    
    return _意向关键词列表


def _检查关键词命中(文本: str) -> tuple[bool, List[str]]:
    """
    检查文本是否命中意向关键词
    
    Args:
        文本: 要检查的文本
    
    Returns:
        (是否命中, 命中的关键词列表)
    """
    关键词列表 = _加载意向关键词()
    
    if not 关键词列表:
        # 如果没有关键词库，默认全部通过（使用AI判断）
        return (True, [])
    
    文本小写 = 文本.lower()
    命中关键词 = []
    
    for 关键词 in 关键词列表:
        if 关键词 in 文本小写:
            命中关键词.append(关键词)
    
    return (len(命中关键词) > 0, 命中关键词)


def _获取AI_API_KEY() -> str:
    """获取AI API密钥"""
    import os
    import json
    
    # 方法1: 从环境变量
    api_key = os.environ.get('QWEN_API_KEY')
    if api_key:
        return api_key
    
    # 方法2: 从配置文件
    try:
        config_file = os.path.join(os.path.dirname(__file__), "..", "脚本配置", "qwen_api_key.json")
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('api_key', '')
    except:
        pass
    
    return ''


class 评论区挖掘器:
    """评论区挖掘器类 - AI识别意向"""
    
    def __init__(self, driver: "WebDriver", 浏览器ID: str = None):
        self.driver = driver
        self.浏览器ID = 浏览器ID
        
        # 统计
        self.已分析评论数 = 0
        self.关键词命中数 = 0
        self.关键词未命中数 = 0
        self.高意向用户数 = 0
        self.中意向用户数 = 0
        self.低意向用户数 = 0
        self.已记录用户数 = 0
        
        # 预加载关键词
        关键词数量 = len(_加载意向关键词())
        print(f"[评论区挖掘器] 初始化完成，浏览器ID={浏览器ID}，关键词数量={关键词数量}")
    
    def AI识别意向(self, 评论文本: str, log_func=None) -> tuple[int, str]:
        """
        使用AI识别评论者的意向等级
        
        Args:
            评论文本: 评论内容
            log_func: 日志函数
        
        Returns:
            (意向评分 0-10, 意向描述)
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        if not AI工具可用:
            return (0, "AI工具不可用")
        
        try:
            # 获取产品类目
            类目 = 获取产品类目()
            
            # 转义评论文本
            转义后文本 = 转义特殊字符(评论文本)
            
            # 构造提示词
            prompt = f"""你是一名专业的客户意向分析专家。请分析以下评论者对"{类目}"产品的购买意向。

评论内容：
{转义后文本}

分析维度：
1. 是否提及价格、采购、供应商等商业关键词
2. 是否表达明确的购买需求或询问
3. 是否表现出专业的行业知识
4. 语气是否认真、专业

意向等级定义：
- 9-10分（高意向）：明确提及价格、MOQ、供应商、采购等，有明显购买意图
  关键词示例：price, cost, MOQ, supplier, wholesale, bulk order, quote
  
- 6-8分（中意向）：询问产品信息、表达兴趣、寻求帮助
  关键词示例：how, where, can I, info, details, contact, interested
  
- 3-5分（低意向）：简单的赞美、表情符号、礼貌性回复
  关键词示例：good, nice, great, love, beautiful, thanks
  
- 0-2分（无意向）：无关内容、垃圾评论、纯表情

输出格式（必须严格遵守）：
评分：X
理由：简短说明（20字以内）

示例：
评分：9
理由：询问批发价格和MOQ

现在请分析上述评论："""
            
            # 请求数据
            request_data = {
                "model": _AI_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            # 发送请求
            response = requests.post(
                _AI_API_URL,
                json=request_data,
                headers={
                    "Authorization": f"Bearer {_获取AI_API_KEY()}",
                    "Content-Type": "application/json"
                },
                timeout=_AI_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("choices") and len(result["choices"]) > 0:
                    content = result["choices"][0].get("message", {}).get("content", "")
                    
                    # 解析响应
                    评分 = 0
                    理由 = "解析失败"
                    
                    lines = content.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if line.startswith('评分：') or line.startswith('评分:'):
                            try:
                                评分 = int(line.split('：')[-1].split(':')[-1].strip())
                            except:
                                pass
                        elif line.startswith('理由：') or line.startswith('理由:'):
                            理由 = line.split('：')[-1].split(':')[-1].strip()
                    
                    return (评分, 理由)
            
        except Exception as e:
            if log_func:
                log(f"    AI识别失败: {e}")
        
        return (0, "识别失败")
    
    def 提取用户信息(self, 评论元素: "WebElement", log_func=None) -> Optional[Dict[str, str]]:
        """
        从评论元素提取用户信息（适配div[dir='auto']元素）
        
        Args:
            评论元素: 评论元素（可能是div[dir='auto']）
            log_func: 日志函数
        
        Returns:
            用户信息字典 {user_id, user_name, profile_url}
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        try:
            # 策略1：直接在评论元素内部查找用户链接
            user_links = self._在元素内查找用户链接(评论元素, log_func)
            
            if user_links:
                # 找到用户链接，提取信息
                最佳链接 = self._选择最佳用户链接(user_links, log_func)
                if 最佳链接:
                    return self._从链接提取用户信息(最佳链接, log_func)
            
            # 策略2：在父容器中查找用户链接
            user_links = self._在父容器查找用户链接(评论元素, log_func)
            
            if user_links:
                # 找到用户链接，提取信息
                最佳链接 = self._选择最佳用户链接(user_links, log_func)
                if 最佳链接:
                    return self._从链接提取用户信息(最佳链接, log_func)
            
            # 策略3：在评论弹窗中通过位置匹配查找用户链接
            user_links = self._在弹窗中按位置查找用户链接(评论元素, log_func)
            
            if user_links:
                最佳链接 = self._选择最佳用户链接(user_links, log_func)
                if 最佳链接:
                    return self._从链接提取用户信息(最佳链接, log_func)
            
            # 策略4：从文本中提取用户名
            return self._从文本提取用户信息(评论元素, log_func)
            
        except Exception as e:
            if log_func:
                log(f"        [调试-提取用户] 异常: {e}")
            return None
    
    def _在元素内查找用户链接(self, 元素: "WebElement", log_func=None) -> List["WebElement"]:
        """在元素内部查找用户链接"""
        try:
            user_links = []
            user_links.extend(元素.find_elements("css selector", "a[href*='/user/']"))
            user_links.extend(元素.find_elements("css selector", "a[href*='/profile.php']"))
            
            all_links = 元素.find_elements("css selector", "a[role='link'], a[tabindex='0'], a[href^='https://www.facebook.com/']")
            for link in all_links:
                href = link.get_attribute("href") or ""
                if href and self._是用户主页链接(href):
                    user_links.append(link)
            
            return user_links
        except:
            return []
    
    def _在父容器查找用户链接(self, 元素: "WebElement", log_func=None) -> List["WebElement"]:
        """在父容器中查找用户链接"""
        try:
            # 向上查找最多3层父容器
            current = 元素
            for level in range(3):
                try:
                    parent = current.find_element("xpath", "..")
                    user_links = self._在元素内查找用户链接(parent)
                    if user_links:
                        if log_func:
                            log_func(f"        [调试-提取用户] 在第{level+1}层父容器找到 {len(user_links)} 个用户链接")
                        return user_links
                    current = parent
                except:
                    break
            return []
        except:
            return []
    
    def _在弹窗中按位置查找用户链接(self, 评论元素: "WebElement", log_func=None) -> List["WebElement"]:
        """在评论弹窗中通过位置匹配查找用户链接"""
        try:
            # 获取评论元素的Y坐标
            评论Y坐标 = 评论元素.location['y']
            
            # 查找评论弹窗
            评论弹窗 = None
            dialogs = self.driver.find_elements("css selector", "[role='dialog']")
            for dialog in dialogs:
                if dialog.is_displayed():
                    评论弹窗 = dialog
                    break
            
            if not 评论弹窗:
                return []
            
            # 在弹窗中查找所有用户链接
            all_links = []
            all_links.extend(评论弹窗.find_elements("css selector", "a[href*='/user/']"))
            all_links.extend(评论弹窗.find_elements("css selector", "a[href*='/profile.php']"))
            all_links.extend(评论弹窗.find_elements("css selector", "a[role='link'][tabindex='0']"))
            
            # 去重
            seen_hrefs = set()
            unique_links = []
            for link in all_links:
                href = link.get_attribute("href") or ""
                if href and href not in seen_hrefs and self._是用户主页链接(href):
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
                if log_func:
                    log_func(f"        [调试-提取用户] 在弹窗中找到 {len(nearby_links)} 个附近的用户链接")
                return [link for _, link in nearby_links]
            
            return []
        except:
            return []
    
    def _选择最佳用户链接(self, user_links: List["WebElement"], log_func=None) -> Optional["WebElement"]:
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
    
    def _从链接提取用户信息(self, 链接: "WebElement", log_func=None) -> Optional[Dict[str, str]]:
        """从用户链接提取用户信息"""
        try:
            profile_url = 链接.get_attribute("href")
            user_name = 链接.text.strip()
            
            if log_func:
                log_func(f"        [调试-提取用户] 找到用户: {user_name}")
                log_func(f"        [调试-提取用户] profile_url: {profile_url[:100] if profile_url else 'None'}")
            
            # 提取用户ID
            user_id = self._提取用户ID(profile_url)
            
            if log_func:
                log_func(f"        [调试-提取用户] user_id: {user_id if user_id else '(提取失败)'}")
            
            if not user_id or not user_name:
                return None
            
            return {
                "user_id": user_id,
                "user_name": user_name,
                "profile_url": profile_url
            }
        except:
            return None
    
    def _是用户主页链接(self, href: str) -> bool:
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
                "/groups/", "/pages/", "/events/", "/marketplace/"
            ]):
                return False
            
            # 检查是否是简单的用户名格式
            path = href.replace("https://www.facebook.com/", "").split("/")[0].split("?")[0]
            if path and len(path) > 2 and not path.isdigit():
                return True
        
        return False
    
    def _提取用户ID(self, profile_url: str) -> str:
        """从profile_url提取用户ID"""
        if not profile_url:
            return ""
        
        try:
            if "/user/" in profile_url:
                return profile_url.split("/user/")[1].split("/")[0].split("?")[0]
            elif "profile.php?id=" in profile_url:
                return profile_url.split("profile.php?id=")[1].split("&")[0]
            else:
                # 尝试从URL中提取用户名作为ID
                import re
                match = re.search(r'facebook\.com/([^/\?]+)', profile_url)
                if match:
                    return match.group(1)
        except:
            pass
        
        return ""
    
    def _从文本提取用户信息(self, 评论元素: "WebElement", log_func=None) -> Optional[Dict[str, str]]:
        """
        当无法找到用户链接时，尝试从文本中提取用户名
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        try:
            # 获取评论元素的完整文本
            full_text = 评论元素.text.strip()
            
            if not full_text:
                return None
            
            # 尝试从文本结构中提取用户名
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            
            if len(lines) >= 2:
                if log_func:
                    log(f"        [调试-提取用户] 分析文本行: {lines[:5]}")
                
                # 检测是否是作者评论（包含Author标签）
                if lines[0].lower() == 'author':
                    if log_func:
                        log(f"        [调试-提取用户] 检测到Author标签，跳过作者评论")
                    return None
                
                # 寻找用户名：通常是第一行，且符合用户名特征
                for i, line in enumerate(lines[:3]):  # 检查前3行
                    if log_func:
                        log(f"        [调试-提取用户] 检查行{i}: '{line}'")
                    
                    # 跳过明显的按钮和标签
                    if line.lower() in ['like', 'reply', 'share', 'comment', 'see translation', 'see more', 'author']:
                        if log_func:
                            log(f"        [调试-提取用户] 跳过按钮/标签: {line}")
                        continue
                    
                    # 跳过数字（点赞数等）
                    if line.isdigit() or (line.endswith('w') and line[:-1].isdigit()) or (line.endswith('k') and line[:-1].isdigit()):
                        if log_func:
                            log(f"        [调试-提取用户] 跳过数字: {line}")
                        continue
                    
                    # 检查是否是用户名特征
                    is_username = (
                        2 <= len(line) <= 50 and  # 合理长度
                        not any(keyword in line.lower() for keyword in [
                            'ago', 'hour', 'minute', 'day', 'week', 'month', 'year',
                            'like', 'reply', 'share', 'comment', 'see more', 'show more',
                            '小时', '分钟', '天', '周', '月', '年', '回复', '点赞', '分享', '评论',
                            'translation', 'translate'
                        ]) and
                        not any(time_word in line.lower() for time_word in ['am', 'pm']) and
                        # 用户名通常不包含太多标点符号
                        line.count('?') + line.count('!') + line.count('.') <= 1
                    )
                    
                    # 额外检查：如果包含多个单词且没有问号/感叹号，更可能是用户名
                    words = line.split()
                    if len(words) >= 2 and not any(char in line for char in ['?', '!']):
                        # 检查是否像人名（包含大写字母开头的单词）
                        if any(word[0].isupper() for word in words if word):
                            is_username = True
                    
                    if is_username:
                        if log_func:
                            log(f"        [调试-提取用户] 找到用户名: {line}")
                        
                        # 生成用户ID
                        user_id = f"text_extracted_{hash(line) % 1000000}"
                        
                        return {
                            "user_id": user_id,
                            "user_name": line,
                            "profile_url": ""
                        }
                    else:
                        if log_func:
                            log(f"        [调试-提取用户] 不符合用户名特征: {line}")
            
            if log_func:
                log(f"        [调试-提取用户] 无法从文本提取用户名")
            
            return None
            
        except Exception as e:
            if log_func:
                log(f"        [调试-提取用户] 文本提取异常: {e}")
            return None
    
    def 记录到潜在用户池(
        self,
        用户信息: Dict[str, str],
        意向评分: int,
        评论文本: str,
        来源帖子ID: str = "",
        来源评论ID: str = "",
        log_func=None
    ) -> bool:
        """
        记录用户到潜在用户池
        
        Args:
            用户信息: 用户信息字典
            意向评分: 意向评分（0-10）
            评论文本: 评论内容
            来源帖子ID: 来源帖子ID
            来源评论ID: 来源评论ID
            log_func: 日志函数
        
        Returns:
            是否成功记录
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        if not _db:
            return False
        
        try:
            # 计算下次动作日期（T+1天起，随机1-3天）
            下次动作日期 = datetime.now() + timedelta(days=random.randint(1, 3))
            
            # 记录到数据库
            success = _db.add_potential_user(
                user_id=用户信息["user_id"],
                user_name=用户信息["user_name"],
                profile_url=用户信息["profile_url"],
                intent_score=意向评分,
                comment_text=评论文本,
                source_post_id=来源帖子ID,
                source_comment_id=来源评论ID,
                discovered_by=self.浏览器ID or "unknown",
                next_action_date=下次动作日期.strftime("%Y-%m-%d")
            )
            
            if success:
                self.已记录用户数 += 1
                log(f"      成功: 已记录到潜在用户池（下次动作: {下次动作日期.strftime('%Y-%m-%d')}）")
                return True
            
        except Exception as e:
            log(f"      记录失败: {e}")
        
        return False
    
    def 执行意向分级动作(
        self,
        评论元素: "WebElement",
        意向评分: int,
        用户信息: Dict[str, str],
        log_func=None
    ) -> bool:
        """
        根据意向评分执行相应动作
        
        Args:
            评论元素: 评论元素
            意向评分: 意向评分（0-10）
            用户信息: 用户信息
            log_func: 日志函数
        
        Returns:
            是否执行了动作
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        try:
            if 意向评分 >= 9:
                # 高意向（9-10分）：只点赞评论
                log(f"      高意向用户: {用户信息['user_name']} (评分: {意向评分})")
                
                # 查找点赞按钮
                try:
                    buttons = 评论元素.find_elements("css selector", "[aria-label='Like' i]")
                    for btn in buttons:
                        if btn.is_displayed():
                            # 检查是否已点赞
                            pressed = btn.get_attribute("aria-pressed")
                            if pressed != "true":
                                self.driver.execute_script("arguments[0].click();", btn)
                                log(f"        成功: 点赞评论")
                                time.sleep(random.uniform(1, 2))
                                return True
                except:
                    pass
                
            elif 意向评分 >= 6:
                # 中意向（6-8分）：访问主页
                log(f"      中意向用户: {用户信息['user_name']} (评分: {意向评分})")
                
                # 点击用户链接
                try:
                    links = 评论元素.find_elements("css selector", "a[href*='/user/'], a[href*='/profile.php']")
                    if links:
                        link = links[0]
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link)
                        time.sleep(random.uniform(0.5, 1))
                        
                        self.driver.execute_script("arguments[0].click();", link)
                        log(f"        成功: 访问主页")
                        
                        # 等待页面加载
                        time.sleep(random.uniform(3, 5))
                        
                        # 返回上一页
                        self.driver.back()
                        time.sleep(random.uniform(2, 3))
                        return True
                except:
                    pass
                
            elif 意向评分 >= 3:
                # 低意向（3-5分）：点赞评论
                log(f"      低意向用户: {用户信息['user_name']} (评分: {意向评分})")
                
                # 查找点赞按钮
                try:
                    buttons = 评论元素.find_elements("css selector", "[aria-label='Like' i]")
                    for btn in buttons:
                        if btn.is_displayed():
                            pressed = btn.get_attribute("aria-pressed")
                            if pressed != "true":
                                self.driver.execute_script("arguments[0].click();", btn)
                                log(f"        成功: 点赞评论")
                                time.sleep(random.uniform(1, 2))
                                return True
                except:
                    pass
            
            else:
                # 无意向（0-2分）：不操作
                log(f"      无意向用户: {用户信息['user_name']} (评分: {意向评分})")
            
        except Exception as e:
            log(f"      执行动作失败: {e}")
        
        return False
    
    def 分析评论列表(
        self,
        评论列表: List["WebElement"],
        来源帖子ID: str = "",
        log_func=None
    ) -> int:
        """
        分析评论列表，识别高意向用户（仅使用关键词匹配）
        
        Args:
            评论列表: 评论元素列表
            来源帖子ID: 来源帖子ID
            log_func: 日志函数
        
        Returns:
            分析的评论数量
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        已分析 = 0
        
        log(f"")
        log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log(f"[评论区挖掘] 开始关键词匹配")
        log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log(f"[评论区挖掘] 待分析评论数: {len(评论列表)}")
        log(f"[评论区挖掘] 关键词库: {len(_加载意向关键词())} 个多语言关键词")
        
        # 提取帖子作者名字（用于过滤作者自己的评论）
        帖子作者 = self._提取帖子作者(log)
        if 帖子作者:
            log(f"[评论区挖掘] 帖子作者: {帖子作者}")
        
        log(f"")
        
        for idx, 评论元素 in enumerate(评论列表, 1):
            try:
                # 提取用户信息（先提取用户，再提取评论文本）
                用户信息 = self.提取用户信息(评论元素, log)
                
                if not 用户信息:
                    if log_func:
                        log(f"[评论 #{idx}] 跳过：无法提取用户信息")
                    continue
                
                # 过滤掉帖子作者的评论
                if 帖子作者 and 用户信息['user_name']:
                    # 检查用户名是否与作者名字匹配
                    用户名 = 用户信息['user_name'].strip()
                    作者名 = 帖子作者.strip()
                    
                    # 移除可能的后缀（如 "'s Post"）
                    作者名_清理 = 作者名.replace("'s Post", "").replace("'s post", "").strip()
                    
                    # 调试输出
                    if log_func:
                        log(f"[评论 #{idx}] [调试-过滤] 用户名='{用户名}', 作者名='{作者名_清理}'")
                        log(f"[评论 #{idx}] [调试-过滤] profile_url={用户信息.get('profile_url', '')[:80]}")
                    
                    # 匹配检查
                    if 用户名 == 作者名 or 用户名 == 作者名_清理 or 作者名_清理 in 用户名:
                        if log_func:
                            log(f"[评论 #{idx}] 跳过：这是帖子作者的评论（{用户名}）")
                        continue
                
                # 提取评论文本
                评论文本 = 评论元素.text.strip()
                
                if log_func:
                    log(f"[评论 #{idx}] [调试] 评论文本长度: {len(评论文本)}, 内容: {评论文本[:50] if 评论文本 else '(空)'}")
                
                if not 评论文本 or len(评论文本) < 5:
                    if log_func:
                        log(f"[评论 #{idx}] 跳过：评论文本为空或太短")
                    continue
                
                # 过滤掉明显是作者回复的评论（基于内容特征）
                作者回复关键词 = [
                    "please contact me",
                    "contact me via",
                    "dm me",
                    "message me",
                    "inbox me",
                    "whatsapp me",
                    "call me",
                    "reach me",
                    "get in touch",
                    "联系我",
                    "私信我",
                    "加我",
                ]
                
                评论文本小写 = 评论文本.lower()
                是作者回复 = any(关键词 in 评论文本小写 for 关键词 in 作者回复关键词)
                
                if 是作者回复:
                    if log_func:
                        log(f"[评论 #{idx}] 跳过：疑似作者回复（包含回复关键词）")
                    continue
                
                log(f"[评论 #{idx}] 用户: {用户信息['user_name']}")
                log(f"[评论 #{idx}] 内容: {评论文本[:100]}")
                
                # 关键词匹配
                命中, 命中关键词 = _检查关键词命中(评论文本)
                
                if not 命中:
                    # 未命中关键词，跳过
                    self.关键词未命中数 += 1
                    log(f"[评论 #{idx}] 未命中关键词，跳过")
                    log(f"")
                    continue
                
                # 命中关键词
                self.关键词命中数 += 1
                self.已分析评论数 += 1
                已分析 += 1
                
                关键词显示 = ', '.join(命中关键词[:5])
                if len(命中关键词) > 5:
                    关键词显示 += f" (+{len(命中关键词) - 5}个)"
                log(f"[评论 #{idx}] [命中] 关键词: {关键词显示}")
                
                # 根据命中关键词数量判断意向等级
                if len(命中关键词) >= 3:
                    意向等级 = "高意向"
                    意向评分 = 9
                    self.高意向用户数 += 1
                elif len(命中关键词) >= 2:
                    意向等级 = "中意向"
                    意向评分 = 7
                    self.中意向用户数 += 1
                else:
                    意向等级 = "低意向"
                    意向评分 = 5
                    self.低意向用户数 += 1
                
                log(f"[评论 #{idx}] [意向] {意向等级} (命中{len(命中关键词)}个关键词)")
                
                # 记录到潜在用户池（意向评分>=5，包含低意向用户）
                if 意向评分 >= 5:
                    记录成功 = self.记录到潜在用户池(
                        用户信息=用户信息,
                        意向评分=意向评分,
                        评论文本=评论文本,
                        来源帖子ID=来源帖子ID,
                        log_func=log
                    )
                    if 记录成功:
                        log(f"[评论 #{idx}] [记录] 已记录到潜在用户池")
                
                # 执行意向分级动作
                self.执行意向分级动作(
                    评论元素=评论元素,
                    意向评分=意向评分,
                    用户信息=用户信息,
                    log_func=log
                )
                
                log(f"")
                
                # 等待一下
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                log(f"[评论 #{idx}] 分析失败: {e}")
                log(f"")
                continue
        
        # 输出统计
        log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log(f"[评论区挖掘] 统计")
        log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log(f"   总评论数: {len(评论列表)}")
        log(f"   关键词命中: {self.关键词命中数} 条")
        log(f"   关键词未命中: {self.关键词未命中数} 条")
        if self.已分析评论数 > 0:
            log(f"   ├─ 高意向: {self.高意向用户数} 个 (命中3+关键词)")
            log(f"   ├─ 中意向: {self.中意向用户数} 个 (命中2个关键词)")
            log(f"   └─ 低意向: {self.低意向用户数} 个 (命中1个关键词)")
        log(f"   记录用户数: {self.已记录用户数} 个")
        log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log(f"")
        
        return 已分析
    
    def _提取帖子作者(self, log_func=None) -> Optional[str]:
        """
        提取帖子作者名字
        
        Args:
            log_func: 日志函数
        
        Returns:
            作者名字，如果提取失败返回None
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        try:
            # 查找评论弹窗
            评论弹窗 = None
            try:
                dialogs = self.driver.find_elements("css selector", "[role='dialog']")
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
                h2_elements = 评论弹窗.find_elements("css selector", "h2[dir='auto']")
                for h2 in h2_elements:
                    text = h2.text.strip()
                    # 检查是否包含 "'s Post" 或 "'s post"
                    if "'s Post" in text or "'s post" in text:
                        # 提取作者名字（移除 "'s Post" 后缀）
                        作者名 = text.replace("'s Post", "").replace("'s post", "").strip()
                        if log_func:
                            log(f"        [调试-作者] 找到作者: {作者名}")
                        return 作者名
            except:
                pass
            
            # 方法2: 通过span标签查找
            try:
                span_elements = 评论弹窗.find_elements("css selector", "span[dir='auto']")
                for span in span_elements:
                    text = span.text.strip()
                    if "'s Post" in text or "'s post" in text:
                        作者名 = text.replace("'s Post", "").replace("'s post", "").strip()
                        if log_func:
                            log(f"        [调试-作者] 找到作者: {作者名}")
                        return 作者名
            except:
                pass
            
            return None
            
        except Exception as e:
            if log_func:
                log(f"        [调试-作者] 提取失败: {e}")
            return None
    
    def 获取统计(self) -> Dict[str, int]:
        """
        获取统计信息
        
        Returns:
            统计字典
        """
        return {
            "已分析评论数": self.已分析评论数,
            "关键词命中数": self.关键词命中数,
            "关键词未命中数": self.关键词未命中数,
            "高意向用户数": self.高意向用户数,
            "中意向用户数": self.中意向用户数,
            "低意向用户数": self.低意向用户数,
            "已记录用户数": self.已记录用户数,
        }


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("评论区挖掘模块 - 测试")
    print("=" * 60)
    
    # 模拟测试
    class MockDriver:
        def find_elements(self, by, value):
            return []
        
        def execute_script(self, script, *args):
            pass
    
    driver = MockDriver()
    挖掘器 = 评论区挖掘器(driver, "test_browser_id")
    
    print("\n[测试1] AI意向识别...")
    
    测试评论 = [
        ("What's the MOQ and price for bulk order?", "高意向"),
        ("How can I contact you for more details?", "中意向"),
        ("Nice product! Love it!", "低意向"),
        ("😊😊😊", "无意向"),
    ]
    
    for 评论, 预期 in 测试评论:
        评分, 理由 = 挖掘器.AI识别意向(评论)
        print(f"\n  评论: {评论}")
        print(f"  评分: {评分}/10")
        print(f"  理由: {理由}")
        print(f"  预期: {预期}")
        print(f"  {'成功' if (评分 >= 9 and 预期 == '高意向') or (6 <= 评分 < 9 and 预期 == '中意向') or (3 <= 评分 < 6 and 预期 == '低意向') or (评分 < 3 and 预期 == '无意向') else '失败'}")
    
    print("\n[测试2] 获取统计信息...")
    统计 = 挖掘器.获取统计()
    print(f"  已分析评论数: {统计['已分析评论数']}")
    print(f"  高意向用户数: {统计['高意向用户数']}")
    print(f"  中意向用户数: {统计['中意向用户数']}")
    print(f"  低意向用户数: {统计['低意向用户数']}")
    print(f"  已记录用户数: {统计['已记录用户数']}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
