"""
阅读模块 - 异常检测机制
检测并处理各种异常情况，提升风控友好性
"""

import time
from typing import TYPE_CHECKING, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

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
        print(f"[异常检测] 警告: 数据库初始化失败: {e2}")


@dataclass
class 异常记录:
    """异常记录数据类"""
    异常类型: str  # 'load_fail', 'captcha', 'restricted', 'timeout'
    发生时间: datetime
    浏览器ID: str
    详细信息: str
    建议暂停时长: int  # 分钟


class 异常检测器:
    """异常检测器类"""
    
    def __init__(self, driver: "WebDriver", 浏览器ID: str = None):
        self.driver = driver
        self.浏览器ID = 浏览器ID
        
        # 异常计数器
        self.连续加载失败次数 = 0
        self.验证码出现次数 = 0
        self.账号限制次数 = 0
        self.超时次数 = 0
        
        # 异常阈值（根据参数表）
        self.连续加载失败阈值 = 3  # 3次
        self.验证码阈值 = 1  # 1次
        self.账号限制阈值 = 1  # 1次
        self.超时阈值 = 30  # 30秒
        
        # 暂停时长（分钟）
        self.加载失败暂停时长 = 30  # 30分钟
        self.验证码暂停时长 = 120  # 2小时
        self.账号限制暂停时长 = 1440  # 24小时
        
        # 异常历史
        self.异常历史: list[异常记录] = []
    
    def 检测页面加载失败(self) -> bool:
        """
        检测页面是否加载失败
        
        Returns:
            是否加载失败
        """
        try:
            # 检查常见的错误页面元素
            错误关键词 = [
                "error",
                "not found",
                "404",
                "500",
                "something went wrong",
                "try again",
                "reload",
            ]
            
            页面文本 = self.driver.find_element("tag name", "body").text.lower()
            
            for 关键词 in 错误关键词:
                if 关键词 in 页面文本:
                    return True
            
            # 检查是否有内容
            if len(页面文本.strip()) < 100:
                return True
            
            return False
            
        except Exception:
            return True
    
    def 检测验证码(self) -> bool:
        """
        检测是否出现验证码
        
        Returns:
            是否出现验证码
        """
        try:
            # 检查验证码相关元素
            验证码选择器 = [
                "[aria-label*='captcha' i]",
                "[aria-label*='verification' i]",
                "[aria-label*='security check' i]",
                "iframe[src*='captcha']",
                "iframe[src*='recaptcha']",
            ]
            
            for 选择器 in 验证码选择器:
                elements = self.driver.find_elements("css selector", 选择器)
                if elements:
                    return True
            
            # 检查页面文本
            页面文本 = self.driver.find_element("tag name", "body").text.lower()
            验证码关键词 = ["captcha", "verification", "security check", "prove you're human"]
            
            for 关键词 in 验证码关键词:
                if 关键词 in 页面文本:
                    return True
            
            return False
            
        except Exception:
            return False
    
    def 检测账号限制(self) -> bool:
        """
        检测账号是否被限制
        
        Returns:
            是否被限制
        """
        try:
            # 检查限制相关文本
            页面文本 = self.driver.find_element("tag name", "body").text.lower()
            
            限制关键词 = [
                "restricted",
                "suspended",
                "blocked",
                "disabled",
                "temporarily unavailable",
                "violat",  # violation, violated
                "against our",  # against our community standards
                "review",  # under review
            ]
            
            for 关键词 in 限制关键词:
                if 关键词 in 页面文本:
                    return True
            
            return False
            
        except Exception:
            return False
    
    def 检测页面超时(self, 开始时间: float, 超时秒数: int = 30) -> bool:
        """
        检测页面加载是否超时
        
        Args:
            开始时间: 开始加载的时间戳
            超时秒数: 超时阈值（秒）
        
        Returns:
            是否超时
        """
        已用时间 = time.time() - 开始时间
        return 已用时间 > 超时秒数
    
    def 记录加载失败(self, 详细信息: str = ""):
        """记录页面加载失败"""
        self.连续加载失败次数 += 1
        
        异常 = 异常记录(
            异常类型="load_fail",
            发生时间=datetime.now(),
            浏览器ID=self.浏览器ID or "unknown",
            详细信息=详细信息,
            建议暂停时长=self.加载失败暂停时长
        )
        self.异常历史.append(异常)
        
        # 记录到数据库
        if _db and self.浏览器ID:
            try:
                _db.record_exception(
                    browser_id=self.浏览器ID,
                    exception_type="load_fail",
                    details=详细信息,
                    pause_minutes=self.加载失败暂停时长
                )
            except Exception as e:
                print(f"[异常检测] 警告: 记录异常到数据库失败: {e}")
    
    def 记录验证码(self, 详细信息: str = ""):
        """记录验证码出现"""
        self.验证码出现次数 += 1
        
        异常 = 异常记录(
            异常类型="captcha",
            发生时间=datetime.now(),
            浏览器ID=self.浏览器ID or "unknown",
            详细信息=详细信息,
            建议暂停时长=self.验证码暂停时长
        )
        self.异常历史.append(异常)
        
        # 记录到数据库
        if _db and self.浏览器ID:
            try:
                _db.record_exception(
                    browser_id=self.浏览器ID,
                    exception_type="captcha",
                    details=详细信息,
                    pause_minutes=self.验证码暂停时长
                )
            except Exception as e:
                print(f"[异常检测] 警告: 记录异常到数据库失败: {e}")
    
    def 记录账号限制(self, 详细信息: str = ""):
        """记录账号被限制"""
        self.账号限制次数 += 1
        
        异常 = 异常记录(
            异常类型="restricted",
            发生时间=datetime.now(),
            浏览器ID=self.浏览器ID or "unknown",
            详细信息=详细信息,
            建议暂停时长=self.账号限制暂停时长
        )
        self.异常历史.append(异常)
        
        # 记录到数据库
        if _db and self.浏览器ID:
            try:
                _db.record_exception(
                    browser_id=self.浏览器ID,
                    exception_type="restricted",
                    details=详细信息,
                    pause_minutes=self.账号限制暂停时长
                )
            except Exception as e:
                print(f"[异常检测] 警告: 记录异常到数据库失败: {e}")
    
    def 记录超时(self, 详细信息: str = ""):
        """记录页面超时"""
        self.超时次数 += 1
        
        异常 = 异常记录(
            异常类型="timeout",
            发生时间=datetime.now(),
            浏览器ID=self.浏览器ID or "unknown",
            详细信息=详细信息,
            建议暂停时长=0  # 超时不暂停，只记录
        )
        self.异常历史.append(异常)
        
        # 记录到数据库
        if _db and self.浏览器ID:
            try:
                _db.record_exception(
                    browser_id=self.浏览器ID,
                    exception_type="timeout",
                    details=详细信息,
                    pause_minutes=0
                )
            except Exception as e:
                print(f"[异常检测] 警告: 记录异常到数据库失败: {e}")
    
    def 重置加载失败计数(self):
        """重置连续加载失败计数（加载成功后调用）"""
        self.连续加载失败次数 = 0
    
    def 是否需要暂停(self) -> tuple[bool, str, int]:
        """
        检查是否需要暂停任务
        
        Returns:
            (是否需要暂停, 原因, 暂停时长分钟)
        """
        # 检查连续加载失败
        if self.连续加载失败次数 >= self.连续加载失败阈值:
            return (True, f"连续加载失败{self.连续加载失败次数}次", self.加载失败暂停时长)
        
        # 检查验证码
        if self.验证码出现次数 >= self.验证码阈值:
            return (True, "出现验证码", self.验证码暂停时长)
        
        # 检查账号限制
        if self.账号限制次数 >= self.账号限制阈值:
            return (True, "账号被限制", self.账号限制暂停时长)
        
        return (False, "", 0)
    
    def 执行全面检测(self, log_func=None) -> tuple[bool, str]:
        """
        执行全面的异常检测
        
        Args:
            log_func: 日志函数
        
        Returns:
            (是否发现异常, 异常描述)
        """
        def log(msg):
            if log_func:
                log_func(msg)
        
        # 1. 检测页面加载失败
        if self.检测页面加载失败():
            self.记录加载失败("页面加载失败或内容异常")
            log("[异常检测] 警告: 页面加载失败")
            
            需要暂停, 原因, 时长 = self.是否需要暂停()
            if 需要暂停:
                return (True, f"页面加载失败 - {原因}，建议暂停{时长}分钟")
        
        # 2. 检测验证码
        if self.检测验证码():
            self.记录验证码("检测到验证码")
            log("[异常检测] 警告: 检测到验证码")
            return (True, f"出现验证码，建议暂停{self.验证码暂停时长}分钟")
        
        # 3. 检测账号限制
        if self.检测账号限制():
            self.记录账号限制("账号被限制")
            log("[异常检测] 警告: 账号被限制")
            return (True, f"账号被限制，建议暂停{self.账号限制暂停时长}分钟")
        
        return (False, "")
    
    def 获取异常统计(self) -> Dict[str, Any]:
        """
        获取异常统计信息
        
        Returns:
            异常统计字典
        """
        return {
            "连续加载失败次数": self.连续加载失败次数,
            "验证码出现次数": self.验证码出现次数,
            "账号限制次数": self.账号限制次数,
            "超时次数": self.超时次数,
            "异常历史数量": len(self.异常历史),
        }


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("异常检测模块 - 测试")
    print("=" * 60)
    
    # 模拟测试
    class MockDriver:
        def find_element(self, by, value):
            class MockElement:
                text = "This is a test page with normal content."
            return MockElement()
        
        def find_elements(self, by, value):
            return []
    
    driver = MockDriver()
    检测器 = 异常检测器(driver, "test_browser_id")
    
    print("\n[测试1] 检测正常页面...")
    if not 检测器.检测页面加载失败():
        print("  成功: 正常页面检测通过")
    else:
        print("  失败: 误判为加载失败")
    
    print("\n[测试2] 检测验证码...")
    if not 检测器.检测验证码():
        print("  成功: 无验证码")
    else:
        print("  失败: 误判有验证码")
    
    print("\n[测试3] 检测账号限制...")
    if not 检测器.检测账号限制():
        print("  成功: 账号正常")
    else:
        print("  失败: 误判账号被限制")
    
    print("\n[测试4] 模拟连续加载失败...")
    for i in range(3):
        检测器.记录加载失败(f"测试失败{i+1}")
    
    需要暂停, 原因, 时长 = 检测器.是否需要暂停()
    if 需要暂停:
        print(f"  成功: 检测到需要暂停 - {原因}，时长{时长}分钟")
    else:
        print("  失败: 未检测到需要暂停")
    
    print("\n[测试5] 获取异常统计...")
    统计 = 检测器.获取异常统计()
    print(f"  连续加载失败: {统计['连续加载失败次数']}次")
    print(f"  验证码出现: {统计['验证码出现次数']}次")
    print(f"  账号限制: {统计['账号限制次数']}次")
    print(f"  超时: {统计['超时次数']}次")
    print(f"  异常历史: {统计['异常历史数量']}条")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
