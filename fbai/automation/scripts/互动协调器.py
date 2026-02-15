# -*- coding: utf-8 -*-
"""
互动协调器
负责协调账号对公共主页帖子的互动（点赞、评论）
"""

import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# 尝试导入比特浏览器 API，用于在互动结束后关闭浏览器
try:
    from bitbrowser_api import bit_browser
except ImportError:
    bit_browser = None


class 互动协调器:
    """互动协调器 - 协调账号互动"""
    
    def __init__(self, main_controller, log_func=None):
        """
        初始化互动协调器
        
        Args:
            main_controller: 主控制器实例
            log_func: 日志输出函数
        """
        self.main_controller = main_controller
        self.log = log_func or print
        self.暂停标志 = {}  # {browser_id: threading.Event}
        
        self.log("[互动协调] ✅ 互动协调器已初始化")
    
    def _获取并发数(self) -> int:
        """
        获取并发数（从认证信息中的窗口数量获取）
        
        Returns:
            并发数，默认为1
        """
        try:
            # 从主控制器获取认证客户端
            auth_client = getattr(self.main_controller, 'auth_client', None)
            if auth_client and hasattr(auth_client, 'user_info') and auth_client.user_info:
                max_windows = auth_client.user_info.get('max_windows', 1)
                self.log(f"[互动协调] 📊 从认证信息获取窗口数量: {max_windows}")
                return max(1, max_windows)
        except Exception as e:
            self.log(f"[互动协调] ⚠️ 获取窗口数量失败: {e}")
        
        return 1  # 默认并发数
    
    def 选择互动账号(self, 所有账号, 比例=0.8):
        """
        随机选择账号进行互动
        
        Args:
            所有账号: 所有账号列表
            比例: 选择比例（默认80%）
        
        Returns:
            选中的账号列表
        """
        if not 所有账号:
            return []
        
        数量 = int(len(所有账号) * 比例)
        数量 = max(1, 数量)  # 至少选1个
        
        选中账号 = random.sample(所有账号, 数量)
        return 选中账号
    
    def 暂停账号(self, browser_id):
        """
        暂停账号任务
        
        Args:
            browser_id: 浏览器ID
        """
        if browser_id not in self.暂停标志:
            self.暂停标志[browser_id] = threading.Event()
        
        self.暂停标志[browser_id].clear()  # 清除=暂停
    
    def 恢复账号(self, browser_id):
        """
        恢复账号任务
        
        Args:
            browser_id: 浏览器ID
        """
        if browser_id in self.暂停标志:
            self.暂停标志[browser_id].set()  # 设置=恢复
    
    def 协调账号互动(self, 帖子URL):
        """
        协调账号互动
        
        Args:
            帖子URL: 帖子链接
        """
        try:
            self.log(f"[互动协调] 🎯 开始协调账号互动: {帖子URL}")
            
            # 获取所有账号
            所有账号 = self._获取所有账号()
            if not 所有账号:
                self.log("[互动协调] ⚠️ 没有可用账号")
                return
            
            # 选择互动账号
            互动比例 = self.main_controller.发帖管理器.配置.get("互动账号比例", 0.8)
            互动账号 = self.选择互动账号(所有账号, 互动比例)
            
            self.log(f"[互动协调] 📊 选择 {len(互动账号)}/{len(所有账号)} 个账号进行互动")
            
            # 暂停这些账号的任务
            for 账号 in 互动账号:
                self.暂停账号(账号['browser_id'])
            
            self.log(f"[互动协调] ⏸️ 已暂停 {len(互动账号)} 个账号的任务")
            
            # 分批执行互动
            self._分批执行互动(互动账号, 帖子URL)
            
            # 恢复所有账号的任务
            for 账号 in 互动账号:
                self.恢复账号(账号['browser_id'])
            
            self.log(f"[互动协调] ▶️ 已恢复 {len(互动账号)} 个账号的任务")
            self.log("[互动协调] ✅ 互动协调完成")
        
        except Exception as e:
            self.log(f"[互动协调] ❌ 互动协调失败: {e}")
    
    def _获取所有账号(self):
        """
        获取所有账号
        
        Returns:
            账号列表
        """
        try:
            # 从主控制器获取所有浏览器
            if not self.main_controller:
                self.log("[互动协调] ⚠️ 主控制器为空，无法获取账号列表")
                return []

            if not hasattr(self.main_controller, "get_all_browsers"):
                self.log("[互动协调] ⚠️ 主控制器不支持 get_all_browsers()，无法获取账号列表")
                return []

            browsers = self.main_controller.get_all_browsers() or []

            账号列表 = []
            for b in browsers:
                name = b.get("name") or ""
                # 排除专用的"公共主页"浏览器，只保留普通账号浏览器
                if name == "公共主页":
                    continue

                browser_id = b.get("id") or b.get("browser_id")
                if not browser_id:
                    continue

                账号列表.append({
                    "browser_id": browser_id,
                    "name": name or browser_id
                })

            self.log(f"[互动协调] 📋 获取到 {len(账号列表)} 个可用于互动的账号")
            return 账号列表

        except Exception as e:
            self.log(f"[互动协调] ❌ 获取账号失败: {e}")
            return []
    
    def _分批执行互动(self, 账号列表, 帖子URL):
        """
        分批执行互动
        
        Args:
            账号列表: 账号列表
            帖子URL: 帖子链接
        """
        配置 = self.main_controller.发帖管理器.配置
        # 从认证信息获取并发数（窗口数量）
        批次大小 = self._获取并发数()
        批次间隔 = 配置.get("批次间隔秒", [30, 60])
        
        self.log(f"[互动协调] 📊 并发数: {批次大小}（来自认证窗口数量）")
        
        成功数 = 0
        失败数 = 0
        
        # 分批处理
        总批次 = (len(账号列表) + 批次大小 - 1) // 批次大小
        
        for i in range(0, len(账号列表), 批次大小):
            批次账号 = 账号列表[i:i+批次大小]
            当前批次 = i // 批次大小 + 1
            
            self.log(f"[互动协调] 📦 执行第 {当前批次}/{总批次} 批（{len(批次账号)}个账号）")
            
            # 并发执行当前批次
            with ThreadPoolExecutor(max_workers=len(批次账号)) as executor:
                futures = {
                    executor.submit(self._账号互动, 账号, 帖子URL): 账号
                    for 账号 in 批次账号
                }
                
                for future in as_completed(futures):
                    账号 = futures[future]
                    try:
                        结果 = future.result()
                        if 结果:
                            成功数 += 1
                            self.log(f"[互动协调] ✅ [{账号.get('name', '未知')}] 互动完成")
                        else:
                            失败数 += 1
                            self.log(f"[互动协调] ❌ [{账号.get('name', '未知')}] 互动失败")
                        
                        # 互动完成后，检查是否需要关闭浏览器
                        self._检查并关闭浏览器(账号.get('browser_id'))
                    
                    except Exception as e:
                        失败数 += 1
                        self.log(f"[互动协调] ❌ [{账号.get('name', '未知')}] 互动异常: {e}")
                        # 异常也要检查并关闭浏览器
                        self._检查并关闭浏览器(账号.get('browser_id'))
            
            # 批次间延迟（最后一批不延迟）
            if 当前批次 < 总批次:
                延迟秒数 = random.randint(批次间隔[0], 批次间隔[1])
                self.log(f"[互动协调] ⏳ 批次间隔 {延迟秒数} 秒...")
                time.sleep(延迟秒数)
        
        self.log(f"[互动协调] 📊 互动统计: 成功 {成功数}, 失败 {失败数}")
    
    def _检查并关闭浏览器(self, browser_id: str):
        """
        检查浏览器是否嵌入到 UI 中。
        - 如果嵌入到 UI 中：浏览器继续执行主账号任务，不关闭
        - 如果没有嵌入到 UI 中：浏览器没有其他任务，关闭浏览器
        
        Args:
            browser_id: 浏览器ID
        """
        try:
            if not browser_id:
                return
            
            # 获取主控制器的 client
            client = getattr(self.main_controller, 'client', None)
            
            # 检查浏览器是否嵌入到 UI 中
            # 通过 client 获取当前嵌入的浏览器列表
            浏览器嵌入UI = False
            
            if client is not None:
                try:
                    # 获取当前嵌入到 UI 中的浏览器列表
                    embedded_browsers = client.get_embedded_browsers() if hasattr(client, 'get_embedded_browsers') else []
                    
                    # 检查当前浏览器是否在嵌入列表中
                    for b in embedded_browsers:
                        b_id = b.get("id") or b.get("browser_id")
                        if b_id == browser_id:
                            浏览器嵌入UI = True
                            break
                except Exception as e:
                    self.log(f"[互动协调] ⚠️ 获取嵌入浏览器列表失败: {e}")
                    # 如果无法获取嵌入列表，默认不关闭（安全起见）
                    浏览器嵌入UI = True
            else:
                # 如果没有 client，尝试通过 BitBrowser API 检查浏览器状态
                if bit_browser is not None:
                    try:
                        # 获取浏览器详情，检查是否正在运行
                        browser_info = bit_browser.get_browser_detail(browser_id)
                        if browser_info.get("success"):
                            # 如果浏览器正在运行，检查是否有其他任务
                            # 这里简单判断：如果浏览器在运行，就不关闭
                            浏览器嵌入UI = True
                    except:
                        pass
            
            if 浏览器嵌入UI:
                # 浏览器嵌入到 UI 中，说明有主账号任务在执行，不关闭
                self.log(f"[互动协调] ✓ 浏览器嵌入UI中，继续执行主任务: {browser_id[:8]}...")
            else:
                # 浏览器不在 UI 中，说明没有其他任务，关闭浏览器
                self.log(f"[互动协调] 🧹 浏览器未嵌入UI，准备关闭: {browser_id[:8]}...")
                
                关闭成功 = False
                
                # 方法1：通过 client 关闭
                if client is not None:
                    try:
                        client.remove_browser(browser_id, close=True)
                        self.log(f"[互动协调] ✅ 已通过client关闭浏览器: {browser_id[:8]}...")
                        关闭成功 = True
                    except Exception as e:
                        self.log(f"[互动协调] ⚠️ client关闭失败: {e}")
                
                # 方法2：直接调用 BitBrowser API 关闭
                if not 关闭成功 and bit_browser is not None:
                    try:
                        bit_browser.close_browser(browser_id)
                        self.log(f"[互动协调] ✅ 已通过BitBrowser API关闭浏览器: {browser_id[:8]}...")
                        关闭成功 = True
                    except Exception as e2:
                        self.log(f"[互动协调] ⚠️ BitBrowser API关闭失败: {e2}")
                
                if not 关闭成功:
                    self.log(f"[互动协调] ⚠️ 无法关闭浏览器: {browser_id[:8]}...")
        
        except Exception as e:
            self.log(f"[互动协调] ⚠️ 检查浏览器逻辑异常: {e}")
    
    def _账号互动(self, 账号, 帖子URL):
        """
        单个账号互动
        
        Args:
            账号: 账号信息
            帖子URL: 帖子链接
        
        Returns:
            是否成功
        """
        try:
            配置 = self.main_controller.发帖管理器.配置
            互动延迟 = 配置.get("互动延迟秒", [5, 30])
            
            # 随机延迟
            延迟秒数 = random.randint(互动延迟[0], 互动延迟[1])
            time.sleep(延迟秒数)
            
            # 调用帖子互动脚本
            from tasks.帖子互动 import 执行帖子互动
            
            结果 = 执行帖子互动(
                账号=账号,
                帖子URL=帖子URL,
                点赞概率=配置.get("点赞概率", 0.8),
                评论概率=1.0,
                log_func=self.log
            )
            
            return 结果
        
        except Exception as e:
            self.log(f"[互动协调] ❌ 账号互动异常: {e}")
            return False
