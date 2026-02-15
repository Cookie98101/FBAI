"""
任务调度器 (Main Controller)
负责：
1. 检测比特浏览器连接状态
2. 管理浏览器实例
3. 调度和分发任务到具体脚本
4. 传递参数给任务脚本
"""

import os
import json
import time
import threading
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from queue import Queue
from dataclasses import dataclass, field

# 导入比特浏览器 API
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from bitbrowser_api import BitBrowserAPI, bit_browser
except ImportError:
    bit_browser = None
    print("警告: 无法导入 bitbrowser_api")

from .task_loader import TaskLoader


@dataclass
class TaskContext:
    """任务执行上下文，传递给任务脚本"""
    browser_id: str                          # 浏览器ID
    browser_ws: str = ""                     # WebSocket 连接地址
    browser_info: Dict = field(default_factory=dict)  # 浏览器详细信息
    params: Dict = field(default_factory=dict)        # 任务参数
    scheduler: Any = None                    # 调度器引用（用于回调）


@dataclass  
class TaskResult:
    """任务执行结果"""
    success: bool
    message: str = ""
    data: Dict = field(default_factory=dict)
    error: str = ""
    duration: float = 0.0  # 执行耗时（秒）


class TaskScheduler:
    """
    任务调度器 - 自动化的核心控制器
    
    使用方式:
        scheduler = TaskScheduler()
        
        # 执行单个任务
        result = scheduler.execute_task(
            browser_id="xxx",
            task_name="read_article",
            params={"read_time": 30, "scroll_count": 5}
        )
        
        # 批量执行
        scheduler.batch_execute(
            browser_ids=["id1", "id2"],
            task_name="read_article",
            params={"read_time": 30}
        )
    """
    
    def __init__(self, config_file: str = "automation_config.json"):
        """
        初始化调度器
        :param config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self.load_config()
        
        # 任务加载器
        self.task_loader = TaskLoader(
            tasks_dir=self.config.get("tasks_dir"),
            remote_url=self.config.get("remote_url")
        )
        
        # 任务队列
        self.task_queue: Queue = Queue()
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        
        # 回调函数
        self.on_task_start: Optional[Callable] = None
        self.on_task_complete: Optional[Callable] = None
        self.on_task_error: Optional[Callable] = None
        self.on_log: Optional[Callable] = None
        
        # 当前活跃的浏览器会话
        self.active_sessions: Dict[str, Dict] = {}
    
    def load_config(self) -> Dict:
        """加载配置"""
        default_config = {
            "tasks_dir": None,  # 使用默认目录
            "remote_url": None,  # 远程脚本服务器
            "max_concurrent": 3,  # 最大并发数
            "retry_count": 2,     # 失败重试次数
            "retry_delay": 5,     # 重试间隔（秒）
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
            except Exception as e:
                print(f"加载配置失败: {e}")
        
        return default_config
    
    def save_config(self):
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def log(self, message: str):
        """输出日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        if self.on_log:
            self.on_log(log_msg)
    
    def check_browser_connection(self) -> bool:
        """检查比特浏览器连接状态"""
        if bit_browser is None:
            self.log("❌ 比特浏览器API未加载")
            return False
        
        try:
            connected = bit_browser.check_connection()
            if connected:
                self.log("✓ 比特浏览器连接正常")
            else:
                self.log("❌ 无法连接到比特浏览器")
            return connected
        except Exception as e:
            self.log(f"❌ 检查连接异常: {e}")
            return False
    
    def get_browser_list(self) -> List[Dict]:
        """获取浏览器列表"""
        if bit_browser is None:
            return []
        
        try:
            result = bit_browser.get_browser_list()
            if result.get("success"):
                return result.get("data", {}).get("list", [])
        except Exception as e:
            self.log(f"获取浏览器列表失败: {e}")
        return []
    
    def open_browser(self, browser_id: str) -> Optional[str]:
        """
        打开浏览器并返回 WebSocket 地址
        :param browser_id: 浏览器ID
        :return: WebSocket 连接地址，失败返回 None
        """
        if bit_browser is None:
            return None
        
        try:
            result = bit_browser.open_browser(browser_id)
            if result.get("success"):
                data = result.get("data", {})
                ws_url = data.get("ws", "")
                driver_path = data.get("driver", "")
                http_address = data.get("http", "")
                
                self.active_sessions[browser_id] = {
                    "ws": ws_url,
                    "driver": driver_path,
                    "http": http_address,
                    "opened_at": datetime.now().isoformat()
                }
                self.log(f"✓ 浏览器已打开: {browser_id}")
                self.log(f"  Selenium地址: {http_address}")
                return ws_url
            else:
                self.log(f"❌ 打开浏览器失败: {result.get('msg')}")
        except Exception as e:
            self.log(f"❌ 打开浏览器异常: {e}")
        return None
    
    def close_browser(self, browser_id: str) -> bool:
        """关闭浏览器（异步）"""
        if bit_browser is None:
            return False
        
        # 异步关闭，避免阻塞
        import threading
        def close_async():
            try:
                result = bit_browser.close_browser(browser_id)
                if result.get("success"):
                    if browser_id in self.active_sessions:
                        del self.active_sessions[browser_id]
                    self.log(f"✓ 浏览器已关闭: {browser_id}")
                else:
                    self.log(f"❌ 关闭浏览器失败: {result.get('msg')}")
            except Exception as e:
                self.log(f"❌ 关闭浏览器异常: {e}")
        
        threading.Thread(target=close_async, daemon=True).start()
        return True
    
    def execute_task(self, browser_id: str, task_name: str, 
                     params: Dict = None, auto_open: bool = True,
                     auto_close: bool = False) -> TaskResult:
        """
        执行单个任务
        :param browser_id: 浏览器ID
        :param task_name: 任务名称
        :param params: 任务参数
        :param auto_open: 是否自动打开浏览器
        :param auto_close: 任务完成后是否自动关闭浏览器
        :return: 任务执行结果
        """
        start_time = time.time()
        params = params or {}
        
        self.log(f"▶ 开始执行任务: {task_name} (浏览器: {browser_id})")
        
        if self.on_task_start:
            self.on_task_start(browser_id, task_name, params)
        
        try:
            # 1. 检查浏览器连接
            if not self.check_browser_connection():
                return TaskResult(
                    success=False,
                    error="比特浏览器未连接",
                    duration=time.time() - start_time
                )
            
            # 2. 打开浏览器（如果需要）
            ws_url = self.active_sessions.get(browser_id, {}).get("ws", "")
            if auto_open and not ws_url:
                ws_url = self.open_browser(browser_id)
                if not ws_url:
                    return TaskResult(
                        success=False,
                        error="无法打开浏览器",
                        duration=time.time() - start_time
                    )
                # 等待浏览器启动
                time.sleep(2)
            
            # 3. 加载任务脚本
            task_func = self.task_loader.get_task_function(task_name, "execute")
            if task_func is None:
                return TaskResult(
                    success=False,
                    error=f"任务脚本不存在或无效: {task_name}",
                    duration=time.time() - start_time
                )
            
            # 4. 构建任务上下文
            session_info = self.active_sessions.get(browser_id, {})
            context = TaskContext(
                browser_id=browser_id,
                browser_ws=session_info.get("ws", ""),
                browser_info={
                    "driver": session_info.get("driver", ""),
                    "http": session_info.get("http", ""),
                    "ws": session_info.get("ws", "")
                },
                params=params,
                scheduler=self
            )
            
            # 5. 执行任务
            self.log(f"  执行中... 参数: {params}")
            result = task_func(context)
            
            # 6. 处理结果
            if isinstance(result, TaskResult):
                task_result = result
            elif isinstance(result, dict):
                task_result = TaskResult(
                    success=result.get("success", False),
                    message=result.get("message", ""),
                    data=result.get("data", {}),
                    error=result.get("error", "")
                )
            elif isinstance(result, bool):
                task_result = TaskResult(success=result)
            else:
                task_result = TaskResult(success=True, data={"result": result})
            
            task_result.duration = time.time() - start_time
            
            # 7. 关闭浏览器（如果需要）
            if auto_close:
                self.close_browser(browser_id)
            
            # 8. 回调
            if task_result.success:
                self.log(f"✓ 任务完成: {task_name} (耗时: {task_result.duration:.1f}s)")
                if self.on_task_complete:
                    self.on_task_complete(browser_id, task_name, task_result)
            else:
                self.log(f"❌ 任务失败: {task_name} - {task_result.error}")
                if self.on_task_error:
                    self.on_task_error(browser_id, task_name, task_result)
            
            return task_result
            
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.log(f"❌ 任务异常: {task_name} - {e}")
            
            result = TaskResult(
                success=False,
                error=error_msg,
                duration=time.time() - start_time
            )
            
            if self.on_task_error:
                self.on_task_error(browser_id, task_name, result)
            
            return result
    
    def batch_execute(self, browser_ids: List[str], task_name: str,
                      params: Dict = None, sequential: bool = True) -> Dict[str, TaskResult]:
        """
        批量执行任务
        :param browser_ids: 浏览器ID列表
        :param task_name: 任务名称
        :param params: 任务参数（所有浏览器使用相同参数）
        :param sequential: 是否顺序执行（False则并发）
        :return: {browser_id: TaskResult}
        """
        results = {}
        
        if sequential:
            for browser_id in browser_ids:
                results[browser_id] = self.execute_task(browser_id, task_name, params)
        else:
            # 并发执行
            threads = []
            for browser_id in browser_ids:
                t = threading.Thread(
                    target=lambda bid: results.update({bid: self.execute_task(bid, task_name, params)}),
                    args=(browser_id,)
                )
                threads.append(t)
                t.start()
            
            for t in threads:
                t.join()
        
        return results
    
    def get_available_tasks(self) -> List[str]:
        """获取所有可用任务"""
        return self.task_loader.get_available_tasks()
    
    def reload_tasks(self):
        """重新加载所有任务脚本"""
        self.task_loader.reload_all_tasks()
        self.log("✓ 任务脚本已重新加载")


# 全局调度器实例
scheduler = TaskScheduler()
