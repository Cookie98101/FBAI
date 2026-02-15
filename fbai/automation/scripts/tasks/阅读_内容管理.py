"""
阅读模块 - 内容管理
包含内容价值分类、内容不足处理等功能
"""

import random
import time
from typing import TYPE_CHECKING, Tuple, Optional

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver


class 内容价值分类器:
    """
    内容价值分类器
    根据帖子内容判断价值等级
    """
    
    # 内容价值等级
    高价值 = "high_value"
    中等价值 = "medium_value"
    普通相关 = "normal_related"
    不相关 = "unrelated"
    
    # 互动概率配置（根据参数表）
    互动概率表 = {
        高价值: {
            '点赞': 0.60,
            '评论': 0.35,
            '私信': 0.20,
            '加好友': 0.15,
            '查看评论': 0.70,
        },
        中等价值: {
            '点赞': 0.45,
            '评论': 0.15,
            '私信': 0.05,
            '加好友': 0.03,
            '查看评论': 0.55,
        },
        普通相关: {
            '点赞': 0.25,
            '评论': 0.03,
            '私信': 0.00,
            '加好友': 0.00,
            '查看评论': 0.35,
        },
        不相关: {
            '点赞': 0.10,
            '评论': 0.00,
            '私信': 0.00,
            '加好友': 0.00,
            '查看评论': 0.10,
        },
    }
    
    def __init__(self):
        """初始化分类器"""
        # 加载关键词（从配置文件或数据库）
        self.高价值关键词 = self._加载高价值关键词()
        self.相关关键词 = self._加载相关关键词()
    
    def _加载高价值关键词(self):
        """加载高价值关键词"""
        # TODO: 从配置文件或数据库加载
        return [
            'supplier', 'manufacturer', 'factory', 'wholesale',
            'MOQ', 'price', 'quote', 'sample', 'OEM', 'ODM',
            'export', 'import', 'trade', 'business', 'B2B',
        ]
    
    def _加载相关关键词(self):
        """加载相关关键词"""
        # TODO: 从配置文件或数据库加载
        return [
            'product', 'quality', 'service', 'delivery',
            'shipping', 'payment', 'order', 'customer',
        ]
    
    def 分类帖子(self, 帖子内容: str) -> str:
        """
        根据帖子内容分类价值等级
        
        Args:
            帖子内容: 帖子文本内容
        
        Returns:
            价值等级（high_value, medium_value, normal_related, unrelated）
        """
        if not 帖子内容:
            return self.不相关
        
        帖子内容_小写 = 帖子内容.lower()
        
        # 检查高价值关键词
        高价值命中 = sum(1 for 关键词 in self.高价值关键词 if 关键词.lower() in 帖子内容_小写)
        if 高价值命中 >= 2:
            return self.高价值
        
        # 检查相关关键词
        相关命中 = sum(1 for 关键词 in self.相关关键词 if 关键词.lower() in 帖子内容_小写)
        if 相关命中 >= 2:
            return self.中等价值
        
        # 如果有任何关键词命中
        if 高价值命中 >= 1 or 相关命中 >= 1:
            return self.普通相关
        
        return self.不相关
    
    def 获取互动概率(self, 价值等级: str, 动作类型: str) -> float:
        """
        获取指定价值等级和动作类型的互动概率
        
        Args:
            价值等级: 价值等级
            动作类型: 动作类型（点赞、评论、私信、加好友、查看评论）
        
        Returns:
            互动概率（0-1）
        """
        if 价值等级 not in self.互动概率表:
            return 0.0
        
        if 动作类型 not in self.互动概率表[价值等级]:
            return 0.0
        
        return self.互动概率表[价值等级][动作类型]
    
    def 应该互动(self, 价值等级: str, 动作类型: str) -> bool:
        """
        根据价值等级和动作类型判断是否应该互动
        
        Args:
            价值等级: 价值等级
            动作类型: 动作类型
        
        Returns:
            是否应该互动
        """
        概率 = self.获取互动概率(价值等级, 动作类型)
        return random.random() < 概率


class 内容管理器:
    """
    内容管理器
    处理内容不足、刷新页面等
    """
    
    def __init__(self, driver: "WebDriver"):
        """
        初始化内容管理器
        
        Args:
            driver: WebDriver实例
        """
        self.driver = driver
        self.刷新次数 = 0
        self.最大刷新次数 = 3
    
    def 检查内容是否充足(self) -> bool:
        """
        检查页面内容是否充足
        
        Returns:
            内容是否充足
        """
        try:
            from selenium.webdriver.common.by import By
            
            # 查找帖子元素
            帖子元素 = self.driver.find_elements(By.CSS_SELECTOR, "[role='article']")
            可见帖子 = [e for e in 帖子元素 if e.is_displayed()]
            
            # 至少需要5个可见帖子
            return len(可见帖子) >= 5
        except:
            return False
    
    def 刷新页面(self, log_func=None) -> bool:
        """
        刷新页面
        
        Args:
            log_func: 日志函数
        
        Returns:
            是否成功刷新
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        try:
            if self.刷新次数 >= self.最大刷新次数:
                log(f"  [内容管理] 已达到最大刷新次数 ({self.最大刷新次数})")
                return False
            
            log(f"  [内容管理] 刷新页面 (第 {self.刷新次数 + 1}/{self.最大刷新次数} 次)...")
            
            # 等待3-5秒
            time.sleep(random.uniform(3, 5))
            
            # 刷新页面
            self.driver.refresh()
            
            # 等待页面加载
            time.sleep(random.uniform(5, 8))
            
            self.刷新次数 += 1
            
            # 检查刷新后内容是否充足
            if self.检查内容是否充足():
                log("  [内容管理] ✓ 刷新成功，内容充足")
                return True
            else:
                log("  [内容管理] ⚠️ 刷新后内容仍不足")
                return False
        except Exception as e:
            log(f"  [内容管理] 刷新失败: {e}")
            return False
    
    def 处理内容不足(self, log_func=None) -> Tuple[bool, str]:
        """
        处理内容不足的情况
        
        Args:
            log_func: 日志函数
        
        Returns:
            (是否成功, 处理方式)
            处理方式: "refreshed"（已刷新）, "switch_to_search"（切换到搜索）, "failed"（失败）
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        log("  [内容管理] 检测到内容不足")
        
        # 尝试刷新页面
        if self.刷新页面(log_func):
            return True, "refreshed"
        
        # 如果刷新失败，建议切换到搜索
        if self.刷新次数 >= self.最大刷新次数:
            log("  [内容管理] 刷新次数已达上限，建议切换到搜索")
            return False, "switch_to_search"
        
        return False, "failed"
    
    def 重置刷新计数(self):
        """重置刷新计数"""
        self.刷新次数 = 0


# 测试代码
if __name__ == "__main__":
    # 测试内容价值分类器
    分类器 = 内容价值分类器()
    
    测试帖子 = [
        "Looking for reliable supplier of electronic components. Need MOQ and price quote.",
        "Great product! The quality is amazing and delivery was fast.",
        "Nice post! I really like it.",
        "今天天气真好",
    ]
    
    print("=" * 60)
    print("内容价值分类测试")
    print("=" * 60)
    
    for 帖子 in 测试帖子:
        价值等级 = 分类器.分类帖子(帖子)
        print(f"\n帖子: {帖子[:50]}...")
        print(f"价值等级: {价值等级}")
        print(f"点赞概率: {分类器.获取互动概率(价值等级, '点赞'):.0%}")
        print(f"评论概率: {分类器.获取互动概率(价值等级, '评论'):.0%}")
        print(f"查看评论概率: {分类器.获取互动概率(价值等级, '查看评论'):.0%}")
