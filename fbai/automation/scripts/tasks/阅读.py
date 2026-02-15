"""
阅读任务
模拟真人阅读 Facebook 首页文章

特性：
- 极小幅度滚动（模拟手指轻滑）
- 长时间停留阅读
- 随机行为模式
- 偶尔不操作（发呆）
- 50%概率通过搜索关键词浏览
- 点赞功能（只点赞超过10赞的帖子）

使用方法：
- 调试模式：修改 DEBUG_BROWSER_ID，直接运行此文件
- 正式调用：main.py 中调用 阅读(driver, ...)
"""

import os
import sys
import time
import random
import math
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

from tasks.去重管理 import 检查是否已操作, 记录操作, 从元素查找帖子ID

# 数据上报 API
数据上报API = "http://localhost:8805/add_data"

# ==================== 调试配置 ====================

# 从环境变量读取浏览器ID
DEBUG_BROWSER_ID = os.environ.get('DEBUG_BROWSER_ID', "7d9ecff84fef490987dcb58004fa2c82")

# ==================== 配置 ====================

@dataclass
class 阅读配置:
    """阅读任务配置"""
    最少阅读文章数: int = 2
    最多阅读文章数: int = 5
    总时长限制秒: int = 600
    搜索概率: float = 0.5
    点赞数量: int = 0
    最低点赞数: int = 10
    评论数量: int = 0

# ==================== 数据上报 ====================

def 上报点赞数据(点赞数: int = 1):
    """上报点赞数据到服务器"""
    try:
        requests.get(f"{数据上报API}?likes={点赞数}", timeout=5)
    except:
        pass

# ==================== 关键词读取 ====================

def 读取搜索关键词() -> List[str]:
    """从搜索关键词.txt读取关键词列表"""
    关键词文件 = os.path.join(脚本配置目录, "搜索关键词.txt")
    
    if not os.path.exists(关键词文件):
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

def 获取随机关键词() -> Optional[str]:
    """随机获取一个搜索关键词"""
    关键词列表 = 读取搜索关键词()
    if 关键词列表:
        return random.choice(关键词列表)
    return None

# ==================== 点赞功能 ====================

def 解析点赞数文本(text: str) -> int:
    """解析点赞数文本，支持 K/M 格式"""
    if not text:
        return 0
    
    text = text.strip().upper()
    
    try:
        if 'K' in text:
            match = re.search(r'([\d.]+)\s*K', text)
            if match:
                return int(float(match.group(1)) * 1000)
        elif 'M' in text:
            match = re.search(r'([\d.]+)\s*M', text)
            if match:
                return int(float(match.group(1)) * 1000000)
        else:
            clean_text = text.replace(',', '')
            numbers = re.findall(r'\d+', clean_text)
            if numbers:
                return int(numbers[0])
    except:
        pass
    
    return 0

def 获取帖子点赞数(帖子元素, debug=False) -> int:
    """
    获取帖子的点赞数量
    
    Facebook 点赞数元素结构示例:
    <span class="xt0b8zv x1jx94hy xj87blo x1lbueug">
        <span><span class="x135b78x">193K</span></span>
    </span>
    """
    找到的数字 = []
    
    try:
        # 方法1: 查找所有 span，找包含 K/M 或纯数字的文本
        all_spans = 帖子元素.find_elements("css selector", "span")
        
        for span in all_spans:
            try:
                text = span.text.strip()
                if not text or len(text) > 15:
                    continue
                
                # 检查是否是点赞数格式
                if re.match(r'^[\d,.]+[KkMm]?$', text):
                    数量 = 解析点赞数文本(text)
                    找到的数字.append((text, 数量))
                    if 数量 >= 10:
                        if debug:
                            print(f"  找到点赞数: {text} = {数量}")
                        return 数量
            except:
                continue
        
        # 方法2: 查找带有反应数量的 aria-label
        点赞数选择器 = [
            "[aria-label*='reaction']",
            "[aria-label*='Like']",
            "[aria-label*='like']",
            "[aria-label*='people reacted']",
            "[aria-label*='others']",
        ]
        
        for 选择器 in 点赞数选择器:
            try:
                elements = 帖子元素.find_elements("css selector", 选择器)
                for el in elements:
                    label = el.get_attribute("aria-label") or ""
                    if label:
                        numbers = re.findall(r'[\d,]+', label)
                        for num_str in numbers:
                            num = int(num_str.replace(',', ''))
                            if num >= 10:
                                if debug:
                                    print(f"  从aria-label找到: {label} = {num}")
                                return num
            except:
                continue
        
    except Exception as e:
        if debug:
            print(f"获取点赞数异常: {e}")
    
    if debug and 找到的数字:
        print(f"  找到的数字（未达标）: {找到的数字[:5]}")
    
    return 0

def 点赞帖子(driver: "WebDriver", 最低点赞数: int = 10, log_func=None, debug=False) -> bool:
    """
    点赞当前可见的帖子（只点赞超过指定点赞数的帖子）
    
    策略：
    1. 直接查找所有点赞数显示元素（"Like: 8.9K people" 格式）
    2. 直接查找所有可点击的 Like 按钮（aria-label="Like"）
    3. 根据 Y 坐标匹配点赞数和按钮
    4. 点击符合条件的帖子
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        # 1. 查找所有点赞数显示元素（"Like: 8.9K people" 格式）
        like_count_elements = driver.find_elements(By.CSS_SELECTOR, "[aria-label*='Like'][aria-label*='people']")
        
        if debug:
            log(f"找到点赞数显示元素: {len(like_count_elements)} 个")
        
        # 筛选出符合条件的点赞数元素
        符合条件的 = []
        for el in like_count_elements:
            try:
                if not el.is_displayed():
                    continue
                
                label = el.get_attribute("aria-label") or ""
                
                # 解析 "Like: 8.9K people" 格式
                match = re.search(r'Like:\s*([\d.]+)([KkMm])?\s*people', label)
                if match:
                    num_str = match.group(1)
                    suffix = match.group(2) or ""
                    
                    数量 = float(num_str)
                    if suffix.upper() == 'K':
                        数量 *= 1000
                    elif suffix.upper() == 'M':
                        数量 *= 1000000
                    数量 = int(数量)
                    
                    if debug:
                        log(f"  发现: {label} -> {数量} 赞")
                    
                    if 数量 >= 最低点赞数:
                        location = el.location
                        符合条件的.append({
                            'element': el,
                            'count': 数量,
                            'y': location['y']
                        })
            except:
                continue
        
        if debug:
            log(f"符合条件的帖子: {len(符合条件的)} 个")
        
        if not 符合条件的:
            log(f"未找到符合条件的帖子（需要 {最低点赞数}+ 赞）")
            return False
        
        # 2. 查找所有可点击的 Like 按钮（aria-label 精确等于 "Like"）
        like_buttons = driver.find_elements(By.CSS_SELECTOR, "[aria-label='Like']")
        
        可点击按钮 = []
        for btn in like_buttons:
            try:
                if btn.is_displayed():
                    # 检查是否已点赞
                    pressed = btn.get_attribute("aria-pressed")
                    if pressed != "true":
                        location = btn.location
                        可点击按钮.append({
                            'element': btn,
                            'y': location['y']
                        })
            except:
                continue
        
        if debug:
            log(f"可点击的 Like 按钮: {len(可点击按钮)} 个")
            for i, btn_info in enumerate(可点击按钮[:5], 1):
                log(f"  按钮 {i}: y={btn_info['y']}")
        
        if not 可点击按钮:
            log("没有可点击的 Like 按钮")
            return False
        
        # 3. 匹配点赞数和按钮（根据 Y 坐标）
        # 随机打乱顺序
        random.shuffle(符合条件的)
        
        for count_info in 符合条件的:
            点赞数 = count_info['count']
            元素y = count_info['y']
            
            if debug:
                log(f"\n处理: {点赞数} 赞的帖子 (y={元素y})")
            
            # 找到最近的 Like 按钮（Y 坐标最接近）
            最近按钮 = None
            最小距离 = float('inf')
            
            for btn_info in 可点击按钮:
                按钮y = btn_info['y']
                # 计算距离（绝对值）
                距离 = abs(按钮y - 元素y)
                # 按钮应该在合理范围内（上下300px）
                if 距离 < 最小距离 and 距离 < 300:
                    最小距离 = 距离
                    最近按钮 = btn_info['element']
            
            if not 最近按钮:
                if debug:
                    log(f"  未找到匹配的 Like 按钮（距离>{300}px）")
                continue
            
            if debug:
                log(f"  找到匹配按钮，距离: {最小距离}px")
            
            # 4. 点击点赞
            # 滚动到按钮可见
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 最近按钮)
            time.sleep(random.uniform(0.3, 0.8))
            
            # 移动鼠标到按钮
            try:
                actions = ActionChains(driver)
                actions.move_to_element(最近按钮)
                actions.perform()
                time.sleep(random.uniform(0.2, 0.5))
            except:
                pass
            
            # 点击（优先使用 JavaScript 避免被遮挡）
            try:
                driver.execute_script("arguments[0].click();", 最近按钮)
            except:
                try:
                    最近按钮.click()
                except:
                    if debug:
                        log("  点击失败，跳过")
                    continue
            
            log(f"✓ 点赞成功（帖子有 {点赞数} 赞）")
            
            # 上报数据
            上报点赞数据(1)
            
            time.sleep(random.uniform(1, 3))
            return True
        
        log("未找到可匹配的 Like 按钮")
        return False
        
    except Exception as e:
        log(f"点赞失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

# ==================== 评论功能 ====================

def 获取随机评论图片() -> Optional[str]:
    """
    从评论图片文件夹随机获取一张图片
    
    Returns:
        图片的绝对路径，如果文件夹为空或不存在则返回 None
    """
    评论图片目录 = os.path.join(脚本配置目录, "评论图片")
    
    if not os.path.exists(评论图片目录):
        return None
    
    try:
        # 获取所有图片文件
        图片扩展名 = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        图片文件列表 = []
        
        for 文件名 in os.listdir(评论图片目录):
            文件路径 = os.path.join(评论图片目录, 文件名)
            if os.path.isfile(文件路径):
                _, 扩展名 = os.path.splitext(文件名.lower())
                if 扩展名 in 图片扩展名:
                    图片文件列表.append(文件路径)
        
        if 图片文件列表:
            return random.choice(图片文件列表)
        
    except Exception:
        pass
    
    return None

def 移除表情符号(text: str) -> str:
    """
    移除文本中的表情符号（emoji）
    ChromeDriver 只支持 BMP 字符，需要过滤掉 emoji
    """
    import re
    # 移除 emoji 和其他非 BMP 字符
    # 保留基本的 ASCII、中文、标点符号等
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # 表情符号
        "\U0001F300-\U0001F5FF"  # 符号和象形文字
        "\U0001F680-\U0001F6FF"  # 交通和地图符号
        "\U0001F1E0-\U0001F1FF"  # 旗帜
        "\U00002702-\U000027B0"  # 装饰符号
        "\U000024C2-\U0001F251"  # 其他符号
        "\U0001F900-\U0001F9FF"  # 补充符号和象形文字
        "\U0001FA00-\U0001FA6F"  # 扩展符号
        "\U00002600-\U000026FF"  # 杂项符号
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text).strip()

def 评论帖子(driver: "WebDriver", log_func=None, debug=False) -> bool:
    """
    评论当前可见的帖子
    
    新策略：
    1. 不点击 "Leave a comment" 按钮
    2. 直接使用帖子下方已存在的评论输入框
    3. 直接查找输入框附近的上传按钮（不需要先点击）
    4. 使用全局去重机制，避免重复评论同一帖子（所有账号共用）
    
    Args:
        driver: WebDriver实例
        log_func: 日志函数
        debug: 是否开启调试模式
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        # 导入 AI 评论函数
        from tasks.自动化工具 import AI评论_带帖子内容
        
        # 1. 查找所有帖子内容元素
        content_divs = driver.find_elements(By.CSS_SELECTOR, "div[dir='auto']")
        
        if debug:
            log(f"找到 div[dir='auto']: {len(content_divs)} 个")
        
        # 过滤出有实际文本内容的
        有效内容 = []
        for div in content_divs:
            try:
                text = div.text.strip()
                if text and len(text) > 10 and div.is_displayed():
                    location = div.location
                    有效内容.append({
                        'element': div,
                        'text': text,
                        'y': location['y']
                    })
            except:
                continue
        
        if debug:
            log(f"有效内容: {len(有效内容)} 个")
        
        if not 有效内容:
            log("未找到有效的帖子内容")
            return False
        
        # 2. 查找所有评论输入框（不点击按钮，直接查找已存在的）
        comment_inputs = []
        
        # 方法1: 通过 aria-label
        comment_inputs.extend(driver.find_elements(By.CSS_SELECTOR, "[aria-label='Write a comment']"))
        comment_inputs.extend(driver.find_elements(By.CSS_SELECTOR, "[aria-label='Write a comment...']"))
        
        # 方法2: 通过 placeholder
        comment_inputs.extend(driver.find_elements(By.CSS_SELECTOR, "[placeholder*='comment' i]"))
        comment_inputs.extend(driver.find_elements(By.CSS_SELECTOR, "[placeholder*='Comment' i]"))
        
        # 方法3: 通过 contenteditable 和 role
        comment_inputs.extend(driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true'][role='textbox']"))
        
        # 去重
        comment_inputs = list(set(comment_inputs))
        
        if debug:
            log(f"找到评论输入框: {len(comment_inputs)} 个")
        
        # 过滤出可见的输入框
        可见输入框 = []
        for inp in comment_inputs:
            try:
                if inp.is_displayed():
                    location = inp.location
                    可见输入框.append({
                        'element': inp,
                        'y': location['y']
                    })
            except:
                continue
        
        if debug:
            log(f"可见输入框: {len(可见输入框)} 个")
        
        if not 可见输入框:
            log("未找到可见的评论输入框")
            return False
        
        # 3. 匹配内容和输入框
        import random
        random.shuffle(有效内容)
        
        for content_info in 有效内容:
            帖子内容 = content_info['text']
            内容y = content_info['y']
            
            if debug:
                log(f"\n处理内容: {帖子内容[:50]}... (y={内容y})")
            
            # 从元素查找真实的帖子ID
            帖子ID = 从元素查找帖子ID(content_info['element'], driver)
            
            if not 帖子ID:
                if debug:
                    log("  跳过（无法获取帖子ID）")
                continue
            
            if debug:
                log(f"  帖子ID: {帖子ID}")
            
            # 检查是否已评论过（全局去重）
            if 检查是否已操作(帖子ID, "comment", 去重天数=15):
                if debug:
                    log("  跳过（15天内已有账号评论过）")
                continue
            
            # 调用 AI 判断
            try:
                评论内容 = AI评论_带帖子内容(帖子内容)
            except:
                评论内容 = ""
            
            if not 评论内容:
                if debug:
                    log("  跳过（AI判断无关）")
                continue
            
            # 移除表情符号
            评论内容 = 移除表情符号(评论内容)
            if not 评论内容:
                continue
            
            log(f"AI 生成评论: {评论内容[:30]}...")
            
            # 找最近的输入框（在内容下方）
            最近输入框 = None
            最小距离 = float('inf')
            
            for inp_info in 可见输入框:
                输入框y = inp_info['y']
                
                if 输入框y > 内容y:  # 必须在下方
                    距离 = 输入框y - 内容y
                    if 距离 < 最小距离 and 距离 < 1000:
                        最小距离 = 距离
                        最近输入框 = inp_info['element']
            
            if not 最近输入框:
                if debug:
                    log("  未找到匹配的输入框")
                continue
            
            if debug:
                log(f"  找到输入框，距离: {最小距离}px")
            
            # 滚动到输入框
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", 最近输入框)
            time.sleep(1)
            
            # 模拟阅读
            等待时间 = random.uniform(10, 30)
            if debug:
                log(f"  模拟阅读 {等待时间:.1f} 秒...")
            time.sleep(等待时间)
            
            # 上传图片（在点击输入框之前）
            图片已上传 = False
            try:
                图片路径 = 获取随机评论图片()
                if 图片路径:
                    if debug:
                        log(f"  准备上传图片: {os.path.basename(图片路径)}")
                    
                    输入框y = 最近输入框.location['y']
                    
                    # 1. 查找输入框附近的上传按钮
                    上传按钮 = None
                    buttons = driver.find_elements(By.CSS_SELECTOR, "[aria-label='Attach a photo or video']")
                    
                    if debug:
                        log(f"  找到 {len(buttons)} 个上传按钮")
                    
                    for btn in buttons:
                        try:
                            if btn.is_displayed():
                                btn_y = btn.location['y']
                                距离 = abs(btn_y - 输入框y)
                                if debug:
                                    log(f"    按钮 y={btn_y}, 距离={距离}")
                                if 距离 < 200:
                                    上传按钮 = btn
                                    if debug:
                                        log(f"    ✓ 选中此按钮")
                                    break
                        except:
                            continue
                    
                    if not 上传按钮:
                        if debug:
                            log("  未找到上传按钮，跳过图片上传")
                    else:
                        # 2. 点击上传按钮
                        if debug:
                            log("  点击上传按钮...")
                        
                        try:
                            driver.execute_script("arguments[0].click();", 上传按钮)
                        except:
                            上传按钮.click()
                        
                        # 等待文件选择器出现
                        time.sleep(1)
                        
                        # 3. 查找并使用 file input
                        all_file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                        if debug:
                            log(f"  找到 {len(all_file_inputs)} 个 file input")
                        
                        # 使用第一个接受 video/image 的 file input
                        # Facebook 的 file input 通常同时支持视频和图片
                        成功发送 = False
                        for idx, fi in enumerate(all_file_inputs):
                            try:
                                accept = fi.get_attribute("accept") or ""
                                
                                # 只要 accept 包含 image 或 video
                                if "image" in accept.lower() or "video" in accept.lower():
                                    if debug:
                                        log(f"  使用 file input {idx + 1}")
                                    
                                    fi.send_keys(图片路径)
                                    成功发送 = True
                                    图片已上传 = True
                                    
                                    if debug:
                                        log(f"  ✓ 图片已发送")
                                    
                                    # 等待图片上传和处理
                                    time.sleep(3)
                                    break
                                    
                            except Exception as e:
                                if debug:
                                    log(f"  file input {idx + 1} 失败: {e}")
                                continue
                        
                        if not 成功发送 and debug:
                            log("  ⚠️ 所有 file input 都发送失败")
            except Exception as e:
                if debug:
                    log(f"  图片上传异常: {e}")
            
            # 点击输入框
            if debug:
                log("  点击输入框...")
            try:
                driver.execute_script("arguments[0].click();", 最近输入框)
            except:
                最近输入框.click()
            time.sleep(0.5)
            
            # 输入评论
            if debug:
                log(f"  输入评论: {评论内容}")
            
            try:
                driver.execute_script("arguments[0].focus();", 最近输入框)
            except:
                pass
            
            time.sleep(0.5)
            
            for char in 评论内容:
                最近输入框.send_keys(char)
                time.sleep(random.uniform(0.03, 0.1))
            
            if debug:
                log("  ✓ 评论输入完成")
            
            time.sleep(random.uniform(1, 2))
            
            # 发送
            if debug:
                log("  按 Enter 发送评论...")
            
            最近输入框.send_keys(Keys.RETURN)
            
            log("✓ 评论已发送")
            
            # 记录操作（全局去重）
            try:
                记录操作(帖子ID, "comment")
                if debug:
                    log(f"  已记录操作（全局）: {帖子ID[:16]}...")
            except Exception as e:
                if debug:
                    log(f"  记录操作失败: {e}")
            
            # 上报数据
            try:
                requests.get(f"{数据上报API}?comments=1", timeout=5)
            except:
                pass
            
            time.sleep(random.uniform(2, 4))
            return True
        
        log("未找到可评论的帖子")
        return False
        
    except Exception as e:
        log(f"评论失败: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return False

# ==================== 真人模拟工具 ====================

class 真人模拟:
    """模拟真人行为的工具类"""
    
    def __init__(self, driver: "WebDriver"):
        self.driver = driver
        self._上次鼠标x = None
        self._上次鼠标y = None
    
    @staticmethod
    def 随机等待(最小秒: float = 0.5, 最大秒: float = 2.0):
        time.sleep(random.uniform(最小秒, 最大秒))
    
    @staticmethod
    def 思考等待():
        r = random.random()
        if r < 0.5:
            time.sleep(random.uniform(2, 4))
        elif r < 0.8:
            time.sleep(random.uniform(4, 8))
        else:
            time.sleep(random.uniform(8, 15))
    
    def 悬停在元素上(self, 选择器列表: List[str] = None):
        from selenium.webdriver.common.action_chains import ActionChains
        
        if 选择器列表 is None:
            选择器列表 = ["[role='article']", "a[href*='/posts/']", "video", "img[alt]"]
        
        try:
            for 选择器 in random.sample(选择器列表, len(选择器列表)):
                elements = self.driver.find_elements("css selector", 选择器)
                可见元素 = [e for e in elements if e.is_displayed()]
                if 可见元素:
                    元素 = random.choice(可见元素[:5])
                    actions = ActionChains(self.driver)
                    actions.move_to_element(元素)
                    actions.perform()
                    time.sleep(random.uniform(0.5, 2.0))
                    return True
        except:
            pass
        return False
    
    def 鼠标微移动(self):
        from selenium.webdriver.common.action_chains import ActionChains
        try:
            dx = random.randint(-30, 30)
            dy = random.randint(-20, 20)
            actions = ActionChains(self.driver)
            actions.move_by_offset(dx, dy)
            actions.perform()
        except:
            pass
    
    def 微滚动(self):
        from selenium.webdriver.common.action_chains import ActionChains
        
        r = random.random()
        if r < 0.30:
            距离 = random.randint(80, 150)
        elif r < 0.70:
            距离 = random.randint(150, 300)
        elif r < 0.90:
            距离 = random.randint(300, 500)
        else:
            距离 = random.randint(500, 800)
        
        try:
            if random.random() < 0.3:
                self.鼠标微移动()
            
            步数 = random.randint(2, 5)
            每步距离 = 距离 // 步数
            
            actions = ActionChains(self.driver)
            for i in range(步数):
                实际步距 = int(每步距离 * random.uniform(0.7, 1.3))
                actions.scroll_by_amount(0, 实际步距)
                actions.pause(random.uniform(0.02, 0.06))
            actions.perform()
        except:
            self.driver.execute_script(f"window.scrollBy(0, {距离})")
        
        self._阅读等待()
    
    def _阅读等待(self):
        r = random.random()
        if r < 0.45:
            等待 = random.uniform(0.8, 2.5)
        elif r < 0.75:
            等待 = random.uniform(2.5, 5)
        elif r < 0.90:
            等待 = random.uniform(5, 10)
        elif r < 0.97:
            等待 = random.uniform(10, 20)
        else:
            等待 = random.uniform(20, 40)
        time.sleep(等待)
    
    def 回滚一点(self):
        from selenium.webdriver.common.action_chains import ActionChains
        距离 = random.randint(50, 200)
        try:
            步数 = random.randint(2, 4)
            每步距离 = 距离 // 步数
            actions = ActionChains(self.driver)
            for i in range(步数):
                实际步距 = int(每步距离 * random.uniform(0.7, 1.3))
                actions.scroll_by_amount(0, -实际步距)
                actions.pause(random.uniform(0.02, 0.05))
            actions.perform()
        except:
            self.driver.execute_script(f"window.scrollBy(0, {-距离})")
        time.sleep(random.uniform(1, 4))
    
    def 获取滚动位置(self) -> int:
        return self.driver.execute_script("return window.pageYOffset")

# ==================== 搜索功能 ====================

def 执行搜索(driver: "WebDriver", 关键词: str, log_func=None) -> bool:
    """在 Facebook 中搜索关键词"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    
    def log(msg):
        if log_func:
            log_func(msg)
    
    try:
        log(f"搜索关键词: {关键词}")
        
        搜索选择器列表 = [
            "input[placeholder*='Search']",
            "input[aria-label*='Search']",
            "[role='search'] input",
        ]
        
        搜索框 = None
        for 选择器 in 搜索选择器列表:
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
            # 尝试点击搜索按钮
            try:
                btns = driver.find_elements(By.CSS_SELECTOR, "[aria-label='Search Facebook']")
                for btn in btns:
                    if btn.is_displayed():
                        btn.click()
                        time.sleep(2)
                        break
                
                for 选择器 in 搜索选择器列表:
                    elements = driver.find_elements(By.CSS_SELECTOR, 选择器)
                    for el in elements:
                        if el.is_displayed():
                            搜索框 = el
                            break
                    if 搜索框:
                        break
            except:
                pass
        
        if not 搜索框:
            log("找不到搜索框")
            return False
        
        搜索框.click()
        time.sleep(random.uniform(0.5, 1))
        
        搜索框.clear()
        for char in 关键词:
            搜索框.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        time.sleep(random.uniform(0.5, 1))
        搜索框.send_keys(Keys.RETURN)
        log("已提交搜索")
        
        time.sleep(random.uniform(3, 5))
        return True
        
    except Exception as e:
        log(f"搜索失败: {e}")
        return False

# ==================== 阅读任务主函数 ====================

def 阅读(driver: "WebDriver", log_func=None, 配置: 阅读配置 = None) -> bool:
    """
    执行阅读任务 - 模拟真人浏览 Facebook
    
    Args:
        driver: WebDriver实例
        log_func: 日志函数
        配置: 阅读配置
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    if 配置 is None:
        配置 = 阅读配置()
    
    log("开始阅读...")
    
    # 50%概率通过搜索关键词浏览
    使用搜索 = random.random() < 配置.搜索概率
    
    if 使用搜索:
        关键词 = 获取随机关键词()
        if 关键词:
            log("本次通过搜索方式浏览")
            if 执行搜索(driver, 关键词, log):
                log("搜索成功，开始浏览搜索结果...")
            else:
                log("搜索失败，改为浏览首页")
        else:
            log("没有搜索关键词，浏览首页")
    else:
        log("本次浏览首页")
    
    模拟器 = 真人模拟(driver)
    开始时间 = time.time()
    滚动次数 = 0
    已点赞数 = 0
    已评论数 = 0
    目标点赞数 = 配置.点赞数量
    目标评论数 = 配置.评论数量
    
    # 计算点赞间隔
    if 目标点赞数 > 0 and 配置.总时长限制秒 > 0:
        点赞间隔 = 配置.总时长限制秒 / (目标点赞数 + 1)
        下次点赞时间 = 点赞间隔 * random.uniform(0.8, 1.2)
    else:
        点赞间隔 = 0
        下次点赞时间 = float('inf')
    
    # 计算评论间隔
    if 目标评论数 > 0 and 配置.总时长限制秒 > 0:
        评论间隔 = 配置.总时长限制秒 / (目标评论数 + 1)
        下次评论时间 = 评论间隔 * random.uniform(0.8, 1.2)
    else:
        评论间隔 = 0
        下次评论时间 = float('inf')
    
    try:
        time.sleep(random.uniform(2, 5))
        
        while True:
            已用时间 = time.time() - 开始时间
            if 已用时间 >= 配置.总时长限制秒:
                log(f"已浏览 {int(已用时间)}秒，达到目标时长")
                break
            
            # 检查是否需要点赞
            if 已点赞数 < 目标点赞数 and 已用时间 >= 下次点赞时间:
                log(f"尝试点赞 ({已点赞数 + 1}/{目标点赞数})...")
                if 点赞帖子(driver, 配置.最低点赞数, log):
                    已点赞数 += 1
                    if 已点赞数 < 目标点赞数:
                        下次点赞时间 = 已用时间 + 点赞间隔 * random.uniform(0.8, 1.2)
                else:
                    下次点赞时间 = 已用时间 + random.uniform(20, 40)
            
            # 检查是否需要评论
            if 已评论数 < 目标评论数 and 已用时间 >= 下次评论时间:
                log(f"尝试评论 ({已评论数 + 1}/{目标评论数})...")
                if 评论帖子(driver, log):
                    已评论数 += 1
                    if 已评论数 < 目标评论数:
                        下次评论时间 = 已用时间 + 评论间隔 * random.uniform(0.8, 1.2)
                else:
                    下次评论时间 = 已用时间 + random.uniform(30, 60)
            
            # 随机行为
            行为 = random.random()
            
            if 行为 < 0.70:
                模拟器.微滚动()
                滚动次数 += 1
            elif 行为 < 0.82:
                模拟器.回滚一点()
            elif 行为 < 0.90:
                模拟器.悬停在元素上()
                time.sleep(random.uniform(0.5, 2))
            elif 行为 < 0.95:
                模拟器.鼠标微移动()
                time.sleep(random.uniform(0.3, 1))
            else:
                time.sleep(random.uniform(2, 6))
            
            if 滚动次数 > 0 and 滚动次数 % 8 == 0:
                log(f"已浏览 {int(已用时间)}秒...")
        
        总用时 = time.time() - 开始时间
        统计信息 = []
        if 目标点赞数 > 0:
            统计信息.append(f"点赞 {已点赞数}/{目标点赞数}")
        if 目标评论数 > 0:
            统计信息.append(f"评论 {已评论数}/{目标评论数}")
        统计文本 = f"，{', '.join(统计信息)}" if 统计信息 else ""
        log(f"✓ 阅读完成，用时 {int(总用时)}秒{统计文本}")
        return True
        
    except Exception as e:
        log(f"✗ 阅读异常: {e}")
        return False

# ==================== 调试模式 ====================

def _调试模式():
    """调试模式入口"""
    print("=" * 60)
    print("阅读功能 - 调试模式")
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
    
    if not debug_port:
        print("❌ 未获取到调试端口")
        return
    
    print(f"✓ 浏览器已打开")
    print(f"  调试端口: {debug_port}")
    print(f"  驱动路径: {driver_path}")
    
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
        
        print(f"✓ Selenium 连接成功")
        print(f"  当前页面: {driver.title}")
        print()
        
    except Exception as e:
        print(f"❌ Selenium 连接失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("-" * 60)
    print("开始执行阅读功能...")
    print("-" * 60)
    
    测试配置 = 阅读配置(
        总时长限制秒=120,
        点赞数量=2,
        最低点赞数=10,
        搜索概率=1  # 调试时不搜索，直接在当前页面测试
    )
    
    成功 = 阅读(driver, 配置=测试配置)
    
    print("-" * 60)
    if 成功:
        print("✓ 阅读功能执行成功")
    else:
        print("✗ 阅读功能执行失败")
    print("-" * 60)
    
    print()
    print("调试完成，浏览器保持打开状态")

# ==================== 单独测试点赞功能 ====================

def _测试点赞():
    """单独测试点赞功能"""
    print("=" * 60)
    print("点赞功能 - 调试模式")
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
    print("测试点赞功能（debug=True）...")
    print("-" * 60)
    
    # 开启调试模式测试点赞
    成功 = 点赞帖子(driver, 最低点赞数=10, log_func=print, debug=True)
    
    print("-" * 60)
    if 成功:
        print("✓ 点赞成功")
    else:
        print("✗ 点赞失败")
    print("-" * 60)

# ==================== 单独测试评论功能 ====================

def _测试评论():
    """单独测试评论功能"""
    print("=" * 60)
    print("评论功能 - 调试模式")
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
    print("提示：请确保页面已滚动到有帖子内容的位置")
    print("按 Enter 开始测试评论功能...")
    print("-" * 60)
    input()
    
    print()
    print("测试评论功能（debug=True）...")
    print("-" * 60)
    
    # 开启调试模式测试评论（全局去重，不需要账号ID）
    成功 = 评论帖子(driver, log_func=print, debug=True)
    
    print("-" * 60)
    if 成功:
        print("✓ 评论成功")
    else:
        print("✗ 评论失败")
    print("-" * 60)

# ==================== 入口 ====================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "like":
            # 单独测试点赞: python 阅读.py like
            _测试点赞()
        elif sys.argv[1] == "comment":
            # 单独测试评论: python 阅读.py comment
            _测试评论()
        else:
            print("用法:")
            print("  python 阅读.py          # 完整测试")
            print("  python 阅读.py like     # 测试点赞")
            print("  python 阅读.py comment  # 测试评论")
    else:
        # 完整测试: python 阅读.py
        _调试模式()
