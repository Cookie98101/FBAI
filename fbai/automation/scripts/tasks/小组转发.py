"""
小组转发任务
从公共主页获取帖子并分享到小组

流程：
1. 调用辅助功能进入公共主页
2. 模拟真人浏览（滚动、停留）
3. 随机选择一个帖子
4. 分享到小组
5. 全局去重（避免重复分享同一帖子）
6. 数据上报

使用方法：
- 调试模式：修改 DEBUG_BROWSER_ID，直接运行此文件
- 正式调用：main.py 中调用 小组转发(driver, ...)
"""

import os
import sys
import time
import random
import json
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

# 导入辅助功能和去重管理
from tasks.辅助_进入公共主页 import 进入公共主页
from tasks.去重管理 import 检查是否已操作, 记录操作, 提取帖子ID
from tasks.分享动态 import 获取公共主页帖子列表, 模拟真人浏览
from tasks.采集小组链接 import 采集小组链接

# 数据上报 API
数据上报API = "http://localhost:8805/add_data"

# ==================== 调试配置 ====================

DEBUG_BROWSER_ID = "dd6c77a66dc74aea8c449207d55a3a87"
# 优先使用调试面板传入的浏览器ID（facebook_dashboard.py 会设置环境变量 DEBUG_BROWSER_ID）
DEBUG_BROWSER_ID = os.environ.get("DEBUG_BROWSER_ID") or DEBUG_BROWSER_ID

# ==================== 配置 ====================

@dataclass
class 小组转发配置:
    """小组转发任务配置"""
    转发数量: int = 1  # 每次运行只转发1个帖子
    浏览时长秒: int = 30  # 浏览多长时间（秒）

# ==================== 读取小组列表 ====================

def 读取小组列表(浏览器ID: str = None) -> List[dict]:
    """
    从 JSON 配置文件读取小组信息列表
    
    Args:
        浏览器ID: 浏览器ID，用于读取该浏览器的小组列表
    
    Returns:
        小组信息列表 [{name: 名称, url: 链接}, ...]
    """
    try:
        json配置文件 = os.path.join(scripts_dir, "脚本配置", "小组链接.json")
        
        if not os.path.exists(json配置文件):
            print(f"[小组转发] JSON 配置文件不存在: {json配置文件}")
            return []
        
        if not 浏览器ID:
            print(f"[小组转发] 错误：必须提供浏览器ID")
            return []
        
        try:
            with open(json配置文件, 'r', encoding='utf-8') as f:
                配置数据 = json.load(f)
            
            # 获取该浏览器的小组列表
            if 浏览器ID in 配置数据:
                小组列表 = 配置数据[浏览器ID]
                print(f"[小组转发] 读取浏览器 {浏览器ID} 的小组列表: {len(小组列表)} 个")
                return 小组列表
            else:
                print(f"[小组转发] 浏览器 {浏览器ID} 没有小组列表")
                return []
        except json.JSONDecodeError as e:
            print(f"[小组转发] JSON 解析失败: {e}")
            return []
        
    except Exception as e:
        print(f"[小组转发] 读取小组列表失败: {e}")
        return []

def 删除已使用的小组(浏览器ID: str, 小组信息: dict) -> bool:
    """
    从配置文件中删除已使用的小组（实现轮换）
    
    Args:
        浏览器ID: 浏览器ID
        小组信息: 小组信息 {name: 名称, url: 链接}
    
    Returns:
        是否成功删除
    """
    try:
        json配置文件 = os.path.join(scripts_dir, "脚本配置", "小组链接.json")
        
        if not os.path.exists(json配置文件):
            print(f"[小组转发] JSON 配置文件不存在，无法删除")
            return False
        
        # 读取配置
        with open(json配置文件, 'r', encoding='utf-8') as f:
            配置数据 = json.load(f)
        
        # 检查浏览器是否存在
        if 浏览器ID not in 配置数据:
            print(f"[小组转发] 浏览器 {浏览器ID} 不存在")
            return False
        
        # 查找并删除该小组
        小组列表 = 配置数据[浏览器ID]
        原始数量 = len(小组列表)
        
        # 根据 URL 匹配删除
        配置数据[浏览器ID] = [
            g for g in 小组列表 
            if g.get('url') != 小组信息.get('url')
        ]
        
        删除数量 = 原始数量 - len(配置数据[浏览器ID])
        
        if 删除数量 > 0:
            # 保存配置
            with open(json配置文件, 'w', encoding='utf-8') as f:
                json.dump(配置数据, f, ensure_ascii=False, indent=2)
            
            print(f"[小组转发] 已删除小组: {小组信息.get('name')[:30]}... (剩余 {len(配置数据[浏览器ID])} 个)")
            return True
        else:
            print(f"[小组转发] 未找到要删除的小组")
            return False
            
    except Exception as e:
        print(f"[小组转发] 删除小组失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def 保存小组链接到JSON(浏览器ID: str, 小组列表: List[dict]) -> bool:
    """
    保存小组信息到 JSON 配置文件
    
    Args:
        浏览器ID: 浏览器ID
        小组列表: 小组信息列表 [{name: 名称, url: 链接}, ...]
    
    Returns:
        是否成功
    """
    try:
        json配置文件 = os.path.join(scripts_dir, "脚本配置", "小组链接.json")
        
        # 读取现有配置（如果存在）
        配置数据 = {}
        if os.path.exists(json配置文件):
            try:
                with open(json配置文件, 'r', encoding='utf-8') as f:
                    配置数据 = json.load(f)
            except:
                配置数据 = {}
        
        # 更新该浏览器的小组列表
        配置数据[浏览器ID] = 小组列表
        
        # 保存配置
        with open(json配置文件, 'w', encoding='utf-8') as f:
            json.dump(配置数据, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 已保存 {len(小组列表)} 个小组到浏览器 {浏览器ID}")
        return True
        
    except Exception as e:
        print(f"\n✗ 保存小组信息失败: {e}")
        return False

# ==================== 分享帖子到小组 ====================

def 分享帖子到小组(driver: "WebDriver", 帖子ID: str, 分享按钮, 小组信息: dict,
                  浏览器ID: str = None, log_func=None, debug=False) -> bool:
    """
    将帖子分享到小组
    
    流程：
    1. 点击 Share 按钮
    2. 等待分享菜单出现
    3. 点击 "Group" 按钮
    4. 搜索小组名称
    5. 选择小组
    6. 点击 Post
    
    Args:
        driver: WebDriver实例
        帖子ID: 帖子ID（用于去重）
        分享按钮: Share 按钮元素
        小组信息: 小组信息 {name: 名称, url: 链接}
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
    
    小组名称 = 小组信息['name']
    小组链接 = 小组信息['url']
    
    try:
        # 检查是否已分享过（全局去重）
        if 检查是否已操作(帖子ID, "share_to_group", 去重天数=15):
            if debug:
                log(f"  跳过（15天内已分享到小组）")
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
        
        # 等待分享菜单完全加载
        等待时间 = random.uniform(5, 10)
        if debug:
            log(f"  等待菜单加载 {等待时间:.1f} 秒...")
        time.sleep(等待时间)
        
        # 3. 点击 "Group" 按钮
        if debug:
            log("  查找 Group 按钮...")
        
        try:
            # 查找包含 "Group" 文本的按钮
            group_buttons = driver.find_elements(By.XPATH, "//span[contains(text(), 'Group')]")
            
            group_button = None
            for span in group_buttons:
                try:
                    if not span.is_displayed():
                        continue
                    
                    # 向上查找可点击的父元素
                    current = span
                    for level in range(6):
                        try:
                            parent = current.find_element(By.XPATH, "..")
                            role = parent.get_attribute("role")
                            
                            if role == "button" or parent.tag_name == "button":
                                group_button = parent
                                if debug:
                                    log(f"    找到 Group 按钮（第{level}层）")
                                break
                            
                            current = parent
                        except:
                            break
                    
                    if group_button:
                        break
                except:
                    continue
            
            if not group_button:
                if debug:
                    log("  ✗ 未找到 Group 按钮")
                return False
            
            # 点击 Group 按钮
            if debug:
                log("  点击 Group 按钮...")
            
            try:
                driver.execute_script("arguments[0].click();", group_button)
            except:
                group_button.click()
            
            # 等待搜索框加载（需要更长时间）
            等待搜索框时间 = random.uniform(3, 5)
            if debug:
                log(f"  等待搜索框加载 {等待搜索框时间:.1f} 秒...")
            time.sleep(等待搜索框时间)
            
        except Exception as e:
            if debug:
                log(f"  ✗ 点击 Group 按钮失败: {e}")
            return False
        
        # 4. 查找并输入小组搜索框
        if debug:
            log("  查找小组搜索框...")
        
        try:
            # 查找 placeholder="Search for groups" 的输入框
            search_inputs = driver.find_elements(By.CSS_SELECTOR, "input[placeholder*='Search for groups']")
            
            search_input = None
            for input_elem in search_inputs:
                if input_elem.is_displayed():
                    search_input = input_elem
                    if debug:
                        log("    找到搜索框")
                    break
            
            if not search_input:
                if debug:
                    log("  ✗ 未找到搜索框")
                return False
            
            if debug:
                log(f"  输入小组名称: {小组名称[:30]}...")
            
            # 先聚焦输入框
            try:
                driver.execute_script("arguments[0].focus();", search_input)
                time.sleep(random.uniform(0.3, 0.5))
            except:
                pass
            
            # 模拟真人逐字输入（重要：触发搜索更新）
            try:
                from selenium.webdriver.common.keys import Keys
                
                # 先清空（如果有内容）
                try:
                    search_input.send_keys(Keys.CONTROL + "a")
                    time.sleep(random.uniform(0.1, 0.2))
                    search_input.send_keys(Keys.DELETE)
                    time.sleep(random.uniform(0.2, 0.4))
                except:
                    pass
                
                if debug:
                    log(f"  开始逐字输入小组名称...")
                
                # 逐字输入
                for i, 字符 in enumerate(小组名称):
                    search_input.send_keys(字符)
                    
                    # 随机输入速度
                    if random.random() < 0.1:  # 10% 稍长停顿
                        time.sleep(random.uniform(0.2, 0.4))
                    else:
                        time.sleep(random.uniform(0.05, 0.15))
                    
                    # 每输入5个字符显示一次进度
                    if debug and (i + 1) % 5 == 0:
                        log(f"    已输入 {i + 1}/{len(小组名称)} 字符")
                
                if debug:
                    log(f"  ✓ 已输入完成（逐字输入，共 {len(小组名称)} 字符）")
                
                # 输入完成后等待搜索结果更新
                等待搜索结果时间 = random.uniform(2, 3)
                if debug:
                    log(f"  等待搜索结果更新 {等待搜索结果时间:.1f} 秒...")
                time.sleep(等待搜索结果时间)
                
            except Exception as e:
                if debug:
                    log(f"  ⚠ 逐字输入失败: {e}")
                
                # 降级：使用 JavaScript 输入
                try:
                    driver.execute_script("arguments[0].value = arguments[1];", search_input, 小组名称)
                    
                    # 触发 input 事件
                    driver.execute_script("""
                        var event = new Event('input', { bubbles: true });
                        arguments[0].dispatchEvent(event);
                    """, search_input)
                    
                    time.sleep(random.uniform(2, 3))
                except:
                    pass
            
        except Exception as e:
            if debug:
                log(f"  ✗ 输入搜索框失败: {e}")
            return False
        
        # 5. 选择搜索结果中的小组
        if debug:
            log("  选择小组...")
        
        try:
            # 查找所有可能的搜索结果元素
            # 方法1: 查找 role="option" 或 role="menuitem" 的元素
            result_candidates = []
            
            try:
                options = driver.find_elements(By.CSS_SELECTOR, "[role='option'], [role='menuitem']")
                if debug:
                    log(f"    找到 {len(options)} 个选项元素")
                
                for option in options:
                    try:
                        if not option.is_displayed():
                            continue
                        
                        # 获取元素文本
                        text = option.text.strip()
                        aria_label = option.get_attribute("aria-label") or ""
                        
                        if debug and text:
                            log(f"    选项: {text[:50]}")
                        
                        # 检查是否包含小组名称的部分内容
                        # 使用前10个字符进行匹配（更宽松）
                        小组名称前缀 = 小组名称[:10] if len(小组名称) >= 10 else 小组名称[:5]
                        
                        if 小组名称前缀 in text or 小组名称前缀 in aria_label:
                            result_candidates.append({
                                'element': option,
                                'text': text,
                                'aria_label': aria_label
                            })
                            if debug:
                                log(f"    ✓ 匹配到候选: {text[:40]}")
                    except:
                        continue
            except Exception as e:
                if debug:
                    log(f"    方法1异常: {e}")
            
            # 方法2: 如果方法1没找到，查找包含小组名称的所有元素
            if not result_candidates:
                try:
                    小组名称前缀 = 小组名称[:10] if len(小组名称) >= 10 else 小组名称[:5]
                    all_elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{小组名称前缀}')]")
                    
                    if debug:
                        log(f"    方法2: 找到 {len(all_elements)} 个包含名称的元素")
                    
                    for elem in all_elements:
                        try:
                            if not elem.is_displayed():
                                continue
                            
                            text = elem.text.strip()
                            
                            # 向上查找可点击的父元素
                            current = elem
                            for level in range(8):
                                try:
                                    parent = current.find_element(By.XPATH, "..")
                                    role = parent.get_attribute("role")
                                    
                                    if role in ["button", "option", "menuitem"]:
                                        result_candidates.append({
                                            'element': parent,
                                            'text': text,
                                            'aria_label': parent.get_attribute("aria-label") or ""
                                        })
                                        if debug:
                                            log(f"    ✓ 找到可点击父元素（第{level}层）: {text[:40]}")
                                        break
                                    
                                    current = parent
                                except:
                                    break
                            
                            if result_candidates:
                                break
                        except:
                            continue
                except Exception as e:
                    if debug:
                        log(f"    方法2异常: {e}")
            
            # 选择第一个候选结果
            if result_candidates:
                选中的元素 = result_candidates[0]['element']
                
                if debug:
                    log(f"  点击选择: {result_candidates[0]['text'][:40]}")
                
                # 使用 JavaScript 点击（避免被拦截）
                try:
                    driver.execute_script("arguments[0].click();", 选中的元素)
                except:
                    选中的元素.click()
                
                if debug:
                    log("    ✓ 已选择小组")
                
                # 等待小组选择生效，输入框可能会刷新
                time.sleep(random.uniform(1, 2))
            else:
                if debug:
                    log("  ✗ 未找到匹配的小组")
                return False
            
        except Exception as e:
            if debug:
                log(f"  ✗ 选择小组失败: {e}")
            return False
        
        # 6. 添加评论（在转发前）
        if debug:
            log("  添加转发评论...")
        
        try:
            # 导入 AI 评论函数
            from tasks.自动化工具 import AI评论_不带帖子内容
            
            # 生成评论内容
            评论内容 = AI评论_不带帖子内容()
            
            if debug:
                log(f"  生成评论: {评论内容[:50]}...")
            
            # 新策略：基于坐标点击输入框
            # 先找到 Post 按钮，然后点击其上方的位置来激活输入框
            try:
                # 先找到 Post 按钮
                post_buttons = driver.find_elements(By.XPATH, "//span[text()='Post']")
                
                post_button_element = None
                for span in post_buttons:
                    try:
                        if not span.is_displayed():
                            continue
                        
                        # 向上查找按钮
                        current = span
                        for level in range(6):
                            try:
                                parent = current.find_element(By.XPATH, "..")
                                role = parent.get_attribute("role")
                                
                                if role == "button":
                                    post_button_element = parent
                                    break
                                
                                current = parent
                            except:
                                break
                        
                        if post_button_element:
                            break
                    except:
                        continue
                
                if post_button_element:
                    # 获取 Post 按钮的位置和大小
                    post_location = post_button_element.location
                    post_size = post_button_element.size
                    post_x = post_location['x']
                    post_y = post_location['y']
                    
                    if debug:
                        log(f"    Post 按钮位置: X={post_x}, Y={post_y}")
                    
                    # 计算输入框的大概位置：Post 按钮上方 150-200 像素
                    # X 坐标保持在 Post 按钮中心附近
                    输入框_x = post_x + post_size['width'] // 2
                    输入框_y = post_y - 180  # Post 按钮上方 180 像素
                    
                    if debug:
                        log(f"    计算输入框位置: X={输入框_x}, Y={输入框_y}")
                        log(f"    点击输入框位置...")
                    
                    # 使用 ActionChains 点击坐标
                    from selenium.webdriver.common.action_chains import ActionChains
                    
                    # 方法1: 使用 ActionChains 移动并点击
                    try:
                        action = ActionChains(driver)
                        action.move_to_element_with_offset(driver.find_element(By.TAG_NAME, "body"), 输入框_x, 输入框_y)
                        action.click()
                        action.perform()
                        time.sleep(random.uniform(0.5, 1))
                        
                        if debug:
                            log(f"    ✓ 已点击输入框位置")
                    except Exception as e:
                        if debug:
                            log(f"    ⚠ ActionChains 点击失败: {e}")
                        
                        # 方法2: 使用 JavaScript 点击坐标
                        try:
                            driver.execute_script(f"""
                                var element = document.elementFromPoint({输入框_x}, {输入框_y});
                                if (element) {{
                                    element.click();
                                    element.focus();
                                }}
                            """)
                            time.sleep(random.uniform(0.5, 1))
                            
                            if debug:
                                log(f"    ✓ 已通过 JavaScript 点击输入框")
                        except Exception as e2:
                            if debug:
                                log(f"    ⚠ JavaScript 点击失败: {e2}")
                    
                    # 输入评论（模拟真人逐字输入）
                    try:
                        from selenium.webdriver.common.keys import Keys
                        
                        # 获取当前焦点元素
                        active_element = driver.switch_to.active_element
                        
                        if debug:
                            log(f"    当前焦点元素: {active_element.tag_name}")
                        
                        # 先清空（如果有内容）
                        try:
                            active_element.send_keys(Keys.CONTROL + "a")
                            time.sleep(random.uniform(0.1, 0.2))
                            active_element.send_keys(Keys.DELETE)
                            time.sleep(random.uniform(0.2, 0.4))
                        except:
                            pass
                        
                        if debug:
                            log(f"  开始逐字输入评论...")
                        
                        # 逐字输入
                        for i, 字符 in enumerate(评论内容):
                            active_element.send_keys(字符)
                            
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
                else:
                    if debug:
                        log("  ⚠ 未找到 Post 按钮，跳过评论")
            except Exception as e:
                if debug:
                    log(f"  ⚠ 添加评论异常: {e}")
        except Exception as e:
            if debug:
                log(f"  ⚠ 添加评论功能异常: {e}")
        
        # 7. 点击 Post 按钮
        if debug:
            log("  查找 Post 按钮...")
        
        try:
            # 查找 Post 按钮（通常是 aria-label="Post" 或文本为 "Post"）
            post_buttons = driver.find_elements(By.XPATH, "//span[text()='Post']")
            
            post_button = None
            for span in post_buttons:
                try:
                    if not span.is_displayed():
                        continue
                    
                    # 向上查找按钮
                    current = span
                    for level in range(6):
                        try:
                            parent = current.find_element(By.XPATH, "..")
                            role = parent.get_attribute("role")
                            
                            if role == "button":
                                post_button = parent
                                if debug:
                                    log(f"    找到 Post 按钮（第{level}层）")
                                break
                            
                            current = parent
                        except:
                            break
                    
                    if post_button:
                        break
                except:
                    continue
            
            if not post_button:
                if debug:
                    log("  ✗ 未找到 Post 按钮")
                return False
            
            # 点击 Post
            if debug:
                log("  点击 Post 按钮...")
            
            try:
                driver.execute_script("arguments[0].click();", post_button)
            except:
                post_button.click()
            
            # 等待发布完成（10-20秒）
            等待发布时间 = random.uniform(10, 20)
            if debug:
                log(f"  等待发布完成 {等待发布时间:.1f} 秒...")
            time.sleep(等待发布时间)
            
            log(f"  ✓ 已转发到小组")
            
            # 8. 删除已使用的小组（轮换使用）
            if 浏览器ID:
                try:
                    删除已使用的小组(浏览器ID, 小组信息)
                except Exception as e:
                    if debug:
                        log(f"  ⚠ 删除小组记录失败: {e}")
            
            # 9. 记录操作（全局去重）
            记录操作(帖子ID, "share_to_group")
            
            # 10. 上报数据（只在成功时上报）
            try:
                requests.get(f"{数据上报API}?forwards=1", timeout=5)
                if debug:
                    log("  ✓ 已上报数据")
            except Exception as e:
                if debug:
                    log(f"  ⚠ 上报数据失败: {e}")
            
            # 11. 检测并关闭弹窗（如果还在）
            try:
                if debug:
                    log("  检测分享弹窗是否关闭...")
                
                # 查找关闭按钮（X 图标）
                # 通常是一个 SVG 图标，包含 X 形状的路径
                close_buttons = driver.find_elements(By.CSS_SELECTOR, "[aria-label*='Close'], [aria-label*='close']")
                
                关闭按钮 = None
                for btn in close_buttons:
                    try:
                        if btn.is_displayed():
                            # 检查是否在弹窗区域（Y 坐标较大）
                            location = btn.location
                            if location['y'] > 100:  # 不是顶部导航栏的按钮
                                关闭按钮 = btn
                                if debug:
                                    log(f"    找到关闭按钮: Y={location['y']}")
                                break
                    except:
                        continue
                
                if 关闭按钮:
                    if debug:
                        log("  点击关闭按钮...")
                    
                    try:
                        driver.execute_script("arguments[0].click();", 关闭按钮)
                    except:
                        关闭按钮.click()
                    
                    time.sleep(random.uniform(0.5, 1))
                    
                    if debug:
                        log("  ✓ 已关闭分享弹窗")
                else:
                    if debug:
                        log("  弹窗可能已自动关闭")
            except Exception as e:
                if debug:
                    log(f"  ⚠ 关闭弹窗异常: {e}")
            
            return True
            
        except Exception as e:
            if debug:
                log(f"  ✗ 点击 Post 按钮失败: {e}")
            
            # 失败时也删除小组（避免重复尝试失败的小组）
            if 浏览器ID:
                try:
                    删除已使用的小组(浏览器ID, 小组信息)
                except:
                    pass
            
            # 失败时也尝试关闭弹窗
            try:
                close_buttons = driver.find_elements(By.CSS_SELECTOR, "[aria-label*='Close'], [aria-label*='close']")
                for btn in close_buttons:
                    try:
                        if btn.is_displayed():
                            location = btn.location
                            if location['y'] > 100:
                                driver.execute_script("arguments[0].click();", btn)
                                time.sleep(random.uniform(0.5, 1))
                                if debug:
                                    log("  已关闭弹窗")
                                break
                    except:
                        continue
            except:
                pass
            
            return False
        
    except Exception as e:
        if debug:
            log(f"  分享到小组失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 失败时也删除小组
        if 浏览器ID:
            try:
                删除已使用的小组(浏览器ID, 小组信息)
            except:
                pass
        
        # 失败时也尝试关闭弹窗
        try:
            close_buttons = driver.find_elements(By.CSS_SELECTOR, "[aria-label*='Close'], [aria-label*='close']")
            for btn in close_buttons:
                try:
                    if btn.is_displayed():
                        location = btn.location
                        if location['y'] > 100:
                            driver.execute_script("arguments[0].click();", btn)
                            time.sleep(random.uniform(0.5, 1))
                            if debug:
                                log("  已关闭弹窗")
                            break
                except:
                    continue
        except:
            pass
        
        return False

# ==================== 主函数 ====================

def 小组转发(driver: "WebDriver", 浏览器ID: str = None, log_func=None, 配置: 小组转发配置 = None) -> bool:
    """
    执行小组转发任务
    
    流程：
    1. 读取小组列表（根据浏览器ID）
    2. 进入公共主页
    3. 模拟真人浏览
    4. 获取帖子列表
    5. 随机选择帖子并分享到小组
    6. 删除已使用的小组（轮换）
    
    Args:
        driver: WebDriver实例
        浏览器ID: 浏览器ID（用于读取该浏览器的小组列表，如果不提供则尝试自动获取）
        log_func: 日志函数
        配置: 小组转发配置
    
    Returns:
        是否成功
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    if 配置 is None:
        配置 = 小组转发配置()
    
    # 如果没有提供浏览器ID，尝试从 driver 的 capabilities 中获取
    if not 浏览器ID:
        try:
            # 尝试从浏览器的 user-agent 或其他信息中获取
            # 这里可以根据实际情况调整
            浏览器ID = driver.capabilities.get('browserName', 'unknown')
            log(f"⚠ 未提供浏览器ID，使用默认: {浏览器ID}")
        except:
            浏览器ID = "default"
            log(f"⚠ 无法获取浏览器ID，使用默认: {浏览器ID}")
    
    log("=" * 60)
    log("开始小组转发任务")
    log("=" * 60)
    log(f"浏览器ID: {浏览器ID}")
    log(f"目标转发数量: {配置.转发数量}")
    log(f"浏览时长: {配置.浏览时长秒}秒")
    
    try:
        # 1. 读取小组列表
        log("\n步骤1: 读取小组列表")
        log("-" * 60)
        
        小组列表 = 读取小组列表(浏览器ID)
        
        # 如果小组列表为空，自动采集
        if not 小组列表:
            log("⚠ 小组列表为空，开始自动采集...")
            log("")
            
            小组列表 = 采集小组链接(driver, log_func, debug=False)
            
            if 小组列表:
                # 保存到配置文件（JSON 格式）
                保存小组链接到JSON(浏览器ID, 小组列表)
                log(f"\n✓ 自动采集完成，共采集 {len(小组列表)} 个小组")
            else:
                log("\n✗ 自动采集失败，未找到小组")
                log("请确保：")
                log("  1. 已登录 Facebook")
                log("  2. 已加入至少一个小组")
                return False
        else:
            log(f"✓ 读取到 {len(小组列表)} 个小组")
        
        # 2. 进入公共主页
        log("\n步骤2: 进入公共主页")
        log("-" * 60)
        
        if not 进入公共主页(driver, log_func, debug=False):
            log("✗ 进入公共主页失败")
            return False
        
        log("✓ 已进入公共主页")
        
        # 3. 模拟真人浏览
        log("\n步骤3: 模拟真人浏览")
        log("-" * 60)
        
        模拟真人浏览(driver, 配置.浏览时长秒, log_func, debug=False)
        
        # 4. 获取帖子列表
        log("\n步骤4: 获取帖子列表")
        log("-" * 60)
        
        帖子列表 = 获取公共主页帖子列表(driver, log_func, debug=True)
        
        if not 帖子列表:
            log("✗ 未找到帖子")
            return False
        
        log(f"\n前5个帖子:")
        for i, 帖子 in enumerate(帖子列表[:5], 1):
            log(f"  {i}. ID:{帖子['post_id'][:20]}...")
        
        # 5. 随机打乱帖子顺序
        random.shuffle(帖子列表)
        
        # 6. 随机选择小组
        目标小组 = random.choice(小组列表)
        log(f"\n目标小组: {目标小组['name'][:40]}...")
        
        # 7. 转发帖子到小组
        log("\n步骤5: 转发帖子到小组")
        log("-" * 60)
        
        已转发数量 = 0
        
        for 帖子信息 in 帖子列表:
            if 已转发数量 >= 配置.转发数量:
                log(f"\n已达到目标转发数量: {配置.转发数量}")
                break
            
            帖子ID = 帖子信息['post_id']
            分享按钮 = 帖子信息['share_button']
            
            log(f"\n处理帖子 {已转发数量 + 1}/{配置.转发数量}")
            log(f"帖子ID: {帖子ID[:20]}...")
            
            # 模拟真人：浏览帖子列表，思考一下
            浏览时间 = random.uniform(2, 4)
            log(f"浏览帖子 {浏览时间:.1f} 秒...")
            time.sleep(浏览时间)
            
            # 转发帖子
            转发成功 = 分享帖子到小组(driver, 帖子ID, 分享按钮, 目标小组, 浏览器ID, log_func, debug=True)
            
            if 转发成功:
                已转发数量 += 1
                log(f"✓ 转发成功 ({已转发数量}/{配置.转发数量})")
                
                # 模拟真人：转发后休息一下
                if 已转发数量 < 配置.转发数量:
                    休息时间 = random.uniform(5, 10)
                    log(f"休息 {休息时间:.1f} 秒...")
                    time.sleep(休息时间)
            else:
                log(f"✗ 转发失败，尝试下一个帖子")
        
        log("\n" + "=" * 60)
        log(f"✓ 小组转发任务完成，共转发 {已转发数量} 个帖子")
        log("=" * 60)
        return True
        
    except Exception as e:
        log(f"\n✗ 小组转发任务异常: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==================== 调试模式 ====================

def _调试模式():
    """调试模式入口"""
    print("=" * 60)
    print("小组转发 - 调试模式")
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
    
    测试配置 = 小组转发配置(
        转发数量=1,
        浏览时长秒=30
    )
    
    成功 = 小组转发(driver, 浏览器ID=DEBUG_BROWSER_ID, 配置=测试配置)
    
    print()
    if 成功:
        print("✓ 小组转发任务执行成功")
    else:
        print("✗ 小组转发任务执行失败")
    
    print()
    print("调试完成，浏览器保持打开状态")

# ==================== 入口 ====================

if __name__ == "__main__":
    _调试模式()

