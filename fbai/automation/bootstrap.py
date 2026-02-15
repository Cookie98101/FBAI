"""
自动化模块启动器 (Bootstrap)
这个文件会被打包进exe，不可热更新
唯一作用：
1. 在加载 main.py 之前检查并应用更新
2. 动态加载并执行外部的 main.py

外部 main.py 和 tasks/*.py 可以随时更新
"""

import os
import sys
import importlib.util
from typing import Any, Optional
from pathlib import Path


class AutomationBootstrap:
    """
    自动化启动器
    负责动态加载外部的 main.py 主控制器
    """
    
    def __init__(self, log_callback=None):
        # 确定脚本目录
        # 打包后：exe所在目录/automation_scripts/
        # 开发时：automation/scripts/
        self.log_callback = log_callback  # 日志回调函数
        self.scripts_dir = self._find_scripts_dir()
        self.main_module = None
        self._controller = None
    
    def _log(self, msg: str):
        """输出日志"""
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(msg)
    
    def _find_scripts_dir(self) -> str:
        """查找脚本目录"""
        exe_dir = os.path.dirname(sys.executable)
        
        # 可能的目录位置（按优先级排序）
        possible_dirs = [
            # 打包后的位置1：exe所在目录/_internal/automation/scripts/
            os.path.join(exe_dir, "_internal", "automation", "scripts"),
            # 打包后的位置2：exe所在目录/automation/scripts/
            os.path.join(exe_dir, "automation", "scripts"),
            # 打包后的位置3：exe所在目录/automation_scripts/（兼容旧版）
            os.path.join(exe_dir, "automation_scripts"),
            # 开发时的位置
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"),
            # 当前工作目录
            os.path.join(os.getcwd(), "automation", "scripts"),
        ]
        
        self._log(f"[Bootstrap] 开始查找脚本目录...")
        self._log(f"[Bootstrap] exe目录: {exe_dir}")
        
        for i, dir_path in enumerate(possible_dirs, 1):
            main_file = os.path.join(dir_path, "main.py")
            main_pyc = os.path.join(dir_path, "main.pyc")
            
            self._log(f"[Bootstrap] 检查路径 {i}: {dir_path}")
            
            if os.path.exists(main_file):
                self._log(f"[Bootstrap] ✓ 找到 main.py: {dir_path}")
                return dir_path
            elif os.path.exists(main_pyc):
                self._log(f"[Bootstrap] ✓ 找到 main.pyc: {dir_path}")
                return dir_path
            else:
                self._log(f"[Bootstrap] ✗ 未找到 main.py/main.pyc")
        
        # 默认使用第一个位置
        default_dir = possible_dirs[0]
        self._log(f"[Bootstrap] ⚠ 所有路径都未找到文件，使用默认: {default_dir}")
        os.makedirs(default_dir, exist_ok=True)
        return default_dir
    
    def _is_dev_environment(self) -> bool:
        """
        检测是否为开发环境
        打包环境特征：sys.frozen = True（PyInstaller设置）
        开发环境特征：sys.frozen 不存在或为 False
        """
        # 使用 PyInstaller 的 frozen 属性判断
        # 打包后 sys.frozen = True，开发时不存在此属性
        if getattr(sys, 'frozen', False):
            # 打包环境，应该执行热更新
            return False
        else:
            # 开发环境，跳过热更新
            return True
    
    def _check_and_update(self):
        """
        在加载 main.py 之前检查并应用更新
        这样可以确保加载的是最新版本
        
        注意：开发环境会跳过热更新，避免覆盖本地代码
        """
        try:
            # 检测开发环境
            if self._is_dev_environment():
                self._log("[Bootstrap] 🔧 检测到开发环境，跳过热更新")
                self._log("[Bootstrap] ✓ 使用本地 .py 源文件")
                return
            
            self._log("[Bootstrap] 🔍 检查更新...")
            
            # 导入热更新模块（优先 .pyc）
            update_module_path = None
            for ext in ['.pyc', '.py']:
                candidate = os.path.join(self.scripts_dir, f"热更新守护进程{ext}")
                if os.path.exists(candidate):
                    update_module_path = candidate
                    break
            
            if update_module_path is None:
                self._log("[Bootstrap] 未找到热更新模块，跳过更新检查")
                return
            
            # 动态导入热更新模块
            spec = importlib.util.spec_from_file_location("update_guard", update_module_path)
            if spec is None or spec.loader is None:
                self._log("[Bootstrap] 无法加载热更新模块")
                return
            
            update_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(update_module)
            
            # 检查更新
            server_version = update_module.获取服务器版本()
            if not server_version:
                self._log("[Bootstrap] ✓ 无法连接更新服务器，使用本地版本")
                return
            
            local_version = update_module.读取本地版本()
            server_ver = server_version.get("version", "0.0.0")
            local_ver = local_version.get("version", "0.0.0")
            
            # 比较文件哈希，找出需要更新的文件
            # 即使版本号相同也要检查，以确保文件完整性
            server_files = server_version.get("files", {})
            local_files = local_version.get("files", {})
            
            # 判断是否为打包环境
            is_frozen = getattr(sys, 'frozen', False)
            
            需要更新 = []
            for file_path, file_info in server_files.items():
                # 打包环境下，跳过 .py 文件，只下载 .pyc 文件
                if is_frozen and file_path.endswith('.py'):
                    # 检查是否有对应的 .pyc 文件
                    pyc_path = file_path.replace('.py', '.pyc')
                    if pyc_path in server_files:
                        # 有对应的 .pyc，跳过 .py 文件
                        continue
                
                server_hash = file_info.get("hash", "")
                full_path = os.path.join(self.scripts_dir, file_path)
                # 转换为 Path 对象，因为 计算文件哈希 需要 Path 对象
                full_path_obj = Path(full_path)
                actual_hash = update_module.计算文件哈希(full_path_obj) if os.path.exists(full_path) else ""
                
                if server_hash != actual_hash:
                    需要更新.append({
                        "path": file_path,
                        "url": file_info.get("url", f"{update_module.UPDATE_SERVER}/files/{file_path}"),
                        "hash": server_hash,
                        "size": file_info.get("size", 0)
                    })
            
            if not 需要更新:
                if server_ver == local_ver:
                    self._log(f"[Bootstrap] ✓ 已是最新版本 (v{local_ver})")
                else:
                    self._log(f"[Bootstrap] ✓ 所有文件已是最新 (v{local_ver})")
                return
            
            # 发现更新
            if server_ver != local_ver:
                self._log(f"[Bootstrap] 发现新版本: v{local_ver} → v{server_ver}")
            else:
                self._log(f"[Bootstrap] 发现文件更新 (版本 v{local_ver})")
            
            # 下载更新
            self._log(f"[Bootstrap] 开始下载 {len(需要更新)} 个文件...")
            
            成功数 = 0
            跳过数 = 0
            失败数 = 0
            for file_info in 需要更新:
                file_path = file_info["path"]
                url = file_info["url"]
                expected_hash = file_info["hash"]
                
                full_path = os.path.join(self.scripts_dir, file_path)
                
                # 下载文件 - 转换为 Path 对象
                if update_module.下载并编译文件(url, Path(full_path)):
                    # 验证哈希 - 转换为 Path 对象
                    # 如果是 .py 文件，实际下载的是 .pyc，所以要检查 .pyc 的哈希
                    if file_path.endswith('.py') and is_frozen:
                        # 打包环境下，检查 .pyc 文件
                        pyc_path = file_path.replace('.py', '.pyc')
                        pyc_full_path = os.path.join(self.scripts_dir, pyc_path)
                        if os.path.exists(pyc_full_path):
                            # 检查 .pyc 文件的哈希（如果 version.json 中有）
                            pyc_info = server_files.get(pyc_path)
                            if pyc_info:
                                pyc_hash = pyc_info.get("hash", "")
                                actual_hash = update_module.计算文件哈希(Path(pyc_full_path))
                                if actual_hash == pyc_hash:
                                    self._log(f"[Bootstrap] ✓ 更新成功: {pyc_path}")
                                    成功数 += 1
                                else:
                                    self._log(f"[Bootstrap] ✗ 哈希校验失败: {pyc_path}")
                                    失败数 += 1
                            else:
                                # version.json 中没有 .pyc 的哈希，跳过验证
                                self._log(f"[Bootstrap] ✓ 更新成功: {pyc_path} (跳过哈希验证)")
                                成功数 += 1
                        else:
                            self._log(f"[Bootstrap] ⚠ .pyc 文件不存在，跳过: {file_path}")
                            跳过数 += 1
                    else:
                        # 非 .py 文件或开发环境，正常验证
                        full_path_obj = Path(full_path)
                        actual_hash = update_module.计算文件哈希(full_path_obj)
                        if actual_hash == expected_hash:
                            self._log(f"[Bootstrap] ✓ 更新成功: {file_path}")
                            成功数 += 1
                        else:
                            self._log(f"[Bootstrap] ✗ 哈希校验失败: {file_path}")
                            失败数 += 1
                else:
                    # 下载失败
                    if file_path.endswith('.py') and is_frozen:
                        # 打包环境下 .py 文件下载失败（实际是 .pyc 下载失败）
                        # 检查本地是否已有对应的 .pyc 文件
                        pyc_path = file_path.replace('.py', '.pyc')
                        pyc_full_path = os.path.join(self.scripts_dir, pyc_path)
                        if os.path.exists(pyc_full_path):
                            self._log(f"[Bootstrap] ⚠ 下载失败，使用本地版本: {pyc_path}")
                            跳过数 += 1
                        else:
                            self._log(f"[Bootstrap] ✗ 下载失败且本地无文件: {file_path}")
                            失败数 += 1
                    elif file_path.endswith('.pyc') and is_frozen:
                        # .pyc 文件下载失败，检查本地是否已有
                        if os.path.exists(full_path):
                            self._log(f"[Bootstrap] ⚠ 下载失败，使用本地版本: {file_path}")
                            跳过数 += 1
                        else:
                            self._log(f"[Bootstrap] ✗ 下载失败且本地无文件: {file_path}")
                            失败数 += 1
                    else:
                        self._log(f"[Bootstrap] ✗ 下载失败: {file_path}")
                        失败数 += 1
            
            # 更新本地版本信息
            if 成功数 > 0:
                update_module.保存本地版本(server_version)
                if 跳过数 > 0 or 失败数 > 0:
                    self._log(f"[Bootstrap] ✓ 更新完成: {成功数}/{len(需要更新)} 个文件 (跳过 {跳过数} 个, 失败 {失败数} 个)")
                else:
                    self._log(f"[Bootstrap] ✓ 更新完成: {成功数}/{len(需要更新)} 个文件")
            elif 跳过数 > 0:
                # 全部跳过，也算成功（使用本地版本）
                self._log(f"[Bootstrap] ✓ 跳过 {跳过数} 个文件，使用本地版本")
            else:
                self._log(f"[Bootstrap] ✗ 更新失败: {失败数} 个文件下载失败")
                
        except Exception as e:
            self._log(f"[Bootstrap] 更新检查失败: {e}")
            # 更新失败不影响程序运行，继续使用本地版本
    
    def load_main(self, force_reload: bool = False) -> Optional[Any]:
        """
        动态加载 main.py 模块
        :param force_reload: 是否强制重新加载
        :return: main 模块对象
        """
        if self.main_module is not None and not force_reload:
            return self.main_module
        
        # 在加载前先检查更新
        self._check_and_update()
        
        # 查找 main.py 或 main.pyc（优先 .pyc）
        main_file = None
        for ext in ['.pyc', '.py']:
            candidate = os.path.join(self.scripts_dir, f"main{ext}")
            if os.path.exists(candidate):
                main_file = candidate
                break
        
        if main_file is None:
            self._log(f"[Bootstrap] 错误: 找不到 main.py 或 main.pyc")
            self._log(f"[Bootstrap] 请确保文件存在于: {self.scripts_dir}")
            return None
        
        try:
            self._log(f"[Bootstrap] 加载主控制器: {main_file}")
            
            # 将 scripts_dir 添加到 Python 模块搜索路径
            # 这样 main.py 中的 "from tasks import ..." 才能正常工作
            if self.scripts_dir not in sys.path:
                sys.path.insert(0, self.scripts_dir)
                self._log(f"[Bootstrap] 已添加到模块搜索路径: {self.scripts_dir}")
            
            if main_file.endswith('.pyc'):
                # 加载 .pyc 字节码
                import marshal
                module = type(sys)('automation_main')
                # 设置必要的模块属性
                module.__file__ = main_file
                module.__name__ = 'automation_main'
                module.__package__ = None
                with open(main_file, 'rb') as f:
                    f.read(16)  # 跳过文件头
                    code = marshal.load(f)
                exec(code, module.__dict__)
            else:
                # 加载 .py 源文件
                spec = importlib.util.spec_from_file_location("automation_main", main_file)
                if spec is None or spec.loader is None:
                    self._log(f"[Bootstrap] 无法加载模块")
                    return None
                module = importlib.util.module_from_spec(spec)
                sys.modules['automation_main'] = module
                spec.loader.exec_module(module)
            
            self.main_module = module
            self._controller = None  # 清除缓存的控制器
            self._log(f"[Bootstrap] ✓ 主控制器加载成功")
            return module
            
        except Exception as e:
            self._log(f"[Bootstrap] 加载失败: {e}")
            import traceback
            self._log(traceback.format_exc())
            return None
    
    def get_controller(self, force_reload: bool = False):
        """
        获取主控制器实例
        :param force_reload: 是否强制重新加载
        :return: AutomationController 实例
        """
        if force_reload:
            self._controller = None
            self.main_module = None
        
        if self._controller is not None:
            return self._controller
        
        module = self.load_main(force_reload)
        if module is None:
            return None
        
        # 获取控制器类或实例
        if hasattr(module, 'controller'):
            self._controller = module.controller
        elif hasattr(module, 'AutomationController'):
            self._controller = module.AutomationController()
        elif hasattr(module, 'get_controller'):
            self._controller = module.get_controller()
        else:
            self._log(f"[Bootstrap] 警告: main.py 中没有找到控制器")
            return None
        
        return self._controller
    
    def reload(self):
        """重新加载主控制器（热更新）"""
        self._log(f"[Bootstrap] 重新加载主控制器...")
        return self.get_controller(force_reload=True)
    
    def execute_task(self, browser_id: str, task_name: str, params: dict = None):
        """
        执行任务（代理到主控制器）
        """
        controller = self.get_controller()
        if controller is None:
            return {"success": False, "error": "主控制器未加载"}
        
        if hasattr(controller, 'execute_task'):
            return controller.execute_task(browser_id, task_name, params or {})
        else:
            return {"success": False, "error": "控制器没有 execute_task 方法"}
    
    def get_available_tasks(self):
        """获取可用任务列表"""
        controller = self.get_controller()
        if controller and hasattr(controller, 'get_available_tasks'):
            return controller.get_available_tasks()
        return []
    
    def check_connection(self):
        """检查浏览器连接"""
        controller = self.get_controller()
        if controller and hasattr(controller, 'check_browser_connection'):
            return controller.check_browser_connection()
        return False


# 全局启动器实例
bootstrap = AutomationBootstrap()
