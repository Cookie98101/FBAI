"""
UI 工作线程管理模块
- 账号切换异步化
- 主线程保护
- 后台任务管理
"""

import time
import traceback
from typing import Callable, Any, Optional
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition
from PyQt5.QtWidgets import QMessageBox


class WorkerThread(QThread):
    """后台工作线程基类"""
    
    # 信号定义
    started = pyqtSignal()  # 线程启动
    finished = pyqtSignal(bool, str)  # 完成 (成功/失败, 消息)
    progress = pyqtSignal(str)  # 进度更新
    error = pyqtSignal(str)  # 错误信息
    
    def __init__(self, parent=None, name: str = "Worker"):
        super().__init__(parent)
        self.running = True
        self.name = name
        self.mutex = QMutex()
        self.wait_condition = QWaitCondition()
        
    def run(self):
        """运行工作线程"""
        try:
            self.started.emit()
            print(f"[{self.name}] 线程已启动")
            self._do_work()
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            print(f"[{self.name}] 错误: {error_msg}")
            self.error.emit(error_msg)
            self.finished.emit(False, str(e))
    
    def _do_work(self):
        """子类实现具体工作"""
        raise NotImplementedError("子类必须实现 _do_work 方法")
    
    def stop(self):
        """停止线程"""
        self.running = False
        self.quit()
        self.wait()
        print(f"[{self.name}] 线程已停止")
    
    def pause(self):
        """暂停线程"""
        self.mutex.lock()
        print(f"[{self.name}] 线程已暂停")
    
    def resume(self):
        """恢复线程"""
        self.mutex.unlock()
        self.wait_condition.wakeAll()
        print(f"[{self.name}] 线程已恢复")


class AccountSwitchThread(WorkerThread):
    """账号切换线程 - 异步处理账号切换"""
    
    account_switched = pyqtSignal(str, bool, str)  # 账号ID, 成功/失败, 消息
    
    def __init__(self, account_id: str, switch_callback: Callable, parent=None):
        super().__init__(parent, name=f"AccountSwitch-{account_id}")
        self.account_id = account_id
        self.switch_callback = switch_callback
        
    def _do_work(self):
        """执行账号切换"""
        try:
            self.progress.emit(f"正在切换到账号: {self.account_id}")
            print(f"[{self.name}] 开始切换账号")
            
            # 步骤1: 关闭当前浏览器
            self.progress.emit("正在关闭当前浏览器...")
            print(f"[{self.name}] 关闭当前浏览器")
            time.sleep(0.5)  # 模拟操作
            
            # 步骤2: 打开新账号浏览器
            self.progress.emit("正在打开新账号浏览器...")
            print(f"[{self.name}] 打开新账号浏览器")
            
            # 执行切换回调
            if self.switch_callback:
                result = self.switch_callback(self.account_id)
                if not result:
                    raise Exception("账号切换回调失败")
            
            # 步骤3: 嵌入浏览器
            self.progress.emit("正在嵌入浏览器...")
            print(f"[{self.name}] 嵌入浏览器")
            time.sleep(0.5)  # 模拟操作
            
            # 完成
            self.progress.emit(f"✅ 账号切换成功: {self.account_id}")
            self.account_switched.emit(self.account_id, True, "切换成功")
            self.finished.emit(True, f"账号 {self.account_id} 切换成功")
            print(f"[{self.name}] 账号切换完成")
            
        except Exception as e:
            error_msg = f"账号切换失败: {str(e)}"
            self.progress.emit(f"❌ {error_msg}")
            self.account_switched.emit(self.account_id, False, error_msg)
            self.finished.emit(False, error_msg)
            print(f"[{self.name}] 错误: {error_msg}")


class DataFetchThread(WorkerThread):
    """数据获取线程 - 异步获取数据"""
    
    data_fetched = pyqtSignal(dict)  # 获取的数据
    
    def __init__(self, fetch_callback: Callable, parent=None):
        super().__init__(parent, name="DataFetch")
        self.fetch_callback = fetch_callback
        
    def _do_work(self):
        """执行数据获取"""
        try:
            self.progress.emit("正在获取数据...")
            print(f"[{self.name}] 开始获取数据")
            
            # 执行获取回调
            if self.fetch_callback:
                data = self.fetch_callback()
                self.data_fetched.emit(data)
                self.finished.emit(True, "数据获取成功")
                print(f"[{self.name}] 数据获取完成")
            else:
                raise Exception("获取回调未设置")
                
        except Exception as e:
            error_msg = f"数据获取失败: {str(e)}"
            self.finished.emit(False, error_msg)
            print(f"[{self.name}] 错误: {error_msg}")


class BrowserOperationThread(WorkerThread):
    """浏览器操作线程 - 异步处理浏览器操作"""
    
    operation_completed = pyqtSignal(str, dict)  # 操作名称, 结果
    
    def __init__(self, operation_name: str, operation_callback: Callable, parent=None):
        super().__init__(parent, name=f"BrowserOp-{operation_name}")
        self.operation_name = operation_name
        self.operation_callback = operation_callback
        
    def _do_work(self):
        """执行浏览器操作"""
        try:
            self.progress.emit(f"正在执行: {self.operation_name}")
            print(f"[{self.name}] 开始执行浏览器操作")
            
            # 执行操作回调
            if self.operation_callback:
                result = self.operation_callback()
                self.operation_completed.emit(self.operation_name, result or {})
                self.finished.emit(True, f"{self.operation_name} 完成")
                print(f"[{self.name}] 浏览器操作完成")
            else:
                raise Exception("操作回调未设置")
                
        except Exception as e:
            error_msg = f"{self.operation_name} 失败: {str(e)}"
            self.finished.emit(False, error_msg)
            print(f"[{self.name}] 错误: {error_msg}")


class UIThreadManager:
    """UI 线程管理器 - 管理所有后台线程"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.threads = {}  # 线程池
        self.active_threads = set()  # 活跃线程集合
        
    def create_account_switch_thread(self, account_id: str, switch_callback: Callable) -> AccountSwitchThread:
        """创建账号切换线程"""
        thread = AccountSwitchThread(account_id, switch_callback, self.parent)
        thread_id = f"account_switch_{account_id}"
        self.threads[thread_id] = thread
        self.active_threads.add(thread_id)
        
        # 连接完成信号
        thread.finished.connect(lambda success, msg: self._on_thread_finished(thread_id, success, msg))
        
        print(f"[UIThreadManager] 创建账号切换线程: {thread_id}")
        return thread
    
    def create_data_fetch_thread(self, fetch_callback: Callable) -> DataFetchThread:
        """创建数据获取线程"""
        thread = DataFetchThread(fetch_callback, self.parent)
        thread_id = f"data_fetch_{int(time.time() * 1000)}"
        self.threads[thread_id] = thread
        self.active_threads.add(thread_id)
        
        # 连接完成信号
        thread.finished.connect(lambda success, msg: self._on_thread_finished(thread_id, success, msg))
        
        print(f"[UIThreadManager] 创建数据获取线程: {thread_id}")
        return thread
    
    def create_browser_operation_thread(self, operation_name: str, operation_callback: Callable) -> BrowserOperationThread:
        """创建浏览器操作线程"""
        thread = BrowserOperationThread(operation_name, operation_callback, self.parent)
        thread_id = f"browser_op_{operation_name}_{int(time.time() * 1000)}"
        self.threads[thread_id] = thread
        self.active_threads.add(thread_id)
        
        # 连接完成信号
        thread.finished.connect(lambda success, msg: self._on_thread_finished(thread_id, success, msg))
        
        print(f"[UIThreadManager] 创建浏览器操作线程: {thread_id}")
        return thread
    
    def _on_thread_finished(self, thread_id: str, success: bool, message: str):
        """线程完成回调"""
        if thread_id in self.active_threads:
            self.active_threads.remove(thread_id)
            print(f"[UIThreadManager] 线程完成: {thread_id} - {'成功' if success else '失败'}")
    
    def stop_all_threads(self):
        """停止所有线程"""
        print(f"[UIThreadManager] 停止所有线程 (共 {len(self.active_threads)} 个活跃线程)")
        for thread_id in list(self.active_threads):
            if thread_id in self.threads:
                thread = self.threads[thread_id]
                if hasattr(thread, 'stop'):
                    thread.stop()
        self.active_threads.clear()
    
    def get_active_thread_count(self) -> int:
        """获取活跃线程数"""
        return len(self.active_threads)
    
    def wait_for_all_threads(self, timeout_ms: int = 30000):
        """等待所有线程完成"""
        print(f"[UIThreadManager] 等待所有线程完成 (超时: {timeout_ms}ms)")
        start_time = time.time()
        while self.active_threads and (time.time() - start_time) * 1000 < timeout_ms:
            time.sleep(0.1)
        
        if self.active_threads:
            print(f"[UIThreadManager] 警告: 仍有 {len(self.active_threads)} 个线程未完成")
        else:
            print(f"[UIThreadManager] 所有线程已完成")


# 全局线程管理器实例
_thread_manager = None


def get_thread_manager(parent=None) -> UIThreadManager:
    """获取全局线程管理器"""
    global _thread_manager
    if _thread_manager is None:
        _thread_manager = UIThreadManager(parent)
    return _thread_manager


def init_thread_manager(parent=None):
    """初始化线程管理器"""
    global _thread_manager
    _thread_manager = UIThreadManager(parent)
    print("[UIThreadManager] 线程管理器已初始化")
    return _thread_manager
