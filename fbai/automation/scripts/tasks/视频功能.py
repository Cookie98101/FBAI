"""
视频功能任务
搜索并观看 Facebook 视频

流程：
1. 点击搜索框
2. 输入随机关键词
3. 回车搜索
4. 点击视频标签
5. 随机观看视频

使用方法：
- 调试模式：修改 DEBUG_BROWSER_ID，直接运行此文件
- 正式调用：main.py 中调用 视频功能(driver, ...)
"""

import os
import sys
import time
import random
from typing import TYPE_CHECKING, Optional, List
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

# 定义脚本配置目录（供模块级别使用）
脚本配置目录 = os.path.join(scripts_dir, "脚本配置")

# ==================== 导入自动化工具 ====================

from 自动化工具 import (
    # 等待
    随机等待, 短等待, 中等待, 长等待, 思考等待, 页面加载等待,
    # 元素查找
    查找元素, 查找所有元素, 查找可见元素, 查找可点击元素, 元素存在,
    # 点击
    点击元素, 点击选择器,
    # 鼠标
    移动到元素, 悬停元素, 鼠标微移动,
    # 滚动
    向下滚动, 向上滚动, 真人滚动, 获取滚动位置,
    # 输入
    真人输入, 快速输入, 按键,
    # 页面
    打开网址, 获取当前网址, 获取页面标题,
    # 评论
    生成评论内容,
)

# ==================== 调试配置 ====================

# 从环境变量读取浏览器ID
DEBUG_BROWSER_ID = os.environ.get('DEBUG_BROWSER_ID', "dd6c77a66dc74aea8c449207d55a3a87")

# ==================== 任务配置 ====================

@dataclass
class 视频配置:
    """视频功能配置"""
    观看时长秒: int = 180           # 总观看时长（秒）
    单个视频最长秒: int = 60        # 单个视频最长观看时间
    单个视频最短秒: int = 10        # 单个视频最短观看时间

# ==================== 素材读取 ====================

# 配置文件路径（使用已定义的 scripts_dir）
已观看视频文件 = os.path.join(scripts_dir, "脚本配置", "已观看视频.txt")
搜索关键词文件 = os.path.join(scripts_dir, "脚本配置", "搜索关键词.txt")

def 加载已观看视频() -> set:
    """加载已观看的视频ID列表"""
    已观看 = set()
    
    if os.path.exists(已观看视频文件):
        try:
            with open(已观看视频文件, 'r', encoding='utf-8') as f:
                for line in f:
                    video_id = line.strip()
                    if video_id:
                        已观看.add(video_id)
        except:
            pass
    
    return 已观看

def 记录已观看视频(video_id: str):
    """记录已观看的视频ID"""
    if not video_id:
        return
    
    # 确保目录存在
    os.makedirs(os.path.dirname(已观看视频文件), exist_ok=True)
    
    try:
        with open(已观看视频文件, 'a', encoding='utf-8') as f:
            f.write(video_id + '\n')
    except:
        pass

def 从链接提取视频ID(href: str) -> Optional[str]:
    """从视频链接中提取视频ID"""
    if not href:
        return None
    
    # 链接格式: /watch/?ref=search&v=1544868833258145&...
    # 提取 v= 后面的数字
    import re
    match = re.search(r'[?&]v=(\d+)', href)
    if match:
        return match.group(1)
    
    return None

def 获取搜索关键词() -> str:
    """
    从素材文件夹读取随机搜索关键词
    
    Returns:
        随机关键词
    """
    if not os.path.exists(搜索关键词文件):
        # 文件不存在，返回默认关键词
        默认关键词 = ["funny videos", "cute cats", "music", "cooking", "travel"]
        return random.choice(默认关键词)
    
    try:
        with open(搜索关键词文件, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 过滤空行
        关键词列表 = [line.strip() for line in lines if line.strip()]
        
        if 关键词列表:
            return random.choice(关键词列表)
        else:
            return "videos"
    except:
        return "videos"

# ==================== 搜索功能 ====================

def 点击搜索框(driver: "WebDriver", log) -> bool:
    """点击 Facebook 搜索框"""
    from selenium.webdriver.common.by import By
    
    # 优先使用测试验证过的选择器
    搜索框选择器列表 = [
        '[role="combobox"]',                    # 测试成功
        '[aria-label="Search Facebook"]',       # 测试成功
        'input[type="search"]',
        'input[placeholder*="Search"]',
    ]
    
    for 选择器 in 搜索框选择器列表:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, 选择器)
            for 搜索框 in elements:
                if 搜索框.is_displayed():
                    log(f"找到搜索框: {选择器}")
                    
                    # 直接点击
                    搜索框.click()
                    短等待()
                    
                    # 验证是否激活
                    active = driver.switch_to.active_element
                    if active.tag_name == "input":
                        log("搜索框已激活")
                        return True
        except Exception as e:
            continue
    
    log("未找到搜索框")
    return False

def 输入搜索词(driver: "WebDriver", 关键词: str, log) -> bool:
    """在搜索框输入关键词"""
    from selenium.webdriver.common.keys import Keys
    
    try:
        # 获取当前焦点元素
        active = driver.switch_to.active_element
        
        if active.tag_name != "input":
            log("搜索框未激活")
            return False
        
        # 清空
        active.send_keys(Keys.CONTROL + "a")
        time.sleep(0.1)
        active.send_keys(Keys.DELETE)
        time.sleep(0.2)
        
        log(f"输入关键词: {关键词}")
        
        # 逐字输入模拟真人
        for char in 关键词:
            active.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        中等待()
        return True
        
    except Exception as e:
        log(f"输入失败: {e}")
        return False

def 执行搜索(driver: "WebDriver", log) -> bool:
    """按回车执行搜索"""
    from selenium.webdriver.common.keys import Keys
    
    log("按回车搜索...")
    
    try:
        active = driver.switch_to.active_element
        active.send_keys(Keys.ENTER)
        
        # 等待搜索结果加载
        页面加载等待(driver, 超时秒=10)
        长等待()
        return True
    except:
        按键(driver, 'enter')
        页面加载等待(driver, 超时秒=10)
        长等待()
        return True

def 点击视频标签(driver: "WebDriver", log) -> bool:
    """点击搜索结果中的视频标签"""
    from selenium.webdriver.common.by import By
    
    中等待()
    
    # 通过文本查找 Videos 链接
    try:
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                if link.is_displayed():
                    text = link.text.strip()
                    if text.lower() == "videos" or text == "视频":
                        log("点击视频标签")
                        link.click()
                        页面加载等待(driver)
                        长等待()
                        return True
            except:
                continue
    except:
        pass
    
    # 备选：通过 href 查找
    视频标签选择器列表 = [
        'a[href*="/videos"]',
        'a[href*="filter=videos"]',
    ]
    
    for 选择器 in 视频标签选择器列表:
        try:
            视频标签 = 查找可点击元素(driver, 选择器, 超时秒=3)
            if 视频标签:
                log("点击视频标签")
                点击元素(driver, 视频标签)
                页面加载等待(driver)
                长等待()
                return True
        except:
            continue
    
    log("未找到视频标签")
    return False

def 选择本周视频(driver: "WebDriver", log) -> bool:
    """
    选择日期筛选：Date Posted -> This week
    """
    from selenium.webdriver.common.by import By
    
    中等待()
    
    # 第一步：点击 "Date Posted" 筛选按钮
    log("查找日期筛选...")
    
    找到日期筛选 = False
    try:
        # 查找所有 span，找 Date posted
        spans = driver.find_elements(By.TAG_NAME, "span")
        for span in spans:
            try:
                text = span.text.strip()
                if text.lower() in ["date posted", "发布日期"]:
                    if span.is_displayed():
                        log("点击 Date Posted")
                        span.click()
                        短等待()
                        找到日期筛选 = True
                        break
            except:
                continue
    except:
        pass
    
    if not 找到日期筛选:
        log("未找到 Date Posted 筛选")
        return False
    
    中等待()
    
    # 第二步：点击 "This week"
    log("选择 This week...")
    
    try:
        spans = driver.find_elements(By.TAG_NAME, "span")
        for span in spans:
            try:
                text = span.text.strip()
                if text.lower() in ["this week", "本周"]:
                    if span.is_displayed():
                        log("点击 This week")
                        span.click()
                        页面加载等待(driver)
                        长等待()
                        return True
            except:
                continue
    except:
        pass
    
    log("未找到 This week 选项")
    return False

# ==================== 视频观看 ====================

def 获取视频卡片列表(driver: "WebDriver", 已观看: set, log) -> List[dict]:
    """
    获取页面上的视频卡片列表
    
    Returns:
        视频信息列表 [{'element': 元素, 'video_id': ID, 'href': 链接, 'title': 标题, 'author': 作者}, ...]
    """
    from selenium.webdriver.common.by import By
    
    视频列表 = []
    
    try:
        # 查找所有 role="article" 的视频卡片
        articles = driver.find_elements(By.CSS_SELECTOR, '[role="article"]')
        
        for article in articles:
            try:
                # 查找卡片内的视频链接
                links = article.find_elements(By.CSS_SELECTOR, 'a[href*="/watch/"]')
                
                for link in links:
                    href = link.get_attribute('href')
                    if not href:
                        continue
                    
                    video_id = 从链接提取视频ID(href)
                    if not video_id:
                        continue
                    
                    # 检查是否已观看
                    if video_id in 已观看:
                        continue
                    
                    # 检查是否已在列表中
                    if any(v['video_id'] == video_id for v in 视频列表):
                        continue
                    
                    # 检查元素是否可见
                    if not link.is_displayed():
                        continue
                    
                    # 提取标题（从 h2 标签或 aria-label 属性）
                    标题 = ""
                    作者 = ""
                    
                    try:
                        # 方法1：从 h2 标签获取标题
                        h2_elements = article.find_elements(By.TAG_NAME, 'h2')
                        for h2 in h2_elements:
                            text = h2.text.strip()
                            if text:
                                标题 = text
                                break
                        
                        # 方法2：从链接的 aria-label 获取
                        if not 标题:
                            aria_label = link.get_attribute('aria-label')
                            if aria_label:
                                标题 = aria_label
                        
                        # 提取作者（通常在 profile 链接中）
                        author_links = article.find_elements(By.CSS_SELECTOR, 'a[href*="/profile.php"], a[href*="facebook.com/"][role="link"]')
                        for author_link in author_links:
                            author_text = author_link.text.strip()
                            if author_text and len(author_text) < 50:  # 作者名不会太长
                                作者 = author_text
                                break
                                
                    except:
                        pass
                    
                    视频列表.append({
                        'element': link,
                        'video_id': video_id,
                        'href': href,
                        'title': 标题,
                        'author': 作者
                    })
                    break  # 每个卡片只取一个链接
                    
            except:
                continue
    except:
        pass
    
    log(f"找到 {len(视频列表)} 个未观看的视频")
    
    # 打印视频列表信息
    for i, v in enumerate(视频列表[:5]):  # 只打印前5个
        title_short = v['title'][:40] + '...' if len(v['title']) > 40 else v['title']
        log(f"  [{i+1}] {v['video_id']}: {title_short}")
    
    return 视频列表

def 点击进入视频(driver: "WebDriver", 视频信息: dict, log) -> bool:
    """点击进入视频播放页面"""
    from selenium.webdriver.common.action_chains import ActionChains
    
    element = 视频信息['element']
    video_id = 视频信息['video_id']
    href = 视频信息.get('href', '')
    title = 视频信息.get('title', '')
    
    title_short = title[:30] + '...' if len(title) > 30 else title
    log(f"点击视频: {video_id} - {title_short}")
    
    try:
        # 方法1：滚动到元素可见后点击
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        短等待()
        
        # 检查元素是否可交互
        if element.is_displayed() and element.is_enabled():
            try:
                element.click()
                页面加载等待(driver, 超时秒=10)
                中等待()
                return True
            except:
                pass
        
        # 方法2：使用 ActionChains
        try:
            actions = ActionChains(driver)
            actions.move_to_element(element)
            actions.pause(0.3)
            actions.click()
            actions.perform()
            页面加载等待(driver, 超时秒=10)
            中等待()
            return True
        except:
            pass
        
        # 方法3：JS 点击
        try:
            driver.execute_script("arguments[0].click();", element)
            页面加载等待(driver, 超时秒=10)
            中等待()
            return True
        except:
            pass
        
        # 方法4：直接打开链接
        if href:
            log(f"尝试直接打开链接...")
            打开网址(driver, href)
            页面加载等待(driver, 超时秒=10)
            中等待()
            return True
            
    except Exception as e:
        log(f"点击视频失败: {e}")
    
    return False

def 观看视频(driver: "WebDriver", 观看秒数: int, log) -> bool:
    """
    观看当前视频
    
    模拟真人观看行为：
    - 偶尔移动鼠标
    - 偶尔滚动一点
    """
    log(f"观看视频 {观看秒数} 秒...")
    
    开始时间 = time.time()
    
    while time.time() - 开始时间 < 观看秒数:
        剩余时间 = 观看秒数 - (time.time() - 开始时间)
        
        # 随机行为
        行为 = random.random()
        
        if 行为 < 0.6:  # 60% 什么都不做，专心看
            等待时间 = min(random.uniform(3, 8), 剩余时间)
            time.sleep(等待时间)
            
        elif 行为 < 0.8:  # 20% 鼠标微移动
            鼠标微移动(driver)
            time.sleep(random.uniform(1, 3))
            
        else:  # 20% 小幅滚动
            if random.random() < 0.5:
                向下滚动(driver, random.randint(30, 80))
            else:
                向上滚动(driver, random.randint(20, 50))
            time.sleep(random.uniform(1, 2))
    
    return True

def 上传点赞数据(log) -> bool:
    """
    上传点赞数据到服务器
    
    Returns:
        是否成功
    """
    try:
        import requests
        url = "http://localhost:8805/add_data?likes=1"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            log("  ✓ 点赞数据已上传")
            return True
        else:
            log(f"  ⚠ 点赞数据上传失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        log(f"  ⚠ 点赞数据上传异常: {e}")
        return False

def 点赞视频(driver: "WebDriver", log) -> bool:
    """
    点赞当前视频
    
    Returns:
        是否成功
    """
    from selenium.webdriver.common.by import By
    
    log("尝试点赞...")
    
    # 先滚动一下让点赞按钮可见
    向下滚动(driver, random.randint(50, 150))
    短等待()
    
    # 点赞按钮选择器
    点赞选择器列表 = [
        '[aria-label="Like"]',
        '[aria-label="赞"]',
        'div[aria-label*="Like"]',
        'span[aria-label*="Like"]',
    ]
    
    try:
        for 选择器 in 点赞选择器列表:
            elements = driver.find_elements(By.CSS_SELECTOR, 选择器)
            for el in elements:
                if el.is_displayed():
                    # 使用 JS 点击，避免被其他元素遮挡
                    try:
                        driver.execute_script("arguments[0].click();", el)
                        短等待()
                        log("✓ 已点赞")
                        # 上传点赞数据
                        上传点赞数据(log)
                        return True
                    except:
                        # 降级：普通点击
                        el.click()
                        短等待()
                        log("✓ 已点赞")
                        # 上传点赞数据
                        上传点赞数据(log)
                        return True
    except Exception as e:
        log(f"点赞失败: {e}")
    
    log("未找到点赞按钮")
    return False

def 上传评论数据(log) -> bool:
    """
    上传评论数据到服务器
    
    Returns:
        是否成功
    """
    try:
        import requests
        url = "http://localhost:8805/add_data?comments=1"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            log("  ✓ 评论数据已上传")
            return True
        else:
            log(f"  ⚠ 评论数据上传失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        log(f"  ⚠ 评论数据上传异常: {e}")
        return False

def 评论视频(driver: "WebDriver", 评论内容: str, log) -> bool:
    """
    评论当前视频
    
    Args:
        评论内容: 要发送的评论文本
    
    Returns:
        是否成功
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    
    log(f"尝试评论: {评论内容}")
    
    # 过滤掉非 BMP 字符（emoji 等），ChromeDriver 不支持
    评论内容_安全 = ''.join(c for c in 评论内容 if ord(c) < 0x10000)
    
    # 评论输入框选择器
    评论框选择器列表 = [
        '[aria-label="Write a comment"]',
        '[aria-label="写评论"]',
        '[aria-label*="comment"][contenteditable="true"]',
        '[placeholder*="Write a comment"]',
        '[placeholder*="写评论"]',
        'div[contenteditable="true"][role="textbox"]',
    ]
    
    try:
        # 先滚动一下，让评论框可见
        向下滚动(driver, random.randint(150, 300))
        中等待()
        
        for 选择器 in 评论框选择器列表:
            elements = driver.find_elements(By.CSS_SELECTOR, 选择器)
            for el in elements:
                if el.is_displayed():
                    # 使用 JS 点击评论框激活，避免被遮挡
                    try:
                        driver.execute_script("arguments[0].click();", el)
                    except:
                        el.click()
                    短等待()
                    
                    # 逐字符输入（模拟真人）
                    for char in 评论内容_安全:
                        el.send_keys(char)
                        time.sleep(random.uniform(0.03, 0.1))
                    
                    中等待()
                    
                    # 按回车发送
                    el.send_keys(Keys.ENTER)
                    中等待()
                    
                    log("✓ 已评论")
                    # 上传评论数据
                    上传评论数据(log)
                    return True
    except Exception as e:
        log(f"评论失败: {e}")
    
    log("未找到评论框")
    return False

def 浏览视频列表(driver: "WebDriver", log):
    """
    模拟真人浏览视频列表
    
    行为：
    - 随机等待（看看列表）
    - 随机滚动（上下看看）
    - 鼠标移动（悬停在某些视频上）
    - 偶尔停下来仔细看某个视频缩略图
    """
    log("浏览视频列表...")
    
    # 随机浏览时间 8-20 秒
    浏览时间 = random.uniform(8, 20)
    开始时间 = time.time()
    
    while time.time() - 开始时间 < 浏览时间:
        行为 = random.random()
        
        if 行为 < 0.35:  # 35% 等待（看列表）
            time.sleep(random.uniform(1.5, 4))
            
        elif 行为 < 0.60:  # 25% 滚动
            if random.random() < 0.7:  # 70% 向下
                向下滚动(driver, random.randint(100, 350))
            else:  # 30% 向上（回看）
                向上滚动(driver, random.randint(50, 200))
            time.sleep(random.uniform(1, 2.5))
            
        elif 行为 < 0.80:  # 20% 鼠标移动
            鼠标微移动(driver)
            time.sleep(random.uniform(0.8, 2))
            
        else:  # 20% 停下来仔细看（模拟犹豫要不要点）
            time.sleep(random.uniform(2, 5))
    
    # 最后稍微等一下再点击
    time.sleep(random.uniform(1, 2.5))

def 滚动到下一个视频(driver: "WebDriver", log):
    """滚动到下一个视频"""
    log("滚动到下一个视频...")
    
    # 随机滚动距离
    滚动距离 = random.randint(300, 600)
    向下滚动(driver, 滚动距离)
    
    中等待()

# ==================== 主任务函数 ====================

def 视频功能(driver: "WebDriver", log_func=None, 配置: 视频配置 = None) -> bool:
    """
    视频功能主函数
    
    流程：
    1. 点击搜索框
    2. 输入随机关键词
    3. 回车搜索
    4. 点击视频标签
    5. 循环观看视频直到时间用完
    
    Args:
        driver: Selenium WebDriver
        log_func: 日志函数
        配置: 视频配置
    
    Returns:
        是否成功
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(f"[视频功能] {msg}")
    
    if 配置 is None:
        配置 = 视频配置()
    
    log("开始视频功能...")
    开始时间 = time.time()
    观看视频数 = 0
    
    try:
        # ========== 1. 点击搜索框 ==========
        if not 点击搜索框(driver, log):
            log("✗ 无法点击搜索框，尝试直接进入视频页")
            打开网址(driver, "https://www.facebook.com/watch")
            页面加载等待(driver, 超时秒=10)
        else:
            # ========== 2. 获取并输入关键词 ==========
            关键词 = 获取搜索关键词()
            if 输入搜索词(driver, 关键词, log):
                # ========== 3. 执行搜索 ==========
                执行搜索(driver, log)
                
                # ========== 4. 点击视频标签 ==========
                点击视频标签(driver, log)
                
                # ========== 5. 选择本周视频 ==========
                选择本周视频(driver, log)
        
        # ========== 6. 加载已观看记录 ==========
        已观看 = 加载已观看视频()
        log(f"已观看记录: {len(已观看)} 个视频")
        
        # 保存搜索结果页URL，用于返回
        搜索结果页URL = 获取当前网址(driver)
        
        # ========== 7. 循环观看视频 ==========
        log("开始观看视频...")
        
        while True:
            已用时间 = time.time() - 开始时间
            剩余时间 = 配置.观看时长秒 - 已用时间
            
            # 检查时间
            if 剩余时间 <= 0:
                log(f"已达到观看时长 {配置.观看时长秒} 秒")
                break
            
            # 获取视频列表（过滤已观看的）
            视频列表 = 获取视频卡片列表(driver, 已观看, log)
            
            if not 视频列表:
                log("没有更多未观看的视频，滚动加载更多...")
                向下滚动(driver, random.randint(400, 700))
                中等待()
                
                # 再次尝试获取
                视频列表 = 获取视频卡片列表(driver, 已观看, log)
                if not 视频列表:
                    log("没有更多视频了")
                    break
            
            # 随机选择一个视频（保存 video_id 和 href，不依赖元素引用）
            视频信息 = random.choice(视频列表)
            video_id = 视频信息['video_id']
            video_href = 视频信息['href']
            video_title = 视频信息.get('title', '')
            
            # 直接通过 href 打开视频（避免元素引用失效问题）
            title_short = video_title[:30] + '...' if len(video_title) > 30 else video_title
            log(f"打开视频: {video_id} - {title_short}")
            
            打开网址(driver, video_href)
            页面加载等待(driver, 超时秒=10)
            中等待()
            
            # 计算本次观看时长（确保最小值不大于最大值）
            已用时间 = time.time() - 开始时间
            剩余时间 = 配置.观看时长秒 - 已用时间
            
            最大观看时长 = min(配置.单个视频最长秒, int(剩余时间))
            最小观看时长 = min(配置.单个视频最短秒, 最大观看时长)
            
            if 最大观看时长 < 配置.单个视频最短秒:
                # 时间不够了，返回列表页后退出
                log("剩余时间不足，返回视频列表...")
                driver.back()
                页面加载等待(driver, 超时秒=10)
                break
            
            本次观看时长 = random.randint(最小观看时长, 最大观看时长)
            
            # 30% 概率额外多看 20-60 秒（模拟对视频感兴趣）
            感兴趣 = random.random() < 0.3
            if 感兴趣:
                额外时长 = random.randint(20, 60)
                本次观看时长 += 额外时长
                log(f"对这个视频感兴趣，多看 {额外时长} 秒")
            
            # 观看视频
            观看视频(driver, 本次观看时长, log)
            
            # 30% 概率评论（使用AI生成）
            if random.random() < 0.3:
                # 检查是否已经评论过这个视频
                from tasks.去重管理 import 检查是否已操作, 记录操作
                
                if not 检查是否已操作(video_id, "comment", 去重天数=15):
                    log("准备评论...")
                    
                    # 使用AI生成评论
                    from tasks.自动化工具 import AI评论_带帖子内容
                    
                    try:
                        # 传递视频标题给AI
                        评论内容 = AI评论_带帖子内容(video_title if video_title else "这个视频")
                        log(f"AI生成评论: {评论内容[:50]}...")
                        
                        # 发送评论
                        if 评论视频(driver, 评论内容, log):
                            # 记录已评论
                            记录操作(video_id, "comment")
                            log("✓ 已评论并记录")
                        
                        中等待()
                    except Exception as e:
                        log(f"评论失败: {e}")
                else:
                    log("已评论过此视频，跳过")
            
            # 如果感兴趣，80% 概率点赞
            if 感兴趣 and random.random() < 0.8:
                # 点赞
                点赞视频(driver, log)
                中等待()
            
            # 记录已观看
            记录已观看视频(video_id)
            已观看.add(video_id)
            观看视频数 += 1
            
            已用时间 = time.time() - 开始时间
            log(f"✓ 已观看 {观看视频数} 个视频，用时 {int(已用时间)} 秒")
            
            # 返回搜索结果页（每次观看完都返回）
            log("返回视频列表...")
            driver.back()
            页面加载等待(driver, 超时秒=10)
            
            # 模拟真人浏览列表（等待、滚动、看看）
            浏览视频列表(driver, log)
        
        总用时 = time.time() - 开始时间
        log(f"✓ 视频功能完成，观看 {观看视频数} 个视频，用时 {int(总用时)} 秒")
        return True
        
    except Exception as e:
        log(f"✗ 视频功能异常: {e}")
        return False

# ==================== 调试模式 ====================

def _调试模式():
    """调试模式入口"""
    print("=" * 60)
    print("视频功能 - 调试模式")
    print("=" * 60)
    print(f"浏览器ID: {DEBUG_BROWSER_ID}")
    print()
    
    # 导入比特浏览器API
    try:
        from bitbrowser_api import BitBrowserAPI
        bit_browser = BitBrowserAPI()
    except ImportError as e:
        print(f"❌ 无法导入 bitbrowser_api: {e}")
        return
    except Exception as e:
        print(f"❌ 初始化 BitBrowserAPI 失败: {e}")
        return
    
    # 1. 打开浏览器
    print("正在打开浏览器...")
    result = bit_browser.open_browser(DEBUG_BROWSER_ID)
    
    if not result.get("success"):
        print(f"❌ 打开浏览器失败: {result}")
        return
    
    data = result.get("data", {})
    debug_port = data.get("http")      # 调试端口，如 "127.0.0.1:9222"
    driver_path = data.get("driver")   # ChromeDriver 路径
    
    if not debug_port:
        print("❌ 未获取到调试端口")
        return
    
    print(f"✓ 浏览器已打开")
    print(f"  调试端口: {debug_port}")
    print(f"  驱动路径: {driver_path}")
    
    # 2. 连接 Selenium
    print("正在连接 Selenium...")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        
        options = Options()
        options.add_experimental_option("debuggerAddress", debug_port)
        
        # 使用比特浏览器提供的 ChromeDriver
        if driver_path:
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=options)
        else:
            # 没有驱动路径，尝试自动查找
            driver = webdriver.Chrome(options=options)
        
        print(f"✓ Selenium 连接成功")
        print(f"  当前页面: {driver.title}")
        print()
        
    except Exception as e:
        print(f"❌ Selenium 连接失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. 执行任务
    print("-" * 60)
    print("开始执行视频功能...")
    print("-" * 60)
    
    # 调试配置（较短时间）
    测试配置 = 视频配置(
        观看时长秒=300,          # 调试用1分钟
        单个视频最长秒=20,
        单个视频最短秒=5
    )
    
    成功 = 视频功能(driver, 配置=测试配置)
    
    print("-" * 60)
    if 成功:
        print("✓ 视频功能执行成功")
    else:
        print("✗ 视频功能执行失败")
    print("-" * 60)
    
    print()
    print("调试完成，浏览器保持打开状态")

# ==================== 入口 ====================

if __name__ == "__main__":
    _调试模式()
