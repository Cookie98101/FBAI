#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Facebook小组互动加权模块

这是一个独立的行为调度模块，不是完整脚本

职责：
- 根据小组加入天数决定互动行为
- 输出行为配额和决策结果
- 不负责具体执行

输入：
- 账号ID
- 已加入小组列表
- 小组历史互动数据

输出：
- 本次运行操作的小组列表
- 每个小组允许的行为类型
- 行为数量 & 比例

使用方法：
- 调试模式：修改 DEBUG_BROWSER_ID，直接运行此文件
- 正式调用：main.py 中调用 小组互动加权模块
"""

import os
import sys
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import requests


# ==================== 路径设置 ====================
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(os.path.dirname(scripts_dir))

for path in [current_dir, scripts_dir, project_root]:
    if path not in sys.path:
        sys.path.insert(0, path)


# ==================== 调试配置 ====================

# 从环境变量读取浏览器ID
DEBUG_BROWSER_ID = os.environ.get('DEBUG_BROWSER_ID', "75fcd7cda44d4c97b7dc441e46525526")

class 小组互动加权模块:
    """
    小组互动加权调度器
    
    核心功能：
    1. 根据账号年龄判断运行频率
    2. 根据小组加入天数决定互动行为
    3. 概率执行不同的行为
    4. 调用其他模块执行具体操作
    """
    
    def __init__(self, driver, logger, api_base="http://localhost:8805", test_mode=False):
        self.driver = driver
        self.logger = logger
        self.api_base = api_base
        self.test_mode = test_mode  # 测试模式：缩短等待时间
        
        # 账号成长阶段配置（决定运行频率）
        self.账号阶段配置 = {
            1: {"天数范围": (0, 3), "每天运行次数": (0, 0), "抽中概率": 0, "操作小组数": (0, 0), "冷却时间": 0},
            2: {"天数范围": (4, 7), "每天运行次数": (0, 1), "抽中概率": 30, "操作小组数": (1, 1), "冷却时间": 72},
            3: {"天数范围": (8, 15), "每天运行次数": (1, 2), "抽中概率": 40, "操作小组数": (1, 2), "冷却时间": 60},
            4: {"天数范围": (16, 25), "每天运行次数": (1, 2), "抽中概率": 50, "操作小组数": (2, 3), "冷却时间": 48},
            5: {"天数范围": (26, 45), "每天运行次数": (1, 3), "抽中概率": 50, "操作小组数": (2, 4), "冷却时间": 48},
            6: {"天数范围": (46, 999), "每天运行次数": (1, 3), "抽中概率": 50, "操作小组数": (3, 5), "冷却时间": 48},
        }
        
        # 小组加入阶段配置（决定互动行为）
        self.小组阶段配置 = {
            1: {
                "天数范围": (0, 3),
                "行为间隔": (30, 90),
                "单组日行为": (0, 1),
                "浏览": 90, "点赞": 10, "评论": 0, "发帖": 0,
                "评论字数": (0, 0),
                "表情概率": (5, 15),
                "允许发帖": False,
                "阅读帖子数": (2, 4),
                "单帖阅读时长": (30, 90),
                "展开评论概率": 20
            },
            2: {
                "天数范围": (4, 7),
                "行为间隔": (20, 60),
                "单组日行为": (1, 1),
                "浏览": 65, "点赞": 25, "评论": 10, "发帖": 0,
                "评论字数": (15, 30),
                "表情概率": (10, 25),
                "允许发帖": False,
                "阅读帖子数": (1, 2),
                "单帖阅读时长": (60, 120),
                "展开评论概率": 30
            },
            3: {
                "天数范围": (8, 14),
                "行为间隔": (15, 45),
                "单组日行为": (1, 2),
                "浏览": 55, "点赞": 20, "评论": 20, "发帖": 5,
                "评论字数": (20, 50),
                "表情概率": (15, 30),
                "允许发帖": False,
                "阅读帖子数": (1, 2),
                "单帖阅读时长": (60, 120),
                "展开评论概率": 40
            },
            4: {
                "天数范围": (15, 21),
                "行为间隔": (10, 40),
                "单组日行为": (1, 2),
                "浏览": 50, "点赞": 15, "评论": 25, "发帖": 10,
                "评论字数": (20, 50),
                "表情概率": (20, 35),
                "允许发帖": True,
                "阅读帖子数": (1, 2),
                "单帖阅读时长": (60, 180),
                "展开评论概率": 50
            },
            5: {
                "天数范围": (22, 30),
                "行为间隔": (8, 35),
                "单组日行为": (1, 3),
                "浏览": 40, "点赞": 15, "评论": 30, "发帖": 15,
                "评论字数": (20, 50),
                "表情概率": (20, 40),
                "允许发帖": True,
                "阅读帖子数": (1, 3),
                "单帖阅读时长": (60, 180),
                "展开评论概率": 50
            },
            6: {
                "天数范围": (31, 999),
                "行为间隔": (5, 30),
                "单组日行为": (1, 3),
                "浏览": 35, "点赞": 10, "评论": 35, "发帖": 20,
                "评论字数": (20, 50),
                "表情概率": (15, 45),
                "允许发帖": True,
                "阅读帖子数": (1, 3),
                "单帖阅读时长": (60, 180),
                "展开评论概率": 40
            },
        }
    
    def 获取账号阶段(self, account_age_days: int) -> int:
        """根据账号年龄获取阶段"""
        for stage, config in self.账号阶段配置.items():
            min_days, max_days = config["天数范围"]
            if min_days <= account_age_days <= max_days:
                return stage
        return 6  # 默认返回最高阶段
    
    def 获取小组阶段(self, group_age_days: int) -> int:
        """根据小组加入天数获取阶段"""
        for stage, config in self.小组阶段配置.items():
            min_days, max_days = config["天数范围"]
            if min_days <= group_age_days <= max_days:
                return stage
        return 6  # 默认返回最高阶段
    
    def 判断是否执行(self, account_age_days: int) -> bool:
        """
        判断本次是否执行互动加权模块
        
        Args:
            account_age_days: 账号年龄（天）
        
        Returns:
            是否执行
        """
        account_stage = self.获取账号阶段(account_age_days)
        config = self.账号阶段配置[account_stage]
        
        # 阶段1禁止互动
        if account_stage == 1:
            self.logger(f"[互动加权] 账号阶段{account_stage}（{account_age_days}天），禁止互动")
            return False
        
        # 根据抽中概率判断
        probability = config["抽中概率"]
        random_value = random.randint(1, 100)
        
        if random_value <= probability:
            self.logger(f"[互动加权] 账号阶段{account_stage}（{account_age_days}天），抽中执行（{random_value}≤{probability}）")
            return True
        else:
            self.logger(f"[互动加权] 账号阶段{account_stage}（{account_age_days}天），未抽中（{random_value}>{probability}）")
            return False
    
    def 选择操作小组(self, account_age_days: int, groups: List[Dict]) -> List[Dict]:
        """
        选择本次要操作的小组
        
        Args:
            account_age_days: 账号年龄（天）
            groups: 已加入的小组列表
        
        Returns:
            选中的小组列表
        """
        account_stage = self.获取账号阶段(account_age_days)
        config = self.账号阶段配置[account_stage]
        
        # 过滤条件
        eligible_groups = []
        now = datetime.now()
        
        for group in groups:
            # 计算加入天数
            joined_date = datetime.strptime(group.get("joined_date", ""), "%Y-%m-%d")
            hours_since_join = (now - joined_date).total_seconds() / 3600
            
            # 新加入小组24小时冷却期
            if hours_since_join < 24:
                continue
            
            # 计算距离上次互动时间
            last_interaction = group.get("last_interaction_date", "")
            if last_interaction:
                last_date = datetime.strptime(last_interaction, "%Y-%m-%d")
                hours_since_last = (now - last_date).total_seconds() / 3600
            else:
                hours_since_last = 999  # 从未互动
            
            # 小组冷却时间
            cooldown_hours = config["冷却时间"]
            if hours_since_last < cooldown_hours:
                continue
            
            eligible_groups.append(group)
        
        if not eligible_groups:
            self.logger("[互动加权] 没有符合条件的小组")
            return []
        
        # 优先级排序
        # 1. 长时间未互动的小组（≥5天）
        # 2. 冷却完成的小组（≥48小时）
        eligible_groups.sort(key=lambda g: (
            -self._计算未互动天数(g),  # 未互动天数越长越优先
            random.random()  # 随机打乱
        ))
        
        # 随机选择小组数量
        min_groups, max_groups = config["操作小组数"]
        num_groups = random.randint(min_groups, min(max_groups, len(eligible_groups)))
        
        selected = eligible_groups[:num_groups]
        self.logger(f"[互动加权] 选中{len(selected)}个小组（共{len(eligible_groups)}个符合条件）")
        
        return selected
    
    def _计算未互动天数(self, group: Dict) -> int:
        """计算小组未互动天数"""
        last_interaction = group.get("last_interaction_date", "")
        if not last_interaction:
            return 999
        
        last_date = datetime.strptime(last_interaction, "%Y-%m-%d")
        days = (datetime.now() - last_date).days
        return days
    
    def 生成小组行为计划(self, group: Dict) -> Dict:
        """
        为单个小组生成行为计划
        
        Args:
            group: 小组信息
        
        Returns:
            行为计划
        """
        # 计算小组加入天数
        joined_date = datetime.strptime(group.get("joined_date", ""), "%Y-%m-%d")
        group_age_days = (datetime.now() - joined_date).days
        
        # 获取小组阶段
        group_stage = self.获取小组阶段(group_age_days)
        config = self.小组阶段配置[group_stage]
        
        self.logger(f"[互动加权] 小组: {group.get('group_name', '未知')}")
        self.logger(f"[互动加权] 加入天数: {group_age_days}天，阶段: {group_stage}")
        
        # 生成行为计划
        plan = {
            "group_url": group.get("group_url", ""),
            "group_name": group.get("group_name", ""),
            "group_age_days": group_age_days,
            "group_stage": group_stage,
            "actions": {}
        }
        
        # 1. 阅读（必须执行）
        plan["actions"]["阅读"] = {
            "执行": True,
            "帖子数": random.randint(*config["阅读帖子数"]),
            "单帖时长": config["单帖阅读时长"],
            "展开评论概率": config["展开评论概率"]
        }
        
        # 2. 点赞（概率执行）
        like_probability = config["点赞"]
        like_random = random.randint(1, 100)
        plan["actions"]["点赞"] = {
            "执行": like_random <= like_probability,
            "概率": like_probability,
            "随机值": like_random
        }
        
        # 3. 评论（概率执行）
        comment_probability = config["评论"]
        comment_random = random.randint(1, 100)
        plan["actions"]["评论"] = {
            "执行": comment_random <= comment_probability,
            "概率": comment_probability,
            "随机值": comment_random,
            "字数范围": config["评论字数"],
            "表情概率": config["表情概率"]
        }
        
        # 4. 发帖（概率执行）
        post_probability = config["发帖"]
        post_random = random.randint(1, 100)
        plan["actions"]["发帖"] = {
            "执行": (post_random <= post_probability) and config["允许发帖"],
            "概率": post_probability,
            "随机值": post_random,
            "允许": config["允许发帖"]
        }
        
        self.logger(f"[互动加权] 行为计划: 阅读✓ 点赞{'✓' if plan['actions']['点赞']['执行'] else '✗'} "
                   f"评论{'✓' if plan['actions']['评论']['执行'] else '✗'} "
                   f"发帖{'✓' if plan['actions']['发帖']['执行'] else '✗'}")
        
        return plan
    
    def 执行小组互动(self, plan: Dict) -> Dict:
        """
        执行单个小组的互动计划
        
        Args:
            plan: 行为计划
        
        Returns:
            执行结果
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        result = {
            "success": True,
            "group_url": plan["group_url"],
            "group_name": plan["group_name"],
            "actions_performed": []
        }
        
        try:
            # 1. 进入小组（真实点击）
            self.logger(f"[互动加权] 进入小组: {plan['group_name']}")
            self.logger(f"[互动加权] URL: {plan['group_url']}")
            
            # 使用driver.get访问小组
            self.driver.get(plan["group_url"])
            
            # 等待页面加载
            time.sleep(random.uniform(3, 8))
            
            # 验证是否成功进入小组
            try:
                # 检查是否有小组特征元素
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@role='main']"))
                )
                self.logger("[互动加权] ✓ 成功进入小组页面")
            except:
                self.logger("[互动加权] ⚠ 页面加载可能有问题，继续执行...")
            
            # 2. 执行阅读（必须）
            if plan["actions"]["阅读"]["执行"]:
                self.logger("[互动加权] 执行阅读...")
                read_result = self._执行阅读(plan["actions"]["阅读"])
                result["actions_performed"].append({"action": "阅读", "result": read_result})
                
                # 等待间隔
                if self.test_mode:
                    wait_time = random.uniform(2, 5)  # 测试模式：2-5秒
                else:
                    wait_time = random.uniform(2, 8) * 60  # 正常模式：2-8分钟
                self.logger(f"[互动加权] 等待{wait_time if self.test_mode else wait_time/60:.1f}{'秒' if self.test_mode else '分钟'}...")
                time.sleep(wait_time)
            
            # 3. 执行点赞（概率）
            if plan["actions"]["点赞"]["执行"]:
                self.logger("[互动加权] 执行点赞...")
                like_result = self._执行点赞()
                result["actions_performed"].append({"action": "点赞", "result": like_result})
                
                # 等待间隔
                if self.test_mode:
                    wait_time = random.uniform(1, 3)  # 测试模式：1-3秒
                else:
                    wait_time = random.uniform(30, 120)  # 正常模式：30-120秒
                time.sleep(wait_time)
            
            # 4. 执行评论（概率）
            if plan["actions"]["评论"]["执行"]:
                self.logger("[互动加权] 执行评论...")
                comment_result = self._执行评论(plan["actions"]["评论"])
                result["actions_performed"].append({"action": "评论", "result": comment_result})
                
                # 等待间隔
                if self.test_mode:
                    wait_time = random.uniform(2, 5)  # 测试模式：2-5秒
                else:
                    wait_time = random.uniform(3, 10) * 60  # 正常模式：3-10分钟
                time.sleep(wait_time)
            
            # 5. 执行发帖（概率）
            if plan["actions"]["发帖"]["执行"]:
                self.logger("[互动加权] 执行发帖...")
                post_result = self._执行发帖()
                result["actions_performed"].append({"action": "发帖", "result": post_result})
            
            # 6. 记录行为数据
            self._记录行为数据(plan, result)
            
        except Exception as e:
            self.logger(f"[互动加权] 执行失败: {e}")
            import traceback
            self.logger(traceback.format_exc())
            result["success"] = False
            result["error"] = str(e)
        
        return result
    
    def _执行阅读(self, config: Dict) -> Dict:
        """
        调用阅读模块
        
        Args:
            config: 阅读配置
        
        Returns:
            执行结果
        """
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            帖子数 = config["帖子数"]
            单帖时长 = config["单帖时长"]
            展开评论概率 = config["展开评论概率"]
            
            self.logger(f"[互动加权] 开始阅读{帖子数}个帖子...")
            
            已阅读数 = 0
            
            for i in range(帖子数):
                try:
                    # 1. 滚动到下一个帖子
                    scroll_amount = random.randint(300, 600)
                    self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                    
                    # 2. 停留阅读
                    if self.test_mode:
                        read_time = random.uniform(3, 8)  # 测试模式：3-8秒
                    else:
                        min_time, max_time = 单帖时长
                        read_time = random.uniform(min_time, max_time)
                    
                    self.logger(f"[互动加权] 阅读第{i+1}个帖子，停留{read_time:.1f}秒...")
                    time.sleep(read_time)
                    
                    # 3. 概率展开评论
                    if random.randint(1, 100) <= 展开评论概率:
                        try:
                            # 查找"查看更多评论"按钮
                            comment_buttons = self.driver.find_elements(By.XPATH, 
                                "//span[contains(text(), '查看') or contains(text(), 'View') or contains(text(), '评论') or contains(text(), 'comment')]")
                            
                            if comment_buttons:
                                comment_buttons[0].click()
                                self.logger("[互动加权] 展开评论区")
                                time.sleep(random.uniform(2, 5))
                        except:
                            pass
                    
                    已阅读数 += 1
                    
                except Exception as e:
                    self.logger(f"[互动加权] 阅读第{i+1}个帖子失败: {e}")
                    continue
            
            self.logger(f"[互动加权] ✓ 完成阅读，共{已阅读数}个帖子")
            return {"success": True, "posts_read": 已阅读数}
            
        except Exception as e:
            self.logger(f"[互动加权] 阅读失败: {e}")
            return {"success": False, "error": str(e), "posts_read": 0}
    
    def _执行点赞(self) -> Dict:
        """执行点赞"""
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            self.logger("[互动加权] 查找可点赞的帖子...")
            
            # 查找点赞按钮（未点赞状态）
            like_selectors = [
                "//div[@aria-label='赞' or @aria-label='Like']",
                "//span[contains(text(), '赞') or contains(text(), 'Like')]//ancestor::div[@role='button']"
            ]
            
            for selector in like_selectors:
                try:
                    like_buttons = self.driver.find_elements(By.XPATH, selector)
                    
                    if like_buttons:
                        # 随机选择一个帖子点赞
                        button = random.choice(like_buttons[:5])  # 只从前5个中选择
                        
                        # 滚动到按钮位置
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                        time.sleep(random.uniform(1, 3))
                        
                        # 点击点赞
                        button.click()
                        self.logger("[互动加权] ✓ 点赞成功")
                        
                        # 上报数据
                        try:
                            requests.get(f"{self.api_base}/add_data?likes=1", timeout=5)
                        except:
                            pass
                        
                        return {"success": True, "likes": 1}
                except:
                    continue
            
            self.logger("[互动加权] 未找到可点赞的帖子")
            return {"success": False, "likes": 0}
            
        except Exception as e:
            self.logger(f"[互动加权] 点赞失败: {e}")
            return {"success": False, "error": str(e), "likes": 0}
    
    def _执行评论(self, config: Dict) -> Dict:
        """执行评论"""
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            min_len, max_len = config["字数范围"]
            表情概率范围 = config["表情概率"]
            
            self.logger(f"[互动加权] 准备评论（{min_len}-{max_len}字）...")
            
            # 1. 生成评论内容（调用AI）
            评论内容 = self._生成评论内容(min_len, max_len)
            
            # 2. 随机添加表情
            if isinstance(表情概率范围, tuple):
                表情概率 = random.randint(表情概率范围[0], 表情概率范围[1])
            else:
                表情概率 = 表情概率范围
            
            if random.randint(1, 100) <= 表情概率:
                表情列表 = ["😊", "👍", "❤️", "😄", "🙏", "💪", "✨", "🎉"]
                评论内容 += " " + random.choice(表情列表)
            
            self.logger(f"[互动加权] 评论内容: {评论内容}")
            
            # 3. 查找评论框
            comment_selectors = [
                "//div[@aria-label='写评论……' or @aria-label='Write a comment...']",
                "//div[@contenteditable='true' and contains(@aria-label, '评论')]",
                "//textarea[@placeholder='写评论……' or @placeholder='Write a comment...']"
            ]
            
            comment_box = None
            for selector in comment_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        comment_box = elements[0]
                        break
                except:
                    continue
            
            if not comment_box:
                self.logger("[互动加权] 未找到评论框")
                return {"success": False, "comments": 0}
            
            # 4. 滚动到评论框
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", comment_box)
            time.sleep(random.uniform(1, 3))
            
            # 5. 点击评论框
            comment_box.click()
            time.sleep(random.uniform(0.5, 1.5))
            
            # 6. 输入评论（模拟打字）
            for char in 评论内容:
                comment_box.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))  # 模拟打字速度
            
            time.sleep(random.uniform(1, 3))
            
            # 7. 查找并点击发送按钮
            send_selectors = [
                "//div[@aria-label='发表评论' or @aria-label='Post comment']",
                "//span[contains(text(), '发表') or contains(text(), 'Post')]//ancestor::div[@role='button']"
            ]
            
            for selector in send_selectors:
                try:
                    send_button = self.driver.find_element(By.XPATH, selector)
                    send_button.click()
                    self.logger("[互动加权] ✓ 评论发送成功")
                    
                    # 上报数据
                    try:
                        requests.get(f"{self.api_base}/add_data?comments=1", timeout=5)
                    except:
                        pass
                    
                    return {"success": True, "comments": 1, "content": 评论内容}
                except:
                    continue
            
            self.logger("[互动加权] 未找到发送按钮")
            return {"success": False, "comments": 0}
            
        except Exception as e:
            self.logger(f"[互动加权] 评论失败: {e}")
            return {"success": False, "error": str(e), "comments": 0}
    
    def _生成评论内容(self, min_len: int, max_len: int) -> str:
        """
        生成评论内容（简化版，实际应调用AI）
        
        Args:
            min_len: 最小字数
            max_len: 最大字数
        
        Returns:
            评论内容
        """
        # 简单的评论模板（实际应调用AI生成）
        评论模板 = [
            "很有用的分享，感谢！",
            "这个方法不错，学习了",
            "说得很有道理",
            "我也遇到过类似的情况",
            "感谢分享，很实用",
            "这个观点很有启发性",
            "学到了新知识",
            "确实是这样的",
            "非常赞同你的看法",
            "这个建议很好"
        ]
        
        # 随机选择一个模板
        base_comment = random.choice(评论模板)
        
        # 如果需要更长的评论，添加补充内容
        if len(base_comment) < min_len:
            补充内容 = [
                "，我之前也试过类似的方法",
                "，这对我很有帮助",
                "，希望能看到更多这样的内容",
                "，期待后续的分享",
                "，这个话题很有意思"
            ]
            base_comment += random.choice(补充内容)
        
        return base_comment
    
    def _执行发帖(self) -> Dict:
        """执行发帖"""
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            self.logger("[互动加权] 准备发帖...")
            
            # 1. 生成帖子内容
            帖子内容 = self._生成帖子内容()
            self.logger(f"[互动加权] 帖子内容: {帖子内容[:50]}...")
            
            # 2. 查找发帖入口
            post_selectors = [
                "//span[contains(text(), '你在想什么') or contains(text(), \"What's on your mind\")]",
                "//div[@role='button' and contains(@aria-label, '创建帖子')]",
                "//div[contains(text(), '写点什么') or contains(text(), 'Write something')]"
            ]
            
            post_entry = None
            for selector in post_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        post_entry = elements[0]
                        break
                except:
                    continue
            
            if not post_entry:
                self.logger("[互动加权] 未找到发帖入口")
                return {"success": False, "posts": 0}
            
            # 3. 点击发帖入口
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", post_entry)
            time.sleep(random.uniform(1, 3))
            post_entry.click()
            time.sleep(random.uniform(2, 4))
            
            # 4. 查找帖子输入框
            content_selectors = [
                "//div[@contenteditable='true' and @role='textbox']",
                "//div[@aria-label='创建公开帖子……' or @aria-label='Create a public post...']"
            ]
            
            content_box = None
            for selector in content_selectors:
                try:
                    content_box = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    break
                except:
                    continue
            
            if not content_box:
                self.logger("[互动加权] 未找到帖子输入框")
                return {"success": False, "posts": 0}
            
            # 5. 输入帖子内容（模拟打字）
            content_box.click()
            time.sleep(random.uniform(0.5, 1.5))
            
            for char in 帖子内容:
                content_box.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            time.sleep(random.uniform(2, 4))
            
            # 6. 查找并点击发布按钮
            publish_selectors = [
                "//div[@aria-label='发布' or @aria-label='Post'][@role='button']",
                "//span[contains(text(), '发布') or contains(text(), 'Post')]//ancestor::div[@role='button']"
            ]
            
            for selector in publish_selectors:
                try:
                    publish_button = self.driver.find_element(By.XPATH, selector)
                    publish_button.click()
                    self.logger("[互动加权] ✓ 帖子发布成功")
                    
                    # 上报数据
                    try:
                        requests.get(f"{self.api_base}/add_data?posts=1", timeout=5)
                    except:
                        pass
                    
                    return {"success": True, "posts": 1, "content": 帖子内容}
                except:
                    continue
            
            self.logger("[互动加权] 未找到发布按钮")
            return {"success": False, "posts": 0}
            
        except Exception as e:
            self.logger(f"[互动加权] 发帖失败: {e}")
            return {"success": False, "error": str(e), "posts": 0}
    
    def _生成帖子内容(self) -> str:
        """
        生成帖子内容（简化版，实际应调用AI）
        
        Returns:
            帖子内容
        """
        # 简单的帖子模板（实际应调用AI生成）
        帖子模板 = [
            "最近发现了一个很实用的方法，分享给大家。",
            "今天学到了一些新知识，记录一下。",
            "有个问题想请教大家，希望能得到一些建议。",
            "分享一下我的经验，希望对大家有帮助。",
            "看到一个有趣的话题，想听听大家的看法。"
        ]
        
        return random.choice(帖子模板)
    
    def _记录行为数据(self, plan: Dict, result: Dict):
        """记录行为数据到数据库"""
        try:
            # 统计各类行为数量
            read_count = 0
            like_count = 0
            comment_count = 0
            post_count = 0
            
            for action in result["actions_performed"]:
                action_type = action.get("action", "")
                action_result = action.get("result", {})
                
                if action_type == "阅读":
                    read_count += action_result.get("posts_read", 0)
                elif action_type == "点赞":
                    like_count += action_result.get("likes", 0)
                elif action_type == "评论":
                    comment_count += action_result.get("comments", 0)
                elif action_type == "发帖":
                    post_count += action_result.get("posts", 0)
            
            data = {
                "group_url": plan["group_url"],
                "group_name": plan["group_name"],
                "group_age_days": plan["group_age_days"],
                "group_stage": plan["group_stage"],
                "read_count": read_count,
                "like_count": like_count,
                "comment_count": comment_count,
                "post_count": post_count,
                "actions": result["actions_performed"],
                "timestamp": datetime.now().isoformat()
            }
            
            # 发送到API
            try:
                response = requests.post(
                    f"{self.api_base}/api/record-group-action",
                    json=data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    self.logger(f"[互动加权] ✓ 行为数据已记录")
                else:
                    self.logger(f"[互动加权] ⚠ 行为数据记录失败: HTTP {response.status_code}")
            except Exception as e:
                self.logger(f"[互动加权] ⚠ 行为数据记录失败: {e}")
                
        except Exception as e:
            self.logger(f"[互动加权] 记录数据失败: {e}")
    
    def 获取已加入小组列表(self) -> List[Dict]:
        """
        从Facebook页面获取账号已加入的小组列表
        
        Returns:
            小组列表
        """
        self.logger("[互动加权] 获取已加入小组列表...")
        
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException, NoSuchElementException
            
            # 1. 访问小组页面
            self.logger("[互动加权] 访问小组页面...")
            self.driver.get("https://www.facebook.com/groups/feed/")
            time.sleep(random.uniform(3, 6))
            
            # 2. 点击"你的小组"或"Your groups"（兼容大小写）
            try:
                # 尝试多种可能的选择器（兼容中英文和大小写）
                selectors = [
                    "//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'your groups')]",
                    "//span[contains(text(), '你的小组')]",
                    "//span[contains(text(), '已加入')]",
                    "//a[contains(@href, '/groups/') and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'your')]"
                ]
                
                clicked = False
                for selector in selectors:
                    try:
                        element = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                        # 滚动到元素
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                        time.sleep(1)
                        element.click()
                        self.logger(f"[互动加权] 点击: {selector}")
                        clicked = True
                        time.sleep(random.uniform(2, 4))
                        break
                    except:
                        continue
                
                if not clicked:
                    self.logger("[互动加权] 未找到小组入口，尝试直接提取")
            except Exception as e:
                self.logger(f"[互动加权] 点击小组入口失败: {e}")
            
            # 3. 滚动加载所有小组
            self.logger("[互动加权] 滚动加载小组...")
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_count = 0
            max_scrolls = 5  # 最多滚动5次
            
            while scroll_count < max_scrolls:
                # 滚动到底部
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
                
                # 计算新的高度
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                
                last_height = new_height
                scroll_count += 1
                self.logger(f"[互动加权] 滚动 {scroll_count}/{max_scrolls}")
            
            # 4. 提取小组信息
            self.logger("[互动加权] 提取小组信息...")
            groups = []
            
            # 改进的选择器：查找真实的小组链接
            # 特征：href包含/groups/且后面有数字ID或名称，不包含特殊关键词
            group_selectors = [
                # 方法1：查找小组卡片中的链接
                "//div[@role='article']//a[contains(@href, '/groups/') and not(contains(@href, '/feed')) and not(contains(@href, '/joins')) and not(contains(@href, '/create'))]",
                # 方法2：查找包含小组名称的链接
                "//a[contains(@href, 'facebook.com/groups/') and not(contains(@href, '/feed')) and not(contains(@href, '/joins'))]",
                # 方法3：查找特定结构的小组链接
                "//a[contains(@href, '/groups/') and @role='link' and not(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'create')) and not(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'your groups'))]"
            ]
            
            group_elements = []
            for selector in group_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        group_elements = elements
                        self.logger(f"[互动加权] 使用选择器: {selector[:80]}...，找到{len(elements)}个元素")
                        break
                except:
                    continue
            
            # 去重并提取信息
            seen_urls = set()
            excluded_keywords = ['feed', 'joins', 'create', 'discover', 'search']
            
            for element in group_elements:
                try:
                    url = element.get_attribute("href")
                    if not url or "/groups/" not in url:
                        continue
                    
                    # 过滤掉特殊页面
                    if any(keyword in url.lower() for keyword in excluded_keywords):
                        continue
                    
                    # 清理URL（去掉参数）
                    if "?" in url:
                        url = url.split("?")[0]
                    if "#" in url:
                        url = url.split("#")[0]
                    
                    # 验证URL格式：必须是 /groups/数字 或 /groups/名称
                    # 排除 /groups/ 这种空的
                    if url.endswith("/groups/") or url.endswith("/groups"):
                        continue
                    
                    # 去重
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    
                    # 提取小组名称
                    try:
                        name = element.text.strip()
                        if not name:
                            name = element.get_attribute("aria-label") or "未知小组"
                        # 过滤掉按钮文本
                        if name.lower() in ['your groups', 'create new group', '你的小组', '创建新小组']:
                            continue
                    except:
                        name = "未知小组"
                    
                    # 添加到列表
                    groups.append({
                        "group_url": url,
                        "group_name": name,
                        "joined_date": "2024-01-01",  # 默认值，实际应从数据库获取
                        "last_interaction_date": ""  # 从数据库获取
                    })
                    
                except Exception as e:
                    continue
            
            self.logger(f"[互动加权] 成功提取{len(groups)}个小组")
            
            # 打印前5个小组
            for i, group in enumerate(groups[:5], 1):
                self.logger(f"[互动加权]   [{i}] {group['group_name']}")
                self.logger(f"[互动加权]       {group['group_url']}")
            
            if len(groups) > 5:
                self.logger(f"[互动加权]   ... 还有{len(groups)-5}个小组")
            
            return groups
            
        except Exception as e:
            self.logger(f"[互动加权] 获取小组列表失败: {e}")
            import traceback
            self.logger(traceback.format_exc())
            return []
    
    def 执行(self, account_id: str, account_age_days: int, groups: List[Dict] = None) -> Dict:
        """
        主执行函数
        
        Args:
            account_id: 账号ID
            account_age_days: 账号年龄（天）
            groups: 已加入的小组列表
        
        Returns:
            执行结果
        """
        self.logger("=" * 60)
        self.logger("[互动加权] 开始执行小组互动加权模块")
        self.logger("=" * 60)
        
        result = {
            "success": True,
            "account_id": account_id,
            "account_age_days": account_age_days,
            "groups_processed": [],
            "total_actions": 0
        }
        
        try:
            # 0. 获取小组列表（如果没有提供）
            if groups is None:
                groups = self.获取已加入小组列表()
                if not groups:
                    result["success"] = False
                    result["reason"] = "无法获取小组列表"
                    return result
            
            # 1. 判断是否执行
            if not self.判断是否执行(account_age_days):
                result["success"] = False
                result["reason"] = "未抽中执行"
                return result
            
            # 2. 选择操作小组
            selected_groups = self.选择操作小组(account_age_days, groups)
            if not selected_groups:
                result["success"] = False
                result["reason"] = "没有符合条件的小组"
                return result
            
            # 3. 对每个小组执行互动
            for group in selected_groups:
                # 生成行为计划
                plan = self.生成小组行为计划(group)
                
                # 执行互动
                group_result = self.执行小组互动(plan)
                result["groups_processed"].append(group_result)
                result["total_actions"] += len(group_result["actions_performed"])
                
                # 小组间隔
                if group != selected_groups[-1]:  # 不是最后一个小组
                    if self.test_mode:
                        wait_time = random.uniform(3, 8)  # 测试模式：3-8秒
                    else:
                        wait_time = random.uniform(5, 15) * 60  # 正常模式：5-15分钟
                    self.logger(f"[互动加权] 等待{wait_time if self.test_mode else wait_time/60:.1f}{'秒' if self.test_mode else '分钟'}后处理下一个小组...")
                    time.sleep(wait_time)
            
            self.logger("=" * 60)
            self.logger(f"[互动加权] 完成！处理{len(result['groups_processed'])}个小组，执行{result['total_actions']}个行为")
            self.logger("=" * 60)
            
        except Exception as e:
            self.logger(f"[互动加权] 执行失败: {e}")
            result["success"] = False
            result["error"] = str(e)
        
        return result


# ==================== 调试配置 ====================

# 从环境变量读取浏览器ID
DEBUG_BROWSER_ID = os.environ.get('DEBUG_BROWSER_ID', "7d9ecff84fef490987dcb58004fa2c82")


# ==================== 调试模式 ====================

def _调试模式():
    """调试模式入口"""
    print("=" * 60)
    print("小组互动加权模块 - 调试模式")
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
    print("开始执行小组互动加权模块...")
    print("-" * 60)
    
    # 创建模块实例（测试模式）
    def logger(msg):
        print(msg)
    
    module = 小组互动加权模块(driver, logger, test_mode=True)
    
    # 执行互动（测试账号：20天）
    result = module.执行(
        account_id='debug_test',
        account_age_days=20  # 测试阶段4
    )
    
    print("-" * 60)
    if result.get("success"):
        print(f"✓ 执行成功")
        print(f"  处理小组数: {len(result.get('groups_processed', []))}")
        print(f"  总行为数: {result.get('total_actions', 0)}")
    else:
        print(f"✗ 执行失败: {result.get('reason', result.get('error', '未知'))}")
    print("=" * 60)
    
    input("\n按回车键关闭浏览器...")
    
    try:
        driver.quit()
        print("✓ 浏览器已关闭")
    except:
        pass


# ==================== 测试代码 ====================

# 测试代码
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        print("用法:")
        print("  python 小组互动加权.py          # 完整测试（需要真实浏览器）")
    else:
        # 完整测试: python 小组互动加权.py
        _调试模式()
