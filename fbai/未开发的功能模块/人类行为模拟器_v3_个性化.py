"""
人类行为模拟器 v3.0 - 集成个性画像系统

功能:
1. 集成账号个性画像系统
2. 根据个性调整所有行为参数
3. 保持原有的情绪和习惯模拟
4. 完美兼容现有代码

版本: 3.0 (个性化版)
作者: AI Assistant
日期: 2025-12-30
"""

import random
import time
import datetime
import logging
from typing import Dict, Optional
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# 导入原有的模拟器
from modules.人类行为模拟器 import HumanBehaviorSimulator as 原版模拟器

# 导入个性画像系统
from core.账号个性画像系统 import 账号个性画像, 个性画像管理器, 个性化行为适配器

logger = logging.getLogger(__name__)


class 人类行为模拟器_个性化版(原版模拟器):
    """
    人类行为模拟器 v3.0 - 集成个性画像
    
    新增功能:
    1. 自动加载账号个性画像
    2. 根据个性调整所有行为参数
    3. 个性化的延迟、打字、鼠标、阅读行为
    4. 保持与原版100%兼容
    """
    
    def __init__(self, driver, config: Dict, 账号ID: str = None):
        """
        初始化个性化行为模拟器
        
        参数:
            driver: Selenium WebDriver 实例
            config: 配置字典
            账号ID: 账号唯一标识（用于加载个性画像）
        """
        # 1. 调用父类初始化
        super().__init__(driver, config)
        
        # 2. 加载或创建个性画像
        self.账号ID = 账号ID or config.get("Facebook账号", "default")
        self.个性画像管理器 = 个性画像管理器("profiles")
        self.个性画像 = self.个性画像管理器.获取或创建画像(self.账号ID)
        
        # 3. 创建个性化适配器
        self.个性适配器 = 个性化行为适配器(self.个性画像)
        
        # 4. 应用个性化参数
        self._应用个性化参数()
        
        # 5. 输出个性信息
        logger.info(f"✨ 账号个性: {', '.join(self.个性画像.个性标签)}")
        logger.info(f"   社交风格: {self.个性画像.兴趣偏好['社交风格']}")
        logger.info(f"   风险等级: {self.个性画像.风险偏好['风险等级']}")
    
    def _应用个性化参数(self):
        """将个性画像应用到行为参数"""
        
        # 1. 应用到习惯模拟器
        if hasattr(self, 'habit_sim'):
            打字参数 = self.个性适配器.获取打字参数()
            self.habit_sim.fast_typer = (打字参数["速度系数"] < 0.9)
            self.habit_sim.frequent_pauser = (打字参数["停顿概率"] > 0.2)
            self.habit_sim.double_check = 打字参数["二次确认"]
            
            鼠标参数 = self.个性适配器.获取鼠标参数()
            self.habit_sim.scroll_before_click = 鼠标参数["点击前滚动"]
            
            阅读参数 = self.个性适配器.获取阅读参数()
            self.habit_sim.careful_reader = (阅读参数["速度系数"] > 1.1)
        
        # 2. 保存个性化参数供后续使用
        self.个性化打字参数 = self.个性适配器.获取打字参数()
        self.个性化鼠标参数 = self.个性适配器.获取鼠标参数()
        self.个性化阅读参数 = self.个性适配器.获取阅读参数()
        
        logger.debug(f"个性化参数已应用:")
        logger.debug(f"  打字速度系数: {self.个性化打字参数['速度系数']:.2f}")
        logger.debug(f"  鼠标速度系数: {self.个性化鼠标参数['速度系数']:.2f}")
        logger.debug(f"  阅读速度系数: {self.个性化阅读参数['速度系数']:.2f}")
    
    # ==================== 重写核心方法，应用个性化 ====================
    
    def smart_delay(self, delay_type: str, base_range: Optional[tuple] = None):
        """
        智能延迟 - 个性化版本
        
        在原有延迟基础上，应用个性化调整
        """
        # 1. 获取基础延迟
        if base_range:
            min_delay, max_delay = base_range
        elif delay_type in self.delays:
            min_delay, max_delay = self.delays[delay_type]
        else:
            min_delay, max_delay = 1, 3
        
        base_delay = random.uniform(min_delay, max_delay)
        
        # 2. 应用原有的调整因子（时间、疲劳、数量、情绪）
        adjusted_delay = base_delay
        adjusted_delay *= self._get_time_multiplier()
        adjusted_delay *= self.fatigue_factor
        adjusted_delay *= self._get_count_multiplier()
        
        if hasattr(self, 'emotion_sim'):
            adjusted_delay *= self.emotion_sim.get_speed_multiplier()
        
        # 3. 应用个性化调整（新增）
        个性化延迟 = self.个性适配器.调整延迟时间(adjusted_delay)
        
        # 4. 记录日志
        logger.info(f"[延迟] {delay_type}: {个性化延迟:.2f}秒 "
                   f"(基础:{base_delay:.2f}, 调整后:{adjusted_delay:.2f}, "
                   f"个性化:{个性化延迟:.2f})")
        
        # 5. 执行延迟
        time.sleep(个性化延迟)
        
        # 6. 更新统计
        self._update_stats(个性化延迟)
        self._update_fatigue()
        
        if hasattr(self, 'emotion_sim'):
            self.emotion_sim.update_emotion()
    
    def human_like_typing(self, element, text: str):
        """
        个性化打字
        
        根据账号个性调整打字速度和错误率
        """
        element.click()
        time.sleep(random.uniform(0.2, 0.5))
        element.clear()
        time.sleep(random.uniform(0.1, 0.3))
        
        # 获取个性化参数
        速度系数 = self.个性化打字参数["速度系数"]
        错误率 = self.个性化打字参数["错误率"]
        停顿概率 = self.个性化打字参数["停顿概率"]
        二次确认 = self.个性化打字参数["二次确认"]
        
        # 情绪系数
        emotion_factor = 1.0
        
        for i, char in enumerate(text):
            # 1. 基础打字速度（个性化）
            base_speed = 0.12 * 速度系数
            
            # 2. 字符类型调整
            if char.isupper():
                base_speed *= 1.5
            elif char.isdigit():
                base_speed *= 1.3
            elif char in '!@#$%^&*()':
                base_speed *= 1.8
            
            # 3. 字母组合速度
            if i > 0:
                combo = text[i-1:i+1].lower()
                fast_combos = ['th', 'he', 'in', 'er', 'an', 'ed', 'nd', 'to', 'es', 'en']
                if combo in fast_combos:
                    base_speed *= 0.7
            
            # 4. 情绪影响
            emotion_factor += 0.01
            base_speed *= emotion_factor
            
            # 5. 思考停顿（个性化）
            if random.random() < 停顿概率:
                time.sleep(random.uniform(0.5, 2.0))
            
            # 6. 输入字符
            element.send_keys(char)
            time.sleep(base_speed)
            
            # 7. 打错字并修正（个性化错误率）
            if random.random() < 错误率 and i < len(text) - 1:
                wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
                element.send_keys(wrong_char)
                time.sleep(random.uniform(0.1, 0.3))
                time.sleep(random.uniform(0.2, 0.5))
                element.send_keys(Keys.BACKSPACE)
                time.sleep(random.uniform(0.1, 0.2))
        
        # 8. 输入完成后检查（个性化）
        if 二次确认:
            time.sleep(random.uniform(0.5, 1.5))
        else:
            time.sleep(random.uniform(0.3, 0.8))
        
        logger.debug(f"完成个性化输入: {len(text)} 个字符 (速度系数:{速度系数:.2f})")
    
    def human_like_click(self, element, double_click: bool = False):
        """
        个性化点击
        
        根据账号个性调整点击行为
        """
        try:
            # 1. 个性化：点击前滚动
            if self.个性化鼠标参数["点击前滚动"]:
                self.driver.execute_script("window.scrollBy(0, 50);")
                time.sleep(random.uniform(0.3, 0.8))
            
            # 2. 个性化：操作前犹豫
            if self.个性化鼠标参数["操作前犹豫"]:
                time.sleep(random.uniform(0.5, 1.5))
            
            # 3. 移动鼠标到元素（使用个性化速度）
            self.human_like_mouse_move(element)
            
            # 4. 短暂停顿
            time.sleep(random.uniform(0.1, 0.3))
            
            # 5. 点击
            if double_click:
                ActionChains(self.driver).double_click(element).perform()
            else:
                element.click()
            
            # 6. 点击后停顿
            time.sleep(random.uniform(0.2, 0.5))
            
            logger.debug(f"完成个性化点击")
        
        except Exception as e:
            logger.warning(f"点击失败: {e}")
            try:
                element.click()
            except:
                pass
    
    def simulate_reading(self, duration: Optional[float] = None):
        """
        个性化阅读行为
        
        根据账号个性调整阅读时长和行为
        """
        if duration is None:
            # 根据个性决定阅读时长
            基础时长 = 5.0
            duration = 基础时长 * self.个性化阅读参数["速度系数"]
        
        注意力 = self.个性化阅读参数["注意力集中度"]
        喜欢回看 = self.个性化阅读参数["喜欢回看"]
        
        logger.debug(f"模拟个性化阅读 {duration:.2f} 秒 (注意力:{注意力}/100)")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            # 根据注意力集中度决定行为
            if 注意力 > 70:
                action = random.choice(['pause', 'small_scroll'])
            elif 注意力 > 40:
                action = random.choice(['scroll', 'pause', 'mouse_move'])
            else:
                action = random.choice(['scroll', 'mouse_move', 'attention'])
            
            if action == 'scroll':
                scroll_amount = random.randint(50, 150)
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            elif action == 'small_scroll':
                scroll_amount = random.randint(20, 50)
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            elif action == 'mouse_move':
                self.random_mouse_movement()
            elif action == 'attention':
                self.simulate_attention()
            
            time.sleep(random.uniform(0.5, 1.5))
        
        # 根据个性决定是否回看
        if 喜欢回看 and random.random() < 0.3:
            self.driver.execute_script("window.scrollBy(0, -100);")
            time.sleep(random.uniform(1, 2))
    
    # ==================== 新增：个性化互动决策方法 ====================
    
    def 获取个性化互动概率(self, 互动类型: str, 基础概率: float) -> float:
        """
        获取个性化的互动概率
        
        参数:
            互动类型: "点赞" / "评论" / "加好友" / "私信"
            基础概率: 基础概率（0-1）
        
        返回:
            个性化后的概率
        """
        return self.个性适配器.调整互动概率(互动类型, 基础概率)
    
    def 是否当前活跃时段(self) -> bool:
        """
        判断当前是否在账号的活跃时段
        
        返回:
            是否活跃
        """
        return self.个性画像.当前是否活跃()
    
    def 获取个性信息(self) -> Dict:
        """
        获取账号的个性信息
        
        返回:
            个性信息字典
        """
        return {
            "账号ID": self.账号ID,
            "个性标签": self.个性画像.个性标签,
            "社交风格": self.个性画像.兴趣偏好["社交风格"],
            "风险等级": self.个性画像.风险偏好["风险等级"],
            "打字速度": self.个性画像.操作习惯["打字速度"],
            "鼠标速度": self.个性画像.操作习惯["鼠标速度"],
            "阅读速度": self.个性画像.操作习惯["阅读速度"],
            "活跃时段": self.个性画像.行为模式["活跃时段"]
        }
    
    def 打印个性信息(self):
        """打印账号的个性信息"""
        self.个性画像.打印画像()
    
    # ==================== 重写统计方法，包含个性信息 ====================
    
    def get_stats(self) -> Dict:
        """
        获取统计信息（包含个性信息）
        """
        # 获取原有统计
        stats = super().get_stats()
        
        # 添加个性信息
        stats['个性标签'] = self.个性画像.个性标签
        stats['社交风格'] = self.个性画像.兴趣偏好['社交风格']
        stats['风险等级'] = self.个性画像.风险偏好['风险等级']
        
        return stats
    
    def print_stats(self):
        """打印统计信息（包含个性信息）"""
        stats = self.get_stats()
        
        print("\n" + "="*50)
        print("人类行为模拟器 - 统计报告 (v3.0 个性化版)")
        print("="*50)
        print(f"账号ID: {self.账号ID}")
        print(f"个性标签: {', '.join(stats['个性标签'])}")
        print(f"社交风格: {stats['社交风格']}")
        print(f"风险等级: {stats['风险等级']}")
        print("-"*50)
        print(f"运行时长: {stats['elapsed_time_formatted']}")
        print(f"执行动作: {stats['actions_count']} 次")
        print(f"已加入小组: {stats['groups_added']} 个")
        print(f"总延迟时间: {stats['total_delay_time']:.2f} 秒")
        print(f"平均延迟: {stats['avg_delay']:.2f} 秒")
        print(f"疲劳系数: {stats['fatigue_factor']:.2f}")
        print(f"当前情绪: {stats.get('current_emotion', 'N/A')}")
        print(f"加入速度: {stats['groups_per_hour']:.2f} 个/小时")
        print("="*50 + "\n")


# ==================== 便捷函数 ====================

def 创建个性化行为模拟器(driver, config: Dict, 账号ID: str = None):
    """
    便捷函数：创建个性化行为模拟器
    
    参数:
        driver: WebDriver实例
        config: 配置字典
        账号ID: 账号唯一标识
    
    返回:
        个性化行为模拟器实例
    """
    return 人类行为模拟器_个性化版(driver, config, 账号ID)


# ==================== 测试代码 ====================

if __name__ == "__main__":
    print("="*60)
    print("人类行为模拟器 v3.0 (个性化版) 测试")
    print("="*60)
    
    # 模拟配置
    config = {
        'anti_detection': {
            'strategy': 'smart',
            'delays': {
                'page_load': [3, 5],
                'scroll': [2, 4],
                'click': [1, 2],
                'after_join_success': [60, 120]
            }
        },
        'Facebook账号': 'test_account_001'
    }
    
    print("\n✅ 人类行为模拟器 v3.0 (个性化版) 加载成功！")
    print("\n新增功能:")
    print("  ✅ 自动加载账号个性画像")
    print("  ✅ 个性化延迟时间")
    print("  ✅ 个性化打字速度")
    print("  ✅ 个性化鼠标行为")
    print("  ✅ 个性化阅读行为")
    print("  ✅ 个性化互动概率")
    print("  ✅ 完美兼容原版模拟器")
    
    print("\n使用方法:")
    print("  from modules.人类行为模拟器_v3_个性化 import 创建个性化行为模拟器")
    print("  simulator = 创建个性化行为模拟器(driver, config, '账号ID')")
    print("  simulator.smart_delay('after_join_success')  # 个性化延迟")
    print("  simulator.打印个性信息()  # 查看账号个性")
    print("="*60)
