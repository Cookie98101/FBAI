"""
任务加载器 - 动态加载外部脚本
支持从远程或本地动态加载任务脚本，打包后仍可更新
"""

import os
import sys
import json
import importlib.util
import requests
from typing import Dict, Any, Optional, Callable
from datetime import datetime


class TaskLoader:
    """
    动态任务加载器
    - 支持从本地 tasks 目录加载脚本
    - 支持从远程服务器下载更新脚本
    - 打包后可通过更新 tasks 目录实现热更新
    """
    
    def __init__(self, tasks_dir: str = None, remote_url: str = None):
        """
        初始化任务加载器
        :param tasks_dir: 本地任务脚本目录，默认为 automation/tasks
        :param remote_url: 远程脚本服务器地址（可选）
        """
        if tasks_dir is None:
            # 默认使用 automation/tasks 目录
            base_dir = os.path.dirname(os.path.abspath(__file__))
            tasks_dir = os.path.join(base_dir, "tasks")
        
        self.tasks_dir = tasks_dir
        self.remote_url = remote_url
        self.loaded_tasks: Dict[str, Any] = {}  # 已加载的任务模块缓存
        self.task_info: Dict[str, Dict] = {}    # 任务元信息
        
        # 注意：不自动创建 tasks 目录，避免创建错误的 automation/tasks 路径
        # 正确的路径应该是 automation/scripts/tasks
        
        # 版本文件路径
        self.version_file = os.path.join(self.tasks_dir, "versions.json")
        self.load_version_info()
    
    def load_version_info(self):
        """加载本地版本信息"""
        self.versions = {}
        if os.path.exists(self.version_file):
            try:
                with open(self.version_file, 'r', encoding='utf-8') as f:
                    self.versions = json.load(f)
            except:
                self.versions = {}
    
    def save_version_info(self):
        """保存版本信息"""
        try:
            with open(self.version_file, 'w', encoding='utf-8') as f:
                json.dump(self.versions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存版本信息失败: {e}")
    
    def get_available_tasks(self) -> list:
        """
        获取所有可用的任务列表
        支持 .py 和 .pyc 文件
        :return: 任务名称列表
        """
        tasks = set()
        if os.path.exists(self.tasks_dir):
            for filename in os.listdir(self.tasks_dir):
                if filename.startswith('_'):
                    continue
                if filename.endswith('.py'):
                    tasks.add(filename[:-3])
                elif filename.endswith('.pyc'):
                    tasks.add(filename[:-4])
        return sorted(list(tasks))
    
    def load_task(self, task_name: str, force_reload: bool = False) -> Optional[Any]:
        """
        动态加载任务模块
        支持 .py 和 .pyc 文件
        :param task_name: 任务名称（不含后缀）
        :param force_reload: 是否强制重新加载
        :return: 任务模块对象
        """
        # 检查缓存
        if not force_reload and task_name in self.loaded_tasks:
            return self.loaded_tasks[task_name]
        
        # 优先查找 .pyc 文件，其次 .py 文件
        task_file = None
        for ext in ['.pyc', '.py']:
            candidate = os.path.join(self.tasks_dir, f"{task_name}{ext}")
            if os.path.exists(candidate):
                task_file = candidate
                break
        
        if task_file is None:
            print(f"任务脚本不存在: {task_name}")
            return None
        
        try:
            # 动态加载模块
            if task_file.endswith('.pyc'):
                # 加载 .pyc 字节码文件
                import importlib.util
                import marshal
                
                with open(task_file, 'rb') as f:
                    # 跳过 .pyc 文件头 (16 bytes for Python 3.7+)
                    f.read(16)
                    code = marshal.load(f)
                
                module = type(sys)('task_name')
                exec(code, module.__dict__)
            else:
                # 加载 .py 源文件
                spec = importlib.util.spec_from_file_location(task_name, task_file)
                if spec is None or spec.loader is None:
                    print(f"无法加载任务模块: {task_name}")
                    return None
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            
            sys.modules[task_name] = module
            
            # 缓存模块
            self.loaded_tasks[task_name] = module
            
            # 读取任务元信息（如果有）
            if hasattr(module, 'TASK_INFO'):
                self.task_info[task_name] = module.TASK_INFO
            
            print(f"✓ 任务加载成功: {task_name} ({os.path.basename(task_file)})")
            return module
            
        except Exception as e:
            print(f"加载任务失败 [{task_name}]: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_task_function(self, task_name: str, func_name: str = "execute") -> Optional[Callable]:
        """
        获取任务的执行函数
        :param task_name: 任务名称
        :param func_name: 函数名称，默认为 execute
        :return: 可调用的函数
        """
        module = self.load_task(task_name)
        if module is None:
            return None
        
        if hasattr(module, func_name):
            return getattr(module, func_name)
        else:
            print(f"任务 [{task_name}] 没有 {func_name} 函数")
            return None
    
    def check_remote_updates(self) -> Dict[str, bool]:
        """
        检查远程是否有脚本更新
        :return: {任务名: 是否有更新}
        """
        if not self.remote_url:
            return {}
        
        updates = {}
        try:
            # 获取远程版本列表
            response = requests.get(f"{self.remote_url}/task_versions", timeout=10)
            if response.status_code == 200:
                remote_versions = response.json()
                
                for task_name, remote_ver in remote_versions.items():
                    local_ver = self.versions.get(task_name, "0")
                    updates[task_name] = remote_ver > local_ver
                    
        except Exception as e:
            print(f"检查远程更新失败: {e}")
        
        return updates
    
    def download_task(self, task_name: str) -> bool:
        """
        从远程下载/更新任务脚本
        :param task_name: 任务名称
        :return: 是否成功
        """
        if not self.remote_url:
            print("未配置远程服务器地址")
            return False
        
        try:
            response = requests.get(
                f"{self.remote_url}/download_task/{task_name}",
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                script_content = data.get("content", "")
                version = data.get("version", "1.0")
                
                # 保存脚本
                task_file = os.path.join(self.tasks_dir, f"{task_name}.py")
                with open(task_file, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                
                # 更新版本信息
                self.versions[task_name] = version
                self.save_version_info()
                
                # 清除缓存，下次使用时重新加载
                if task_name in self.loaded_tasks:
                    del self.loaded_tasks[task_name]
                
                print(f"✓ 任务下载成功: {task_name} (v{version})")
                return True
            else:
                print(f"下载任务失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"下载任务异常: {e}")
            return False
    
    def reload_all_tasks(self):
        """重新加载所有任务"""
        self.loaded_tasks.clear()
        for task_name in self.get_available_tasks():
            self.load_task(task_name, force_reload=True)
