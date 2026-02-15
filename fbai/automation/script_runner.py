"""
脚本运行器 - 动态加载并执行可热更新的脚本

这个模块负责：
1. 动态加载 scripts/main.py
2. 支持热更新（每次执行都重新加载）
3. 提供统一的执行接口给 UI 和命令行
"""

import os
import sys
import importlib.util
from typing import Dict, Any, Optional

from .task_scheduler import TaskScheduler


class ScriptRunner:
    """
    脚本运行器
    动态加载并执行 scripts/main.py
    """
    
    def __init__(self, scripts_dir: str = None):
        """
        初始化脚本运行器
        :param scripts_dir: 脚本目录，默认为 automation/scripts
        """
        if scripts_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            scripts_dir = os.path.join(base_dir, "scripts")
        
        self.scripts_dir = scripts_dir
        self.main_script_path = os.path.join(scripts_dir, "main.py")
        self.scheduler = TaskScheduler()
        self._main_module = None
    
    def load_main(self, force_reload: bool = True) -> Optional[Any]:
        """
        加载 main.py 模块
        :param force_reload: 是否强制重新加载（热更新）
        :return: 模块对象
        """
        if not os.path.exists(self.main_script_path):
            print(f"❌ 主脚本不存在: {self.main_script_path}")
            return None
        
        try:
            # 每次都重新加载，实现热更新
            spec = importlib.util.spec_from_file_location("main_script", self.main_script_path)
            if spec is None or spec.loader is None:
                print(f"❌ 无法加载主脚本")
                return None
            
            module = importlib.util.module_from_spec(spec)
            
            # 从 sys.modules 中移除旧模块（如果存在）
            if "main_script" in sys.modules:
                del sys.modules["main_script"]
            
            sys.modules["main_script"] = module
            spec.loader.exec_module(module)
            
            self._main_module = module
            print(f"✓ 主脚本已加载: {self.main_script_path}")
            return module
            
        except Exception as e:
            print(f"❌ 加载主脚本失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def run(self, browser_id: str = None, browser_ids: list = None,
            task_name: str = None, params: dict = None,
            mode: str = 'single') -> Dict[str, Any]:
        """
        执行主脚本
        
        :param browser_id: 单个浏览器ID
        :param browser_ids: 浏览器ID列表（批量模式）
        :param task_name: 任务名称
        :param params: 任务参数
        :param mode: 执行模式 ('single', 'batch', 'auto')
        :return: 执行结果
        """
        # 每次执行都重新加载，实现热更新
        module = self.load_main(force_reload=True)
        
        if module is None:
            return {
                "success": False,
                "error": "无法加载主脚本"
            }
        
        if not hasattr(module, 'run'):
            return {
                "success": False,
                "error": "主脚本缺少 run 函数"
            }
        
        # 构建执行上下文
        context = {
            'scheduler': self.scheduler,
            'browser_id': browser_id,
            'browser_ids': browser_ids or [],
            'task_name': task_name,
            'params': params or {},
            'mode': mode
        }
        
        try:
            # 调用主脚本的 run 函数
            result = module.run(context)
            return result if isinstance(result, dict) else {"success": True, "data": result}
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"❌ 执行主脚本失败: {e}")
            print(error_detail)
            return {
                "success": False,
                "error": f"执行失败: {str(e)}"
            }
    
    def run_single(self, browser_id: str, task_name: str, params: dict = None) -> Dict[str, Any]:
        """执行单个任务的快捷方法"""
        return self.run(
            browser_id=browser_id,
            task_name=task_name,
            params=params,
            mode='single'
        )
    
    def run_batch(self, browser_ids: list, task_name: str, params: dict = None) -> Dict[str, Any]:
        """批量执行任务的快捷方法"""
        return self.run(
            browser_ids=browser_ids,
            task_name=task_name,
            params=params,
            mode='batch'
        )
    
    def run_auto(self) -> Dict[str, Any]:
        """自动模式的快捷方法"""
        return self.run(mode='auto')
    
    def get_available_tasks(self) -> list:
        """获取可用任务列表"""
        return self.scheduler.get_available_tasks()
    
    def get_browser_list(self) -> list:
        """获取浏览器列表"""
        return self.scheduler.get_browser_list()
    
    def check_connection(self) -> bool:
        """检查比特浏览器连接"""
        return self.scheduler.check_browser_connection()


# 全局实例
script_runner = ScriptRunner()
