"""
自动化工具库
提供通用的自动化操作函数，供各任务脚本调用

功能：
- 点击操作（普通点击、随机偏移点击）
- 滑动操作（滚动、贝塞尔曲线滑动）
- 输入操作（模拟真人输入）
- 等待操作（随机等待、思考等待）
- 鼠标操作（移动、悬停）
- 元素查找（安全查找、等待元素）
"""

import time
import random
import math
from typing import TYPE_CHECKING, List, Tuple, Optional, Union

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.remote.webelement import WebElement

# ==================== 等待操作 ====================

def 随机等待(最小秒: float = 0.5, 最大秒: float = 2.0):
    """随机等待一段时间"""
    time.sleep(random.uniform(最小秒, 最大秒))

def 短等待():
    """短暂等待 0.3-0.8秒"""
    time.sleep(random.uniform(0.3, 0.8))

def 中等待():
    """中等等待 1-3秒"""
    time.sleep(random.uniform(1, 3))

def 长等待():
    """长等待 3-6秒"""
    time.sleep(random.uniform(3, 6))

def 思考等待():
    """
    模拟人思考的等待
    50% 短停顿(2-4秒)
    30% 中停顿(4-8秒)
    20% 长停顿(8-15秒)
    """
    r = random.random()
    if r < 0.5:
        time.sleep(random.uniform(2, 4))
    elif r < 0.8:
        time.sleep(random.uniform(4, 8))
    else:
        time.sleep(random.uniform(8, 15))

def 页面加载等待(driver: "WebDriver", 超时秒: int = 10) -> bool:
    """等待页面加载完成"""
    try:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        WebDriverWait(driver, 超时秒).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return True
    except:
        return False

# ==================== 元素查找 ====================

def 查找元素(driver: "WebDriver", 选择器: str, 超时秒: int = 5) -> Optional["WebElement"]:
    """
    安全查找单个元素
    
    Args:
        driver: WebDriver
        选择器: CSS选择器
        超时秒: 等待超时时间
    
    Returns:
        元素或None
    """
    try:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        element = WebDriverWait(driver, 超时秒).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 选择器))
        )
        return element
    except:
        return None

def 查找所有元素(driver: "WebDriver", 选择器: str) -> List["WebElement"]:
    """
    查找所有匹配的元素
    
    Returns:
        元素列表（可能为空）
    """
    try:
        return driver.find_elements("css selector", 选择器)
    except:
        return []

def 查找可见元素(driver: "WebDriver", 选择器: str, 超时秒: int = 5) -> Optional["WebElement"]:
    """查找可见的元素"""
    try:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        element = WebDriverWait(driver, 超时秒).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 选择器))
        )
        return element
    except:
        return None

def 查找可点击元素(driver: "WebDriver", 选择器: str, 超时秒: int = 5) -> Optional["WebElement"]:
    """查找可点击的元素"""
    try:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        element = WebDriverWait(driver, 超时秒).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 选择器))
        )
        return element
    except:
        return None

def 元素存在(driver: "WebDriver", 选择器: str) -> bool:
    """检查元素是否存在"""
    try:
        elements = driver.find_elements("css selector", 选择器)
        return len(elements) > 0
    except:
        return False

def 等待元素消失(driver: "WebDriver", 选择器: str, 超时秒: int = 10) -> bool:
    """等待元素消失"""
    try:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        WebDriverWait(driver, 超时秒).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, 选择器))
        )
        return True
    except:
        return False

# ==================== 点击操作 ====================

def 点击元素(driver: "WebDriver", 元素: "WebElement") -> bool:
    """
    点击元素（带随机偏移，模拟真人）
    """
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        
        # 获取元素大小
        size = 元素.size
        宽 = size.get('width', 10)
        高 = size.get('height', 10)
        
        # 随机偏移（在元素中心附近）
        偏移x = random.randint(-int(宽 * 0.2), int(宽 * 0.2))
        偏移y = random.randint(-int(高 * 0.2), int(高 * 0.2))
        
        actions = ActionChains(driver)
        actions.move_to_element_with_offset(元素, 偏移x, 偏移y)
        actions.pause(random.uniform(0.05, 0.15))
        actions.click()
        actions.perform()
        
        return True
    except:
        # 降级：直接点击
        try:
            元素.click()
            return True
        except:
            return False

def 点击选择器(driver: "WebDriver", 选择器: str, 超时秒: int = 5) -> bool:
    """通过选择器查找并点击元素"""
    元素 = 查找可点击元素(driver, 选择器, 超时秒)
    if 元素:
        return 点击元素(driver, 元素)
    return False

def 双击元素(driver: "WebDriver", 元素: "WebElement") -> bool:
    """双击元素"""
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        
        actions = ActionChains(driver)
        actions.move_to_element(元素)
        actions.pause(random.uniform(0.05, 0.1))
        actions.double_click()
        actions.perform()
        return True
    except:
        return False

def 右键点击(driver: "WebDriver", 元素: "WebElement") -> bool:
    """右键点击元素"""
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        
        actions = ActionChains(driver)
        actions.move_to_element(元素)
        actions.context_click()
        actions.perform()
        return True
    except:
        return False

def 点击坐标(driver: "WebDriver", x: int, y: int) -> bool:
    """点击指定坐标"""
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        
        actions = ActionChains(driver)
        actions.move_by_offset(x, y)
        actions.click()
        actions.perform()
        return True
    except:
        return False

# ==================== 鼠标操作 ====================

def 移动到元素(driver: "WebDriver", 元素: "WebElement") -> bool:
    """移动鼠标到元素上"""
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        
        actions = ActionChains(driver)
        actions.move_to_element(元素)
        actions.perform()
        return True
    except:
        return False

def 悬停元素(driver: "WebDriver", 元素: "WebElement", 停留秒: float = None) -> bool:
    """悬停在元素上一段时间"""
    if 移动到元素(driver, 元素):
        if 停留秒 is None:
            停留秒 = random.uniform(0.5, 2.0)
        time.sleep(停留秒)
        return True
    return False

def 鼠标微移动(driver: "WebDriver"):
    """鼠标小幅度随机移动"""
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        
        dx = random.randint(-30, 30)
        dy = random.randint(-20, 20)
        
        actions = ActionChains(driver)
        actions.move_by_offset(dx, dy)
        actions.perform()
    except:
        pass

def 贝塞尔移动鼠标(driver: "WebDriver", 目标x: int, 目标y: int, 起点x: int = None, 起点y: int = None):
    """
    使用贝塞尔曲线移动鼠标，模拟真人轨迹
    
    Args:
        driver: WebDriver
        目标x, 目标y: 目标坐标
        起点x, 起点y: 起点坐标（默认页面中心）
    """
    from selenium.webdriver.common.action_chains import ActionChains
    
    try:
        # 默认起点为页面中心
        if 起点x is None:
            起点x = driver.execute_script("return window.innerWidth / 2")
        if 起点y is None:
            起点y = driver.execute_script("return window.innerHeight / 2")
        
        # 生成贝塞尔曲线轨迹
        点数 = random.randint(10, 20)
        
        # 控制点（添加随机偏移，使轨迹弯曲）
        距离 = math.sqrt((目标x - 起点x) ** 2 + (目标y - 起点y) ** 2)
        偏移 = 距离 * 0.3
        
        控制点1x = 起点x + (目标x - 起点x) * 0.3 + random.uniform(-偏移, 偏移)
        控制点1y = 起点y + (目标y - 起点y) * 0.3 + random.uniform(-偏移, 偏移)
        控制点2x = 起点x + (目标x - 起点x) * 0.7 + random.uniform(-偏移, 偏移)
        控制点2y = 起点y + (目标y - 起点y) * 0.7 + random.uniform(-偏移, 偏移)
        
        actions = ActionChains(driver)
        上一个x, 上一个y = 起点x, 起点y
        
        for i in range(点数):
            t = i / (点数 - 1)
            
            # 三次贝塞尔曲线公式
            t2 = t * t
            t3 = t2 * t
            mt = 1 - t
            mt2 = mt * mt
            mt3 = mt2 * mt
            
            x = mt3 * 起点x + 3 * mt2 * t * 控制点1x + 3 * mt * t2 * 控制点2x + t3 * 目标x
            y = mt3 * 起点y + 3 * mt2 * t * 控制点1y + 3 * mt * t2 * 控制点2y + t3 * 目标y
            
            # 添加微小抖动
            x += random.uniform(-2, 2)
            y += random.uniform(-2, 2)
            
            dx = int(x - 上一个x)
            dy = int(y - 上一个y)
            
            if dx != 0 or dy != 0:
                actions.move_by_offset(dx, dy)
                if random.random() < 0.15:
                    actions.pause(random.uniform(0.01, 0.04))
            
            上一个x, 上一个y = x, y
        
        actions.perform()
    except:
        pass

# ==================== 滚动操作 ====================

def 向下滚动(driver: "WebDriver", 距离: int = None):
    """
    向下滚动页面
    
    Args:
        距离: 滚动距离（像素），默认随机100-400
    """
    if 距离 is None:
        距离 = random.randint(100, 400)
    
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        
        步数 = random.randint(2, 5)
        每步距离 = 距离 // 步数
        
        actions = ActionChains(driver)
        for i in range(步数):
            实际步距 = int(每步距离 * random.uniform(0.7, 1.3))
            actions.scroll_by_amount(0, 实际步距)
            actions.pause(random.uniform(0.02, 0.06))
        actions.perform()
    except:
        # 降级：JS滚动
        driver.execute_script(f"window.scrollBy(0, {距离})")

def 向上滚动(driver: "WebDriver", 距离: int = None):
    """向上滚动页面"""
    if 距离 is None:
        距离 = random.randint(50, 200)
    
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        
        步数 = random.randint(2, 4)
        每步距离 = 距离 // 步数
        
        actions = ActionChains(driver)
        for i in range(步数):
            实际步距 = int(每步距离 * random.uniform(0.7, 1.3))
            actions.scroll_by_amount(0, -实际步距)
            actions.pause(random.uniform(0.02, 0.05))
        actions.perform()
    except:
        driver.execute_script(f"window.scrollBy(0, {-距离})")

def 滚动到元素(driver: "WebDriver", 元素: "WebElement") -> bool:
    """滚动页面使元素可见"""
    try:
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 元素)
        time.sleep(random.uniform(0.3, 0.6))
        return True
    except:
        return False

def 滚动到顶部(driver: "WebDriver"):
    """滚动到页面顶部"""
    try:
        driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'})")
        time.sleep(random.uniform(0.5, 1.0))
    except:
        pass

def 滚动到底部(driver: "WebDriver"):
    """滚动到页面底部"""
    try:
        driver.execute_script("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
        time.sleep(random.uniform(0.5, 1.0))
    except:
        pass

def 获取滚动位置(driver: "WebDriver") -> int:
    """获取当前滚动位置"""
    try:
        return driver.execute_script("return window.pageYOffset")
    except:
        return 0

def 真人滚动(driver: "WebDriver"):
    """
    模拟真人滚动浏览
    滚动距离随机变化，模拟真人浏览习惯
    """
    r = random.random()
    
    if r < 0.30:  # 30% 小滚动
        距离 = random.randint(80, 150)
    elif r < 0.70:  # 40% 中等滚动
        距离 = random.randint(150, 300)
    elif r < 0.90:  # 20% 较大滚动
        距离 = random.randint(300, 500)
    else:  # 10% 大滚动
        距离 = random.randint(500, 800)
    
    向下滚动(driver, 距离)

# ==================== 输入操作 ====================

def 真人输入(driver: "WebDriver", 元素: "WebElement", 文本: str, 清空: bool = True) -> bool:
    """
    模拟真人输入文本
    
    特点：
    - 逐字输入
    - 随机输入速度
    - 偶尔打错再删除
    
    Args:
        元素: 输入框元素
        文本: 要输入的文本
        清空: 是否先清空输入框
    """
    try:
        from selenium.webdriver.common.keys import Keys
        
        # 点击输入框
        点击元素(driver, 元素)
        短等待()
        
        # 清空
        if 清空:
            元素.send_keys(Keys.CONTROL + "a")
            time.sleep(random.uniform(0.1, 0.2))
            元素.send_keys(Keys.DELETE)
            time.sleep(random.uniform(0.2, 0.4))
        
        # 逐字输入
        for i, 字符 in enumerate(文本):
            # 偶尔打错（5%概率）
            if random.random() < 0.05 and i > 0:
                错误字符 = random.choice('abcdefghijklmnopqrstuvwxyz')
                元素.send_keys(错误字符)
                time.sleep(random.uniform(0.1, 0.3))
                元素.send_keys(Keys.BACKSPACE)
                time.sleep(random.uniform(0.1, 0.2))
            
            元素.send_keys(字符)
            
            # 随机输入速度
            if random.random() < 0.1:  # 10% 稍长停顿
                time.sleep(random.uniform(0.2, 0.5))
            else:
                time.sleep(random.uniform(0.05, 0.15))
        
        return True
    except:
        return False

def 快速输入(driver: "WebDriver", 元素: "WebElement", 文本: str, 清空: bool = True) -> bool:
    """快速输入文本（不模拟真人）"""
    try:
        from selenium.webdriver.common.keys import Keys
        
        if 清空:
            元素.clear()
        元素.send_keys(文本)
        return True
    except:
        return False

def 按键(driver: "WebDriver", 键: str) -> bool:
    """
    按下键盘按键
    
    Args:
        键: 按键名称，如 'enter', 'tab', 'escape', 'backspace'
    """
    try:
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        
        键映射 = {
            'enter': Keys.ENTER,
            'tab': Keys.TAB,
            'escape': Keys.ESCAPE,
            'esc': Keys.ESCAPE,
            'backspace': Keys.BACKSPACE,
            'delete': Keys.DELETE,
            'space': Keys.SPACE,
            'up': Keys.UP,
            'down': Keys.DOWN,
            'left': Keys.LEFT,
            'right': Keys.RIGHT,
            'home': Keys.HOME,
            'end': Keys.END,
            'pageup': Keys.PAGE_UP,
            'pagedown': Keys.PAGE_DOWN,
        }
        
        实际键 = 键映射.get(键.lower(), 键)
        
        actions = ActionChains(driver)
        actions.send_keys(实际键)
        actions.perform()
        return True
    except:
        return False

# ==================== 页面操作 ====================

def 打开网址(driver: "WebDriver", url: str, 等待加载: bool = True) -> bool:
    """打开网址"""
    try:
        driver.get(url)
        if 等待加载:
            页面加载等待(driver)
        return True
    except:
        return False

def 刷新页面(driver: "WebDriver"):
    """刷新页面"""
    try:
        driver.refresh()
        页面加载等待(driver)
    except:
        pass

def 后退(driver: "WebDriver"):
    """浏览器后退"""
    try:
        driver.back()
        页面加载等待(driver)
    except:
        pass

def 前进(driver: "WebDriver"):
    """浏览器前进"""
    try:
        driver.forward()
        页面加载等待(driver)
    except:
        pass

def 获取当前网址(driver: "WebDriver") -> str:
    """获取当前网址"""
    try:
        return driver.current_url
    except:
        return ""

def 获取页面标题(driver: "WebDriver") -> str:
    """获取页面标题"""
    try:
        return driver.title
    except:
        return ""

def 执行JS(driver: "WebDriver", 脚本: str, *参数):
    """执行JavaScript"""
    try:
        return driver.execute_script(脚本, *参数)
    except:
        return None

# ==================== 截图 ====================

def 截图(driver: "WebDriver", 保存路径: str = None) -> Optional[bytes]:
    """
    截取页面截图
    
    Args:
        保存路径: 保存路径（可选），不提供则返回bytes
    
    Returns:
        截图bytes或None
    """
    try:
        if 保存路径:
            driver.save_screenshot(保存路径)
            return None
        else:
            return driver.get_screenshot_as_png()
    except:
        return None

def 元素截图(元素: "WebElement", 保存路径: str = None) -> Optional[bytes]:
    """截取元素截图"""
    try:
        if 保存路径:
            元素.screenshot(保存路径)
            return None
        else:
            return 元素.screenshot_as_png
    except:
        return None

# ==================== 评论生成 ====================

# 硬编码评论模板（后续可替换为AI生成）
# 注意：不使用 emoji，因为 ChromeDriver 不支持 BMP 以外的字符
_评论模板列表 = [
    # 通用正面评论
    "Great video!",
    "Love this!",
    "Amazing content!",
    "This is awesome!",
    "So good!",
    "Incredible!",
    "Wow, this is great!",
    "Nice one!",
    "Keep it up!",
    "This made my day!",
    "Fantastic!",
    "So cool!",
    "Love it!",
    "This is fire!",
    "Brilliant!",
    "Really enjoyed this!",
    "Thanks for sharing!",
    "Very nice!",
    "Well done!",
    "Awesome work!",
    # 带标题相关的模板（{keyword}会被替换）
    "Love this {keyword}!",
    "Great {keyword} content!",
    "{keyword} is amazing!",
    "Nice {keyword} video!",
]

# 从标题提取关键词的简单方法
def _提取关键词(标题: str) -> str:
    """从标题中提取一个关键词"""
    if not 标题:
        return "video"
    
    # 简单分词，取第一个有意义的词
    words = 标题.split()
    for word in words:
        word = word.strip().lower()
        # 过滤掉太短或无意义的词
        if len(word) > 3 and word not in ['this', 'that', 'with', 'from', 'have', 'been']:
            return word
    
    return "video"

def 生成评论内容(标题: str = "") -> str:
    """
    生成评论内容
    
    Args:
        标题: 视频标题（可选，用于生成相关评论）
    
    Returns:
        评论文本
    """
    # 随机选择一个模板
    模板 = random.choice(_评论模板列表)
    
    # 如果模板包含 {keyword}，替换为标题关键词
    if '{keyword}' in 模板:
        关键词 = _提取关键词(标题)
        评论 = 模板.replace('{keyword}', 关键词)
    else:
        评论 = 模板
    
    return 评论

# ==================== AI 评论生成 ====================

import requests
import re
import os
import json

# AI API 配置
_AI_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
_AI_MODEL = "Qwen/Qwen3-8b"
_AI_TIMEOUT = 60  # 秒

def _获取AI_API_KEY() -> str:
    """从配置文件获取 AI API Key"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        scripts_dir = os.path.dirname(current_dir)
        配置文件 = os.path.join(scripts_dir, "脚本配置", "qwen_api_key.txt")
        
        if os.path.exists(配置文件):
            with open(配置文件, 'r', encoding='utf-8') as f:
                key = f.read().strip()
                if key:
                    return key
    except:
        pass
    
    # 默认API Key
    return "sk-synvthmozuvymapxavwcxjyuhoxypyygdurmhnhbqntwgcst"

# 备用评论列表（API 失败时使用）
_备用评论列表 = [
    "This product is amazing! I've been using it for a while now and it has made such a difference in my daily routine. Highly recommend!",
    "Just tried this out and I'm impressed! The quality is excellent and it works exactly as described. Worth every penny!",
    "I'm so glad I discovered this! It's become an essential part of my day. Great value for money and super convenient!",
    "Absolutely love this! It exceeded my expectations in every way. The design is perfect and it's very user-friendly.",
    "This is a game changer! I've recommended it to all my friends. It's reliable, efficient, and makes life so much easier.",
    "Fantastic product! I've tried many similar ones but this stands out. The attention to detail is impressive. 5 stars!",
    "I'm blown away by how well this works! It's intuitive, stylish, and delivers on its promises. Definitely worth checking out!",
    "Such a great find! It's improved my productivity and made things so much simpler. Quality materials and excellent craftsmanship.",
    "I'm thoroughly impressed! This product has made a noticeable difference. It's well-designed and built to last. Highly recommended!",
    "Outstanding quality! I've been using it daily and it continues to perform flawlessly. Great investment for anyone looking for reliability.",
    "This has been a wonderful addition to my collection! It's functional, attractive, and everything I hoped for. Exceeded expectations!",
    "I can't say enough good things about this! It's transformed how I approach my tasks. Efficient, durable, and absolutely worth it!",
    "Top-notch product! From the packaging to the performance, everything is perfect. I'm a customer for life. Strongly recommend!",
    "What a brilliant innovation! It solves problems I didn't even know I had. Sleek design and flawless functionality. Love it!",
    "Exceptional value! The features are exactly what I needed. Easy to use and performs beautifully. Couldn't be happier with this purchase!",
]

def 获取产品类目() -> str:
    """
    获取产品类目配置
    
    Returns:
        产品类目字符串，默认返回 "各种产品"
    """
    try:
        # 尝试从配置文件读取
        current_dir = os.path.dirname(os.path.abspath(__file__))
        scripts_dir = os.path.dirname(current_dir)
        配置文件 = os.path.join(scripts_dir, "脚本配置", "产品类目.txt")
        
        if os.path.exists(配置文件):
            with open(配置文件, 'r', encoding='utf-8') as f:
                类目 = f.read().strip()
                if 类目:
                    return 类目
    except:
        pass
    
    return "各种产品"

def 转义特殊字符(text: str) -> str:
    """
    转义特殊字符，防止 JSON 解析错误
    
    Args:
        text: 原始文本
    
    Returns:
        转义后的文本
    """
    if not text:
        return ""
    
    # 转义常见特殊字符
    text = text.replace('\\', '\\\\')
    text = text.replace('"', '\\"')
    text = text.replace('\n', '\\n')
    text = text.replace('\r', '\\r')
    text = text.replace('\t', '\\t')
    
    return text

def 清理AI响应(response: str) -> str:
    """
    清理 AI 响应，提取【】中的内容
    
    Args:
        response: AI 原始响应
    
    Returns:
        清理后的评论内容，如果是 NO 或无关则返回空字符串
    """
    if not response:
        return ""
    
    # 检查是否包含 NO（不区分大小写）
    if "NO" in response.upper() or "无关" in response:
        print(f"[AI评论-调试] AI 判断为无关，返回空")
        return ""
    
    # 尝试提取【】中的内容
    match = re.search(r'【(.+?)】', response, re.DOTALL)
    if match:
        content = match.group(1).strip()
        # 再次检查内容是否是 NO
        if content.upper() == "NO" or "无关" in content:
            print(f"[AI评论-调试] 提取内容为 NO，返回空")
            return ""
        print(f"[AI评论-调试] 提取到评论: {content}")
        return content
    
    # 如果没有【】，尝试提取有意义的内容
    # 去除 think 标签等
    response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
    response = re.sub(r'<[^>]+>', '', response)
    response = response.strip()
    
    # 如果响应太长，可能不是有效评论
    if len(response) > 200:
        print(f"[AI评论-调试] 响应太长 ({len(response)} 字符)，返回空")
        return ""
    
    # 最后检查是否是 NO
    if response.upper() == "NO":
        print(f"[AI评论-调试] 清理后为 NO，返回空")
        return ""
    
    print(f"[AI评论-调试] 最终评论: {response}")
    return response

def AI评论_不带帖子内容() -> str:
    """
    使用 AI 生成评论（不基于帖子内容）
    
    Returns:
        生成的评论内容，失败时返回备用评论
    """
    # 随机选择备用评论
    备用评论 = random.choice(_备用评论列表)
    
    try:
        # 获取产品类目
        类目 = 获取产品类目()
        
        # 构造提示词
        prompt = f"你是一名专业的社交媒体评论生成专家。请生成一条英文的积极评价并推荐包含{类目}的帖子的评论。输出必须严格包裹在中文书名号中，格式为【这里是要生成的英文评论内容】。评论内容应真实生动、符合日常生活，避免广告语气。严格控制评论长度在80字以内，并且不要包含任何中文字符"
        
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
                cleaned = 清理AI响应(content)
                if cleaned:
                    return cleaned
        
    except Exception as e:
        print(f"[AI评论] 调用 API 出错: {e}")
    
    return 备用评论

def AI评论_带帖子内容(帖子内容: str) -> str:
    """
    使用 AI 根据帖子内容生成评论
    
    Args:
        帖子内容: Facebook 帖子的文本内容
    
    Returns:
        生成的评论内容，如果帖子与行业无关返回空字符串，失败时返回备用评论
    """
    # 随机选择备用评论
    备用评论 = random.choice(_备用评论列表)
    
    try:
        # 获取产品类目
        类目 = 获取产品类目()
        
        # 转义帖子内容
        转义后内容 = 转义特殊字符(帖子内容)
        
        # 构造提示词
        prompt = f"""你是一名社交媒体用户，对{类目}感兴趣。

任务：
1. 判断以下帖子是否与"{类目}"相关
   - 如果完全无关，直接输出：NO
   - 如果相关，继续第2步

2. 根据帖子内容生成一条真实、自然的英文评论
   - 评论要简短（5-15个单词）
   - 表达真实感受，不要套用模板
   - 可以用 1-2 个 emoji
   - 用【】包围评论内容
   - 不要提及品牌名

评论风格参考（不要照抄）：
- 表达喜欢：Love this style! / This is amazing!
- 表达兴趣：So cool! / Really impressive!
- 表达认同：Totally agree! / Exactly what I needed!
- 询问互动：Where can I get this? / More details please!

帖子内容：
{转义后内容}

重要：必须根据帖子内容生成独特的评论，不要重复示例！"""
        
        # 调试输出
        print(f"\n[AI评论-调试] 产品类目: {类目}")
        print(f"[AI评论-调试] 帖子内容: {帖子内容[:100]}...")
        print(f"[AI评论-调试] 完整 Prompt:\n{prompt}\n")
        
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
                print(f"[AI评论-调试] AI 原始响应: {content}")
                cleaned = 清理AI响应(content)
                # 如果返回空（NO 或无效），表示与行业无关
                return cleaned
        else:
            print(f"[AI评论] API 返回错误状态码: {response.status_code}")
            print(f"[AI评论] 响应内容: {response.text[:200]}")
        
    except Exception as e:
        print(f"[AI评论] 调用 API 出错: {e}")
        import traceback
        traceback.print_exc()
    
    return 备用评论
