# -*- coding: utf-8 -*-
"""
自动发帖管理器
负责定时发帖任务的调度和执行
"""

import os
import json
import random
import time
import threading
from datetime import datetime, time as dt_time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone


class 自动发帖管理器:
    """自动发帖管理器 - 负责定时发帖"""
    
    def __init__(self, log_func=None, main_controller=None, main_window=None):
        """
        初始化自动发帖管理器
        
        Args:
            log_func: 日志输出函数
            main_controller: 主控制器实例（用于获取浏览器列表）
            main_window: 主窗口实例（用于调用主页发帖功能）
        """
        self.log = log_func or print
        self.main_controller = main_controller  # 保存主控制器引用
        self.main_window = main_window  # 保存主窗口引用
        
        # 加载配置（需要先加载配置才能获取时区）
        self.配置文件路径 = os.path.join(
            os.path.dirname(__file__),
            "脚本配置",
            "自动发帖配置.json"
        )
        self.配置 = self._加载配置()
        
        # 从配置文件读取时区，默认为 Asia/Shanghai
        配置时区 = self.配置.get("时区", "Asia/Shanghai")
        
        # 创建调度器，使用配置的时区
        try:
            self.tz = timezone(配置时区)
            self.scheduler = BackgroundScheduler(timezone=self.tz)
            self.log(f"[自动发帖] ✓ 使用时区: {配置时区}")
        except Exception as e:
            self.log(f"[自动发帖] ⚠️ 无法设置时区 {配置时区}，使用 UTC: {e}")
            # 如果失败，使用 UTC
            self.tz = 'UTC'
            self.scheduler = BackgroundScheduler(timezone=self.tz)
        
        self.互动协调器 = None
        
        # 今日发帖记录
        self.今日已发帖 = {
            "早上": False,
            "中午": False,
            "晚上": False,
            "日期": datetime.now().strftime("%Y-%m-%d")
        }
        
        # 今日发帖时间
        self.今日发帖时间 = {
            "早上": None,
            "中午": None,
            "晚上": None
        }
        
        self.log("[自动发帖] ✅ 自动发帖管理器已初始化")

        # 基于文件的发帖结果监控：结果文件路径
        self._result_file_path = self._获取发帖结果文件路径()
    
    def _加载配置(self):
        """加载配置文件"""
        默认配置 = {
            "启用自动发帖": True,
            "每天发帖次数": 3,
            "早上时间段": [8, 10],
            "中午时间段": [12, 14],
            "晚上时间段": [18, 21],
            "互动账号比例": 0.8,
            "互动延迟秒": [5, 30],
            "点赞概率": 0.8,
            "评论概率": 0.3,
            "批次大小": 5,
            "批次间隔秒": [30, 60],
            "AI提示词": "分享今天的好心情",
            "联系方式": "",
            "媒体文件夹": ""
        }
        
        try:
            if os.path.exists(self.配置文件路径):
                with open(self.配置文件路径, 'r', encoding='utf-8') as f:
                    配置 = json.load(f)
                    # 合并默认配置
                    for key, value in 默认配置.items():
                        if key not in 配置:
                            配置[key] = value
                    return 配置
        except Exception as e:
            self.log(f"[自动发帖] ⚠️ 加载配置失败: {e}，使用默认配置")
        
        return 默认配置

    def _获取发帖结果文件路径(self) -> str:
        """获取自动发帖结果共享文件路径（项目根目录下 auto_post_result.txt）。"""
        try:
            # 本文件位于 automation/scripts 目录，项目根目录是上级目录
            scripts_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(scripts_dir)
            return os.path.join(project_root, "auto_post_result.txt")
        except Exception:
            # 兜底：当前工作目录
            return os.path.join(os.getcwd(), "auto_post_result.txt")

    def _重置发帖结果文件(self):
        """将本次发帖结果文件重置为 PENDING。"""
        try:
            with open(self._result_file_path, "w", encoding="utf-8") as f:
                f.write("PENDING")
            self.log(f"[自动发帖] 🔁 已重置发帖结果文件为 PENDING: {self._result_file_path}")
        except Exception as e:
            self.log(f"[自动发帖] ⚠️ 无法重置发帖结果文件: {e}")

    def _轮询发帖结果文件(self, 超时秒: int = 300):
        """在后台线程中轮询发帖结果文件，直到不再是 PENDING 或超时。

        文件内容约定：
          - "PENDING": 发帖进行中
          - "NO": 发帖失败或未获取到URL
          - 其他非空字符串: 视为帖子URL
        """
        start = time.time()
        self.log("[自动发帖] 🔍 通过文件开始监控本次发帖结果...")
        last_value = None
        while True:
            try:
                if os.path.exists(self._result_file_path):
                    with open(self._result_file_path, "r", encoding="utf-8") as f:
                        value = f.read().strip()
                else:
                    value = ""
            except Exception as e:
                self.log(f"[自动发帖] ⚠️ 读取发帖结果文件失败: {e}")
                value = ""

            if value != last_value:
                last_value = value
                self.log(f"[自动发帖] 🔎 发帖结果文件当前内容: '{value}'")

            if value and value != "PENDING":
                # 有最终结果
                if value != "NO":
                    # 当作发帖成功，触发现有成功逻辑
                    try:
                        self._on_post_success(value)
                    except Exception as e:
                        self.log(f"[自动发帖] ❌ 通过文件触发发帖成功回调时出错: {e}")
                else:
                    self.log("[自动发帖] ⚠️ 文件结果为 NO，视为本次发帖未成功或未获取到URL")
                break

            if time.time() - start > 超时秒:
                self.log("[自动发帖] ⚠️ 等待发帖结果超时，停止文件监控")
                break

            time.sleep(2)

    def _切换到自动化标签页(self):
        """将主窗口切换到“自动化”分页（如果可用）。"""
        try:
            if not self.main_window:
                return
            if not hasattr(self.main_window, "tab_widget"):
                return

            from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

            tab_widget = self.main_window.tab_widget

            # 查找名为“自动化”的标签页索引
            index = -1
            try:
                for i in range(tab_widget.count()):
                    if tab_widget.tabText(i) == "自动化":
                        index = i
                        break
            except Exception:
                index = -1

            if index >= 0:
                # 使用 QueuedConnection 确保在 GUI 线程中切换标签
                QMetaObject.invokeMethod(
                    tab_widget,
                    "setCurrentIndex",
                    Qt.QueuedConnection,
                    Q_ARG(int, index)
                )
                self.log("[自动发帖] ✓ 已切换回“自动化”标签页")
        except Exception as e:
            self.log(f"[自动发帖] ⚠️ 切换到“自动化”标签页失败: {e}")
    
    def 设置互动协调器(self, 互动协调器):
        """设置互动协调器"""
        self.互动协调器 = 互动协调器
        self.log("[自动发帖] ✅ 互动协调器已设置")
    
    def 生成随机时间(self, 时间段):
        """
        生成随机时间
        
        Args:
            时间段: (开始小时, 结束小时)
        
        Returns:
            (小时, 分钟)
        """
        开始小时, 结束小时 = 时间段
        小时 = random.randint(开始小时, 结束小时 - 1)
        分钟 = random.randint(0, 59)
        return (小时, 分钟)
    
    def 执行发帖(self, 时段):
        """
        执行发帖
        
        Args:
            时段: "早上"/"中午"/"晚上"
        """
        try:
            # 检查是否已发帖
            今天 = datetime.now().strftime("%Y-%m-%d")
            if self.今日已发帖["日期"] != 今天:
                # 新的一天，重置标记
                self.今日已发帖 = {
                    "早上": False,
                    "中午": False,
                    "晚上": False,
                    "日期": 今天
                }
            
            if self.今日已发帖[时段]:
                self.log(f"[自动发帖] ⚠️ {时段}已发帖，跳过")
                return
            
            self.log(f"[自动发帖] 🚀 开始{时段}发帖...")
            
            # 调用主页发帖功能
            成功, 帖子URL = self._调用主页发帖()
            
            if 成功:
                # 注意：由于是异步调用，这里无法立即获取帖子URL
                # 标记为已发帖，避免重复发帖
                self.今日已发帖[时段] = True
                
                if 帖子URL:
                    self.log(f"[自动发帖] ✅ {时段}发帖已触发: {帖子URL}")
                else:
                    self.log(f"[自动发帖] ✅ {时段}发帖已触发（异步执行中）")
                
                # 注意：账号互动需要等待发帖完成后手动触发
                # 或者通过信号机制在发帖成功后自动触发
            else:
                self.log(f"[自动发帖] ❌ {时段}发帖失败")
        
        except Exception as e:
            self.log(f"[自动发帖] ❌ 执行发帖异常: {e}")
    
    def _调用主页发帖(self):
        """
        调用主页发帖功能
        
        Returns:
            (是否成功, 帖子URL)
        """
        try:
            # 1. 检查主窗口
            if not self.main_window:
                self.log("[自动发帖] ❌ 主窗口未设置")
                self.log("[自动发帖] 💡 请在「主页发帖」标签页中手动点击「开始发帖」")
                return (False, "")
            
            # 2. 检查主页发帖浏览器
            if not hasattr(self.main_window, 'homepage_browser'):
                self.log("[自动发帖] ❌ 主页发帖标签页未初始化")
                return (False, "")
            
            homepage_browser = self.main_window.homepage_browser
            
            # 3. 检查公共主页浏览器是否已打开
            if not homepage_browser.browser_id:
                self.log("[自动发帖] ❌ 公共主页浏览器未打开")
                self.log("[自动发帖] 💡 请先在「主页发帖」标签页中打开公共主页浏览器")
                return (False, "")
            
            # 4. 连接信号（如果还没连接）
            try:
                # 断开之前的连接（避免重复连接）
                homepage_browser.post_success.disconnect()
                homepage_browser.post_failed.disconnect()
            except:
                pass
            
            # 连接发帖成功信号
            homepage_browser.post_success.connect(self._on_post_success)
            # 连接发帖失败信号
            homepage_browser.post_failed.connect(self._on_post_failed)
            
            self.log("[自动发帖] ✓ 已连接发帖结果信号")
            
            # 5. 设置配置到主页发帖UI
            AI提示词 = self.配置.get("AI提示词", "")
            联系方式 = self.配置.get("联系方式", "")
            媒体文件夹 = self.配置.get("媒体文件夹", "")

            # 日志仍然完整输出当前自动发帖配置
            self.log(f"[自动发帖] 📝 AI提示词: {AI提示词[:50]}..." if len(AI提示词) > 50 else f"[自动发帖] 📝 AI提示词: {AI提示词}")
            self.log(f"[自动发帖] 📞 联系方式: {联系方式}")
            self.log(f"[自动发帖] 📁 媒体文件夹: {媒体文件夹}")

            # 6. 设置UI输入框的值（在主线程中）
            # 注意：只有当自动发帖配置中对应字段为非空时才覆盖 UI，
            # 否则保留 homepage_browser 自己的本地配置（config.json）
            from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

            if AI提示词:
                QMetaObject.invokeMethod(
                    homepage_browser.post_text_edit,
                    "setPlainText",
                    Qt.QueuedConnection,
                    Q_ARG(str, AI提示词)
                )

            if 联系方式:
                QMetaObject.invokeMethod(
                    homepage_browser.contact_input,
                    "setText",
                    Qt.QueuedConnection,
                    Q_ARG(str, 联系方式)
                )

            if 媒体文件夹:
                QMetaObject.invokeMethod(
                    homepage_browser.media_folder_input,
                    "setText",
                    Qt.QueuedConnection,
                    Q_ARG(str, 媒体文件夹)
                )
            
            # 7. 强制切换到主页发帖标签页（确保浏览器可见）
            try:
                if hasattr(self.main_window, 'tab_widget'):
                    # 查找主页发帖标签页的索引
                    for i in range(self.main_window.tab_widget.count()):
                        if self.main_window.tab_widget.tabText(i) == "主页发帖":
                            # 使用 QMetaObject 在主线程中切换
                            QMetaObject.invokeMethod(
                                self.main_window.tab_widget,
                                "setCurrentIndex",
                                Qt.QueuedConnection,
                                Q_ARG(int, i)
                            )
                            self.log("[自动发帖] ✓ 已切换到主页发帖标签页")
                            break
            except Exception as e:
                self.log(f"[自动发帖] ⚠️ 切换标签页失败: {e}")
            
            # 8. 调用发帖方法（在后台线程中执行，不需要QTimer）
            self.log("[自动发帖] 🚀 开始发帖...")
            self.log("[自动发帖] 💡 发帖完成后会自动触发账号互动")
            
            # 使用 QMetaObject.invokeMethod 以 QueuedConnection 在主页发帖控件所属的 GUI 线程中调用
            from PyQt5.QtCore import QMetaObject, Qt

            try:
                self.log("[自动发帖] ✓ 开始执行发帖方法...")
                QMetaObject.invokeMethod(
                    homepage_browser,
                    "_auto_post_with_bitbrowser",
                    Qt.QueuedConnection
                )
            except Exception as e:
                self.log(f"[自动发帖] ❌ 执行发帖失败: {e}")
                import traceback
                self.log(f"[自动发帖] 错误详情:\n{traceback.format_exc()}")
            
            # 注意：由于是异步调用，这里无法立即知道结果
            # 实际结果会通过信号回调 _on_post_success 或 _on_post_failed
            self.log("[自动发帖] ✓ 已触发发帖，等待结果...")
            
            # 返回成功，实际结果通过信号获取
            return (True, "")
            
        except Exception as e:
            import traceback
            self.log(f"[自动发帖] ❌ 调用主页发帖失败: {type(e).__name__}: {str(e)}")
            self.log(f"[自动发帖] 错误详情:\n{traceback.format_exc()}")
            return (False, "")
    
    def _on_post_success(self, 帖子URL):
        """
        发帖成功回调（通过信号触发）
        
        Args:
            帖子URL: 帖子链接
        """
        # 先记录一条日志，确认已经收到主页发帖的成功信号
        self.log(f"[自动发帖] 📡 收到发帖成功信号，URL={帖子URL}")
        # 无论是否拿到帖子URL，先把主界面切回“自动化”分页
        self._切换到自动化标签页()

        if 帖子URL:
            self.log(f"[自动发帖] ✅ 发帖成功！帖子URL: {帖子URL}")
        else:
            self.log("[自动发帖] ✅ 发帖成功！（等待审核中，暂无URL）")
        
        # 只有在拿到帖子URL时才触发账号互动
        if self.互动协调器 and 帖子URL:
            self.log("[自动发帖] 🎯 开始触发账号互动...")
            threading.Thread(
                target=self.互动协调器.协调账号互动,
                args=(帖子URL,),
                daemon=True
            ).start()
        elif not 帖子URL:
            self.log("[自动发帖] ⚠️ 帖子URL为空，跳过账号互动")
            self.log("[自动发帖] 💡 提示：Facebook审核通过后，可手动获取帖子URL并触发互动")
    
    def _on_post_failed(self, 错误信息):
        """
        发帖失败回调（通过信号触发）
        
        Args:
            错误信息: 错误描述
        """
        # 先记录一条日志，确认已经收到主页发帖的失败信号
        self.log(f"[自动发帖] 📡 收到发帖失败信号: {错误信息}")
        # 发帖失败同样切回“自动化”分页，方便用户在自动化界面观察和继续任务
        self._切换到自动化标签页()

        self.log(f"[自动发帖] ❌ 发帖失败: {错误信息}")
    
    def 手动发帖(self):
        """手动触发发帖（用于测试）"""
        self.log("[自动发帖] 🧪 手动触发发帖...")

        # 使用文件方式重置本次发帖结果
        self._重置发帖结果文件()

        成功, 帖子URL = self._调用主页发帖()
        
        if 成功:
            # 注意：由于是异步调用，这里无法立即获取帖子URL
            # 实际的发帖结果需要在主页发帖标签页中查看
            if 帖子URL:
                self.log(f"[自动发帖] ✅ 手动发帖已触发: {帖子URL}")
            else:
                self.log("[自动发帖] ✅ 手动发帖已触发（异步执行中）")
            
            # 注意：账号互动需要等待发帖完成后手动触发
            # 或者通过信号机制在发帖成功后自动触发
            # 此外，开启一个后台线程通过文件轮询发帖结果，作为信号机制的兜底
            try:
                threading.Thread(target=self._轮询发帖结果文件, daemon=True).start()
            except Exception as e:
                self.log(f"[自动发帖] ⚠️ 启动发帖结果文件监控线程失败: {e}")
        else:
            self.log("[自动发帖] ❌ 手动发帖失败")
    
    def 添加定时任务(self):
        """添加定时任务"""
        if not self.配置.get("启用自动发帖", True):
            self.log("[自动发帖] ⚠️ 自动发帖未启用")
            return
        
        # 生成今日随机时间
        早上时间 = self.生成随机时间(tuple(self.配置["早上时间段"]))
        中午时间 = self.生成随机时间(tuple(self.配置["中午时间段"]))
        晚上时间 = self.生成随机时间(tuple(self.配置["晚上时间段"]))
        
        self.今日发帖时间["早上"] = 早上时间
        self.今日发帖时间["中午"] = 中午时间
        self.今日发帖时间["晚上"] = 晚上时间
        
        # 添加早上发帖任务
        self.scheduler.add_job(
            self.执行发帖,
            CronTrigger(hour=早上时间[0], minute=早上时间[1], timezone=self.tz),
            args=["早上"],
            id='morning_post',
            replace_existing=True
        )
        self.log(f"[自动发帖] ✅ 早上发帖任务已添加: {早上时间[0]:02d}:{早上时间[1]:02d}")
        
        # 添加中午发帖任务
        self.scheduler.add_job(
            self.执行发帖,
            CronTrigger(hour=中午时间[0], minute=中午时间[1], timezone=self.tz),
            args=["中午"],
            id='noon_post',
            replace_existing=True
        )
        self.log(f"[自动发帖] ✅ 中午发帖任务已添加: {中午时间[0]:02d}:{中午时间[1]:02d}")
        
        # 添加晚上发帖任务
        self.scheduler.add_job(
            self.执行发帖,
            CronTrigger(hour=晚上时间[0], minute=晚上时间[1], timezone=self.tz),
            args=["晚上"],
            id='evening_post',
            replace_existing=True
        )
        self.log(f"[自动发帖] ✅ 晚上发帖任务已添加: {晚上时间[0]:02d}:{晚上时间[1]:02d}")
        
        # 添加每日0点重新生成时间的任务
        self.scheduler.add_job(
            self.添加定时任务,
            CronTrigger(hour=0, minute=0, timezone=self.tz),
            id='regenerate_times',
            replace_existing=True
        )
        self.log("[自动发帖] ✅ 每日重新生成时间任务已添加")
    
    def 启动(self):
        """启动自动发帖管理器"""
        try:
            self.添加定时任务()
            self.scheduler.start()
            self.log("[自动发帖] ✅ 自动发帖管理器已启动")
        except Exception as e:
            import traceback
            错误详情 = traceback.format_exc()
            self.log(f"[自动发帖] ❌ 启动失败: {type(e).__name__}: {str(e)}")
            self.log(f"[自动发帖] 错误详情:\n{错误详情}")
    
    def 停止(self):
        """停止自动发帖管理器"""
        try:
            self.scheduler.shutdown()
            self.log("[自动发帖] ✅ 自动发帖管理器已停止")
        except Exception as e:
            self.log(f"[自动发帖] ❌ 停止失败: {e}")
