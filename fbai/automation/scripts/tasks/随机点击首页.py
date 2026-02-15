"""
随机点击首页任务
模拟新手探索 Facebook 各个板块

特性：
- 随机点击首页的各个板块（视频、市场、小组、游戏等）
- 模拟新手：慢速操作、好奇探索、频繁返回首页
- 每个板块停留较长时间，仔细浏览
- 随机滚动、随机点击
- 装作对 Facebook 很不熟悉

流程：
1. 确保在首页
2. 随机选择一个板块
3. 点击进入板块
4. 模拟新手浏览（慢速滚动、长时间停留）
5. 点击首页图标返回
6. 重复2-5步

使用方法：
- 调试模式：修改 DEBUG_BROWSER_ID，直接运行此文件
- 正式调用：main.py 中调用 随机点击首页(driver, ...)
"""

import os
import sys
import time
import random
from typing import TYPE_CHECKING, List, Dict
from dataclasses import dataclass

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

# ==================== 调试配置 ====================

# 从环境变量读取浏览器ID
DEBUG_BROWSER_ID = os.environ.get('DEBUG_BROWSER_ID', "dd6c77a66dc74aea8c449207d55a3a87")

# ==================== 配置 ====================

@dataclass
class 随机点击首页配置:
    """随机点击首页任务配置"""
    探索板块数量: int = 4  # 探索多少个板块（增加到4个）
    每个板块最小停留秒: float = 25  # 每个板块最少停留时间（增加）
    每个板块最大停留秒: float = 45  # 每个板块最多停留时间（增加）
    滚动次数最小: int = 4  # 每个板块最少滚动次数（增加）
    滚动次数最大: int = 8  # 每个板块最多滚动次数（增加）
    查看自己首页: bool = True  # 是否查看自己的首页

# ==================== 辅助函数 ====================

def 随机延迟(最小秒: float = 1, 最大秒: float = 3):
    """随机延迟，模拟真人操作"""
    time.sleep(random.uniform(最小秒, 最大秒))

def 新手延迟(最小秒: float = 2, 最大秒: float = 5):
    """新手延迟（更长），模拟不熟悉的操作"""
    time.sleep(random.uniform(最小秒, 最大秒))

def 平滑滚动(driver: "WebDriver", 滚动量: int = 300):
    """平滑滚动，模拟真人"""
    driver.execute_script(f"window.scrollBy({{top: {滚动量}, behavior: 'smooth'}});")
    随机延迟(1, 2)

def 新手滚动(driver: "WebDriver"):
    """新手滚动：慢速、小幅度、频繁停顿"""
    # 小幅度滚动
    滚动量 = random.randint(150, 300)
    driver.execute_script(f"window.scrollBy({{top: {滚动量}, behavior: 'smooth'}});")
    
    # 停顿观察
    观察时间 = random.uniform(2, 4)
    time.sleep(观察时间)

def 人性化点击(driver: "WebDriver", 元素):
    """模拟真人点击，带鼠标移动"""
    from selenium.webdriver.common.action_chains import ActionChains
    
    try:
        actions = ActionChains(driver)
        # 移动到元素
        actions.move_to_element(元素).perform()
        新手延迟(0.5, 1.5)  # 新手犹豫时间更长
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

# ==================== 板块定义 ====================

# Facebook 首页左侧导航栏的板块
首页板块列表 = [
    {
        "name": "我的主页",
        "keywords": ["Profile", "个人主页", "我的主页"],
        "aria_labels": ["Profile", "个人主页"],
        "description": "查看自己的主页",
        "is_profile": True  # 标记为个人主页
    },
    {
        "name": "视频",
        "keywords": ["Watch", "视频", "Video"],
        "aria_labels": ["Watch", "视频"],
        "description": "观看视频",
        "is_profile": False
    },
    {
        "name": "市场",
        "keywords": ["Marketplace", "市场"],
        "aria_labels": ["Marketplace", "市场"],
        "description": "浏览市场",
        "is_profile": False
    },
    {
        "name": "小组",
        "keywords": ["Groups", "小组", "群组"],
        "aria_labels": ["Groups", "小组"],
        "description": "查看小组",
        "is_profile": False
    },
    {
        "name": "游戏",
        "keywords": ["Gaming", "游戏", "Play Games"],
        "aria_labels": ["Gaming", "游戏"],
        "description": "玩游戏",
        "is_profile": False
    },
    {
        "name": "活动",
        "keywords": ["Events", "活动"],
        "aria_labels": ["Events", "活动"],
        "description": "查看活动",
        "is_profile": False
    },
    {
        "name": "页面",
        "keywords": ["Pages", "页面", "专页"],
        "aria_labels": ["Pages", "页面"],
        "description": "浏览页面",
        "is_profile": False
    },
    {
        "name": "好友",
        "keywords": ["Friends", "好友", "朋友"],
        "aria_labels": ["Friends", "好友"],
        "description": "查看好友",
        "is_profile": False
    },
]

# ==================== 核心功能 ====================

def 返回首页(driver: "WebDriver", log_func=None, debug=False) -> bool:
    """点击首页图标返回首页"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        log("  返回首页...")
        
        # 新手：先思考一下怎么返回
        新手延迟(1, 2)
        
        # 多种返回首页的方式
        方式列表 = [
            # 方法1: 点击 Facebook logo（href="/"）
            ("点击 Facebook Logo", "//a[@aria-label='Facebook' and @href='/']"),
            # 方法2: 点击首页链接（Home）
            ("点击首页链接", "//a[@aria-label='Home' or @aria-label='首页']"),
            # 方法3: 查找包含 Facebook SVG 的链接且 href="/"
            ("点击 Facebook 图标", "//a[@href='/' and @role='link']//svg"),
            # 方法4: 直接访问首页
            ("直接访问", None),
        ]
        
        for 方式名称, 选择器 in 方式列表:
            try:
                if 选择器:
                    log(f"    尝试: {方式名称}")
                    
                    if "SVG" in 方式名称:
                        # 如果是 SVG，需要找到父元素 <a>
                        svg元素 = WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located((By.XPATH, 选择器))
                        )
                        # 获取父元素 <a>
                        首页元素 = svg元素.find_element(By.XPATH, "..")
                    else:
                        首页元素 = WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located((By.XPATH, 选择器))
                        )
                    
                    if 首页元素.is_displayed():
                        # 验证 href 是否为 "/"
                        href = 首页元素.get_attribute("href")
                        if href and (href.endswith('/') or href == 'https://www.facebook.com/' or href == 'https://www.facebook.com'):
                            if 人性化点击(driver, 首页元素):
                                log(f"      ✓ 成功返回首页")
                                新手延迟(2, 3)
                                return True
                        else:
                            log(f"      ⚠ href 不正确: {href}")
                else:
                    # 直接访问首页
                    log(f"    尝试: {方式名称}")
                    driver.get('https://www.facebook.com')
                    log(f"      ✓ 成功返回首页")
                    新手延迟(2, 3)
                    return True
            except Exception as e:
                log(f"      失败: {e}")
                continue
        
        log("  ⚠ 返回首页失败")
        return False
        
    except Exception as e:
        log(f"  ✗ 返回首页异常: {e}")
        return False

def 查找板块入口(driver: "WebDriver", 板块信息: Dict, log_func=None, debug=False):
    """查找板块入口元素"""
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    try:
        板块名称 = 板块信息["name"]
        关键词列表 = 板块信息["keywords"]
        是否个人主页 = 板块信息.get("is_profile", False)
        
        log(f"    查找 {板块名称} 入口...")
        
        # 如果是个人主页，使用特殊的查找方式
        if 是否个人主页:
            # 查找用户头像或个人主页链接
            选择器列表 = [
                # 通过头像图片的 alt 属性（通常包含用户名）
                "//img[contains(@alt, 'profile picture') or contains(@alt, '头像')]/ancestor::a",
                # 通过左侧导航栏的第一个链接（通常是个人主页）
                "//div[@role='navigation']//a[1]",
                # 通过包含用户名的链接
                "//a[contains(@href, '/profile.php') or contains(@href, '/me')]",
            ]
            
            for 选择器 in 选择器列表:
                try:
                    元素列表 = driver.find_elements(By.XPATH, 选择器)
                    for 元素 in 元素列表:
                        if 元素.is_displayed():
                            # 验证是否是个人主页链接
                            href = 元素.get_attribute("href")
                            if href and ('/profile.php' in href or '/me' in href or 'facebook.com/' in href):
                                log(f"      ✓ 找到个人主页入口")
                                return 元素
                except:
                    continue
        else:
            # 普通板块的查找方式 - 更严格的匹配
            # 先定义每个板块必须包含的 href 关键词
            板块href映射 = {
                "市场": "marketplace",
                "视频": "watch",
                "小组": "groups",
                "游戏": "gaming",
                "活动": "events",
                "页面": "pages",
                "好友": "friends",
            }
            
            必须包含的href = 板块href映射.get(板块名称, "").lower()
            
            for 关键词 in 关键词列表:
                选择器列表 = [
                    # 方法1: 通过 aria-label 精确匹配
                    f"//a[@aria-label='{关键词}' and @role='link']",
                    # 方法2: 通过 href 匹配（更可靠）
                    f"//a[contains(@href, '/{关键词.lower()}') and @role='link']",
                ]
                
                for 选择器 in 选择器列表:
                    try:
                        元素列表 = driver.find_elements(By.XPATH, 选择器)
                        for 元素 in 元素列表:
                            if 元素.is_displayed():
                                # 验证 href 是否正确
                                href = 元素.get_attribute("href")
                                if not href:
                                    continue
                                
                                href_lower = href.lower()
                                
                                # 严格验证：必须包含对应的 href 关键词
                                if 必须包含的href and 必须包含的href not in href_lower:
                                    log(f"      ⚠ href 不匹配: {href[:50]}... (需要包含 '{必须包含的href}')")
                                    continue
                                
                                # 排除小组链接（对于非小组板块）
                                if '/groups/' in href_lower and 板块名称 != "小组":
                                    log(f"      ⚠ 排除小组链接: {href[:50]}...")
                                    continue
                                
                                # 验证通过
                                log(f"      ✓ 找到入口 (href: {href[:50]}...)")
                                return 元素
                    except Exception as e:
                        log(f"      查找异常: {e}")
                        continue
            
            # 如果上面的方法都失败，尝试更宽松的匹配（但仍然验证 href）
            log(f"      尝试宽松匹配...")
            for 关键词 in 关键词列表:
                try:
                    # 通过文本内容匹配
                    元素列表 = driver.find_elements(By.XPATH, f"//a[contains(text(), '{关键词}')]")
                    for 元素 in 元素列表:
                        if 元素.is_displayed():
                            href = 元素.get_attribute("href")
                            if not href:
                                continue
                            
                            href_lower = href.lower()
                            
                            # 同样的严格验证
                            if 必须包含的href and 必须包含的href not in href_lower:
                                continue
                            
                            # 排除小组链接
                            if '/groups/' in href_lower and 板块名称 != "小组":
                                continue
                            
                            log(f"      ✓ 找到入口 (文本匹配, href: {href[:50]}...)")
                            return 元素
                except Exception as e:
                    log(f"      宽松匹配异常: {e}")
                    continue
        
        log(f"      ✗ 未找到入口")
        return None
        
    except Exception as e:
        log(f"      异常: {e}")
        return None

def 探索板块(driver: "WebDriver", 板块信息: Dict, 配置: 随机点击首页配置, 
            log_func=None, debug=False) -> bool:
    """探索一个板块"""
    from selenium.webdriver.common.by import By
    
    def log(msg):
        if log_func:
            log_func(msg)
        elif debug:
            print(msg)
    
    板块名称 = 板块信息["name"]
    板块描述 = 板块信息["description"]
    
    try:
        log(f"\n  探索板块: {板块名称} ({板块描述})")
        log("  " + "-" * 50)
        
        # 1. 查找板块入口
        板块入口 = 查找板块入口(driver, 板块信息, log_func, debug)
        
        if not 板块入口:
            log(f"  ✗ 未找到 {板块名称} 入口")
            return False
        
        # 2. 新手：先看一眼，犹豫一下
        log(f"  看到了 {板块名称}，考虑要不要点...")
        新手延迟(1, 3)
        
        # 3. 点击进入板块
        log(f"  点击进入 {板块名称}...")
        if not 人性化点击(driver, 板块入口):
            log(f"  ✗ 点击失败")
            return False
        
        # 4. 等待页面加载
        log(f"  等待页面加载...")
        新手延迟(3, 5)
        
        # 5. 新手浏览：慢速滚动、长时间停留
        停留时间 = random.uniform(配置.每个板块最小停留秒, 配置.每个板块最大停留秒)
        滚动次数 = random.randint(配置.滚动次数最小, 配置.滚动次数最大)
        
        log(f"  开始浏览 {板块名称}...")
        log(f"    计划停留: {停留时间:.1f}秒")
        log(f"    计划滚动: {滚动次数} 次")
        
        开始时间 = time.time()
        已滚动次数 = 0
        
        while time.time() - 开始时间 < 停留时间:
            # 新手滚动
            if 已滚动次数 < 滚动次数:
                log(f"    滚动 {已滚动次数 + 1}/{滚动次数}...")
                新手滚动(driver)
                已滚动次数 += 1
                
                # 滚动后，偶尔会停下来仔细看某个内容（30%概率）
                if random.random() < 0.3:
                    仔细观察时间 = random.uniform(3, 6)
                    log(f"      仔细看这个... ({仔细观察时间:.1f}秒)")
                    time.sleep(仔细观察时间)
            else:
                # 滚动完了，就停留观察
                观察时间 = random.uniform(3, 5)
                log(f"    观察中... ({观察时间:.1f}秒)")
                time.sleep(观察时间)
            
            # 偶尔会往回滚动（15%概率，增加）
            if random.random() < 0.15:
                log(f"    往回看看...")
                回滚量 = random.randint(150, 300)
                driver.execute_script(f"window.scrollBy({{top: -{回滚量}, behavior: 'smooth'}});")
                新手延迟(1.5, 3)
            
            # 偶尔会点击某个元素（8%概率，增加）
            if random.random() < 0.08:
                try:
                    log(f"    这个看起来有意思，点进去看看...")
                    # 查找可点击的元素
                    可点击元素 = driver.find_elements(By.XPATH, "//a[@role='link']")
                    if 可点击元素:
                        随机元素 = random.choice(可点击元素[:15])  # 从前15个中选
                        if 随机元素.is_displayed():
                            人性化点击(driver, 随机元素)
                            
                            # 查看详情
                            查看时间 = random.uniform(3, 6)
                            log(f"      看看这是什么... ({查看时间:.1f}秒)")
                            time.sleep(查看时间)
                            
                            # 可能会滚动一下（50%概率）
                            if random.random() < 0.5:
                                log(f"      往下看看...")
                                新手滚动(driver)
                            
                            # 返回
                            log(f"      ← 返回")
                            driver.back()
                            新手延迟(2, 3)
                except Exception as e:
                    log(f"      点击失败: {e}")
            
            # 偶尔会停顿发呆（10%概率）
            if random.random() < 0.1:
                发呆时间 = random.uniform(2, 4)
                log(f"    发呆中... ({发呆时间:.1f}秒)")
                time.sleep(发呆时间)
        
        log(f"  ✓ 完成浏览 {板块名称}")
        return True
        
    except Exception as e:
        log(f"  ✗ 探索 {板块名称} 异常: {e}")
        return False

# ==================== 主函数 ====================

def 随机点击首页(driver: "WebDriver", 浏览器ID: str = None, log_func=None, 
                配置: 随机点击首页配置 = None) -> bool:
    """
    执行随机点击首页任务
    
    流程：
    1. 确保在首页
    2. 随机选择板块
    3. 探索板块
    4. 返回首页
    5. 重复2-4步
    
    Args:
        driver: WebDriver实例
        浏览器ID: 浏览器ID（可选）
        log_func: 日志函数
        配置: 随机点击首页配置
    
    Returns:
        是否成功
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    if 配置 is None:
        配置 = 随机点击首页配置()
    
    log("=" * 60)
    log("开始随机点击首页任务（新手探索模式）")
    log("=" * 60)
    log(f"探索板块数量: {配置.探索板块数量}")
    log(f"每个板块停留: {配置.每个板块最小停留秒:.0f}-{配置.每个板块最大停留秒:.0f}秒")
    log(f"每个板块滚动: {配置.滚动次数最小}-{配置.滚动次数最大}次")
    
    try:
        # 1. 确保在首页
        当前网址 = driver.current_url
        if 'facebook.com' not in 当前网址 or '/watch' in 当前网址 or '/marketplace' in 当前网址:
            log("\n不在首页，正在跳转...")
            driver.get('https://www.facebook.com')
            新手延迟(3, 5)
        
        # 2. 随机打乱板块顺序
        可用板块 = 首页板块列表.copy()
        
        # 如果配置了查看自己首页，确保个人主页在第一个
        if 配置.查看自己首页:
            个人主页 = None
            其他板块 = []
            for 板块 in 可用板块:
                if 板块.get("is_profile", False):
                    个人主页 = 板块
                else:
                    其他板块.append(板块)
            
            # 打乱其他板块
            random.shuffle(其他板块)
            
            # 个人主页放在第一个
            if 个人主页:
                可用板块 = [个人主页] + 其他板块
                log("\n优先查看自己的主页（新手好奇自己的页面）")
            else:
                可用板块 = 其他板块
        else:
            random.shuffle(可用板块)
        
        # 3. 探索指定数量的板块
        已探索数量 = 0
        
        for i, 板块信息 in enumerate(可用板块):
            if 已探索数量 >= 配置.探索板块数量:
                log(f"\n已完成 {配置.探索板块数量} 个板块的探索")
                break
            
            log(f"\n{'=' * 60}")
            log(f"第 {已探索数量 + 1}/{配置.探索板块数量} 个板块")
            log(f"{'=' * 60}")
            
            # 探索板块
            成功 = 探索板块(driver, 板块信息, 配置, log_func, debug=True)
            
            if 成功:
                已探索数量 += 1
                
                # 返回首页（除非是最后一个板块）
                if 已探索数量 < 配置.探索板块数量:
                    log(f"\n准备返回首页...")
                    新手延迟(2, 3)
                    
                    if 返回首页(driver, log_func, debug=True):
                        # 返回首页后，新手会停留一下，看看首页
                        log(f"  回到首页了，看看有什么...")
                        新手延迟(2, 4)
                    else:
                        log(f"  ⚠ 返回首页失败，尝试直接访问")
                        driver.get('https://www.facebook.com')
                        新手延迟(3, 5)
            else:
                log(f"  跳过此板块，尝试下一个")
        
        log("\n" + "=" * 60)
        log(f"✓ 随机点击首页任务完成，共探索 {已探索数量} 个板块")
        log("=" * 60)
        return True
        
    except Exception as e:
        log(f"\n✗ 随机点击首页任务异常: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==================== 调试模式 ====================

def _调试模式():
    """调试模式入口"""
    print("=" * 60)
    print("随机点击首页 - 调试模式")
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
    
    测试配置 = 随机点击首页配置(
        探索板块数量=4,
        每个板块最小停留秒=25,
        每个板块最大停留秒=45,
        滚动次数最小=4,
        滚动次数最大=8,
        查看自己首页=True
    )
    
    成功 = 随机点击首页(driver, 浏览器ID=DEBUG_BROWSER_ID, 配置=测试配置)
    
    print()
    if 成功:
        print("✓ 随机点击首页任务执行成功")
    else:
        print("✗ 随机点击首页任务执行失败")
    
    print()
    print("调试完成，浏览器保持打开状态")

# ==================== 入口 ====================

if __name__ == "__main__":
    _调试模式()
