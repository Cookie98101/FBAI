import sys
import os
import random
import math
import json
import requests
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta

# ============ QtWebEngine配置（必须在最开始设置）============
# 必须在任何Qt组件导入之前设置，否则QtWebEngine会报错
from PyQt5.QtCore import Qt, QCoreApplication
# 禁用GPU加速，解决部分环境（如远程桌面、特定显卡）下的白屏问题
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --no-sandbox"
# 同时也尝试设置软件渲染属性
QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

# 设置环境变量以确保GUI能正常显示
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = ''

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QGridLayout, QMessageBox, QGraphicsDropShadowEffect,
                             QTabWidget, QProgressBar, QTextEdit, QFormLayout, QSpinBox, QLineEdit,
                             QSizePolicy, QLayout, QFrame, QScrollArea, QCheckBox)
from PyQt5.QtCore import Qt, QTimer, QRect, QRectF, QPointF, QPropertyAnimation, QEasingCurve, pyqtSignal, pyqtSlot, QSize, QThread, QMetaObject, QObject, Q_ARG
from PyQt5.QtCore import Qt as QtCore_Qt
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush, QLinearGradient, QRadialGradient, QGradient, QPainterPath, QPixmap, QPolygonF, QPalette, QTransform, QFontMetrics, QIcon, QStandardItem, QStandardItemModel, QDesktopServices

# 注意：QtWebEngineWidgets 必须在 QApplication 创建之后才能导入
# 所以不在这里导入，而是在需要时动态导入

# 导入后台服务
from backend_service import start_backend_service

# 导入用户认证模块
from auth_client import AuthClient, AuthDialog

# 导入自定义视频预览控件
from video_preview_widget import VideoPreviewWidget, VideoPreviewContainer

# 导入旋转地球组件
from globe_widget import RotatingGlobe

# 导入 UI 线程管理器（Phase 2&3: 账号切换异步化 + 主线程保护）
from ui_worker_threads import init_thread_manager

# 导入比特浏览器API
try:
    from bitbrowser_api import BitBrowserAPI, bit_browser
    BITBROWSER_AVAILABLE = True
except ImportError:
    BITBROWSER_AVAILABLE = False
    print("警告: 无法导入bitbrowser_api模块")

# 导入自动化启动器（支持热更新）
try:
    from automation.bootstrap import bootstrap as automation_bootstrap
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False
    automation_bootstrap = None
    print("警告: 无法导入automation模块")

# 尝试导入路由管理器
try:
    from route_manager import route_manager, get_endpoint, get_method
    ROUTES_AVAILABLE = True
except ImportError:
    ROUTES_AVAILABLE = False
    print("警告: 无法导入route_manager模块")
    # 创建一个模拟的路由管理器
    class MockRouteManager:
        def get_endpoint(self, name):
            return f"/{name}"
        def get_method(self, name):
            return "GET" if name.startswith("get") else "POST"
    route_manager = MockRouteManager()
    get_endpoint = route_manager.get_endpoint
    get_method = route_manager.get_method

# ============ 调试面板相关代码（内联以避免打包依赖问题）============

# 尝试导入 pynput（快捷键监听）
try:
    from pynput import keyboard as pynput_keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    pynput_keyboard = None
    print("警告: 无法导入pynput模块，快捷键功能不可用")

import threading


def _get_debug_scripts_base_dir():
    """获取脚本基础目录（兼容打包和开发环境）"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
        scripts_dir = os.path.join(base, '_internal', 'automation', 'scripts')
        if os.path.exists(scripts_dir):
            return scripts_dir
        scripts_dir = os.path.join(base, 'automation', 'scripts')
        if os.path.exists(scripts_dir):
            return scripts_dir
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'automation', 'scripts')


def _get_debug_config_file():
    """获取调试配置文件路径"""
    scripts_dir = _get_debug_scripts_base_dir()
    return os.path.join(scripts_dir, "脚本配置", "debug_config.json")


def _set_debug_browser_id(browser_id: str) -> bool:
    """设置调试浏览器ID"""
    try:
        config_file = _get_debug_config_file()
        config_dir = os.path.dirname(config_file)
        os.makedirs(config_dir, exist_ok=True)
        
        config = {"debug_mode": False, "browser_id": browser_id, "script_name": None, "timestamp": None}
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        
        config["browser_id"] = browser_id
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"[DebugConfig] ✓ 浏览器ID已保存: {browser_id}")
        return True
    except Exception as e:
        print(f"[DebugConfig] ❌ 设置浏览器ID失败: {e}")
        return False


class SimpleHotkeyListener:
    """简化版快捷键监听器（内联版本）"""
    
    def __init__(self, callback, hotkey_combo: str = "ctrl+shift+d"):
        self.callback = callback
        self.hotkey_combo = hotkey_combo.lower()
        self.listener = None
        self.is_running = False
        self.thread = None
        self.required_keys = set()
        self.pressed_keys = set()
        self._parse_hotkey()
    
    def _parse_hotkey(self):
        """解析快捷键组合"""
        parts = self.hotkey_combo.split('+')
        for part in parts:
            self.required_keys.add(part.strip().lower())
        print(f"[HotkeyListener] 快捷键组合: {self.hotkey_combo}, 需要的键: {self.required_keys}")
    
    def start(self):
        """启动快捷键监听"""
        if not PYNPUT_AVAILABLE:
            print("[HotkeyListener] 错误: pynput未安装")
            return False
        
        if self.is_running:
            return False
        
        try:
            self.is_running = True
            
            def listen():
                try:
                    with pynput_keyboard.Listener(on_press=self._on_press, on_release=self._on_release) as listener:
                        self.listener = listener
                        print("[HotkeyListener] 监听器已启动")
                        listener.join()
                except Exception as e:
                    print(f"[HotkeyListener] 监听异常: {e}")
                finally:
                    self.is_running = False
            
            self.thread = threading.Thread(target=listen, daemon=True)
            self.thread.start()
            print(f"[HotkeyListener] 快捷键监听已启动 ({self.hotkey_combo})")
            return True
        except Exception as e:
            print(f"[HotkeyListener] 启动失败: {e}")
            self.is_running = False
            return False
    
    def _on_press(self, key):
        """按键按下事件"""
        try:
            key_name = None
            if hasattr(key, 'char') and key.char:
                key_name = key.char.lower()
            elif hasattr(key, 'name'):
                key_name = key.name.lower()
            else:
                return
            
            # 处理控制字符
            control_char_map = {
                '\x01': 'a', '\x02': 'b', '\x03': 'c', '\x04': 'd', '\x05': 'e',
                '\x06': 'f', '\x07': 'g', '\x08': 'h', '\x09': 'i', '\x0a': 'j',
                '\x0b': 'k', '\x0c': 'l', '\x0d': 'm', '\x0e': 'n', '\x0f': 'o',
                '\x10': 'p', '\x11': 'q', '\x12': 'r', '\x13': 's', '\x14': 't',
                '\x15': 'u', '\x16': 'v', '\x17': 'w', '\x18': 'x', '\x19': 'y', '\x1a': 'z',
            }
            if key_name in control_char_map:
                key_name = control_char_map[key_name]
            
            # 特殊键名映射
            key_mapping = {'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl', 'shift_l': 'shift', 'shift_r': 'shift',
                          'alt_l': 'alt', 'alt_r': 'alt', 'cmd': 'cmd', 'cmd_l': 'cmd', 'cmd_r': 'cmd'}
            if key_name in key_mapping:
                key_name = key_mapping[key_name]
            
            self.pressed_keys.add(key_name)
            
            if self.required_keys.issubset(self.pressed_keys):
                print(f"[HotkeyListener] ✓ 快捷键被触发: {self.hotkey_combo}")
                try:
                    self.callback()
                except Exception as e:
                    print(f"[HotkeyListener] 回调异常: {e}")
        except Exception as e:
            print(f"[HotkeyListener] on_press异常: {e}")
    
    def _on_release(self, key):
        """按键释放事件"""
        try:
            key_name = None
            if hasattr(key, 'char') and key.char:
                key_name = key.char.lower()
            elif hasattr(key, 'name'):
                key_name = key.name.lower()
            else:
                return
            
            control_char_map = {
                '\x01': 'a', '\x02': 'b', '\x03': 'c', '\x04': 'd', '\x05': 'e',
                '\x06': 'f', '\x07': 'g', '\x08': 'h', '\x09': 'i', '\x0a': 'j',
                '\x0b': 'k', '\x0c': 'l', '\x0d': 'm', '\x0e': 'n', '\x0f': 'o',
                '\x10': 'p', '\x11': 'q', '\x12': 'r', '\x13': 's', '\x14': 't',
                '\x15': 'u', '\x16': 'v', '\x17': 'w', '\x18': 'x', '\x19': 'y', '\x1a': 'z',
            }
            if key_name in control_char_map:
                key_name = control_char_map[key_name]
            
            key_mapping = {'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl', 'shift_l': 'shift', 'shift_r': 'shift',
                          'alt_l': 'alt', 'alt_r': 'alt', 'cmd': 'cmd', 'cmd_l': 'cmd', 'cmd_r': 'cmd'}
            if key_name in key_mapping:
                key_name = key_mapping[key_name]
            
            self.pressed_keys.discard(key_name)
        except:
            pass
    
    def stop(self):
        """停止监听"""
        if self.listener:
            self.listener.stop()
        self.is_running = False


class DebugBrowserLoader(QObject):
    """浏览器列表加载器"""
    loaded = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def run(self):
        try:
            if BITBROWSER_AVAILABLE:
                api = BitBrowserAPI()
                result = api.get_browser_list(page=0, page_size=100)
                browsers_list = []
                if result.get("success"):
                    browsers = result.get("data", {}).get("list", [])
                    
                    # 获取所有浏览器的运行状态（使用PID接口）
                    browser_ids = [b.get("id") for b in browsers if b.get("id")]
                    running_browsers = set()
                    
                    try:
                        pids_result = api.get_alive_browser_pids(browser_ids)
                        if pids_result.get("success"):
                            running_pids = pids_result.get("data", {})
                            running_browsers = set(running_pids.keys())
                    except:
                        pass
                    
                    for browser in browsers:
                        browser_id = browser.get("id")
                        browser_name = browser.get("name", "未命名")
                        if browser_id:
                            is_online = browser_id in running_browsers
                            browsers_list.append({
                                "id": browser_id, 
                                "name": browser_name,
                                "online": is_online
                            })
                self.loaded.emit(browsers_list)
            else:
                self.error.emit("BitBrowser API不可用")
        except Exception as e:
            self.error.emit(str(e))


class ScriptUpdater(QObject):
    """脚本更新器 - 从服务器下载最新脚本"""
    output_received = pyqtSignal(str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.update_server = "http://43.142.176.53:8805/update_server"
        self.scripts_dir = None
    
    def run(self):
        """执行更新"""
        try:
            self._log("正在检查脚本目录...")
            
            # 获取脚本目录
            if getattr(sys, 'frozen', False):
                # 打包后的exe环境
                base_path = os.path.dirname(sys.executable)
                self.scripts_dir = os.path.join(base_path, "_internal", "automation", "scripts")
            else:
                # 开发环境
                base_path = os.path.dirname(os.path.abspath(__file__))
                self.scripts_dir = os.path.join(base_path, "automation", "scripts")
            
            if not os.path.exists(self.scripts_dir):
                self._log(f"❌ 脚本目录不存在: {self.scripts_dir}")
                self.finished.emit(1)
                return
            
            self._log(f"✓ 脚本目录: {self.scripts_dir}")
            
            # 获取服务器版本信息
            self._log("正在连接更新服务器...")
            version_url = f"{self.update_server}/api/version.php"
            
            try:
                import requests
                response = requests.get(version_url, timeout=10)
                if response.status_code != 200:
                    self._log(f"❌ 服务器响应错误: HTTP {response.status_code}")
                    self.finished.emit(1)
                    return
                
                server_data = response.json()
                self._log(f"✓ 服务器版本: {server_data.get('version', '未知')}")
                
            except Exception as e:
                self._log(f"❌ 连接服务器失败: {e}")
                self.finished.emit(1)
                return
            
            # 读取本地版本
            version_file = os.path.join(self.scripts_dir, "version.json")
            local_version = "0.0.0"
            local_files = {}
            
            if os.path.exists(version_file):
                try:
                    import json
                    with open(version_file, 'r', encoding='utf-8') as f:
                        local_data = json.load(f)
                        local_version = local_data.get('version', '0.0.0')
                        local_files = local_data.get('files', {})
                    self._log(f"本地版本: {local_version}")
                except:
                    self._log("本地版本文件读取失败，将全量更新")
            else:
                self._log("本地版本文件不存在，将全量更新")
            
            # 比较文件并下载更新
            server_files = server_data.get('files', {})
            updated_count = 0
            failed_count = 0
            
            self._log(f"\n开始检查 {len(server_files)} 个文件...")
            
            for file_path, file_info in server_files.items():
                server_hash = file_info.get('hash', '')
                local_hash = local_files.get(file_path, {}).get('hash', '')
                
                # 检查是否需要更新
                if server_hash and server_hash == local_hash:
                    continue  # 文件未变化，跳过
                
                # 下载文件
                file_url = f"{self.update_server}/files/{file_path}"
                local_file_path = os.path.join(self.scripts_dir, file_path.replace('/', os.sep))
                
                self._log(f"下载: {file_path}")
                
                try:
                    response = requests.get(file_url, timeout=30)
                    if response.status_code == 200:
                        # 确保目录存在
                        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                        
                        # 保存文件
                        with open(local_file_path, 'wb') as f:
                            f.write(response.content)
                        
                        self._log(f"  ✓ 下载成功")
                        updated_count += 1
                    else:
                        self._log(f"  ✗ 下载失败: HTTP {response.status_code}")
                        failed_count += 1
                except Exception as e:
                    self._log(f"  ✗ 下载失败: {e}")
                    failed_count += 1
            
            # 更新本地版本文件
            if updated_count > 0:
                try:
                    import json
                    with open(version_file, 'w', encoding='utf-8') as f:
                        json.dump(server_data, f, ensure_ascii=False, indent=2)
                    self._log(f"\n✓ 版本文件已更新")
                except Exception as e:
                    self._log(f"\n⚠ 版本文件更新失败: {e}")
            
            # 输出统计
            self._log(f"\n更新统计:")
            self._log(f"  - 检查文件: {len(server_files)} 个")
            self._log(f"  - 更新成功: {updated_count} 个")
            self._log(f"  - 更新失败: {failed_count} 个")
            self._log(f"  - 无需更新: {len(server_files) - updated_count - failed_count} 个")
            
            if failed_count > 0:
                self.finished.emit(1)
            else:
                self.finished.emit(0)
                
        except Exception as e:
            self._log(f"❌ 更新异常: {e}")
            import traceback
            self._log(traceback.format_exc())
            self.error.emit(str(e))
            self.finished.emit(1)
    
    def _log(self, message):
        """输出日志"""
        self.output_received.emit(message)


class DebugScriptRunner(QObject):
    """脚本执行器 - 在当前进程中执行脚本（不需要外部Python环境）"""
    output_received = pyqtSignal(str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)
    
    def __init__(self, script_path, browser_id):
        super().__init__()
        self.script_path = script_path
        self.browser_id = browser_id
        self._is_running = False
        self._original_stdout = None
        self._original_stderr = None
    
    def _setup_paths(self):
        """设置 sys.path，确保脚本能导入所需模块"""
        paths_to_add = []
        
        # 脚本所在目录 (tasks/)
        script_dir = os.path.dirname(self.script_path)
        paths_to_add.append(script_dir)  # 添加 tasks 目录本身
        
        # scripts 目录 (automation/scripts/) - 这是包的根目录
        scripts_dir = os.path.dirname(script_dir)
        
        # automation 目录
        automation_dir = os.path.dirname(scripts_dir)
        paths_to_add.append(automation_dir)
        paths_to_add.append(scripts_dir)
        
        # 项目根目录
        project_root = os.path.dirname(automation_dir)
        paths_to_add.append(project_root)
        
        if getattr(sys, 'frozen', False):
            # 打包环境：添加 _internal 目录
            exe_dir = os.path.dirname(sys.executable)
            internal_dir = os.path.join(exe_dir, '_internal')
            if os.path.exists(internal_dir):
                paths_to_add.append(internal_dir)
                # 也添加 _internal/automation/scripts
                internal_scripts = os.path.join(internal_dir, 'automation', 'scripts')
                if os.path.exists(internal_scripts):
                    paths_to_add.append(internal_scripts)
                    # 添加 _internal/automation/scripts/tasks
                    internal_tasks = os.path.join(internal_scripts, 'tasks')
                    if os.path.exists(internal_tasks):
                        paths_to_add.append(internal_tasks)
        
        # 添加到 sys.path（必须在脚本执行前完成）
        for path in paths_to_add:
            if path not in sys.path:
                sys.path.insert(0, path)
        
        return paths_to_add
    
    def run(self):
        """在当前进程中执行脚本"""
        self._is_running = True
        return_code = 0
        
        try:
            # 设置环境变量
            os.environ['DEBUG_BROWSER_ID'] = self.browser_id
            
            # 设置路径
            paths = self._setup_paths()
            self.output_received.emit(f"[路径设置] 已添加 {len(paths)} 个路径到 sys.path")
            
            # 关键修复：预先导入 tasks 包及常用子模块
            try:
                import tasks
                # 预导入常用的子模块，让它们在 sys.modules 中可用
                try:
                    import tasks.去重管理
                except:
                    pass
                try:
                    import tasks.自动化工具
                except:
                    pass
                try:
                    import tasks.辅助_进入公共主页
                except:
                    pass
                self.output_received.emit(f"[模块预加载] tasks 包及子模块已加载")
            except ImportError as e:
                self.output_received.emit(f"[警告] 无法预加载 tasks 包: {e}")
            
            # 读取脚本内容
            if not os.path.exists(self.script_path):
                self.error.emit(f"脚本文件不存在: {self.script_path}")
                self.finished.emit(1)
                return
            
            # 检查是否是 .pyc 文件（需要特殊处理）
            is_pyc = self.script_path.endswith('.pyc')
            script_content = None
            
            if not is_pyc:
                # .py 文件：尝试多种编码读取
                for encoding in ['utf-8', 'gbk', 'latin-1']:
                    try:
                        with open(self.script_path, 'r', encoding=encoding) as f:
                            script_content = f.read()
                        break
                    except UnicodeDecodeError:
                        continue
                
                if script_content is None:
                    self.error.emit(f"无法读取脚本文件（编码错误）: {self.script_path}")
                    self.finished.emit(1)
                    return
            
            # 创建输出捕获器（模拟文件对象接口）
            class OutputCapture:
                def __init__(self, signal, original):
                    self.signal = signal
                    self.original = original
                    self._buffer = ""  # 内部缓冲区
                    self.encoding = 'utf-8'
                    self.errors = 'replace'
                
                def write(self, text):
                    if text:
                        # 发送到原始输出（控制台）
                        if self.original:
                            try:
                                self.original.write(text)
                            except:
                                pass
                        # 发送到信号（UI）
                        self._buffer += str(text)
                        while '\n' in self._buffer:
                            line, self._buffer = self._buffer.split('\n', 1)
                            if line.strip():
                                self.signal.emit(line)
                
                def flush(self):
                    if self._buffer.strip():
                        self.signal.emit(self._buffer.strip())
                        self._buffer = ""
                    if self.original:
                        try:
                            self.original.flush()
                        except:
                            pass
                
                def isatty(self):
                    return False
                
                def readable(self):
                    return False
                
                def writable(self):
                    return True
                
                def seekable(self):
                    return False
            
            # 重定向输出
            self._original_stdout = sys.stdout
            self._original_stderr = sys.stderr
            capture = OutputCapture(self.output_received, self._original_stdout)
            sys.stdout = capture
            sys.stderr = capture
            
            try:
                # 对于 .pyc 文件，使用 importlib 动态导入
                if is_pyc:
                    import importlib.util
                    import importlib.machinery
                    
                    # 生成模块名（基于文件名）
                    module_name = os.path.splitext(os.path.basename(self.script_path))[0]
                    
                    # 使用 SourcelessFileLoader 加载 .pyc 文件
                    loader = importlib.machinery.SourcelessFileLoader(module_name, self.script_path)
                    spec = importlib.util.spec_from_loader(module_name, loader)
                    
                    if spec is None:
                        raise ImportError(f"无法创建模块规范: {self.script_path}")
                    
                    module = importlib.util.module_from_spec(spec)
                    
                    # 将模块添加到 sys.modules（避免重复导入）
                    sys.modules[module_name] = module
                    
                    # 执行模块
                    spec.loader.exec_module(module)
                    
                    return_code = 0
                    
                else:
                    # 对于 .py 文件，使用原来的 exec 方式
                    # 创建脚本的全局命名空间
                    script_globals = {
                        '__name__': '__main__',
                        '__file__': self.script_path,
                        '__builtins__': __builtins__,
                    }
                    
                    # 关键修复：将已导入的 tasks 模块注入到脚本的命名空间
                    # 这样脚本中的 from tasks.xxx import yyy 就能找到模块了
                    if 'tasks' in sys.modules:
                        script_globals['tasks'] = sys.modules['tasks']
                        # 同时注入所有 tasks 的子模块
                        for module_name, module in sys.modules.items():
                            if module_name.startswith('tasks.'):
                                script_globals[module_name] = module
                    
                    # 执行脚本
                    exec(compile(script_content, self.script_path, 'exec'), script_globals)
                    
                    return_code = 0
                
            except SystemExit as e:
                # 脚本调用了 sys.exit()
                return_code = e.code if isinstance(e.code, int) else 0
            except Exception as e:
                import traceback
                error_msg = traceback.format_exc()
                self.output_received.emit(f"❌ 脚本执行错误:\n{error_msg}")
                return_code = 1
            finally:
                # 恢复输出
                capture.flush()
                sys.stdout = self._original_stdout
                sys.stderr = self._original_stderr
            
            self.finished.emit(return_code)
            
        except Exception as e:
            import traceback
            self.error.emit(f"执行器错误: {e}\n{traceback.format_exc()}")
            self.finished.emit(1)
        finally:
            self._is_running = False
    
    def stop(self):
        """停止执行（注意：exec 方式无法真正中断）"""
        self._is_running = False
        # 恢复输出
        if self._original_stdout:
            sys.stdout = self._original_stdout
        if self._original_stderr:
            sys.stderr = self._original_stderr


class DebugSidebar(QFrame):
    """调试侧边栏（内联版本）"""
    script_executed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scripts_dict = {}
        self.browsers_list = []
        self.is_expanded = False
        self.runner_thread = None
        self.runner = None
        self.browser_loader_thread = None
        self.browser_loader = None
        self._browsers_loaded = False
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        
        self.setStyleSheet("""
            DebugSidebar { background-color: #1a1f2e; border-left: 1px solid #2a3f5f; }
            QLabel { color: #c9d1d9; font-size: 11px; background-color: transparent; }
            QComboBox { background-color: #161b22; color: #c9d1d9; border: 1px solid #30363d; border-radius: 4px; padding: 4px; font-size: 10px; }
            QPushButton { background-color: #0d6efd; color: white; border: none; border-radius: 4px; padding: 6px 12px; font-size: 10px; font-weight: bold; }
            QPushButton:hover { background-color: #0b5ed7; }
            QTextEdit { background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 4px; font-size: 9px; font-family: Courier; }
        """)
        
        self._load_scripts()
        self._init_ui()
        self.setMaximumWidth(0)
        self.setMinimumWidth(0)
        self.setVisible(True)
    
    def _load_scripts(self):
        """加载脚本列表"""
        try:
            tasks_dir = os.path.join(_get_debug_scripts_base_dir(), "tasks")
            if not os.path.exists(tasks_dir):
                print(f"[DebugSidebar] tasks目录不存在: {tasks_dir}")
                return
            
            script_files = {}  # 用于去重：{脚本名: 文件路径}
            
            # 收集所有脚本文件
            for filename in os.listdir(tasks_dir):
                if not filename.startswith('__') and not filename.startswith('.'):
                    if filename.endswith('.py'):
                        script_name = filename[:-3]  # 去掉 .py
                        script_path = os.path.join(tasks_dir, filename)
                        script_files[script_name] = script_path
                    elif filename.endswith('.pyc'):
                        script_name = filename[:-4]  # 去掉 .pyc
                        script_path = os.path.join(tasks_dir, filename)
                        # 如果没有 .py 文件，才使用 .pyc
                        if script_name not in script_files:
                            script_files[script_name] = script_path
            
            if script_files:
                self.scripts_dict = script_files
                print(f"[DebugSidebar] ✓ 加载 {len(self.scripts_dict)} 个脚本")
            else:
                print(f"[DebugSidebar] ⚠ 未找到脚本文件")
        except Exception as e:
            print(f"[DebugSidebar] 加载脚本异常: {e}")
            import traceback
            traceback.print_exc()
    
    def _load_browsers(self):
        """异步加载浏览器列表"""
        if self._browsers_loaded or (self.browser_loader_thread and self.browser_loader_thread.isRunning()):
            return
        
        self.browser_loader_thread = QThread()
        self.browser_loader = DebugBrowserLoader()
        self.browser_loader.moveToThread(self.browser_loader_thread)
        self.browser_loader_thread.started.connect(self.browser_loader.run)
        self.browser_loader.loaded.connect(self._on_browsers_loaded)
        self.browser_loader.error.connect(self._on_browsers_error)
        self.browser_loader_thread.start()
    
    def _on_browsers_loaded(self, browsers_list):
        self.browsers_list = browsers_list
        self._browsers_loaded = True
        self.browser_combo.clear()
        if browsers_list:
            for browser in browsers_list:
                # 添加状态指示器：使用 ● 符号，通过文本颜色标记区分
                browser_id = browser['id']
                browser_name = browser['name']
                
                if browser.get('online', False):
                    # 在线：绿色圆点
                    display_text = f"● {browser_id} ({browser_name})"
                    # 设置绿色前景色
                    self.browser_combo.addItem(display_text, browser_id)
                    index = self.browser_combo.count() - 1
                    self.browser_combo.setItemData(index, QColor("#3fb950"), Qt.ForegroundRole)
                else:
                    # 离线：红色圆点
                    display_text = f"● {browser_id} ({browser_name})"
                    # 设置红色前景色
                    self.browser_combo.addItem(display_text, browser_id)
                    index = self.browser_combo.count() - 1
                    self.browser_combo.setItemData(index, QColor("#f85149"), Qt.ForegroundRole)
                
            self.browser_combo.setEnabled(True)
        else:
            self.browser_combo.addItem("没有浏览器")
            self.browser_combo.setEnabled(False)
        self._cleanup_browser_loader()
    
    def _on_browsers_error(self, error_msg):
        print(f"[DebugSidebar] 加载浏览器失败: {error_msg}")
        self.browser_combo.clear()
        self.browser_combo.addItem("加载失败")
        self.browser_combo.setEnabled(False)
        self._cleanup_browser_loader()
    
    def _cleanup_browser_loader(self):
        if self.browser_loader_thread:
            self.browser_loader_thread.quit()
            self.browser_loader_thread.wait(1000)
            self.browser_loader_thread = None
            self.browser_loader = None
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        title = QLabel("🔧 调试面板")
        title.setStyleSheet("font-weight: bold; font-size: 12px; color: #58a6ff;")
        layout.addWidget(title)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: #2a3f5f;")
        layout.addWidget(separator)
        
        layout.addWidget(QLabel("浏览器:"))
        self.browser_combo = QComboBox()
        self.browser_combo.addItem("加载中...")
        self.browser_combo.setEnabled(False)
        layout.addWidget(self.browser_combo)
        
        layout.addWidget(QLabel("脚本:"))
        self.script_combo = QComboBox()
        if self.scripts_dict:
            for script_name in sorted(self.scripts_dict.keys()):
                self.script_combo.addItem(script_name, script_name)
        else:
            self.script_combo.addItem("没有脚本")
            self.script_combo.setEnabled(False)
        layout.addWidget(self.script_combo)
        
        # 按钮布局
        buttons_layout = QHBoxLayout()
        
        run_btn = QPushButton("▶ 运行脚本")
        run_btn.setMinimumHeight(32)
        run_btn.clicked.connect(self._run_script)
        buttons_layout.addWidget(run_btn)
        
        update_btn = QPushButton("🔄 更新脚本")
        update_btn.setMinimumHeight(32)
        update_btn.clicked.connect(self._update_scripts)
        buttons_layout.addWidget(update_btn)
        
        layout.addLayout(buttons_layout)
        
        layout.addWidget(QLabel("执行日志:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(300)
        layout.addWidget(self.log_text, 1)
        
        self.setLayout(layout)
    
    def _run_script(self):
        """运行脚本"""
        if self.runner_thread and self.runner_thread.isRunning():
            self.log_text.append("⚠ 已有脚本正在运行")
            return
        
        if not self.browsers_list or not self.scripts_dict:
            self.log_text.append("❌ 没有可用的浏览器或脚本")
            return
        
        browser_id = self.browser_combo.currentData()
        if not browser_id:
            self.log_text.append("❌ 浏览器ID为空")
            return
        
        script_name = self.script_combo.currentData()
        script_path = self.scripts_dict.get(script_name)
        if not script_path:
            self.log_text.append("❌ 脚本路径不存在")
            return
        
        if script_path.endswith('.pyc'):
            py_path = script_path[:-1]
            if os.path.exists(py_path):
                script_path = py_path
        
        _set_debug_browser_id(browser_id)
        
        self.log_text.clear()
        self.log_text.append(f"▶ 执行: {script_name}")
        self.log_text.append(f"🔑 浏览器ID: {browser_id}")
        self.log_text.append("-" * 40)
        
        self._current_script_name = script_name
        self.runner_thread = QThread()
        self.runner = DebugScriptRunner(script_path, browser_id)
        self.runner.moveToThread(self.runner_thread)
        self.runner_thread.started.connect(self.runner.run)
        self.runner.output_received.connect(self._on_output)
        self.runner.finished.connect(self._on_finished)
        self.runner.error.connect(self._on_error)
        self.runner_thread.start()
    
    def _update_scripts(self):
        """更新脚本"""
        if self.runner_thread and self.runner_thread.isRunning():
            self.log_text.append("⚠ 有脚本正在运行，请等待完成后再更新")
            return
        
        self.log_text.clear()
        self.log_text.append("🔄 开始更新脚本...")
        self.log_text.append("-" * 40)
        
        # 在新线程中执行更新
        self.runner_thread = QThread()
        self.runner = ScriptUpdater()
        self.runner.moveToThread(self.runner_thread)
        self.runner_thread.started.connect(self.runner.run)
        self.runner.output_received.connect(self._on_output)
        self.runner.finished.connect(self._on_update_finished)
        self.runner.error.connect(self._on_error)
        self.runner_thread.start()
    
    def _on_update_finished(self, return_code):
        """更新完成"""
        self.log_text.append("-" * 40)
        if return_code == 0:
            self.log_text.append("✅ 更新完成")
            # 刷新脚本列表
            self._refresh_scripts()
        else:
            self.log_text.append(f"❌ 更新失败 (返回码: {return_code})")
        self._cleanup_thread()
    
    def _refresh_scripts(self):
        """刷新脚本列表"""
        try:
            self.script_combo.clear()
            scripts_base_dir = _get_debug_scripts_base_dir()
            tasks_dir = os.path.join(scripts_base_dir, "tasks")
            
            if os.path.exists(tasks_dir):
                self.scripts_dict = {}
                script_files = {}  # 用于去重：{脚本名: 文件路径}
                
                # 收集所有脚本文件
                for filename in os.listdir(tasks_dir):
                    if not filename.startswith('__') and not filename.startswith('.'):
                        if filename.endswith('.py'):
                            script_name = filename[:-3]  # 去掉 .py
                            script_path = os.path.join(tasks_dir, filename)
                            script_files[script_name] = script_path
                        elif filename.endswith('.pyc'):
                            script_name = filename[:-4]  # 去掉 .pyc
                            script_path = os.path.join(tasks_dir, filename)
                            # 如果没有 .py 文件，才使用 .pyc
                            if script_name not in script_files:
                                script_files[script_name] = script_path
                
                # 按名称排序并添加到下拉框
                if script_files:
                    for script_name in sorted(script_files.keys()):
                        script_path = script_files[script_name]
                        self.scripts_dict[script_name] = script_path
                        self.script_combo.addItem(script_name, script_name)
                    
                    # 启用下拉框
                    self.script_combo.setEnabled(True)
                    self.log_text.append(f"✓ 已刷新脚本列表，共 {len(self.scripts_dict)} 个脚本")
                else:
                    self.script_combo.addItem("没有脚本")
                    self.script_combo.setEnabled(False)
                    self.log_text.append("⚠ 未找到脚本文件")
            else:
                self.script_combo.addItem("脚本目录不存在")
                self.script_combo.setEnabled(False)
                self.log_text.append("⚠ 脚本目录不存在")
        except Exception as e:
            self.log_text.append(f"❌ 刷新脚本列表失败: {e}")
            import traceback
            self.log_text.append(traceback.format_exc())
    
    def _on_output(self, line):
        self.log_text.append(line)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
    
    def _on_finished(self, return_code):
        self.log_text.append("-" * 40)
        if return_code == 0:
            self.log_text.append("✅ 执行完成")
            self.script_executed.emit(self._current_script_name)
        else:
            self.log_text.append(f"❌ 执行失败 (返回码: {return_code})")
        self._cleanup_thread()
    
    def _on_error(self, error_msg):
        self.log_text.append(f"❌ 异常: {error_msg}")
        self._cleanup_thread()
    
    def _cleanup_thread(self):
        if self.runner_thread:
            self.runner_thread.quit()
            self.runner_thread.wait(1000)
            self.runner_thread = None
            self.runner = None
    
    def toggle_sidebar(self):
        """切换侧边栏"""
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()
    
    def expand(self):
        """展开"""
        if self.is_expanded:
            return
        self.is_expanded = True
        if not self._browsers_loaded:
            self._load_browsers()
        
        self.animation = QPropertyAnimation(self, b"minimumWidth")
        self.animation.setDuration(300)
        self.animation.setStartValue(0)
        self.animation.setEndValue(320)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        self.max_animation = QPropertyAnimation(self, b"maximumWidth")
        self.max_animation.setDuration(300)
        self.max_animation.setStartValue(0)
        self.max_animation.setEndValue(320)
        self.max_animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        self.animation.start()
        self.max_animation.start()
        print("[DebugSidebar] 侧边栏已展开")
    
    def collapse(self):
        """折叠"""
        if not self.is_expanded:
            return
        self.is_expanded = False
        
        self.animation = QPropertyAnimation(self, b"minimumWidth")
        self.animation.setDuration(300)
        self.animation.setStartValue(320)
        self.animation.setEndValue(0)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        self.max_animation = QPropertyAnimation(self, b"maximumWidth")
        self.max_animation.setDuration(300)
        self.max_animation.setStartValue(320)
        self.max_animation.setEndValue(0)
        self.max_animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        self.animation.start()
        self.max_animation.start()
        print("[DebugSidebar] 侧边栏已折叠")


class DebugIntegration:
    """调试功能集成类（内联版本）"""
    _instance = None
    _listener = None
    _debug_panel = None
    _main_window = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def set_debug_panel(cls, panel, main_window):
        cls._debug_panel = panel
        cls._main_window = main_window
    
    @staticmethod
    def show_debug_panel():
        try:
            if DebugIntegration._debug_panel and hasattr(DebugIntegration._debug_panel, 'toggle_sidebar'):
                DebugIntegration._debug_panel.toggle_sidebar()
                return True
        except Exception as e:
            print(f"[DebugIntegration] 显示面板失败: {e}")
        return False
    
    @staticmethod
    def start_hotkey_listener(hotkey: str = "ctrl+shift+d"):
        if not PYNPUT_AVAILABLE:
            print("[DebugIntegration] pynput不可用，快捷键功能禁用")
            return False
        try:
            listener = SimpleHotkeyListener(DebugIntegration.show_debug_panel, hotkey)
            if listener.start():
                DebugIntegration._listener = listener
                print(f"[DebugIntegration] 快捷键监听已启动 ({hotkey})")
                return True
        except Exception as e:
            print(f"[DebugIntegration] 启动快捷键监听异常: {e}")
        return False


def init_debug_mode(enable_hotkey=True, hotkey="ctrl+shift+d", debug_panel=None, main_window=None):
    """初始化调试模式（内联版本）"""
    debug = DebugIntegration()
    if debug_panel and main_window:
        debug.set_debug_panel(debug_panel, main_window)
    if enable_hotkey:
        return debug.start_hotkey_listener(hotkey)
    return True

# ============ 调试面板代码结束 ============

class AutoVideoGenerationThread(QThread):
    """自动生成视频监控线程"""
    video_generated = pyqtSignal(str)  # 发送生成的视频路径
    generation_failed = pyqtSignal(str)  # 发送生成失败的错误信息
    status_updated = pyqtSignal(str)  # 发送状态更新信息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.video_save_path = ""
        self.min_video_count = 5
        self.check_interval = 30  # 30秒检查一次
        self.dashboard = parent
        
    def set_config(self, video_save_path, min_video_count):
        """设置配置"""
        self.video_save_path = video_save_path
        self.min_video_count = min_video_count
        
    def stop(self):
        """停止监控"""
        self.running = False
        self.quit()
        self.wait()
        
    def run(self):
        """运行监控循环"""
        self.running = True
        print(f"🎬 自动生成视频监控已启动")
        print(f"📁 监控目录: {self.video_save_path}")
        print(f"📊 最小视频数量: {self.min_video_count}")
        print(f"⏱️ 检查间隔: {self.check_interval}秒")
        
        while self.running:
            try:
                # 检查视频数量
                video_count = self.count_videos()
                self.status_updated.emit(f"当前视频数量: {video_count}/{self.min_video_count}")
                
                if video_count < self.min_video_count:
                    print(f"📉 视频数量不足 ({video_count}/{self.min_video_count})，开始生成视频...")
                    self.status_updated.emit(f"视频数量不足，正在生成新视频...")
                    
                    # 异步生成视频，不阻塞UI
                    self.generate_video_async()
                    
                # 等待检查间隔
                for i in range(self.check_interval):
                    if not self.running:
                        break
                    self.msleep(1000)  # 每秒检查一次是否需要停止
                    
            except Exception as e:
                print(f"❌ 自动生成视频监控异常: {e}")
                self.generation_failed.emit(f"监控异常: {e}")
                # 发生异常时等待更长时间再重试
                for i in range(60):  # 等待60秒
                    if not self.running:
                        break
                    self.msleep(1000)
        
        print(f"🛑 自动生成视频监控已停止")
        
    def count_videos(self):
        """统计视频文件数量"""
        try:
            if not os.path.exists(self.video_save_path):
                return 0
                
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
            video_files = []
            
            for file in os.listdir(self.video_save_path):
                if any(file.lower().endswith(ext) for ext in video_extensions):
                    video_files.append(file)
                    
            return len(video_files)
            
        except Exception as e:
            print(f"❌ 统计视频文件失败: {e}")
            return 0
            
    def generate_video_async(self):
        """异步生成视频"""
        success = False  # 初始化success变量
        try:
            self.status_updated.emit("🔄 开始异步视频生成...")
            
            if self.dashboard and hasattr(self.dashboard, 'generate_video_safe'):
                self.status_updated.emit("📞 调用generate_video_safe方法...")
                
                # 创建调试日志
                debug_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_generation_debug.log")
                def debug_log(message):
                    try:
                        with open(debug_log_path, "a", encoding="utf-8") as f:
                            import datetime
                            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                            f.write(f"[{timestamp}] {message}\n")
                            f.flush()
                        print(f"[DEBUG] {message}")  # 同时输出到控制台
                    except:
                        pass
                
                debug_log("🎯 准备调用generate_video_safe方法")
                debug_log(f"📊 dashboard对象: {type(self.dashboard)}")
                debug_log(f"📊 方法存在: {hasattr(self.dashboard, 'generate_video_safe')}")
                
                try:
                    # 使用安全的视频生成方法，确保不会阻塞UI
                    debug_log("🚀 开始调用generate_video_safe...")
                    success = self.dashboard.generate_video_safe()
                    debug_log(f"📊 调用完成，返回值: {success}")
                    debug_log(f"📊 success类型: {type(success)}")
                    debug_log(f"📊 success布尔值: {bool(success)}")
                except Exception as call_error:
                    debug_log(f"❌ 调用generate_video_safe异常: {call_error}")
                    import traceback
                    debug_log(f"📋 异常堆栈: {traceback.format_exc()}")
                    success = False

                debug_log(f"🔍 最终success值: {success}")
                if success:
                    debug_log("✅ 判断为成功，发送成功信号")
                    self.status_updated.emit("✅ 视频生成成功")
                else:
                    debug_log("❌ 判断为失败，发送失败信号")
                    self.status_updated.emit("❌ generate_video_safe返回失败")
                    self.generation_failed.emit("视频生成失败，请检查提示词和网络连接")
            else:
                self.status_updated.emit("❌ 无法访问generate_video_safe方法")
                self.generation_failed.emit("无法访问视频生成功能")
                
        except Exception as e:
            print(f"❌ 异步生成视频失败: {e}")
            import traceback
            error_details = traceback.format_exc()
            self.status_updated.emit(f"❌ 异步生成异常: {str(e)}")
            self.generation_failed.emit(f"生成视频异常: {e}\n详细信息: {error_details}")


class LoadingSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_spinner)
        self.timer.start(50)  # 20 FPS
        self.setFixedSize(50, 50)
        
    def update_spinner(self):
        self.angle = (self.angle + 10) % 360
        self.update()
        
    def paintEvent(self, a0):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        
        # 绘制旋转的线条
        for i in range(12):
            angle = self.angle + i * 30
            alpha = 255 - (i * 20)
            color = QColor(88, 166, 255, alpha)  # 蓝色系
            
            painter.setPen(QPen(color, 3))
            painter.save()
            painter.rotate(angle)
            painter.drawLine(0, -15, 0, -5)
            painter.restore()

class FacebookLogoWidget(QWidget):
    """自定义Facebook Logo控件 - 反向效果（圆形背景为白色50%透明度，字母f是透明的）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)  # logo 设置固定大小，稍微小一点
        
    def paintEvent(self, a0):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 获取控件的矩形区域
        rect = self.rect()
        
        # 绘制圆形背景（白色50%透明度）
        painter.setBrush(QBrush(QColor(255, 255, 255, 128)))  # 50%透明度的白色
        painter.setPen(QtCore_Qt.NoPen)
        painter.drawEllipse(rect)
        
        # 绘制字母"f"（透明效果，通过擦除背景实现）
        # 设置混合模式为擦除
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.setPen(QPen(QtCore_Qt.black, 2))
        # 调整字体大小，使字母"f"在圆形中更合适
        painter.setFont(QFont("Arial", 16, QFont.Bold))  # 减小字体大小
        
        # 计算文字位置，更好地居中
        font_metrics = painter.fontMetrics()
        text_width = font_metrics.horizontalAdvance("f")
        text_height = font_metrics.height()
        
        x = (rect.width() - text_width) // 2
        y = (rect.height() + text_height) // 2 - 1  # 调整垂直位置使其向上移动
        
        # 绘制透明的"f"
        painter.drawText(x, y, "f")

class MarqueeLabel(QLabel):
    """自定义标签类（静态显示，不滚动）"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.original_text = text
        # 设置文本居左对齐
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

class ChartsBackgroundWidget(QWidget):
    """图表统一背景容器"""
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def paintEvent(self, event):
        """绘制简洁的垂直渐变背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 只使用垂直渐变，无星光效果
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(15, 23, 42))    # 深蓝
        gradient.setColorAt(0.5, QColor(18, 25, 45))    # 中层蓝
        gradient.setColorAt(1.0, QColor(13, 17, 23))    # 深黑蓝
        gradient.setSpread(QGradient.PadSpread)
        painter.fillRect(self.rect(), gradient)

class GradientSeparatorLine(QWidget):
    """渐变分割线组件 - 左右两边透明，带文字标签"""
    def __init__(self, label_text="", parent=None):
        super().__init__(parent)
        self.label_text = label_text
        self.setFixedHeight(40)  # 增加高度到40，确保文字有足够空间且不被裁剪
        self.setMinimumWidth(50)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 分割线位置下移，更靠近底部
        line_y = 20  # 从8增加到20，下移12像素
        
        # 创建水平渐变：左边透明 -> 中间不透明 -> 右边透明
        gradient = QLinearGradient(0, 0, width, 0)
        gradient.setColorAt(0.0, QColor(80, 100, 120, 0))      # 左边完全透明
        gradient.setColorAt(0.2, QColor(80, 100, 120, 120))    # 渐入
        gradient.setColorAt(0.5, QColor(80, 100, 120, 150))    # 中间最不透明
        gradient.setColorAt(0.8, QColor(80, 100, 120, 120))    # 渐出
        gradient.setColorAt(1.0, QColor(80, 100, 120, 0))      # 右边完全透明
        
        painter.fillRect(0, line_y, width, 1, gradient)
        
        # 绘制文字标签（左下方）
        if self.label_text:
            # 使用与柱状图柱子相同的蓝色
            painter.setPen(QPen(QColor(88, 166, 255)))
            font = painter.font()
            font.setPointSize(9)  # 增大字体
            font.setBold(False)
            painter.setFont(font)
            # 文字显示在分割线下方，增加与分割线的距离
            painter.drawText(12, line_y + 18, self.label_text)  # 增加距离从13到18，更远离分割线

class BarChartWidget(QWidget):
    """柱状图组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = {}
        self.colors = [
            QColor(88, 166, 255),   # 蓝色
            QColor(255, 107, 129),  # 粉红
            QColor(106, 255, 193),  # 青绿
            QColor(255, 193, 106),  # 橙色
            QColor(193, 106, 255),  # 紫色
            QColor(255, 228, 106),  # 黄色
            QColor(106, 228, 255),  # 天蓝
        ]
        self.hovered_index = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(150)
    
    def set_data(self, data_dict):
        """设置柱状图数据"""
        self.data = data_dict
        self.update()
        
    def paintEvent(self, event):
        """绘制柱状图"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if not self.data:
            return
        
        # 计算柱状图参数
        margin_left = 30
        margin_right = 30
        margin_top = 20
        margin_bottom = 40  # 增加底部边距，为日期标签留空间
        
        bar_area_width = self.width() - margin_left - margin_right
        bar_area_height = self.height() - margin_top - margin_bottom
        
        # 调试信息
        # print(f"柱状图: height={self.height()}, 底边y={self.height() - margin_bottom}")  # 已关闭调试日志
        
        # 绘制背景网格线（等高线）
        max_value = max(self.data.values()) if self.data.values() else 1
        num_grid_lines = 5  # 绘制5条水平网格线
        
        painter.setPen(QPen(QColor(80, 100, 120, 150), 1, Qt.DashLine))  # 更亮的虚线，增加透明度
        for i in range(num_grid_lines + 1):
            y = self.height() - margin_bottom - (bar_area_height * i // num_grid_lines)
            # 绘制水平网格线
            painter.drawLine(margin_left, y, self.width() - margin_right, y)
            
            # 绘制网格线对应的数值标签
            if i > 0:  # 不在底部绘制0
                value = int(max_value * i / num_grid_lines)
                painter.setPen(QPen(QColor(150, 170, 190)))  # 更亮的标签颜色
                font = painter.font()
                font.setPointSize(7)
                painter.setFont(font)
                painter.drawText(5, y - 3, margin_left - 10, 20, Qt.AlignRight | Qt.AlignVCenter, str(value))
                painter.setPen(QPen(QColor(80, 100, 120, 150), 1, Qt.DashLine))  # 恢复网格线画笔
        
        num_bars = len(self.data)
        # 计算柱子宽度，确保左右对称
        # 柱子更宽，间距更小
        # 设间距为s，柱宽为w，则：num_bars * w + (num_bars - 1) * s = bar_area_width
        # 设 w = 2.5s（柱子是间距的2.5倍），则：num_bars * 2.5s + (num_bars - 1) * s = bar_area_width
        # 即：(num_bars * 3.5 - 1) * s = bar_area_width
        spacing = bar_area_width / (num_bars * 3.5 - 1)
        bar_width = int(spacing * 2.5)
        spacing = int(spacing)
        
        # 计算实际使用的总宽度
        total_used_width = num_bars * bar_width + (num_bars - 1) * spacing
        # 计算剩余空间，平均分配到左右
        remaining_space = bar_area_width - total_used_width
        start_offset = remaining_space // 2
        
        # 绘制柱子（从计算出的起始位置开始）
        x = margin_left + start_offset
        for i, (label, value) in enumerate(self.data.items()):
            # 统一使用深蓝色
            base_color = QColor(58, 136, 215)  # 深蓝色
            
            # 计算柱子高度
            bar_height = int((value / max_value) * bar_area_height)
            bar_y = self.height() - margin_bottom - bar_height
            
            # 悬停效果
            if i == self.hovered_index:
                color = base_color.lighter(130)
                bar_width_adjusted = int(bar_width * 1.05)  # 悬停时稍微放大
                x_adjusted = x - (bar_width_adjusted - bar_width) // 2
            else:
                color = base_color
                bar_width_adjusted = bar_width
                x_adjusted = x
            
            # 绘制柱子（渐变效果）
            bar_gradient = QLinearGradient(x_adjusted, bar_y, x_adjusted, bar_y + bar_height)
            bar_gradient.setColorAt(0, color.lighter(115))
            bar_gradient.setColorAt(1, color)
            
            painter.setBrush(QBrush(bar_gradient))
            painter.setPen(Qt.NoPen)
            painter.drawRect(x_adjusted, bar_y, bar_width_adjusted, bar_height)
            
            # 绘制数值（在柱子顶部）
            painter.setPen(QPen(QColor(201, 209, 217)))
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(x, bar_y - 5, bar_width, 20, Qt.AlignCenter, str(int(value)))
            
            # 绘制日期标签（在柱子底部）
            painter.setPen(QPen(QColor(150, 160, 170)))
            font.setPointSize(7)
            painter.setFont(font)
            label_y = self.height() - margin_bottom + 5
            painter.drawText(x - 10, label_y, bar_width + 20, 30, Qt.AlignCenter, label)
            
            x += bar_width + spacing  # 移动到下一个柱子位置
    
    def mouseMoveEvent(self, event):
        """处理鼠标移动"""
        if not self.data:
            return
            
        margin_left = 30
        margin_right = 30
        bar_area_width = self.width() - margin_left - margin_right
        num_bars = len(self.data)
        # 使用与绘制时相同的计算方式
        spacing = bar_area_width / (num_bars * 3.5 - 1)
        bar_width = int(spacing * 2.5)
        spacing = int(spacing)
        
        total_used_width = num_bars * bar_width + (num_bars - 1) * spacing
        remaining_space = bar_area_width - total_used_width
        start_offset = remaining_space // 2
        
        old_index = self.hovered_index
        self.hovered_index = -1
        
        x = margin_left + start_offset
        for i in range(num_bars):
            if x <= event.pos().x() <= x + bar_width:
                self.hovered_index = i
                self.setCursor(Qt.PointingHandCursor)
                break
            x += bar_width + spacing
        
        if self.hovered_index == -1:
            self.setCursor(Qt.ArrowCursor)
        
        if old_index != self.hovered_index:
            self.update()
    
    def leaveEvent(self, event):
        """鼠标离开"""
        if self.hovered_index != -1:
            self.hovered_index = -1
            self.update()

class PieChartWidget(QWidget):
    """3D饼图组件，带鼠标悬停效果和自动播放"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = {}  # 存储饼图数据 {标签: 数值}
        self.colors = [
            QColor(88, 166, 255),   # 蓝色
            QColor(255, 107, 129),  # 粉红
            QColor(106, 255, 193),  # 青绿
            QColor(255, 193, 106),  # 橙色
            QColor(193, 106, 255),  # 紫色
            QColor(255, 228, 106),  # 黄色
            QColor(106, 228, 255),  # 天蓝
        ]
        self.hovered_index = -1  # 当前悬停的扇形索引
        self.auto_highlight_index = 0  # 自动高亮的索引
        self.is_mouse_hovering = False  # 是否有鼠标悬停
        self.setMouseTracking(True)
        self.setMinimumSize(250, 250)
        
        # 自动播放定时器
        self.auto_play_timer = QTimer(self)
        self.auto_play_timer.timeout.connect(self.auto_highlight_next)
        self.auto_play_timer.start(2000)  # 每2秒切换一次
        
    def set_data(self, data_dict):
        """设置饼图数据，过滤掉值为0的项"""
        # 过滤掉值为0的数据项
        self.data = {k: v for k, v in data_dict.items() if v > 0}
        self.auto_highlight_index = 0  # 重置自动高亮索引
        self.update()
    
    def auto_highlight_next(self):
        """自动高亮下一个饼块"""
        if not self.data or self.is_mouse_hovering:
            return  # 如果没有数据或鼠标正在悬停，不执行自动播放
        
        # 切换到下一个索引
        self.auto_highlight_index = (self.auto_highlight_index + 1) % len(self.data)
        self.update()
        
    def paintEvent(self, event):
        """绘制3D饼图"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if not self.data:
            # 如果没有数据，显示提示文字
            painter.setPen(QPen(QColor(150, 150, 150)))
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, "暂无数据")
            return
        
        # 计算总值
        total = sum(self.data.values())
        if total == 0:
            return
        
        # 饼图参数（为突出效果预留空间，调整中心位置）
        center_x = self.width() // 2
        # 优化中心位置，向上移动但要确保底部有足够空间
        center_y = self.height() // 2 - 5  # 向上移动5像素，平衡上下空间，确保悬停时底部不被裁剪
        # 增大半径，使饼图更大更清晰
        radius = int(min(self.width() - 60, self.height() - 70) // 2.5)  # 底部预留空间从60增加到70
        
        # 计算每个扇形的角度
        angles = []
        start_angle = 90 * 16  # 从顶部开始（Qt使用16分之一度）
        
        for i, (label, value) in enumerate(self.data.items()):
            span_angle = int((value / total) * 360 * 16)
            angles.append((start_angle, span_angle, label, i))
            start_angle += span_angle
        
        # 确定当前要高亮的索引（鼠标悬停优先，否则使用自动播放索引）
        highlight_index = self.hovered_index if self.is_mouse_hovering else self.auto_highlight_index
        
        # 绘制所有普通扇形
        for i, (start, span, label, idx) in enumerate(angles):
            if idx == highlight_index:
                continue  # 高亮的扇形最后绘制
            
            color = self.colors[i % len(self.colors)]
            
            # 使用渐变创建3D效果
            gradient = QRadialGradient(center_x, center_y - 5, radius * 0.6)
            gradient.setColorAt(0, color.lighter(130))
            gradient.setColorAt(0.5, color)
            gradient.setColorAt(1, color.darker(120))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)  # 无边框，更高级
            
            rect = QRect(
                center_x - radius,
                center_y - radius,
                radius * 2,
                radius * 2
            )
            painter.drawPie(rect, start, span)
        
        # 最后绘制高亮的扇形，确保它在最上层
        if highlight_index >= 0 and highlight_index < len(angles):
            start, span, label, idx = angles[highlight_index]
            color = self.colors[highlight_index % len(self.colors)]
            
            # 高亮效果：稍微放大
            scale_factor = 1.12  # 放大12%
            hover_radius = int(radius * scale_factor)
            
            # 使用更强的渐变效果
            gradient = QRadialGradient(center_x, center_y - 8, hover_radius * 0.6)
            gradient.setColorAt(0, color.lighter(150))
            gradient.setColorAt(0.5, color.lighter(120))
            gradient.setColorAt(1, color)
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)  # 高亮时也无边框
            
            rect = QRect(
                center_x - hover_radius,
                center_y - hover_radius,
                hover_radius * 2,
                hover_radius * 2
            )
            painter.drawPie(rect, start, span)
            
            # 可选：添加微妙的光晕效果
            glow_gradient = QRadialGradient(center_x, center_y, hover_radius)
            glow_gradient.setColorAt(0, QColor(255, 255, 255, 0))
            glow_gradient.setColorAt(0.7, QColor(255, 255, 255, 0))
            glow_gradient.setColorAt(1, QColor(255, 255, 255, 30))
            painter.setBrush(QBrush(glow_gradient))
            painter.drawPie(rect, start, span)
        
        # 绘制百分比在饼图扇形外侧
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        
        cumulative_angle = 90  # 从顶部开始（度数）
        for i, (label, value) in enumerate(self.data.items()):
            percentage = (value / total) * 100
            span_degrees = (value / total) * 360
            
            # 计算扇形中心角度
            mid_angle = cumulative_angle + span_degrees / 2
            mid_angle_rad = math.radians(mid_angle)
            
            # 计算百分比文字位置（在饼图外侧）
            label_distance = radius + 25  # 距离圆心的距离
            label_x = center_x + label_distance * math.cos(mid_angle_rad)
            label_y = center_y - label_distance * math.sin(mid_angle_rad)  # y轴向下为正
            
            # 绘制百分比
            percentage_text = f"{percentage:.1f}%"
            text_rect = QRect(int(label_x - 30), int(label_y - 10), 60, 20)
            painter.drawText(text_rect, QtCore_Qt.AlignCenter, percentage_text)
            
            cumulative_angle += span_degrees
        
        # 绘制图例（横向排列，只显示标签文字）
        painter.setPen(QPen(QColor(201, 209, 217)))
        font = painter.font()
        font.setPointSize(8)  # 从 9 改为 8
        font.setBold(False)
        painter.setFont(font)
        
        # 横向图例：在饼图下方居中显示（往下移动）
        legend_y = center_y + radius + 40  # 从 30 改为 40
        
        # 计算所有图例项的总宽度以实现居中
        legend_items = list(self.data.items())
        fm = QFontMetrics(font)
        
        # 每个图例项的宽度 = 颜色块(12) + 间距(4) + 文字宽度 + 项间距(12)
        legend_widths = []
        for label, value in legend_items:
            text_width = fm.width(label)
            item_width = 12 + 4 + text_width + 12  # 颜色块 + 间距 + 文字 + 项间距（缩小）
            legend_widths.append(item_width)
        
        total_legend_width = sum(legend_widths) - 12  # 减去最后一项的间距
        legend_start_x = (self.width() - total_legend_width) // 2  # 居中起始位置
        
        current_x = legend_start_x
        for i, (label, value) in enumerate(legend_items):
            color = self.colors[i % len(self.colors)]
            
            # 如果是悬停项或自动高亮项，绘制背景高亮
            is_highlighted = (i == self.hovered_index) or (not self.is_mouse_hovering and i == self.auto_highlight_index)
            
            if is_highlighted:
                painter.fillRect(current_x - 4, legend_y - 2, legend_widths[i], 16, QColor(255, 255, 255, 15))
            
            # 绘制颜色块（缩小）
            if is_highlighted:
                painter.fillRect(current_x - 1, legend_y - 1, 14, 14, color.lighter(120))
            else:
                painter.fillRect(current_x, legend_y, 12, 12, color)
            
            # 绘制文字（只显示标签，不显示百分比）
            text = label
            if is_highlighted:
                painter.setPen(QPen(QColor(255, 255, 255)))
                font_bold = painter.font()
                font_bold.setBold(True)
                painter.setFont(font_bold)
            else:
                painter.setPen(QPen(QColor(201, 209, 217)))
                font_normal = painter.font()
                font_normal.setBold(False)
                painter.setFont(font_normal)
            
            painter.drawText(current_x + 16, legend_y + 10, text)  # 调整文字位置
            
            # 移动到下一个图例项位置
            current_x += legend_widths[i]
    
    def mouseMoveEvent(self, event):
        """处理鼠标移动事件"""
        if not self.data:
            return
        
        # 标记鼠标正在悬停，暂停自动播放
        self.is_mouse_hovering = True
            
        mouse_x = event.pos().x()
        mouse_y = event.pos().y()
        
        # 计算鼠标相对于饼图中心的位置（必须与paintEvent中保持一致）
        center_x = self.width() // 2
        center_y = self.height() // 2 - 5  # 与绘制时保持一致
        radius = int(min(self.width() - 60, self.height() - 70) // 2.5)  # 与绘制时保持一致
        
        # 先检查是否在图例区域（横向）- 使用与绘制相同的计算逻辑
        total = sum(self.data.values())
        legend_y = center_y + radius + 40  # 与绘制时保持一致（从 30 改为 40）
        
        # 调试信息
        # if mouse_y > center_y:  # 只在下半部分打印
        #     print(f"鼠标Y: {mouse_y}, 图例检测起始Y: {center_y + radius + 20}, 中心Y: {center_y}, 半径: {radius}, 最大半径: {int(radius * 1.12)}")
        
        # 计算图例项宽度和起始位置（与paintEvent保持一致）
        legend_items = list(self.data.items())
        font = self.font()
        font.setPointSize(8)  # 与绘制时一致
        fm = QFontMetrics(font)
        
        legend_widths = []
        for label, value in legend_items:
            text_width = fm.width(label)
            item_width = 12 + 4 + text_width + 12  # 与绘制时一致
            legend_widths.append(item_width)
        
        total_legend_width = sum(legend_widths) - 12  # 与绘制时一致
        legend_start_x = (self.width() - total_legend_width) // 2
        
        old_index = self.hovered_index
        self.hovered_index = -1
        
        # 检查是否悬停在横向图例上
        # 确保图例检测范围不会干扰饼图区域
        legend_check_min_y = center_y + radius + 20  # 确保在饼图之下
        current_x = legend_start_x
        for i, (label, value) in enumerate(legend_items):
            # 图例区域：使用实际计算的宽度
            if (current_x - 5 <= mouse_x <= current_x + legend_widths[i] - 5 and
                legend_check_min_y <= mouse_y <= legend_y + 20):
                self.hovered_index = i
                self.setCursor(Qt.PointingHandCursor)  # 手型光标
                if old_index != self.hovered_index:
                    self.update()
                return
            current_x += legend_widths[i]
        
        # 恢复默认光标
        self.setCursor(Qt.ArrowCursor)
        
        # 如果不在图例上，检查饼图区域
        # 考虑悬停时的放大效果
        max_radius = int(radius * 1.12)
        
        dx = mouse_x - center_x
        dy = mouse_y - center_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        # 检查是否在饼图范围内
        if distance > max_radius:
            if old_index != -1:
                self.hovered_index = -1
                self.update()
            return
        
        # 计算鼠标角度（使用与Qt完全相同的系统）
        # Qt的drawPie使用的角度系统：
        # - 角度单位：1/16度（所以90度=90*16）
        # - 0度 = 3点钟方向
        # - 正角度 = 逆时针方向
        # - 90度 = 12点钟，180度 = 9点钟，270度 = 6点钟
        
        # atan2返回弧度，转为度数
        angle_rad = math.atan2(-dy, dx)  # 注意：dy取负，因为屏幕y轴向下
        angle_deg = math.degrees(angle_rad)
        
        # 转换为0-360范围
        if angle_deg < 0:
            angle_deg += 360
        
        # 现在angle_deg就是Qt的角度系统
        # 0度=3点钟，90度=12点钟，180度=9点钟，270度=6点钟
        mouse_angle = angle_deg
        
        # 转换为16分之一度（与drawPie一致）
        mouse_angle_16 = int(mouse_angle * 16)
        
        # 计算每个扇形的角度范围（与绘制时完全一致）
        start_angle_16 = 90 * 16  # 从90度开始（12点钟）
        
        # old_index 已在函数开头定义
        self.hovered_index = -1
        
        for i, (label, value) in enumerate(self.data.items()):
            span_angle_16 = int((value / total) * 360 * 16)
            end_angle_16 = start_angle_16 + span_angle_16
            
            # 检查鼠标是否在这个扇形范围内
            # 需要处理角度超过360*16的情况
            start_deg = (start_angle_16 / 16) % 360
            end_deg = (end_angle_16 / 16) % 360
            
            in_range = False
            if start_deg <= end_deg:
                # 正常情况
                if start_deg <= mouse_angle <= end_deg:
                    in_range = True
            else:
                # 跨越0度
                if mouse_angle >= start_deg or mouse_angle <= end_deg:
                    in_range = True
            
            if in_range:
                self.hovered_index = i
                break
            
            start_angle_16 = end_angle_16
        
        # 只有当索引改变时才更新（减少重绘）
        if old_index != self.hovered_index:
            # 更新整个widget以确保放大的扇区和文字完全显示
            # 特别是底部扇区放大时需要更大的更新区域
            self.update()
    
    def leaveEvent(self, event):
        """鼠标离开时重置并恢复自动播放"""
        self.is_mouse_hovering = False  # 恢复自动播放
        if self.hovered_index != -1:
            self.hovered_index = -1
            self.update()

class FacebookDataVisualizationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = []
        # 使用绝对路径，确保打包后也能正确找到数据文件
        import os
        import sys
        if getattr(sys, 'frozen', False):
            # 打包后的exe运行时
            base_path = os.path.dirname(sys.executable)
        else:
            # 开发环境下
            base_path = os.path.dirname(os.path.abspath(__file__))
        self.data_file = os.path.join(base_path, "data", "facebook_data.json")
        print("=" * 80)
        print(f"[数据可视化组件] 数据文件路径: {self.data_file}")
        print(f"[数据可视化组件] 文件是否存在: {os.path.exists(self.data_file)}")
        print("=" * 80)
        self.load_data()
        # 移除最小高度限制，让布局更灵活
        
        # 动画相关属性
        self.animation_phase = 0
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(50)  # 20 FPS
        
        # 添加加载动画
        self.loading_spinner = LoadingSpinner(self)
        self.loading_spinner.hide()
        
        # 渐变色配置
        self.gradient_colors = [
            QColor(255, 0, 128),    # 粉红
            QColor(128, 0, 255),    # 紫色
            QColor(0, 128, 255),    # 蓝色
            QColor(0, 255, 128),    # 青绿
            QColor(255, 255, 0),    # 黄色
        ]
        
        # 添加悬停相关属性
        self.hovered_point = None  # 当前悬停的数据点
        self.hovered_value = None  # 当前悬停点的数值
        self.hovered_metric = None  # 当前悬停点的指标名称
        self.setMouseTracking(True)  # 启用鼠标跟踪
        
        # 添加数字滚动动画相关属性
        self.number_animations = {}  # 存储每个数字的动画状态
        self.target_numbers = {}  # 目标数字
        self.current_numbers = {}  # 当前显示的数字
        self.animation_duration = 100  # 增加动画持续帧数（约5秒）
        self.animation_frame = 0  # 当前动画帧
        
    def start_number_animation(self, data_items):
        """启动数字滚动动画"""
        # print(f"[数字动画] 启动动画，数据项: {data_items}")  # 已关闭调试日志
        # 重置动画状态
        self.animation_frame = 0
        self.number_animations = {}
        
        # 为每个数据项设置动画
        for i, (value, label) in enumerate(data_items):
            key = label
            # 如果是第一次，从0开始
            if key not in self.current_numbers:
                self.current_numbers[key] = 0
            
            self.target_numbers[key] = value
            self.number_animations[key] = {
                'start': self.current_numbers[key],
                'end': value,
                'active': True
            }
            # print(f"[数字动画] 设置动画 {key}: {self.current_numbers[key]} -> {value}")  # 已关闭调试日志
        
        # 立即触发一次更新以启动动画
        self.update()
        # print("[数字动画] 动画已启动")  # 已关闭调试日志
    
    def update_number_animation(self):
        """更新数字滚动动画"""
        # 检查是否有激活的动画
        active_animations = any(anim['active'] for anim in self.number_animations.values())
        if not active_animations:
            return
            
        if self.animation_frame < self.animation_duration:
            self.animation_frame += 1
            
            # 使用缓动函数（easeOutQuart）使动画更明显
            progress = self.animation_frame / self.animation_duration
            eased_progress = 1 - pow(1 - progress, 4)
            
            # 更新每个数字
            for key, anim in self.number_animations.items():
                if anim['active']:
                    start = anim['start']
                    end = anim['end']
                    self.current_numbers[key] = start + (end - start) * eased_progress
            
            # print(f"[数字动画] 帧: {self.animation_frame}/{self.animation_duration}, 进度: {eased_progress:.2f}")  # 已关闭调试日志
            self.update()
        else:
            # 动画结束，确保显示精确值
            for key, anim in self.number_animations.items():
                self.current_numbers[key] = anim['end']
                anim['active'] = False
            # print("[数字动画] 动画已完成")  # 已关闭调试日志
        
    def load_data(self):
        """从文件加载数据，如果文件不存在则生成示例数据"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                print(f"[数据加载] ✓ 已从文件加载数据: {len(self.data)} 条记录")
                if self.data:
                    print(f"[数据加载] 日期范围: {self.data[0]['date']} 到 {self.data[-1]['date']}")
            else:
                # 如果数据文件不存在，生成示例数据并保存
                print(f"[数据加载] 数据文件不存在，生成新数据...")
                self.generate_sample_data()
                self.save_data()
                print(f"[数据加载] ✓ 已生成并保存数据: {len(self.data)} 条记录")
                if self.data:
                    print(f"[数据加载] 日期范围: {self.data[0]['date']} 到 {self.data[-1]['date']}")
        except Exception as e:
            print(f"[数据加载] ❌ 加载数据时出错: {e}")
            import traceback
            traceback.print_exc()
            # 出错时生成示例数据
            self.generate_sample_data()
            print(f"[数据加载] ✓ 出错后生成数据: {len(self.data)} 条记录")
    
    def save_data(self):
        """将数据保存到文件"""
        try:
            # 确保数据目录存在
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存数据时出错: {e}")
    
    def generate_sample_data(self):
        """生成Facebook示例数据"""
        self.data = []
        # 生成15天的数据
        for i in range(15):
            date = (datetime.now() - timedelta(days=14-i)).strftime('%Y-%m-%d')
            self.data.append({
                'date': date,
                'likes': random.randint(50, 500),
                'comments': random.randint(10, 200),
                'shares': random.randint(5, 100),
                'friends': random.randint(1, 50),
                'posts': random.randint(1, 20),
                'accounts': random.randint(1, 10),
                'groups': random.randint(1, 30)
            })
    
    def update_data(self):
        """更新数据，添加当天数据并删除最早一天的数据"""
        # 删除最早一天的数据
        if len(self.data) >= 15:
            self.data.pop(0)
        
        # 添加当天数据
        today = datetime.now().strftime('%Y-%m-%d')
        new_data = {
            'date': today,
            'likes': random.randint(50, 500),
            'comments': random.randint(10, 200),
            'shares': random.randint(5, 100),
            'friends': random.randint(1, 50),
            'posts': random.randint(1, 20),
            'accounts': random.randint(1, 10),
            'groups': random.randint(1, 30)
        }
        self.data.append(new_data)
        self.save_data()  # 保存数据到文件
        self.update()
    
    def update_animation(self):
        # 更新动画相位
        self.animation_phase = (self.animation_phase + 0.1) % (2 * math.pi)
        # 更新数字滚动动画
        self.update_number_animation()
        self.update()  # 触发重绘
    
    def mouseMoveEvent(self, event):
        """处理鼠标移动事件，检测悬停在数据点上"""
        # 重置悬停状态
        self.hovered_point = None
        self.hovered_value = None
        self.hovered_metric = None
        
        if not self.data:
            super().mouseMoveEvent(event)
            return
            
        # 计算绘图区域（与paintEvent中保持一致）
        top_margin = 100
        left_right_margin = 100  # 与paintEvent中保持一致
        bottom_margin = 50  # 与paintEvent中保持一致
        graph_width = self.width() - 2 * left_right_margin
        graph_height = self.height() - bottom_margin - top_margin
        y_axis_offset = 50
        
        # 合并同一天的数据
        merged_data = self.merge_daily_data(self.data)
        
        # 定义要绘制的数据类型和颜色
        metrics = [
            ('likes', '点赞数', QColor(255, 99, 132)),      # 红色
            ('comments', '评论数', QColor(54, 162, 235)),   # 蓝色
            ('shares', '分享数', QColor(255, 206, 86)),     # 黄色
            ('friends', '好友数', QColor(75, 192, 192)),    # 青色
            ('posts', '动态数', QColor(153, 102, 255)),     # 紫色
            ('groups', '今日加组', QColor(255, 159, 64)),     # 橙色
            ('forwards', '今日转发', QColor(255, 99, 255)),   # 粉色
        ]
        
        # 显示所有数据，按时间顺序排列
        display_data = merged_data
        display_count = len(display_data)
        
        # 检查鼠标是否悬停在某个数据点上
        mouse_pos = event.pos()
        hover_radius = 10  # 悬停检测半径
        
        # 为每种数据类型检查悬停
        for idx, (metric, label, color) in enumerate(metrics):
            # 获取该指标的数据
            values = [item.get(metric, 0) for item in display_data]
            if not values:
                continue
                
            min_val = min(values)
            max_val = max(values)
            range_val = max_val - min_val if max_val != min_val else 1

            # 计算绘图区域（每种数据类型占用一部分高度）
            chart_height = graph_height // len(metrics)
            chart_top = top_margin + idx * chart_height
            chart_bottom = chart_top + chart_height
            
            # 检查每个数据点
            for i, value in enumerate(values):
                # 正确计算x位置（与paintEvent中保持一致）
                x = left_right_margin + y_axis_offset + (i * graph_width) // (display_count - 1) if display_count > 1 else left_right_margin + y_axis_offset
                # 根据数值在图表区域内的位置计算y坐标
                y = chart_bottom - ((value - min_val) * chart_height) // range_val if range_val != 0 else chart_bottom
                
                # 计算鼠标与数据点的距离
                distance = math.sqrt((mouse_pos.x() - x) ** 2 + (mouse_pos.y() - y) ** 2)
                
                # 如果在悬停检测范围内
                if distance <= hover_radius:
                    self.hovered_point = QPointF(x, y)
                    self.hovered_value = value
                    self.hovered_metric = label
                    break
            
            # 如果找到了悬停点，跳出循环
            if self.hovered_point:
                break
        
        # 触发重绘
        self.update()
        super().mouseMoveEvent(event)
    

    

    
    def paintEvent(self, a0):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 设置科技感背景
        self.draw_background(painter)
        
        if not self.data:
            self.draw_placeholder(painter)
            return
            
        # 计算绘图区域（增加顶部边距以让出空间给今日数据）
        top_margin = 100  # 减少顶部边距，使图表区域向上延伸
        left_right_margin = 100  # 左右边距，为纵轴标签留出更多空间
        bottom_margin = 50  # 微调底部边距，使X轴位置与柱状图底边精确对齐
        
        # 计算图表宽度和高度
        chart_width = self.width() - 2 * left_right_margin
        graph_width = chart_width
        # 直接指定图表高度，使X轴位置与柱状图对齐
        graph_height = self.height() - bottom_margin - top_margin
            
        # 绘制科技感网格
        self.draw_grid(painter, left_right_margin, graph_width, graph_height, top_margin)
        
        # 绘制坐标轴
        self.draw_axes(painter, left_right_margin, graph_width, graph_height, top_margin)
        
        # 绘制不同类型的图表
        self.draw_facebook_charts(painter, left_right_margin, graph_width, graph_height, top_margin)
            
        # 绘制今日数据（移除了标题）
        self.draw_title(painter)
        
        # 绘制悬停提示
        self.draw_hover_tooltip(painter)
        

        
    def draw_background(self, painter):
        # 创建简洁的垂直渐变背景
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(15, 23, 42))    # 深蓝
        gradient.setColorAt(0.5, QColor(18, 25, 45))    # 中层蓝
        gradient.setColorAt(1.0, QColor(13, 17, 23))    # 深黑蓝
        gradient.setSpread(QGradient.PadSpread)
        painter.fillRect(self.rect(), gradient)
    
    def draw_grid(self, painter, margin, graph_width, graph_height, top_margin=60):
        # 绘制动态网格线
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Y轴偏移量，用于向右移动网格线，与Y轴位置完全对齐
        y_axis_offset = 50
        
        # 水平网格线（增强视觉效果）
        # 确保水平网格线与Y轴完全对齐
        y_start = top_margin
        y_end = top_margin + graph_height
        for i in range(6):
            y_pos = y_start + (i * (y_end - y_start)) // 5
            # 添加动态效果
            alpha = 100 + int(50 * math.sin(self.animation_phase + i))
            
            # 绘制主网格线（添加发光效果）
            main_pen = QPen(QColor(88, 166, 255, alpha), 1, QtCore_Qt.DashLine)
            main_pen.setDashPattern([4, 4])  # 自定义虚线模式
            painter.setPen(main_pen)
            # 只在折线图区域绘制水平网格线，延伸到X轴终点，与Y轴对齐
            # 确保水平网格线不会超出Y轴边界
            if top_margin <= y_pos <= top_margin + graph_height:
                painter.drawLine(margin + y_axis_offset, y_pos, margin + y_axis_offset + graph_width, y_pos)
            
            # 绘制主网格线发光效果
            glow_pen = QPen(QColor(88, 166, 255, alpha//3), 3, QtCore_Qt.DashLine)
            glow_pen.setDashPattern([4, 4])
            painter.setPen(glow_pen)
            # 确保水平网格线发光效果不会超出Y轴边界
            if top_margin <= y_pos <= top_margin + graph_height:
                painter.drawLine(margin + y_axis_offset, y_pos, margin + y_axis_offset + graph_width, y_pos)
            
            # 绘制次级网格线（更细的线）
            if i < 5:  # 不在最后一行绘制次级线
                sub_y_pos = y_pos + (y_end - y_start) // 10
                sub_alpha = max(30, alpha - 30)  # 更透明
                
                # 绘制次级网格线
                sub_pen = QPen(QColor(88, 166, 255, sub_alpha), 1, QtCore_Qt.DotLine)
                sub_pen.setDashPattern([2, 6])  # 更细的点线
                painter.setPen(sub_pen)
                # 确保次级水平网格线不会超出Y轴边界
                if top_margin <= sub_y_pos <= top_margin + graph_height:
                    painter.drawLine(margin + y_axis_offset, sub_y_pos, margin + y_axis_offset + graph_width, sub_y_pos)
                
                # 绘制次级网格线发光效果
                sub_glow_pen = QPen(QColor(88, 166, 255, sub_alpha//4), 2, QtCore_Qt.DotLine)
                sub_glow_pen.setDashPattern([2, 6])
                painter.setPen(sub_glow_pen)
                # 确保次级水平网格线发光效果不会超出Y轴边界
                if top_margin <= sub_y_pos <= top_margin + graph_height:
                    painter.drawLine(margin + y_axis_offset, sub_y_pos, margin + y_axis_offset + graph_width, sub_y_pos)
            
        # 垂直网格线（根据数据点数量动态生成）
        data_points = len(self.data) if self.data else 15
        for i in range(data_points):
            # 修改网格线位置，使其与Y轴对齐
            # 确保最后一条竖线能延伸到X轴终点
            x_pos = margin + y_axis_offset + (i * graph_width) // (data_points - 1) if data_points > 1 else margin + y_axis_offset
            y_start = top_margin
            y_end = top_margin + graph_height
            
            # 主垂直网格线
            alpha = 100 + int(50 * math.sin(self.animation_phase + i * 0.5))
            main_pen = QPen(QColor(88, 166, 255, alpha), 1, QtCore_Qt.DashLine)
            main_pen.setDashPattern([4, 4])
            painter.setPen(main_pen)
            # 确保垂直网格线与Y轴完全对齐
            if margin + y_axis_offset <= x_pos <= margin + y_axis_offset + graph_width:
                painter.drawLine(x_pos, y_start, x_pos, y_end)
            
            # 主垂直网格线发光效果
            glow_pen = QPen(QColor(88, 166, 255, alpha//3), 3, QtCore_Qt.DashLine)
            glow_pen.setDashPattern([4, 4])
            painter.setPen(glow_pen)
            # 确保垂直网格线发光效果与Y轴完全对齐
            if margin + y_axis_offset <= x_pos <= margin + y_axis_offset + graph_width:
                painter.drawLine(x_pos, y_start, x_pos, y_end)
            
            # 次级垂直网格线
            if i < 6:  # 不在最后一列绘制次级线
                sub_x_pos = x_pos + graph_width // 12
                # 确保次级网格线不超过X轴终点，并与Y轴对齐
                if margin + y_axis_offset <= sub_x_pos <= margin + y_axis_offset + graph_width:
                    sub_alpha = max(30, alpha - 30)
                    
                    # 绘制次级网格线
                    sub_pen = QPen(QColor(88, 166, 255, sub_alpha), 1, QtCore_Qt.DotLine)
                    sub_pen.setDashPattern([2, 6])
                    painter.setPen(sub_pen)
                    painter.drawLine(sub_x_pos, y_start, sub_x_pos, y_end)
                    
                    # 绘制次级网格线发光效果
                    sub_glow_pen = QPen(QColor(88, 166, 255, sub_alpha//4), 2, QtCore_Qt.DotLine)
                    sub_glow_pen.setDashPattern([2, 6])
                    painter.setPen(sub_glow_pen)
                    painter.drawLine(sub_x_pos, y_start, sub_x_pos, y_end)
                
        # 添加背景网格点效果
        grid_point_color = QColor(88, 166, 255, 30)
        painter.setPen(QPen(grid_point_color, 1))
        painter.setBrush(QBrush(grid_point_color))
        
        # 绘制网格点（与Y轴对齐）
        for i in range(0, graph_width, 20):
            for j in range(0, graph_height, 20):
                x = margin + y_axis_offset + i
                y = top_margin + j
                # 确保网格点在正确的范围内，并与Y轴对齐
                if margin + y_axis_offset <= x <= margin + y_axis_offset + graph_width and top_margin <= y <= top_margin + graph_height:
                    # 添加动态效果
                    point_alpha = 20 + int(10 * math.sin(self.animation_phase + i*0.1 + j*0.1))
                    point_color = QColor(88, 166, 255, point_alpha)
                    painter.setPen(QPen(point_color, 1))
                    painter.setBrush(QBrush(point_color))
                    painter.drawEllipse(QPointF(x, y), 1, 1)
            
    def draw_axes(self, painter, margin, graph_width, graph_height, top_margin=60):
        # 计算坐标轴位置
        y_start = top_margin
        y_end = top_margin + graph_height
        x_axis_y = y_end  # X轴位置
        
        # Y轴偏移量，用于向右移动Y轴，增加与指标标签的距离
        y_axis_offset = 50
        
        # 绘制坐标轴（增强视觉效果）
        # Y轴
        # 绘制Y轴主线条
        y_axis_pen = QPen(QColor(88, 166, 255), 3)
        y_axis_pen.setCapStyle(QtCore_Qt.RoundCap)
        painter.setPen(y_axis_pen)
        painter.drawLine(margin + y_axis_offset, y_start, margin + y_axis_offset, y_end)
        
        # 绘制Y轴发光效果
        glow_pen = QPen(QColor(88, 166, 255, 100), 6)
        glow_pen.setCapStyle(QtCore_Qt.RoundCap)
        painter.setPen(glow_pen)
        painter.drawLine(margin + y_axis_offset, y_start, margin + y_axis_offset, y_end)
        
        # 绘制Y轴箭头
        arrow_size = 10
        arrow_pen = QPen(QColor(88, 166, 255), 2)
        painter.setPen(arrow_pen)
        painter.drawLine(int(margin + y_axis_offset - arrow_size/2), int(y_start + arrow_size), int(margin + y_axis_offset), int(y_start))
        painter.drawLine(int(margin + y_axis_offset + arrow_size/2), int(y_start + arrow_size), int(margin + y_axis_offset), int(y_start))
        
        # X轴
        # 绘制X轴主线条
        x_axis_pen = QPen(QColor(88, 166, 255), 3)
        x_axis_pen.setCapStyle(QtCore_Qt.RoundCap)
        painter.setPen(x_axis_pen)
        # 只在折线图区域绘制X轴，延伸到箭头位置
        painter.drawLine(margin + y_axis_offset, x_axis_y, margin + y_axis_offset + graph_width, x_axis_y)
        
        # 绘制X轴发光效果
        glow_pen = QPen(QColor(88, 166, 255, 100), 6)
        glow_pen.setCapStyle(QtCore_Qt.RoundCap)
        painter.setPen(glow_pen)
        # 只在折线图区域绘制X轴发光效果，延伸到箭头位置
        painter.drawLine(margin + y_axis_offset, x_axis_y, margin + y_axis_offset + graph_width, x_axis_y)
        
        # 绘制X轴箭头
        painter.setPen(arrow_pen)
        painter.drawLine(int(margin + y_axis_offset + graph_width - arrow_size), int(x_axis_y - arrow_size/2), int(margin + y_axis_offset + graph_width), int(x_axis_y))
        painter.drawLine(int(margin + y_axis_offset + graph_width - arrow_size), int(x_axis_y + arrow_size/2), int(margin + y_axis_offset + graph_width), int(x_axis_y))
        
        # 绘制X轴标签（日期）- 简洁样式，无背景和描边
        # 合并同一天的数据
        merged_data = self.merge_daily_data(self.data)
        
        # 显示所有数据标签，按时间顺序排列
        display_data = merged_data
        display_count = len(display_data)
        for i in range(display_count):
            if i < len(display_data):
                # 正确计算x位置，确保按时间顺序显示（最新的在右侧）
                x_pos = margin + y_axis_offset + (i * graph_width) // (display_count - 1) if display_count > 1 else margin + y_axis_offset
                date_str = display_data[i]['date'][5:]  # 只显示月日
                text_width = painter.fontMetrics().horizontalAdvance(date_str)
                
                # 直接绘制标签文字，无背景框
                painter.setPen(QPen(QColor(201, 209, 217)))
                font = painter.font()
                font.setPointSize(9)
                font.setBold(False)  # 改为非粗体，与柱状图统一
                painter.setFont(font)
                # 使用矩形版本的drawText，与柱状图对齐
                label_rect = QRect(int(x_pos - text_width/2) - 10, x_axis_y + 5, text_width + 20, 30)
                painter.drawText(label_rect, Qt.AlignCenter, date_str)
                
        # 注意：Y轴刻度线已移除，因为draw_grid方法会绘制网格线
        # 这样可以避免重复绘制导致的视觉问题
        
    def merge_daily_data(self, data):
        """合并同一天的数据"""
        if not data:
            return []
        
        # 按日期分组数据
        date_groups = {}
        for item in data:
            date = item['date']
            if date not in date_groups:
                date_groups[date] = []
            date_groups[date].append(item)
        
        # 合并同一天的数据
        merged_data = []
        for date, items in date_groups.items():
            if len(items) == 1:
                # 如果只有一条数据，直接使用
                merged_data.append(items[0])
            else:
                # 如果有多条数据，合并数值型字段
                merged_item = {'date': date}
                numeric_fields = ['likes', 'comments', 'shares', 'friends', 'posts', 'accounts', 'groups']
                for field in numeric_fields:
                    merged_item[field] = sum(item.get(field, 0) for item in items)
                merged_data.append(merged_item)
        
        # 按日期排序
        merged_data.sort(key=lambda x: x['date'])
        return merged_data
    
    def draw_facebook_charts(self, painter, margin, graph_width, graph_height, top_margin=60):
        """绘制Facebook数据图表"""
        if not self.data:
            return
            
        # Y轴偏移量，与draw_axes函数中保持一致
        y_axis_offset = 50
            
        # 合并同一天的数据
        merged_data = self.merge_daily_data(self.data)
            
        # 定义要绘制的数据类型和颜色
        metrics = [
            ('likes', '点赞数', QColor(255, 99, 132)),      # 红色
            ('comments', '评论数', QColor(54, 162, 235)),   # 蓝色
            ('shares', '分享数', QColor(255, 206, 86)),     # 黄色
            ('friends', '好友数', QColor(75, 192, 192)),    # 青色
            ('posts', '动态数', QColor(153, 102, 255)),     # 紫色
            ('groups', '今日加组', QColor(255, 159, 64)),     # 橙色
            ('forwards', '今日转发', QColor(255, 99, 255)),   # 粉色
        ]
        
        # 显示所有数据，按时间顺序排列
        display_data = merged_data
        display_count = len(display_data)
        
        # 为每种数据类型绘制图表
        for idx, (metric, label, color) in enumerate(metrics):
            # 获取该指标的数据
            values = [item.get(metric, 0) for item in display_data]
            if not values:
                continue
                
            min_val = min(values)
            max_val = max(values)
            range_val = max_val - min_val if max_val != min_val else 1

            # 计算绘图区域（每种数据类型占用一部分高度）
            chart_height = graph_height // len(metrics)
            chart_top = top_margin + idx * chart_height
            chart_bottom = chart_top + chart_height
            
            # 绘制数据点和连线
            points = []
            for i, value in enumerate(values):
                # 正确计算x位置，确保按时间顺序显示（最新的在右侧）
                x = margin + y_axis_offset + (i * graph_width) // (display_count - 1) if display_count > 1 else margin + y_axis_offset
                # 根据数值在图表区域内的位置计算y坐标
                y = chart_bottom - ((value - min_val) * chart_height) // range_val if range_val != 0 else chart_bottom
                points.append(QPointF(x, y))
                
            # 绘制渐变填充区域（在折线下方）
            if len(points) > 1:
                # 创建填充区域的点（包括底部边界）
                fill_points = points[:]
                fill_points.append(QPointF(points[-1].x(), chart_bottom))
                fill_points.append(QPointF(points[0].x(), chart_bottom))
                
                # 创建渐变填充（增强视觉效果）
                gradient = QLinearGradient(0, chart_top, 0, chart_bottom)
                gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 150))
                gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 30))
                
                painter.setPen(QPen(QtCore_Qt.NoPen))
                painter.setBrush(QBrush(gradient))
                painter.drawPolygon(fill_points)
                
                # 添加发光效果
                glow_gradient = QRadialGradient(
                    points[len(points)//2].x(), 
                    chart_top + chart_height//2, 
                    graph_width//3
                )
                glow_gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 80))
                glow_gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
                
                painter.setBrush(QBrush(glow_gradient))
                painter.setPen(QPen(QtCore_Qt.NoPen))
                painter.drawPolygon(fill_points)
                
            # 绘制连线（使用更粗的线条和阴影效果）
            # 首先绘制阴影效果
            shadow_pen = QPen(QColor(0, 0, 0, 80), 4)
            painter.setPen(shadow_pen)
            for i in range(len(points) - 1):
                painter.drawLine(points[i] + QPointF(1, 1), points[i+1] + QPointF(1, 1))
                
            # 然后绘制主线条（添加渐变效果）
            line_gradient = QLinearGradient(points[0].x(), points[0].y(), points[-1].x(), points[-1].y())
            line_gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 150))
            line_gradient.setColorAt(0.5, QColor(color.red(), color.green(), color.blue(), 255))
            line_gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 150))
            
            line_pen = QPen(QBrush(line_gradient), 4)
            line_pen.setCapStyle(QtCore_Qt.RoundCap)
            line_pen.setJoinStyle(QtCore_Qt.RoundJoin)
            painter.setPen(line_pen)
            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i+1])
                
            # 绘制数据点（增强视觉效果）
            for i, point in enumerate(points):
                # 计算动态效果
                pulse_effect = 1 + 0.2 * math.sin(self.animation_phase + i)
                
                # 绘制外圈高亮（添加脉冲效果）
                outer_radius = 8 * pulse_effect
                painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
                painter.setBrush(QBrush(color))
                painter.drawEllipse(point, outer_radius, outer_radius)
                
                # 绘制内圈（添加发光效果）
                inner_radius = 3 * pulse_effect
                painter.setPen(QPen(QtCore_Qt.NoPen))
                inner_gradient = QRadialGradient(point, inner_radius * 2)
                inner_gradient.setColorAt(0, QColor(255, 255, 255, 255))
                inner_gradient.setColorAt(0.7, QColor(255, 255, 255, 180))
                inner_gradient.setColorAt(1, QColor(255, 255, 255, 0))
                painter.setBrush(QBrush(inner_gradient))
                painter.drawEllipse(point, inner_radius, inner_radius)
                
                # 如果是悬停点，绘制额外的高亮效果
                if self.hovered_point and math.sqrt((point.x() - self.hovered_point.x()) ** 2 + 
                                                   (point.y() - self.hovered_point.y()) ** 2) < 15:
                    # 绘制多层脉冲效果
                    for j in range(3):
                        pulse_radius = 15 + int(8 * math.sin(self.animation_phase * 3 + j * 0.5))
                        alpha = max(0, 150 - j * 50)
                        painter.setPen(QPen(QColor(255, 255, 255, alpha), 2))
                        painter.setBrush(QBrush(QtCore_Qt.NoBrush))
                        painter.drawEllipse(point, pulse_radius, pulse_radius)
                    
            # 绘制指标标签（增强视觉效果）
            # 绘制背景框（添加渐变效果），再向右移动20像素
            label_rect = QRect(margin - 70, chart_top + chart_height // 2 - 15, 100, 30)
            
            # 创建标签背景渐变
            label_gradient = QLinearGradient(label_rect.left(), label_rect.top(), label_rect.right(), label_rect.bottom())
            label_gradient.setColorAt(0, QColor(0, 0, 0, 180))
            label_gradient.setColorAt(1, QColor(0, 0, 0, 120))
            
            painter.setPen(QPen(QColor(100, 180, 255, 200), 1))
            painter.setBrush(QBrush(label_gradient))
            painter.drawRoundedRect(label_rect, 6, 6)
            
            # 绘制标签文字（添加发光效果）
            painter.setPen(QPen(QColor(255, 255, 255)))
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            
            # 绘制发光文字
            glow_pen = QPen(QColor(100, 180, 255, 100), 3)
            painter.setPen(glow_pen)
            painter.drawText(label_rect.adjusted(1, 1, 1, 1), QtCore_Qt.AlignCenter, label)
            
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(label_rect, QtCore_Qt.AlignCenter, label)
            
    def draw_hover_tooltip(self, painter):
        """绘制悬停提示框"""
        if not self.hovered_point or self.hovered_value is None:
            return
            
        # 设置提示框样式
        tooltip_padding = 8
        tooltip_radius = 6
        
        # 计算文本尺寸
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        text = str(self.hovered_value)
        text_width = painter.fontMetrics().horizontalAdvance(text)
        text_height = painter.fontMetrics().height()
        
        # 计算提示框尺寸
        tooltip_width = text_width + 2 * tooltip_padding
        tooltip_height = text_height + 2 * tooltip_padding
        
        # 计算提示框位置（在数据点上方）
        tooltip_x = int(self.hovered_point.x() - tooltip_width / 2)
        tooltip_y = int(self.hovered_point.y() - tooltip_height - 10)
        
        # 确保提示框不会超出窗口边界
        if tooltip_x < 0:
            tooltip_x = 0
        elif tooltip_x + tooltip_width > self.width():
            tooltip_x = self.width() - tooltip_width
            
        if tooltip_y < 0:
            tooltip_y = int(self.hovered_point.y() + 10)  # 如果上方空间不足，在下方显示
            
        # 绘制提示框背景
        tooltip_rect = QRect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
        painter.setBrush(QBrush(QColor(30, 30, 30, 220)))
        painter.drawRoundedRect(tooltip_rect, tooltip_radius, tooltip_radius)
        
        # 绘制数值文本
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(tooltip_rect, QtCore_Qt.AlignCenter, text)
        
        # 绘制指向线
        pointer_start = QPointF(self.hovered_point.x(), self.hovered_point.y() - 5 if tooltip_y < self.hovered_point.y() else self.hovered_point.y() + 5)
        pointer_end = QPointF(self.hovered_point.x(), tooltip_y + tooltip_height if tooltip_y < self.hovered_point.y() else tooltip_y)
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
        painter.drawLine(pointer_start, pointer_end)
        

            

    



    

            
    def draw_title(self, painter):
        """绘制今日数据信息"""
        # 获取今日数据（最后一行）
        if self.data:
            today_data = self.data[-1]
            # 定义要显示的数据项
            data_items = [
                (today_data['likes'], "今日点赞"),
                (today_data['comments'], "今日评论"),
                (today_data['shares'], "今日分享"),
                (today_data['friends'], "今日好友"),
                (today_data['posts'], "今日动态"),
                (today_data['groups'], "今日加组"),
                (today_data.get('forwards', 0), "今日转发"),
                (today_data['accounts'], "今日账号")
            ]
            
            # 检查是否需要启动新的动画
            need_animation = False
            for value, label in data_items:
                if label not in self.target_numbers or self.target_numbers[label] != value:
                    need_animation = True
                    break
            
            if need_animation:
                self.start_number_animation(data_items)
            
            # 设置绘制参数 - 自适应宽度
            left_margin = 20
            right_margin = 20
            available_width = self.width() - left_margin - right_margin  # 减去左右边距
            item_width = available_width // len(data_items)  # 平均分配宽度
            item_width = max(80, min(item_width, 150))  # 限制在80-150之间
            
            # 重新计算总宽度和起始位置
            total_width = len(data_items) * item_width
            # 确保不会超出右边界
            if total_width > available_width:
                item_width = available_width // len(data_items)
                start_x = left_margin
            else:
                start_x = (self.width() - total_width) // 2  # 居中显示
            
            y_pos = 30  # 调整位置以适应更大的字体
            
            # 绘制每个数据项
            for i, (value, label) in enumerate(data_items):
                x_pos = start_x + i * item_width
                
                # 获取当前动画数字（如果有的话）
                if label in self.current_numbers:
                    display_value = int(self.current_numbers[label])
                else:
                    display_value = value
                
                # 绘制数值（更大更醒目的字体）
                painter.setPen(QPen(QColor(255, 255, 255)))
                font = painter.font()
                font.setPointSize(20)  # 进一步增大字体大小
                font.setBold(True)
                painter.setFont(font)
                value_rect = QRect(x_pos, y_pos, item_width, 40)  # 增加矩形高度
                painter.drawText(value_rect, QtCore_Qt.AlignCenter, str(display_value))
                
                # 绘制标签（小字体，自适应）
                painter.setPen(QPen(QColor(201, 209, 217)))
                font = painter.font()
                # 根据item_width调整字体大小，确保文字能完整显示
                if item_width < 90:
                    font.setPointSize(7)  # 窗口很小时使用最小字体
                elif item_width < 100:
                    font.setPointSize(8)  # 窗口小时使用更小的字体
                elif item_width < 120:
                    font.setPointSize(9)
                else:
                    font.setPointSize(10)  # 正常字体
                font.setBold(False)
                painter.setFont(font)
                label_rect = QRect(x_pos, y_pos + 40, item_width, 25)  # 调整标签位置
                # 使用 TextWordWrap 标志确保长文本可以换行或省略
                painter.drawText(label_rect, QtCore_Qt.AlignCenter, label)

class VersionCheckWorker(QObject):
    """版本检查工作对象（异步，不阻塞UI）"""
    version_checked = pyqtSignal(int)  # 发送版本号
    finished = pyqtSignal()            # 工作完成信号
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        self._is_running = True  # 添加运行标志

    def check_version(self):
        """执行版本检查任务"""
        try:
            import urllib.request
            import json
            
            # 检查对象是否仍然有效
            if not self._is_running:
                return
            
            # 创建请求对象，设置短超时
            req = urllib.request.Request(self.url)
            
            # 发送请求，设置超时为1秒
            response = urllib.request.urlopen(req, timeout=1)
            
            if response.getcode() == 200:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('status') == 'success':
                    version = result.get('version', 0)
                    # 再次检查对象是否仍然有效
                    if self._is_running:
                        self.version_checked.emit(version)
        except:
            # 静默失败，不影响用户体验
            pass
        finally:
            # 只有在对象仍然有效时才发送finished信号
            if self._is_running:
                try:
                    self.finished.emit()
                except RuntimeError:
                    # 对象已被删除，忽略错误
                    pass
    
    def stop(self):
        """停止工作"""
        self._is_running = False

class DataFetchWorker(QObject):
    """数据获取工作对象"""
    data_fetched = pyqtSignal(object)  # 发送获取到的数据
    error_occurred = pyqtSignal(str)   # 发送错误信息
    finished = pyqtSignal()            # 工作完成信号
    
    def __init__(self, url, monitor_path=None):
        super().__init__()
        self.url = url
        self.monitor_path = monitor_path or r"D:\FacebookSpider\FB推广系统\账号管理"

    def is_hidden_or_temp(self, filepath):
        """判断文件是否为隐藏文件或临时文件"""
        import stat
        # 获取文件名
        filename = os.path.basename(filepath)
        
        # 检查是否为隐藏文件（Windows）
        if filename.startswith('.') or (os.name == 'nt' and self.has_hidden_attribute(filepath)):
            return True
        
        # 检查是否为临时文件
        temp_extensions = ['.tmp', '.temp', '.swp', '.bak']
        for ext in temp_extensions:
            if filename.lower().endswith(ext):
                return True
        
        return False

    def has_hidden_attribute(self, filepath):
        """检查Windows文件是否具有隐藏属性"""
        import stat
        try:
            # 获取文件属性
            attrs = os.stat(filepath).st_file_attributes
            # 检查是否包含隐藏属性
            return attrs & stat.FILE_ATTRIBUTE_HIDDEN
        except (OSError, AttributeError):
            return False

    def fetch_data(self):
        """执行数据获取任务"""
        try:
            # 发送请求到后台服务获取当前数据
            import urllib.request
            import json
            
            # 设置请求头
            headers = {
                'User-Agent': 'FacebookDashboard/1.0'
            }
            
            # 创建请求对象
            req = urllib.request.Request(self.url, headers=headers)
            
            # 发送请求，设置超时为15秒
            response = urllib.request.urlopen(req, timeout=15)
            
            # 检查HTTP状态码
            if response.getcode() != 200:
                self.error_occurred.emit(f"HTTP Error: {response.getcode()}")
                self.finished.emit()
                return
            
            # 获取响应内容并使用UTF-8解码
            response_content = response.read()
            # 始终使用UTF-8解码，因为后端已明确设置UTF-8编码
            result = json.loads(response_content.decode('utf-8'))
            
            # 直接使用后端返回的数据（账号数量由后端从比特浏览器API获取）
            self.data_fetched.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.finished.emit()

class FacebookDashboard(QMainWindow):
    # 定义信号用于线程安全的 UI 更新
    update_log_signal = pyqtSignal(str)

    def __init__(self, auth_client=None):
        print("[__init__] 开始初始化 FacebookDashboard...")
        try:
            super().__init__()
            print("[__init__] ✓ QMainWindow 初始化完成")
        except Exception as e:
            print(f"[__init__] ❌ QMainWindow 初始化失败: {e}")
            raise
        
        self.auth_client = auth_client
        self.data_fetch_thread = None
        self.data_fetch_worker = None
        
        # 设置窗口标题（包含用户名）
        try:
            username = self.load_username_from_simulator_config()
            self.setWindowTitle(f"Facebook Marketing Pro - {username}")
            print(f"[__init__] ✓ 窗口标题已设置: {username}")
        except Exception as e:
            print(f"[__init__] ⚠ 设置窗口标题失败: {e}")
            self.setWindowTitle("Facebook Marketing Pro")
        
        # 设置窗口图标
        try:
            self.set_window_icon()
            print("[__init__] ✓ 窗口图标已设置")
        except Exception as e:
            print(f"[__init__] ⚠ 设置窗口图标失败: {e}")
        
        # 获取屏幕尺寸信息
        try:
            app = QApplication.instance()
            screen = app.primaryScreen()
            screen_geometry = screen.geometry()
            available_geometry = screen.availableGeometry()
            
            # 打印屏幕尺寸信息用于调试
            print(f"[__init__] 屏幕完整尺寸: {screen_geometry.width()} x {screen_geometry.height()}")
            print(f"[__init__] 可用屏幕尺寸(不含任务栏): {available_geometry.width()} x {available_geometry.height()}")
            print(f"[__init__] 任务栏高度估算: {screen_geometry.height() - available_geometry.height()}")
            
            # 使用固定的窗口尺寸，确保窗口大小符合要求
            width = 1200
            # 设置窗口高度与最大化状态一致，但不超过可用空间
            height = min(available_geometry.height() - 40, 1000)  # 减去任务栏高度，但不超过1000px
            
            # 设置窗口的最小尺寸，确保内容不会被截断
            self.setMinimumSize(1000, height)
            
            # 确保窗口不会超出可用空间
            width = min(width, available_geometry.width() - 30)
            height = min(height, available_geometry.height() - 40)
            
            # 计算窗口位置，确保完全在可用区域内显示
            # 将窗口放置在可用区域的右上角，紧贴边缘
            x = available_geometry.x() + available_geometry.width() - width
            # 确保窗口顶部对齐到可用区域顶部，紧贴边缘
            y = available_geometry.y()
            
            # 确保窗口完全在可用区域内（进行边界检查）
            # 特别确保窗口底部不会超出可用区域（避免被任务栏遮挡）
            max_y = available_geometry.y() + available_geometry.height() - height
            if y > max_y:
                y = max_y
                
            if x < available_geometry.x():
                x = available_geometry.x()
            if y < available_geometry.y():
                y = available_geometry.y()
            if x + width > available_geometry.x() + available_geometry.width():
                x = available_geometry.x() + available_geometry.width() - width
            if y + height > available_geometry.y() + available_geometry.height():
                y = available_geometry.y() + available_geometry.height() - height
            
            print(f"[__init__] 窗口最终尺寸: {width} x {height}")
            print(f"[__init__] 窗口位置: ({x}, {y})")
            print(f"[__init__] 窗口底部位置: {y + height}")
            print(f"[__init__] 可用区域底部: {available_geometry.y() + available_geometry.height()}")
            
            self.setGeometry(x, y, width, height)
            # 初始化最大化高度属性
            self._maximized_height = height
            print("[__init__] ✓ 窗口几何属性已设置")
        except Exception as e:
            print(f"[__init__] ⚠ 设置窗口几何属性失败: {e}")
            # 使用默认值
            self.setGeometry(100, 100, 1200, 800)
            self._maximized_height = 800
        
        self.button_click_effects = {}  # 存储按钮点击效果的动画
        self.backend_service_process = None  # 添加后端服务进程变量
        
        # 启动后台服务
        try:
            self.backend_service = None
            self.start_backend_service()
            print("[__init__] ✓ 后台服务已启动")
        except Exception as e:
            print(f"[__init__] ⚠ 启动后台服务失败: {e}")
        
        # 设置窗口标志和样式
        try:
            # 恢复无边框模式
            self.setWindowFlags(Qt.FramelessWindowHint)  # 无边框窗口
            self.drag_position = None  # 用于窗口拖动
            print("[__init__] ✓ 窗口标志已设置")
        except Exception as e:
            print(f"[__init__] ⚠ 设置窗口标志失败: {e}")
        
        # 初始化UI
        print("[__init__] 准备初始化UI...")
        try:
            self.init_ui()
            print("[__init__] ✓ UI初始化成功")
        except Exception as e:
            print(f"[__init__] ❌ UI初始化失败: {e}")
            import traceback
            traceback.print_exc()
            # 不要 raise，尝试继续
            print("[__init__] ⚠ 尝试继续初始化...")
        
        # 连接信号和槽（用于线程安全的 UI 更新）
        try:
            self.update_log_signal.connect(self._update_log_text)
            print("[__init__] ✓ 信号槽已连接")
        except Exception as e:
            print(f"[__init__] ⚠ 连接信号槽失败: {e}")
        
        # ============ Phase 2&3: 初始化线程管理器 ============
        # 用于账号切换异步化和主线程保护
        try:
            self.thread_manager = init_thread_manager(self)
            print("[__init__] ✅ UI 线程管理器已初始化")
        except Exception as e:
            print(f"[__init__] ⚠ 初始化线程管理器失败: {e}")
        
        # 初始化自动生成视频监控线程
        self.auto_video_thread = None
        
        # 初始化心跳定时器（5分钟一次）
        try:
            self.heartbeat_timer = QTimer(self)
            self.heartbeat_timer.timeout.connect(self._send_heartbeat)
            self.heartbeat_timer.start(5 * 60 * 1000)  # 5分钟 = 300,000毫秒
            print("[__init__] ✓ 心跳定时器已启动（间隔: 5分钟）")
        except Exception as e:
            print(f"[__init__] ⚠ 启动心跳定时器失败: {e}")
        
        print("[__init__] ✅ FacebookDashboard初始化完成")
    
    def _send_heartbeat(self):
        """
        发送心跳信号（定时器回调）
        
        特点：
        - 5分钟发送一次
        - 不参与认证验证
        - 失败不影响程序运行
        - 仅用于监控用户在线状态
        """
        try:
            # 检查是否有认证客户端
            if not hasattr(self, 'auth_client') or not self.auth_client:
                return
            
            # 发送心跳
            success, message = self.auth_client.send_heartbeat()
            
            if success:
                print(f"[心跳] ✓ {message}")
            else:
                # 失败只记录日志，不影响程序运行
                print(f"[心跳] ✗ {message}")
                
        except Exception as e:
            # 任何异常都不影响程序运行
            print(f"[心跳] ✗ 发送异常: {e}")
    
    def load_remote_address(self):
        """加载远程地址配置"""
        try:
            config_file = "remote_config.json"
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('remote_address', 'http://43.142.176.53:8805')
            else:
                return 'http://43.142.176.53:8805'
        except Exception as e:
            print(f"[ERROR] 加载远程地址配置失败: {e}")
            return 'http://43.142.176.53:8805'
    
    def _load_notification(self):
        """从服务器加载系统通知"""
        default_notification = "就绪 - Facebook数据展示程序正在运行 - 当前版本支持实时数据刷新功能 - 程序每30秒自动刷新一次数据"
        
        try:
            # 获取服务器地址
            server_url = self.load_remote_address()
            api_url = f"{server_url}/auth_backend/api/admin.php"
            
            # 调用API获取通知
            response = requests.post(
                api_url,
                data={'action': 'get_notification'},
                timeout=3
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    notification = result.get('data', {}).get('notification', '')
                    if notification:
                        print(f"[通知] ✓ 从服务器加载通知成功")
                        return notification
            
            print(f"[通知] 使用默认通知")
            return default_notification
            
        except Exception as e:
            print(f"[通知] 加载通知失败，使用默认通知: {e}")
            return default_notification
    
    def save_remote_address(self, address):
        """保存远程地址配置"""
        try:
            config = {
                'remote_address': address,
                'updated_time': datetime.now().isoformat()
            }
            with open("remote_config.json", 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"[OK] 远程地址已保存: {address}")
        except Exception as e:
            print(f"[ERROR] 保存远程地址配置失败: {e}")
    
    def get_full_api_url(self, endpoint):
        """获取完整的API URL"""
        # 硬编码API服务器地址
        base_address = 'http://43.142.176.53'
        return f"{base_address}:8805{endpoint}"
    
    def load_config(self):
        """加载配置"""
        pass
    
    def set_window_icon(self):
        """设置窗口图标"""
        try:
            icon_paths = []
            
            if getattr(sys, 'frozen', False):
                # 打包后的exe环境，尝试多个位置
                exe_dir = os.path.dirname(sys.executable)
                internal_dir = sys._MEIPASS
                
                # 优先尝试exe同级目录
                icon_paths.extend([
                    os.path.join(exe_dir, "facebook_logo.png"),
                    os.path.join(exe_dir, "facebook_logo.svg"),
                    os.path.join(internal_dir, "facebook_logo.png"),
                    os.path.join(internal_dir, "facebook_logo.svg")
                ])
            else:
                # 开发环境
                base_path = os.path.dirname(os.path.abspath(__file__))
                icon_paths.extend([
                    os.path.join(base_path, "facebook_logo.png"),
                    os.path.join(base_path, "facebook_logo.svg")
                ])
            
            # 尝试加载图标
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    icon = QIcon(icon_path)
                    if not icon.isNull():
                        self.setWindowIcon(icon)
                        print(f"[OK] 窗口图标已设置: {icon_path}")
                        return True
            
            print("[WARN] 未找到有效的窗口图标文件")
            print(f"[DEBUG] 尝试的路径: {icon_paths}")
            return False
            
        except Exception as e:
            print(f"[ERROR] 设置窗口图标失败: {e}")
            return False
        
    def start_backend_service(self):
        """启动后台服务（使用waitress生产级服务器）"""
        try:
            # 1. 异步清理占用 8805 端口的旧进程（不阻塞 UI）
            print("[后端服务] 检查端口 8805...")
            QTimer.singleShot(0, self._cleanup_port_8805_async)
            
            # 2. 检查后端服务是否已经在运行
            import requests
            try:
                response = requests.get('http://localhost:8805/get_current_data', timeout=1)
                if response.status_code == 200:
                    print("[后端服务] 后端服务已在运行")
                    return True
            except:
                pass
            
            # 3. 延迟启动后端服务（等待端口清理完成）
            QTimer.singleShot(2500, self._start_backend_thread)
            
            return True
            
        except Exception as e:
            print(f"[后端服务] 启动后端服务时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _cleanup_port_8805_async(self):
        """异步清理占用 8805 端口的旧进程（在后台线程中执行）"""
        import threading
        threading.Thread(target=self._cleanup_port_8805, daemon=True).start()
    
    def _start_backend_thread(self):
        """启动后端服务线程"""
        from PyQt5.QtCore import QThread
        
        class BackendServiceThread(QThread):
            """后端服务线程（支持优雅关闭）"""
            def __init__(self, parent=None):
                super().__init__(parent)
                self.running = False
                
            def run(self):
                """运行后端服务"""
                try:
                    self.running = True
                    print("[后端服务] 开始导入 backend_service...")
                    from backend_service import app
                    import logging
                    
                    print("[后端服务] 导入成功，配置日志...")
                    # 禁用Flask和werkzeug的详细日志
                    logging.getLogger('werkzeug').setLevel(logging.ERROR)
                    logging.getLogger('urllib3').setLevel(logging.ERROR)
                    app.logger.setLevel(logging.ERROR)
                    
                    print("[后端服务] 正在启动 Waitress 服务器 (127.0.0.1:8805)...")
                    
                    # 使用waitress启动服务（生产级WSGI服务器）
                    try:
                        from waitress import serve
                        import socket
                        
                        print("[后端服务] 使用 Waitress 服务器（生产级）")
                        print("[后端服务] 配置端口重用选项...")
                        
                        # 创建自定义 socket 并设置 SO_REUSEADDR
                        def create_socket():
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 0)
                            return sock
                        
                        print("[后端服务] 服务器启动中...")
                        serve(app, host='127.0.0.1', port=8805, threads=4, 
                              channel_timeout=30, _quiet=False, _sock=create_socket())
                        
                    except ImportError:
                        print("[后端服务] Waitress未安装，使用Flask开发服务器")
                        app.run(host='127.0.0.1', port=8805, debug=False, use_reloader=False, threaded=True)
                        
                    print("[后端服务] 服务器已停止")
                    
                except Exception as e:
                    print(f"[后端服务] 启动失败: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    self.running = False
            
            def stop(self):
                """停止后端服务"""
                if self.running:
                    print("[后端服务] 正在停止服务...")
                    self.running = False
                    try:
                        import requests
                        requests.post('http://localhost:8805/shutdown', timeout=2)
                    except:
                        pass
                    self.quit()
                    self.wait(3000)
        
        # 创建并启动后端服务线程
        self.backend_thread = BackendServiceThread(self)
        self.backend_thread.start()
        
        print("[后端服务] 后端服务正在后台启动...")
        
        # 使用 QTimer 异步检查服务状态
        self._backend_check_count = 0
        self._backend_check_timer = QTimer()
        self._backend_check_timer.timeout.connect(self._check_backend_status)
        self._backend_check_timer.start(500)
    
    def _check_backend_status(self):
        """异步检查后端服务状态（不阻塞 UI）"""
        try:
            import requests
            response = requests.get('http://localhost:8805/get_current_data', timeout=1)
            if response.status_code == 200:
                print("[后端服务] ✓ 后端服务启动成功")
                self._backend_check_timer.stop()
                return
        except:
            pass
        
        self._backend_check_count += 1
        if self._backend_check_count >= 10:  # 最多检查 10 次（5 秒）
            print("[后端服务] ⚠ 后端服务可能未完全启动")
            self._backend_check_timer.stop()
            return False
    
    def _cleanup_port_8805(self):
        """清理占用 8805 端口的旧进程"""
        try:
            import subprocess
            import os
            import time
            
            # 获取当前进程ID
            current_pid = os.getpid()
            
            # 查找占用 8805 端口的进程
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # 解析输出，找到占用 8805 端口的进程
            pids_to_kill = set()
            for line in result.stdout.split('\n'):
                if ':8805' in line and 'LISTENING' in line:
                    parts = line.split()
                    if parts:
                        try:
                            pid = int(parts[-1])
                            # 不要杀死当前进程
                            if pid != current_pid:
                                pids_to_kill.add(pid)
                        except:
                            pass
            
            # 关闭找到的进程
            if pids_to_kill:
                print(f"[后端服务] 发现 {len(pids_to_kill)} 个占用端口的旧进程，正在清理...")
                for pid in pids_to_kill:
                    try:
                        # 使用 /F 强制终止，/T 终止子进程
                        subprocess.run(
                            ['taskkill', '/F', '/T', '/PID', str(pid)],
                            capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                        )
                        print(f"[后端服务] ✓ 已关闭进程 {pid}")
                    except Exception as e:
                        print(f"[后端服务] ⚠ 关闭进程 {pid} 失败: {e}")
                
                # 等待端口释放（增加等待时间）
                print("[后端服务] 等待端口释放...")
                time.sleep(2)
                
                # 再次检查端口是否真的释放了
                result2 = subprocess.run(
                    ['netstat', '-ano'],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                still_occupied = False
                for line in result2.stdout.split('\n'):
                    if ':8805' in line and 'LISTENING' in line:
                        still_occupied = True
                        print(f"[后端服务] ⚠ 端口仍被占用: {line.strip()}")
                
                if not still_occupied:
                    print("[后端服务] ✓ 端口清理完成")
                else:
                    print("[后端服务] ⚠ 警告：端口可能仍被占用")
            else:
                print("[后端服务] ✓ 端口 8805 空闲")
                
        except Exception as e:
            print(f"[后端服务] ⚠ 清理端口时出错: {e}")
    
    
    def create_title_bar(self, main_layout):
        """创建自定义标题栏"""
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("""
            QWidget {
                background-color: #161b22;
                border-bottom: 1px solid #30363d;
            }
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        
        # Facebook Logo (自定义绘制控件)
        logo_widget = FacebookLogoWidget()
        title_layout.addWidget(logo_widget)
        
        # 标题标签（显示用户名）
        username = self.load_username_from_simulator_config()
        title_label = QLabel(f"Facebook Marketing Pro - {username}")
        title_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #c9d1d9;
            background: transparent;
            border: none;
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # 最小化按钮
        min_button = QPushButton("−")
        min_button.setFixedSize(32, 30)
        min_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #8b949e;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0969da;
                color: white;
            }
        """)
        min_button.clicked.connect(self.showMinimized)
        title_layout.addWidget(min_button)
        
        # 最大化按钮
        max_button = QPushButton("□")
        max_button.setFixedSize(32, 30)
        max_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #8b949e;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0969da;
                color: white;
            }
        """)
        max_button.clicked.connect(self.toggle_maximize)
        title_layout.addWidget(max_button)
        
        # 关闭按钮
        close_button = QPushButton("✕")
        close_button.setFixedSize(32, 30)
        close_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #8b949e;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0969da;
                color: white;
            }
        """)
        close_button.clicked.connect(self.close)
        title_layout.addWidget(close_button)
        
        main_layout.addWidget(title_bar)
        
    def check_and_show_pie_chart(self):
        """检查窗口状态并显示/隐藏图表容器"""
        if hasattr(self, 'charts_background'):
            if self.isMaximized():
                print("[饼图调试] 窗口已最大化，显示饼图和柱状图")
                self.charts_background.show()
            else:
                print(f"[饼图调试] 窗口未最大化，保持隐藏。窗口大小: {self.width()}x{self.height()}")
                self.charts_background.hide()
        
    def toggle_maximize(self):
        """切换最大化状态"""
        if self.isMaximized():
            self.showNormal()
            # 还原时隐藏图表容器（延迟执行）
            QTimer.singleShot(50, lambda: self.charts_background.hide() if hasattr(self, 'charts_background') else None)
            print("[饼图调试] 窗口还原，将隐藏饼图和柱状图")
        else:
            # 保存最大化状态下的高度
            screen = QApplication.primaryScreen()
            available_geometry = screen.availableGeometry()
            self._maximized_height = available_geometry.height() - 40  # 减去任务栏高度
            self.showMaximized()
            # 最大化时显示图表容器（延迟执行）
            QTimer.singleShot(50, lambda: self.charts_background.show() if hasattr(self, 'charts_background') else None)
            print("[饼图调试] 窗口最大化，将显示饼图和柱状图")
            
    def mousePressEvent(self, event):
        """处理鼠标按下事件，用于窗口拖动"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        """处理鼠标移动事件，用于窗口拖动"""
        if event.buttons() == Qt.LeftButton and self.drag_position is not None:
            if not self.isMaximized():  # 只有在非最大化状态下才能拖动
                self.move(event.globalPos() - self.drag_position)
                event.accept()
        # 调用父类的mouseMoveEvent以确保子组件也能接收到鼠标事件
        super().mouseMoveEvent(event)
                
    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件"""
        self.drag_position = None
        event.accept()
        
    def add_button_hover_effect(self, button):
        """为按钮添加悬停动画效果"""
        # 不需要额外的悬停效果，QPushButton已经内置了:hover样式
        # 在按钮的样式表中定义:hover状态即可实现悬停效果
        pass
        
    def add_button_click_effect(self, button):
        """为按钮添加点击动画效果"""
        # 添加悬停效果
        self.add_button_hover_effect(button)
        
        effect = QGraphicsDropShadowEffect()
        effect.setBlurRadius(20)
        effect.setXOffset(0)
        effect.setYOffset(0)
        effect.setColor(QColor(88, 166, 255, 150))  # 蓝色发光效果
        button.setGraphicsEffect(effect)
        
        # 创建动画
        animation = QPropertyAnimation(effect, b"blurRadius")
        animation.setDuration(200)
        animation.setStartValue(20)
        animation.setEndValue(5)
        
        self.button_click_effects[button] = {
            'effect': effect,
            'animation': animation
        }
        
        # 连接按钮点击事件
        button.pressed.connect(lambda: self.start_button_click_effect(button))
        button.released.connect(lambda: self.end_button_click_effect(button))
        
    def start_button_click_effect(self, button):
        """开始按钮点击效果"""
        if button in self.button_click_effects:
            effect = self.button_click_effects[button]['effect']
            animation = self.button_click_effects[button]['animation']
            animation.setDirection(QPropertyAnimation.Forward)
            animation.start()
            
    def end_button_click_effect(self, button):
        """结束按钮点击效果"""
        if button in self.button_click_effects:
            effect = self.button_click_effects[button]['effect']
            animation = self.button_click_effects[button]['animation']
            animation.setDirection(QPropertyAnimation.Backward)
            animation.start()
        
    def init_ui(self):
        print("[init_ui] 开始初始化UI...")
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 移除边距
        central_widget.setStyleSheet("background-color: #0d1117;")
        print("[init_ui] ✓ 中央部件已创建")
        
        # 恢复自定义标题栏
        self.create_title_bar(main_layout)
        print("[init_ui] ✓ 标题栏已创建")
        
        # 添加发光标题
        self.title_container = QWidget()
        self.title_container.setStyleSheet("background-color: #0d1117;")
        title_container_layout = QHBoxLayout(self.title_container)
        title_container_layout.setContentsMargins(10, 15, 10, 10)
        title_container_layout.setAlignment(Qt.AlignCenter)
        
        title_container_layout.addStretch()
        
        # 添加旋转地球
        self.title_globe_widget = RotatingGlobe(size=100)
        title_container_layout.addWidget(self.title_globe_widget)
        
        title_container_layout.addSpacing(20)
        
        # 添加发光主标题
        self.title_label = GlowingLabel("Facebook Marketing Pro")
        self.title_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.title_label.setTextColor(QColor(13, 17, 23))
        
        title_container_layout.addWidget(self.title_label)
        title_container_layout.addStretch()
        
        main_layout.addWidget(self.title_container)
        
        # 创建标签页控件容器
        tab_container = QWidget()
        tab_container.setStyleSheet("background-color: #0d1117;")
        tab_container_layout = QHBoxLayout(tab_container)
        tab_container_layout.setContentsMargins(3, 3, 3, 3)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        
        # 设置标签页属性，确保可以正常切换
        self.tab_widget.setTabsClosable(False)
        self.tab_widget.setMovable(False)
        self.tab_widget.setUsesScrollButtons(True)
        
        # 设置窗口样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0d1117;
                border: 1px solid #30363d;
            }
            QWidget {
                background-color: #0d1117;
                color: #c9d1d9;
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
            }
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #30363d;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 15px;
                background-color: #161b22;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #58a6ff;
            }
            QPushButton {
                background-color: #0d6efd;
                border: 1px solid #0d6efd;
                color: white;
                padding: 8px 16px;
                text-align: center;
                font-size: 13px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
                border: 1px solid #0b5ed7;
            }
            QPushButton:pressed {
                background-color: #0a58ca;
            }
            QComboBox {
                padding: 6px;
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: #161b22;
                color: #c9d1d9;
                min-width: 120px;
            }
            QComboBox:hover {
                border: 1px solid #58a6ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #58a6ff;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #161b22;
                border: 1px solid #30363d;
                selection-background-color: #0d6efd;
                color: #c9d1d9;
            }
            QTableWidget {
                gridline-color: #30363d;
                selection-background-color: #0d6efd;
                alternate-background-color: #161b22;
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #161b22;
                padding: 8px;
                border: 1px solid #30363d;
                font-weight: bold;
                color: #58a6ff;
            }
            QLabel {
                color: #c9d1d9;
            }
            QTabWidget::pane {
                border: 1px solid #30363d;
                border-radius: 8px;
                background-color: #161b22;
                padding: 0px;
                margin: 0px;
                position: relative;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #0d1117;
                color: #c9d1d9;
                padding: 8px 16px;
                border: 1px solid #30363d;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background-color: #161b22;
                color: #58a6ff;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background-color: #1a2028;
            }
        """)
        tab_container_layout.addWidget(self.tab_widget)
        
        # 创建调试侧边栏
        print("[init_ui] 正在创建调试侧边栏...")
        self.debug_sidebar = DebugSidebar()
        print("[init_ui] ✓ 调试侧边栏已创建")
        
        # 创建侧边栏的容器
        sidebar_container = QWidget()
        sidebar_container.setStyleSheet("background-color: #0d1117;")
        sidebar_container_layout = QVBoxLayout(sidebar_container)
        sidebar_container_layout.setContentsMargins(0, 38, 0, 0)
        sidebar_container_layout.setSpacing(0)
        sidebar_container_layout.addWidget(self.debug_sidebar)
        
        # 创建包含tab_container和侧边栏容器的水平布局
        content_with_sidebar_layout = QHBoxLayout()
        content_with_sidebar_layout.setContentsMargins(0, 0, 0, 0)
        content_with_sidebar_layout.setSpacing(0)
        
        content_with_sidebar_layout.addWidget(tab_container, 1)
        content_with_sidebar_layout.addWidget(sidebar_container, 0)
        
        # 创建容器来包含这个布局
        content_with_sidebar_widget = QWidget()
        content_with_sidebar_widget.setLayout(content_with_sidebar_layout)
        main_layout.addWidget(content_with_sidebar_widget)
        print("[init_ui] ✓ 侧边栏布局已创建")
        
        # 初始化调试模式
        print("[init_ui] 正在初始化调试模式...")
        init_debug_mode(enable_hotkey=True, hotkey="ctrl+shift+d",
                       debug_panel=self.debug_sidebar, main_window=self)
        print("[init_ui] ✓ 调试模式已初始化")
        
        # 创建首页标签页（数据可视化 - 延迟加载）
        home_container = QWidget()
        home_container_layout = QVBoxLayout(home_container)
        home_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加加载提示
        home_loading_label = QLabel("正在加载数据可视化...")
        home_loading_label.setStyleSheet("color: white; font-size: 16px; padding: 20px;")
        home_loading_label.setAlignment(Qt.AlignCenter)
        home_container_layout.addWidget(home_loading_label)
        
        self.tab_widget.addTab(home_container, "系统首页")
        
        # 延迟加载首页内容
        def load_home_tab():
            try:
                # 移除加载提示
                home_container_layout.removeWidget(home_loading_label)
                home_loading_label.deleteLater()
                
                # 调用实际的创建函数
                self.create_home_tab_content(home_container_layout)
                
                print("[延迟加载] ✓ 首页数据可视化已加载")
                
            except Exception as e:
                print(f"[延迟加载] ❌ 首页加载失败: {e}")
                import traceback
                traceback.print_exc()
                
                # 移除加载提示
                try:
                    home_container_layout.removeWidget(home_loading_label)
                    home_loading_label.deleteLater()
                except:
                    pass
                
                # 显示简化版首页
                welcome_label = QLabel("Facebook Marketing Pro\n\n欢迎使用！\n\n数据可视化功能加载失败")
                welcome_label.setStyleSheet("color: white; font-size: 20px; padding: 40px;")
                welcome_label.setAlignment(Qt.AlignCenter)
                home_container_layout.addWidget(welcome_label)
        
        # 延迟2000ms加载（给其他组件更多时间）
        QTimer.singleShot(2000, load_home_tab)
        print("[init_ui] ✓ 首页标签页已创建（延迟加载）")
        
        # 尝试创建主页发帖标签页（使用延迟加载）
        try:
            print("[init_ui] 正在创建主页发帖标签页...")
            # 创建一个占位容器
            posting_container = QWidget()
            posting_container_layout = QVBoxLayout(posting_container)
            posting_container_layout.setContentsMargins(0, 0, 0, 0)
            
            # 添加加载提示
            loading_label = QLabel("正在加载主页发帖功能...")
            loading_label.setStyleSheet("color: white; font-size: 16px; padding: 20px;")
            loading_label.setAlignment(Qt.AlignCenter)
            posting_container_layout.addWidget(loading_label)
            
            # 先添加占位标签页
            tab_index = self.tab_widget.addTab(posting_container, "主页发帖")
            
            # 使用定时器延迟加载实际内容
            def load_posting_tab():
                try:
                    from homepage_browser import HomepageBrowser
                    # 移除加载提示
                    posting_container_layout.removeWidget(loading_label)
                    loading_label.deleteLater()
                    
                    # 创建实际的主页发帖浏览器
                    self.homepage_browser = HomepageBrowser(self)
                    posting_container_layout.addWidget(self.homepage_browser)
                    
                    print("[延迟加载] ✓ 主页发帖功能已加载")
                except Exception as e:
                    print(f"[延迟加载] ❌ 主页发帖加载失败: {e}")
                    # 显示错误信息
                    error_label = QLabel(f"主页发帖功能加载失败\n\n{str(e)}")
                    error_label.setStyleSheet("color: #ff6b6b; font-size: 14px; padding: 20px;")
                    error_label.setAlignment(Qt.AlignCenter)
                    posting_container_layout.addWidget(error_label)
            
            # 延迟500ms加载
            QTimer.singleShot(500, load_posting_tab)
            print("[init_ui] ✓ 主页发帖标签页已创建（延迟加载）")
            
        except Exception as e:
            print(f"[init_ui] ❌ 主页发帖标签页创建失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 创建自动化标签页（延迟加载） - 移到IP代理管理之前
        automation_container = QWidget()
        automation_container_layout = QVBoxLayout(automation_container)
        automation_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加加载提示
        automation_loading_label = QLabel("正在加载自动化功能...")
        automation_loading_label.setStyleSheet("color: white; font-size: 16px; padding: 20px;")
        automation_loading_label.setAlignment(Qt.AlignCenter)
        automation_container_layout.addWidget(automation_loading_label)
        
        self.tab_widget.addTab(automation_container, "自动任务")
        
        # 延迟加载自动化功能
        def load_automation_tab():
            try:
                from browser_monitor_server import BrowserMonitorServer
                
                # 移除加载提示
                automation_container_layout.removeWidget(automation_loading_label)
                automation_loading_label.deleteLater()
                
                # 创建浏览器监控服务器实例
                self.browser_monitor = BrowserMonitorServer(auth_client=self.auth_client, main_window=self)
                automation_container_layout.addWidget(self.browser_monitor)
                
                # 创建代理属性，使旧代码能够正常工作
                self.automation_log = self.browser_monitor.log_text
                self.task_combo = None
                self.task_params_input = None
                self.browser_table = None
                self.bit_connection_status = None
                
                print("[延迟加载] ✓ 自动化功能已加载")
                
            except Exception as e:
                print(f"[延迟加载] ❌ 自动化功能加载失败: {e}")
                import traceback
                traceback.print_exc()
                
                # 移除加载提示
                try:
                    automation_container_layout.removeWidget(automation_loading_label)
                    automation_loading_label.deleteLater()
                except:
                    pass
                
                # 显示错误信息
                error_label = QLabel(f"自动化功能加载失败\n\n{str(e)}\n\n请检查 browser_monitor_server.py")
                error_label.setStyleSheet("color: #ff6b6b; font-size: 14px; padding: 20px;")
                error_label.setAlignment(Qt.AlignCenter)
                automation_container_layout.addWidget(error_label)
        
        # 延迟1000ms加载
        QTimer.singleShot(1000, load_automation_tab)
        print("[init_ui] ✓ 自动化标签页已创建（延迟加载）")
        
        # 创建视频生成标签页
        print("[init_ui] 正在创建视频生成标签页...")
        try:
            self.create_video_generation_tab()
            print("[init_ui] ✓ 视频生成标签页已创建")
        except Exception as e:
            print(f"[init_ui] ❌ 视频生成标签页创建失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 创建IP代理管理标签页（使用外部浏览器方案 - 内嵌浏览器在当前环境无法工作）
        proxy_container = QWidget()
        proxy_container_layout = QVBoxLayout(proxy_container)
        proxy_container_layout.setContentsMargins(40, 40, 40, 40)
        proxy_container_layout.setSpacing(30)
        
        # 标题
        title_label = QLabel("IP代理管理系统")
        title_label.setStyleSheet("""
            QLabel {
                color: #58a6ff;
                font-size: 36px;
                font-weight: bold;
                padding: 20px;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        proxy_container_layout.addWidget(title_label)
        
        # 说明卡片
        info_card = QWidget()
        info_card.setStyleSheet("""
            QWidget {
                background-color: #161b22;
                border: 2px solid #30363d;
                border-radius: 12px;
            }
        """)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(30, 30, 30, 30)
        info_layout.setSpacing(15)
        
        info_icon = QLabel("🌐")
        info_icon.setStyleSheet("font-size: 64px;")
        info_icon.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(info_icon)
        
        info_text = QLabel("代理管理服务运行在:")
        info_text.setStyleSheet("color: #8b949e; font-size: 16px;")
        info_text.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(info_text)
        
        url_label = QLabel("http://127.0.0.1:5000/")
        url_label.setStyleSheet("""
            QLabel {
                color: #58a6ff;
                font-size: 24px;
                font-weight: bold;
                padding: 15px;
                background-color: #0d1117;
                border-radius: 8px;
            }
        """)
        url_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(url_label)
        
        proxy_container_layout.addWidget(info_card)
        
        # ==================== IP代理管理标签页 ====================
        # 使用内嵌浏览器方案
        print("[IP代理] 创建IP代理管理标签页（内嵌浏览器方案）...")
        self.create_proxy_manager_tab()

        
        # ==================== 不再需要测试标签页 ====================
        
        # 连接标签页切换信号
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        print("[init_ui] ✓ UI初始化完成")
        print(f"[init_ui] 标签页数量: {self.tab_widget.count()}")
    
    def create_home_tab_content(self, parent_layout):
        """创建首页标签页的实际内容（完整版）"""
        # 主内容区域 - 使用水平布局
        main_content_container = QWidget()
        main_content_container.setStyleSheet("background-color: #0d1117;")
        main_content_container_layout = QHBoxLayout(main_content_container)
        main_content_container_layout.setContentsMargins(12, 12, 12, 12)
        
        main_content_layout = QHBoxLayout()
        main_content_layout.setSpacing(15)
        
        # 左侧 - 图表区域
        self.chart_group = QGroupBox("数据走势")
        chart_layout = QHBoxLayout(self.chart_group)
        chart_layout.setContentsMargins(10, 10, 10, 10)
        chart_layout.setSpacing(0)
        
        # 折线图
        self.visualization_widget = FacebookDataVisualizationWidget()
        chart_layout.addWidget(self.visualization_widget, 3)
        
        # 饼图和柱状图容器（统一背景）
        self.charts_background = ChartsBackgroundWidget()
        charts_bg_layout = QVBoxLayout(self.charts_background)
        charts_bg_layout.setContentsMargins(10, 5, 10, 10)
        charts_bg_layout.setSpacing(0)
        
        charts_bg_layout.addSpacing(15)
        
        # 饼图上方的分割线和标题
        pie_separator_line = GradientSeparatorLine("任务占比")
        charts_bg_layout.addWidget(pie_separator_line)
        
        # 饼图
        self.pie_chart_widget = PieChartWidget()
        self.pie_chart_widget.set_data({
            '点赞': 100,
            '评论': 50,
            '分享': 30,
            '好友': 20,
            '动态': 10
        })
        self.pie_chart_widget.setMinimumWidth(300)
        self.pie_chart_widget.setMinimumHeight(320)
        self.pie_chart_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.pie_chart_widget.setStyleSheet("background-color: transparent; padding-top: 0px; padding-bottom: 40px;")
        charts_bg_layout.addWidget(self.pie_chart_widget, 3)
        
        charts_bg_layout.addSpacing(0)
        
        # 添加渐变透明分割线，带"账号留存"标签
        separator_line = GradientSeparatorLine("账号留存")
        charts_bg_layout.addWidget(separator_line)
        
        # 柱状图
        self.bar_chart_widget = BarChartWidget()
        self.bar_chart_widget.set_data({
            '点赞': 100,
            '评论': 50,
            '分享': 30,
            '好友': 20,
            '动态': 10
        })
        self.bar_chart_widget.setMinimumHeight(180)
        self.bar_chart_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.bar_chart_widget.setStyleSheet("background-color: transparent;")
        charts_bg_layout.addWidget(self.bar_chart_widget, 2)
        
        # 设置统一背景容器的样式和大小
        self.charts_background.setMinimumWidth(300)
        self.charts_background.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.charts_background.hide()
        
        chart_layout.addWidget(self.charts_background, 1)
        
        print("=" * 80)
        print(f"[饼图调试] 饼图组件已创建")
        print(f"[饼图调试] 饼图数据: {self.pie_chart_widget.data}")
        print(f"[饼图调试] 饼图初始可见性: {self.pie_chart_widget.isVisible()}")
        print("=" * 80)
        
        QTimer.singleShot(100, self.check_and_show_pie_chart)
        
        main_content_layout.addWidget(self.chart_group, 3)
        
        # 右侧 - 数据表、模拟器监控和日志输出区域
        right_panel = QVBoxLayout()
        right_panel.setSpacing(15)
        
        # 数据表区域
        table_group = QGroupBox("详细数据")
        table_layout = QVBoxLayout(table_group)
        table_layout.setContentsMargins(10, 10, 10, 10)
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(9)
        self.data_table.setHorizontalHeaderLabels(["日期", "点赞数", "评论数", "分享数", "好友数", "动态数", "今日加组", "今日转发", "账号数"])
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.data_table.setAlternatingRowColors(True)
        
        # 隐藏垂直头部并解决表格左上角顶点白色问题
        self.data_table.verticalHeader().setVisible(False)
        corner_widget = QWidget()
        corner_widget.setStyleSheet("background-color: #161b22; border: 1px solid #30363d;")
        self.data_table.setCornerWidget(corner_widget)
        
        self.populate_table()
        table_layout.addWidget(self.data_table)
        right_panel.addWidget(table_group, 3)
        
        # 浏览器状态区域（卡片式显示）
        browser_status_group = QGroupBox("浏览器状态")
        browser_status_layout = QVBoxLayout(browser_status_group)
        browser_status_layout.setContentsMargins(10, 15, 10, 15)
        browser_status_layout.setSpacing(10)
        
        # 浏览器卡片容器（滚动区域）
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:horizontal {
                border: none;
                background-color: #0d1117;
                height: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background-color: #30363d;
                border-radius: 4px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #484f58;
            }
        """)
        
        # 卡片容器（使用水平布局，单行显示）
        self.browser_cards_container = QWidget()
        self.browser_cards_layout = QHBoxLayout(self.browser_cards_container)
        self.browser_cards_layout.setContentsMargins(5, 5, 5, 5)
        self.browser_cards_layout.setSpacing(10)
        self.browser_cards_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        scroll_area.setWidget(self.browser_cards_container)
        browser_status_layout.addWidget(scroll_area)
        
        right_panel.addWidget(browser_status_group, 1)
        
        # 日志输出区域
        log_group = QGroupBox("请求日志")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(10, 15, 10, 15)
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setMaximumHeight(100)
        self.log_text_edit.setStyleSheet("""
            color: #8b949e; 
            padding: 8px;
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 5px;
            font-size: 12px;
            font-family: Consolas, Monaco, monospace;
        """)
        self.log_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.log_text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        log_layout.addWidget(self.log_text_edit)
        right_panel.addWidget(log_group, 1)
        
        # 添加扩展功能按钮
        self.create_extension_buttons(right_panel)
        
        main_content_layout.addLayout(right_panel, 2)
        
        main_content_container_layout.addLayout(main_content_layout)
        parent_layout.addWidget(main_content_container)
        
        # 状态栏
        status_container = QWidget()
        status_container.setStyleSheet("background-color: #0d1117;")
        status_container_layout = QHBoxLayout(status_container)
        status_container_layout.setContentsMargins(12, 12, 12, 12)
        
        # 从服务器加载通知，如果失败则使用默认通知
        notification_text = self._load_notification()
        self.status_label = MarqueeLabel(notification_text)
        self.status_label.setStyleSheet("""
            color: #8b949e; 
            padding: 8px;
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 5px;
            font-size: 12px;
        """)
        status_container_layout.addWidget(self.status_label)
        parent_layout.addWidget(status_container)
        
        # 实时检查数据版本（每2秒检查一次）
        self.current_data_version = 0
        self.version_check_timer = QTimer(self)
        self.version_check_timer.timeout.connect(self.check_data_version)
        self.version_check_timer.start(2000)
        
        # 定时获取请求日志
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.fetch_request_logs)
        self.log_timer.start(5000)
        
        # 启动浏览器状态自动刷新（每分钟）
        self.start_browser_refresh_timer()
        # 首次刷新（延迟500ms，确保UI完全初始化并且窗口已最大化）
        QTimer.singleShot(500, self.refresh_browser_cards)
        
        print("✓ 首页完整内容已创建（包含饼图、柱状图、日志等）")
        
    def create_home_tab(self):
        """创建首页标签页"""
        # 创建首页标签页的主部件
        home_widget = QWidget()
        home_layout = QVBoxLayout(home_widget)
        home_layout.setContentsMargins(0, 0, 0, 0)
        
        # 主内容区域 - 使用水平布局
        main_content_container = QWidget()  # 创建一个容器来控制边距
        main_content_container.setStyleSheet("background-color: #0d1117;")
        main_content_container_layout = QHBoxLayout(main_content_container)
        main_content_container_layout.setContentsMargins(12, 12, 12, 12)
        
        main_content_layout = QHBoxLayout()
        main_content_layout.setSpacing(15)  # 恢复组件之间的间距，确保足够的空间
        
        # 左侧 - 图表区域
        self.chart_group = QGroupBox("数据走势")
        chart_layout = QHBoxLayout(self.chart_group)  # 改为水平布局
        chart_layout.setContentsMargins(10, 10, 10, 10)  # 减少顶部边距，让背景往上移
        chart_layout.setSpacing(0)  # 移除组件间距，让内部组件紧贴
        
        # 折线图
        self.visualization_widget = FacebookDataVisualizationWidget()
        chart_layout.addWidget(self.visualization_widget, 3)  # 拉伸因子3
        
        # 饼图和柱状图容器（统一背景）
        self.charts_background = ChartsBackgroundWidget()
        charts_bg_layout = QVBoxLayout(self.charts_background)
        charts_bg_layout.setContentsMargins(10, 5, 10, 10)  # 减少顶部边距从10到5
        charts_bg_layout.setSpacing(0)  # 移除所有默认间距
        
        # 添加间距，让"任务占比"分割线向下移动
        charts_bg_layout.addSpacing(15)
        
        # 饼图上方的分割线和标题
        pie_separator_line = GradientSeparatorLine("任务占比")
        charts_bg_layout.addWidget(pie_separator_line)
        
        # 不添加额外间距，让饼图紧贴分割线
        
        # 饼图
        self.pie_chart_widget = PieChartWidget()
        # 设置初始示例数据，确保饼图可见
        self.pie_chart_widget.set_data({
            '点赞': 100,
            '评论': 50,
            '分享': 30,
            '好友': 20,
            '动态': 10
        })
        # 设置尺寸和样式
        self.pie_chart_widget.setMinimumWidth(300)
        self.pie_chart_widget.setMinimumHeight(320)  # 增加最小高度，让饼图有更多空间
        self.pie_chart_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        # 使用透明背景，增加底部内边距以容纳悬停时突出的饼块
        self.pie_chart_widget.setStyleSheet("background-color: transparent; padding-top: 0px; padding-bottom: 40px;")  # 增加底部内边距，确保悬停时不被裁剪
        charts_bg_layout.addWidget(self.pie_chart_widget, 3)  # 饼图占3份，增加占比
        
        # 添加更小的垂直间距，让分割线更靠上
        charts_bg_layout.addSpacing(0)  # 移除上方间距
        
        # 添加渐变透明分割线，带"账号留存"标签
        separator_line = GradientSeparatorLine("账号留存")
        charts_bg_layout.addWidget(separator_line)
        
        # 不需要额外间距，因为分割线组件本身高度已包含文字空间
        # charts_bg_layout.addSpacing(10)  # 移除，避免过多空白
        
        # 柱状图
        self.bar_chart_widget = BarChartWidget()
        self.bar_chart_widget.set_data({
            '点赞': 100,
            '评论': 50,
            '分享': 30,
            '好友': 20,
            '动态': 10
        })
        self.bar_chart_widget.setMinimumHeight(180)  # 降低最小高度到180
        self.bar_chart_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)  # 改回Preferred，不过度扩展
        # 使用透明背景
        self.bar_chart_widget.setStyleSheet("background-color: transparent;")
        charts_bg_layout.addWidget(self.bar_chart_widget, 2)  # 柱状图占2份，减少占比
        
        # 设置统一背景容器的样式和大小
        self.charts_background.setMinimumWidth(300)
        self.charts_background.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        # 初始状态隐藏（因为窗口初始不是最大化）
        self.charts_background.hide()
        
        chart_layout.addWidget(self.charts_background, 1)  # 拉伸因子1
        
        # 调试：确认饼图已创建
        print("=" * 80)
        print(f"[饼图调试] 饼图组件已创建")
        print(f"[饼图调试] 饼图数据: {self.pie_chart_widget.data}")
        print(f"[饼图调试] 饼图初始可见性: {self.pie_chart_widget.isVisible()}")
        print("=" * 80)
        
        # 使用定时器延迟检查窗口状态（确保窗口完全加载）
        QTimer.singleShot(100, self.check_and_show_pie_chart)
        
        main_content_layout.addWidget(self.chart_group, 3)  # 恢复拉伸因子为3，平衡左右区域宽度
        
        # 右侧 - 数据表、模拟器监控和日志输出区域
        right_panel = QVBoxLayout()
        right_panel.setSpacing(15)  # 恢复组件之间的间距，确保足够的空间
        
        # 数据表区域
        table_group = QGroupBox("详细数据")
        table_layout = QVBoxLayout(table_group)
        table_layout.setContentsMargins(10, 10, 10, 10)  # 与左侧图表区域对齐，减少顶部边距
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(9)
        self.data_table.setHorizontalHeaderLabels(["日期", "点赞数", "评论数", "分享数", "好友数", "动态数", "今日加组", "今日转发", "账号数"])
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.data_table.setAlternatingRowColors(True)
        
        # 隐藏垂直头部并解决表格左上角顶点白色问题
        self.data_table.verticalHeader().setVisible(False)
        corner_widget = QWidget()
        corner_widget.setStyleSheet("background-color: #161b22; border: 1px solid #30363d;")
        self.data_table.setCornerWidget(corner_widget)
        
        self.populate_table()
        table_layout.addWidget(self.data_table)
        right_panel.addWidget(table_group, 3)  # 恢复拉伸因子为3
        
        # 浏览器状态区域（卡片式显示）
        browser_status_group = QGroupBox("浏览器状态")
        browser_status_layout = QVBoxLayout(browser_status_group)
        browser_status_layout.setContentsMargins(10, 15, 10, 15)
        browser_status_layout.setSpacing(10)
        
        # 浏览器卡片容器（滚动区域）
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # 水平滚动条
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 禁用垂直滚动条
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:horizontal {
                border: none;
                background-color: #0d1117;
                height: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background-color: #30363d;
                border-radius: 4px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #484f58;
            }
        """)
        
        # 卡片容器（使用水平布局，单行显示）
        self.browser_cards_container = QWidget()
        self.browser_cards_layout = QHBoxLayout(self.browser_cards_container)
        self.browser_cards_layout.setContentsMargins(5, 5, 5, 5)
        self.browser_cards_layout.setSpacing(10)
        self.browser_cards_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        scroll_area.setWidget(self.browser_cards_container)
        browser_status_layout.addWidget(scroll_area)
        
        right_panel.addWidget(browser_status_group, 1)  # 设置拉伸因子为1
        
        # 日志输出区域
        log_group = QGroupBox("请求日志")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(10, 15, 10, 15)
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setMaximumHeight(100)  # 限制最大高度为100像素
        self.log_text_edit.setStyleSheet("""
            color: #8b949e; 
            padding: 8px;
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 5px;
            font-size: 12px;
            font-family: Consolas, Monaco, monospace;
        """)
        self.log_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.log_text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        log_layout.addWidget(self.log_text_edit)
        right_panel.addWidget(log_group, 1)  # 设置拉伸因子为1，减小占比
        
        # 添加扩展功能按钮
        self.create_extension_buttons(right_panel)
        
        main_content_layout.addLayout(right_panel, 2)  # 恢复拉伸因子为2
        
        main_content_container_layout.addLayout(main_content_layout)
        home_layout.addWidget(main_content_container)
        
        # 状态栏
        status_container = QWidget()  # 创建一个容器来控制边距
        status_container.setStyleSheet("background-color: #0d1117;")
        status_container_layout = QHBoxLayout(status_container)
        status_container_layout.setContentsMargins(12, 12, 12, 12)
        
        # 从服务器加载通知，如果失败则使用默认通知
        notification_text = self._load_notification()
        self.status_label = MarqueeLabel(notification_text)
        self.status_label.setStyleSheet("""
            color: #8b949e; 
            padding: 8px;
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 5px;
            font-size: 12px;
        """)
        status_container_layout.addWidget(self.status_label)
        home_layout.addWidget(status_container)
        
        # 将首页标签页添加到标签页控件中
        self.tab_widget.addTab(home_widget, "数据首页")
        
        # 实时检查数据版本（每2秒检查一次）
        self.current_data_version = 0
        self.version_check_timer = QTimer(self)
        self.version_check_timer.timeout.connect(self.check_data_version)
        self.version_check_timer.start(2000)  # 每2秒检查一次版本
        
        # 定时获取请求日志
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.fetch_request_logs)
        self.log_timer.start(5000)  # 每5秒获取一次请求日志
        
        # 启动浏览器状态自动刷新（每分钟）
        self.start_browser_refresh_timer()
        # 首次刷新（延迟500ms，确保UI完全初始化并且窗口已最大化）
        QTimer.singleShot(500, self.refresh_browser_cards)
        
    def create_extension_buttons(self, layout):
        """创建扩展功能按钮"""
        try:
            # 检查路由是否可用
            if not ROUTES_AVAILABLE:
                print("路由管理器不可用，跳过扩展按钮创建")
                return
                
            # 创建扩展功能区域
            extension_group = QGroupBox("扩展功能")
            extension_layout = QVBoxLayout(extension_group)
            extension_layout.setContentsMargins(10, 15, 10, 15)
            
            # 创建按钮样式表
            button_style = """
                QPushButton {
                    background-color: #238636;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #2ea043;
                }
                QPushButton:pressed {
                    background-color: #1f6feb;
                }
            """
            
            # 获取可用路由（异步，避免阻塞）
            available_routes = []
            
            def fetch_routes():
                nonlocal available_routes
                try:
                    response = requests.get("http://localhost:8805/get_available_routes", timeout=1)
                    if response.status_code == 200:
                        available_routes = response.json().get("routes", [])
                except:
                    pass
            
            # 在后台线程中获取路由
            import threading
            route_thread = threading.Thread(target=fetch_routes, daemon=True)
            route_thread.start()
            route_thread.join(timeout=0.5)  # 最多等待0.5秒
            
            # 根据可用路由创建按钮
            buttons_created = False
            
            # 检查是否有桌面程序执行路由
            if "/execute_desktop_program" in available_routes:
                desktop_btn = QPushButton("执行桌面程序")
                desktop_btn.setStyleSheet(button_style)
                desktop_btn.clicked.connect(self.execute_desktop_program)
                extension_layout.addWidget(desktop_btn)
                buttons_created = True
            
            # 检查是否有后端程序执行路由
            if "/execute_backend_program" in available_routes:
                backend_btn = QPushButton("执行后端程序")
                backend_btn.setStyleSheet(button_style)
                backend_btn.clicked.connect(self.execute_backend_program)
                extension_layout.addWidget(backend_btn)
                buttons_created = True
                
            # 如果创建了按钮，则添加到布局中
            if buttons_created:
                layout.addWidget(extension_group)
            else:
                # 如果没有可用的扩展路由，隐藏扩展功能区域
                extension_group.hide()
                
        except Exception as e:
            print(f"创建扩展按钮时出错: {e}")
            # 隐藏扩展功能区域
            if 'extension_group' in locals():
                extension_group.hide()
        
    def execute_desktop_program(self):
        """执行桌面程序"""
        try:
            # 这里可以添加执行桌面程序的逻辑
            # 例如：打开记事本
            response = requests.post(
                "http://localhost:8805/execute_desktop_program",
                json={"program": "notepad.exe"},
                timeout=10
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    QMessageBox.information(self, "成功", f"程序执行成功: {result.get('message')}")
                else:
                    QMessageBox.warning(self, "错误", f"程序执行失败: {result.get('message')}")
            else:
                QMessageBox.critical(self, "错误", f"请求失败: {response.status_code}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"执行桌面程序时出错: {str(e)}")

    def execute_backend_program(self):
        """执行后端程序"""
        try:
            # 这里可以添加执行后端程序的逻辑
            response = requests.post(
                "http://localhost:8805/execute_backend_program",
                json={"command": "echo Hello World"},
                timeout=10
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    QMessageBox.information(self, "成功", f"后端程序执行成功: {result.get('output')}")
                else:
                    QMessageBox.warning(self, "错误", f"后端程序执行失败: {result.get('message')}")
            else:
                QMessageBox.critical(self, "错误", f"请求失败: {response.status_code}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"执行后端程序时出错: {str(e)}")
            
    def populate_table(self):
        """填充表格数据"""
        data = self.visualization_widget.data
        self.data_table.setRowCount(len(data))
        
        # 获取今日数据（最后一行）
        today_data = data[-1] if data else {}
        
        # 更新饼图数据（使用今日数据）
        if today_data:
            pie_data = {
                '点赞': today_data.get('likes', 0),
                '评论': today_data.get('comments', 0),
                '分享': today_data.get('shares', 0),
                '好友': today_data.get('friends', 0),
                '动态': today_data.get('posts', 0),
                '加组': today_data.get('groups', 0),
                '转发': today_data.get('forwards', 0),
            }
            self.pie_chart_widget.set_data(pie_data)
        
        # 更新柱状图数据（使用近7天的账号数量）
        if hasattr(self, 'bar_chart_widget') and len(data) > 0:
            # 获取最近7天的数据
            recent_7_days = data[-7:] if len(data) >= 7 else data
            bar_data = {}
            for item in recent_7_days:
                date = item.get('date', '')
                accounts = item.get('accounts', 0)
                # 使用日期作为标签（只显示月-日）
                if date:
                    # 提取月-日部分，例如 "2024-01-15" -> "01-15"
                    date_parts = date.split('-')
                    if len(date_parts) >= 3:
                        label = f"{date_parts[1]}-{date_parts[2]}"
                    else:
                        label = date
                else:
                    label = f"第{len(bar_data)+1}天"
                bar_data[label] = accounts
            self.bar_chart_widget.set_data(bar_data)
        
        # 更新图表标题
        self.chart_group.setTitle("数据走势")
        
        for row, item in enumerate(data):
            # 日期
            date_item = QTableWidgetItem(item['date'])
            date_item.setTextAlignment(QtCore_Qt.AlignCenter)
            self.data_table.setItem(row, 0, date_item)
            
            # 点赞数
            likes_item = QTableWidgetItem(str(item['likes']))
            likes_item.setTextAlignment(QtCore_Qt.AlignCenter)
            self.data_table.setItem(row, 1, likes_item)
            
            # 评论数
            comments_item = QTableWidgetItem(str(item['comments']))
            comments_item.setTextAlignment(QtCore_Qt.AlignCenter)
            self.data_table.setItem(row, 2, comments_item)
            
            # 分享数
            shares_item = QTableWidgetItem(str(item['shares']))
            shares_item.setTextAlignment(QtCore_Qt.AlignCenter)
            self.data_table.setItem(row, 3, shares_item)
            
            # 好友数
            friends_item = QTableWidgetItem(str(item['friends']))
            friends_item.setTextAlignment(QtCore_Qt.AlignCenter)
            self.data_table.setItem(row, 4, friends_item)
            
            # 动态数
            posts_item = QTableWidgetItem(str(item['posts']))
            posts_item.setTextAlignment(QtCore_Qt.AlignCenter)
            self.data_table.setItem(row, 5, posts_item)
            
            # 今日加组
            groups_item = QTableWidgetItem(str(item['groups']))
            groups_item.setTextAlignment(QtCore_Qt.AlignCenter)
            self.data_table.setItem(row, 6, groups_item)
            
            # 今日转发（只显示 forwards 字段）
            forwards_value = item.get('forwards', 0)
            forwards_item = QTableWidgetItem(str(forwards_value))
            forwards_item.setTextAlignment(QtCore_Qt.AlignCenter)
            self.data_table.setItem(row, 7, forwards_item)
            
            # 账号数（移到最后）
            accounts_item = QTableWidgetItem(str(item['accounts']))
            accounts_item.setTextAlignment(QtCore_Qt.AlignCenter)
            self.data_table.setItem(row, 8, accounts_item)
            
    def show_loading(self):
        """显示加载动画"""
        self.visualization_widget.loading_spinner.show()
        self.visualization_widget.loading_spinner.raise_()  # 确保加载动画在最上层
        # 在窗口居中显示加载动画
        spinner_x = self.visualization_widget.geometry().x() + (
            self.visualization_widget.width() - self.visualization_widget.loading_spinner.width()) // 2
        spinner_y = self.visualization_widget.geometry().y() + (
            self.visualization_widget.height() - self.visualization_widget.loading_spinner.height()) // 2
        self.visualization_widget.loading_spinner.move(spinner_x, spinner_y)
        
    def hide_loading(self):
        """隐藏加载动画"""
        self.visualization_widget.loading_spinner.hide()
        
    def refresh_data(self):
        """刷新数据"""
        self.show_loading()
        # 使用异步方式获取数据
        self.fetch_real_data_async()
        
    def fetch_real_data_async(self):
        """异步获取真实数据"""
        try:
            # 创建数据获取工作对象和线程
            url = "http://localhost:8805/get_current_data"
            # 账号管理路径已废弃（改用比特浏览器API）
            self.data_fetch_worker = DataFetchWorker(url, None)
            self.data_fetch_thread = QThread()
            
            # 将工作对象移动到线程
            self.data_fetch_worker.moveToThread(self.data_fetch_thread)
            
            # 连接信号和槽
            self.data_fetch_worker.data_fetched.connect(self.on_data_fetched)
            self.data_fetch_worker.error_occurred.connect(self.on_data_fetch_error)
            self.data_fetch_worker.finished.connect(self.on_data_fetch_finished)
            self.data_fetch_worker.finished.connect(self.data_fetch_thread.quit)
            self.data_fetch_worker.finished.connect(self.data_fetch_worker.deleteLater)
            self.data_fetch_thread.finished.connect(self.data_fetch_thread.deleteLater)
            
            # 启动线程并触发数据获取
            self.data_fetch_thread.start()
            self.data_fetch_worker.fetch_data()
        except Exception as e:
            print(f"启动数据获取线程时出错: {e}")
            self.update_log(f"日志: 启动数据获取线程时出错 - {str(e)}")
            self.hide_loading()

    def on_data_fetched(self, result):
        """数据获取成功的回调"""
        try:
            if result.get('status') == 'success':
                # 更新版本号
                if 'version' in result:
                    self.current_data_version = result['version']
                
                # 数据获取成功，更新本地数据
                fetched_data = result.get('data', [])
                if fetched_data:
                    # 使用获取到的数据替换当前数据
                    print("=" * 80)
                    print(f"[数据获取] ✓ 从后端获取到 {len(fetched_data)} 条数据")
                    if fetched_data:
                        print(f"[数据获取] 日期范围: {fetched_data[0]['date']} 到 {fetched_data[-1]['date']}")
                    print(f"[数据获取] 数据版本: {self.current_data_version}")
                    print("=" * 80)
                    self.visualization_widget.data = fetched_data
                    self.visualization_widget.save_data()  # 保存到本地文件
                    
                    # 触发数字滚动动画
                    if fetched_data:
                        today_data = fetched_data[-1]
                        data_items = [
                            (today_data['likes'], "今日点赞"),
                            (today_data['comments'], "今日评论"),
                            (today_data['shares'], "今日分享"),
                            (today_data['friends'], "今日好友"),
                            (today_data['posts'], "今日动态"),
                            (today_data['groups'], "今日加组"),
                            (today_data.get('forwards', 0), "今日转发"),
                            (today_data['accounts'], "今日账号")
                        ]
                        self.visualization_widget.start_number_animation(data_items)
                    
                    # 更新界面
                    self.visualization_widget.update()
                    self.populate_table()
                    self.update_log(f"日志: 成功获取数据，共{len(self.visualization_widget.data)}条记录 (v{self.current_data_version})")
                else:
                    # 如果没有获取到数据，只刷新界面，不修改数据
                    self.visualization_widget.update()
                    self.populate_table()
                    self.update_log("日志: 未获取到数据，显示现有数据")
            else:
                print(f"数据获取失败: {result.get('message')}")
                self.update_log(f"日志: 数据获取失败 - {result.get('message')}")
                # 获取数据失败，只刷新界面，不修改数据
                self.visualization_widget.update()
                self.populate_table()
        except Exception as e:
            print(f"处理获取到的数据时出错: {e}")
            self.update_log(f"日志: 处理数据时出错 - {str(e)}")
            # 出现异常时，只刷新界面，不修改数据
            self.visualization_widget.update()
            self.populate_table()
        finally:
            # 确保隐藏加载动画
            self.hide_loading()

    def on_data_fetch_error(self, error_message):
        """数据获取失败的回调"""
        print(f"数据获取失败: {error_message}")
        self.update_log(f"日志: 数据获取失败 - {error_message}")
        # 获取数据失败，只刷新界面，不修改数据
        self.visualization_widget.update()
        self.populate_table()
        # 确保隐藏加载动画
        self.hide_loading()

    def on_data_fetch_finished(self):
        """数据获取完成的回调"""
        # 确保隐藏加载动画
        self.hide_loading()
    
    def update_log(self, message):
        """更新日志输出栏"""
        if hasattr(self, 'log_text_edit'):
            # 获取当前文本
            current_text = self.log_text_edit.toPlainText()
            # 添加新消息
            new_text = current_text + "\n" + message if current_text else message
            # 设置文本
            self.log_text_edit.setText(new_text)
            # 滚动到底部
            self.log_text_edit.verticalScrollBar().setValue(
                self.log_text_edit.verticalScrollBar().maximum()
            )
        # 如果存在旧的log_label，也更新它（为了兼容性）
        if hasattr(self, 'log_label'):
            self.log_label.setText(message)
    
    def check_data_version(self):
        """检查数据版本是否有更新（异步，不阻塞UI）"""
        # 如果上一个检查还在进行中，跳过本次检查
        try:
            if hasattr(self, 'version_check_thread') and self.version_check_thread is not None and self.version_check_thread.isRunning():
                return
        except RuntimeError:
            # 线程已被删除，继续执行
            pass
        
        try:
            # 创建版本检查工作对象和线程
            url = "http://localhost:8805/check_data_version"
            self.version_check_worker = VersionCheckWorker(url)
            self.version_check_thread = QThread()
            
            # 将工作对象移动到线程
            self.version_check_worker.moveToThread(self.version_check_thread)
            
            # 连接信号和槽
            self.version_check_worker.version_checked.connect(self.on_version_checked)
            self.version_check_worker.finished.connect(self.version_check_thread.quit)
            self.version_check_worker.finished.connect(self.version_check_worker.deleteLater)
            self.version_check_thread.finished.connect(self.version_check_thread.deleteLater)
            
            # 启动线程并触发版本检查
            self.version_check_thread.started.connect(self.version_check_worker.check_version)
            self.version_check_thread.start()
        except Exception as e:
            # 静默失败，不影响用户体验
            pass
    
    def on_version_checked(self, server_version):
        """版本检查完成的回调"""
        try:
            # 如果服务器版本号更新，则刷新数据
            if server_version > self.current_data_version:
                print(f"[实时更新] 检测到数据更新: v{self.current_data_version} → v{server_version}")
                self.current_data_version = server_version
                self.refresh_data()
                self.update_log(f"日志: 检测到数据更新，自动刷新 (版本: {server_version})")
        except Exception as e:
            pass
    
    def auto_refresh(self):
        """自动刷新数据"""
        self.refresh_data()
        
    def fetch_request_logs(self):
        """获取并显示请求日志（异步，不阻塞 UI）"""
        # 使用线程异步请求，避免阻塞 UI
        def _fetch():
            try:
                import urllib.request
                import json
                
                # 发送请求到后台服务获取请求日志
                url = "http://localhost:8805/get_request_logs"
                headers = {
                    'User-Agent': 'FacebookDashboard/1.0'
                }
                
                # 创建请求对象
                req = urllib.request.Request(url, headers=headers)
                
                # 发送请求，设置超时为 1 秒（快速失败）
                response = urllib.request.urlopen(req, timeout=1)
                
                # 检查HTTP状态码
                if response.getcode() == 200:
                    # 获取响应内容并使用UTF-8解码
                    response_content = response.read()
                    result = json.loads(response_content.decode('utf-8'))
                    
                    if result.get('status') == 'success':
                        logs = result.get('data', [])
                        if logs:
                            # 构建日志文本，显示最近几条日志
                            log_texts = []
                            # 显示最近5条日志
                            for log in logs[-5:]:
                                log_text = f"[{log['timestamp']}] {log['method']} {log['path']} - {log['client_ip']} - Status: {log['status_code']}"
                                log_texts.append(log_text)
                            
                            # 使用信号在主线程中更新 UI（线程安全）
                            log_content = "\n".join(log_texts)
                            self.update_log_signal.emit(log_content)
            except Exception as e:
                # 静默失败，不打印错误（避免刷屏）
                # 如果需要调试，可以取消注释下面这行
                # print(f"获取请求日志时出错: {e}")
                pass
        
        # 在后台线程中执行请求
        import threading
        thread = threading.Thread(target=_fetch, daemon=True)
        thread.start()
    
    def _update_log_text(self, text):
        """更新日志文本（在主线程中调用）"""
        if hasattr(self, 'log_text_edit'):
            self.log_text_edit.setText(text)
        
    def test_maximize(self):
        """测试最大化功能"""
        print(f"测试前状态: isMaximized={self.isMaximized()}")
        self.toggle_maximize()
        print(f"测试后状态: isMaximized={self.isMaximized()}")
        # 触发resizeEvent
        self.resizeEvent(None)

    def create_video_generation_tab(self):
        """创建视频生成标签页"""
        # 创建视频生成标签页的主部件
        video_widget = QWidget()
        video_layout = QVBoxLayout(video_widget)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setAlignment(Qt.AlignTop)  # 设置顶部对齐，使内容向上靠拢
        video_layout.setSpacing(0)  # 设置布局间距为0
        
        # 视频生成控制面板
        control_container = QWidget()  # 创建一个容器来控制边距
        control_container.setStyleSheet("background-color: #0d1117;")
        control_container_layout = QHBoxLayout(control_container)
        control_container_layout.setContentsMargins(12, 12, 12, 12)  # 统一边距为12
        control_container_layout.setAlignment(Qt.AlignTop)  # 设置顶部对齐
        
        control_group = QGroupBox("视频生成设置")
        control_group.setAlignment(Qt.AlignTop)  # 将标题向上对齐
        # 使用与其它栏目一致的样式设置，但调整边框圆角使其更紧凑
        control_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #30363d;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 15px;  /* 增加顶部内边距以确保标题不被遮挡 */
                font-size: 14px;
                font-weight: bold;
                background-color: #161b22;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #58a6ff;
            }
        """)
        control_layout = QVBoxLayout(control_group)
        control_layout.setContentsMargins(6, 6, 6, 6)  # 统一内边距为6px
        control_layout.setSpacing(5)  # 减少控件间距为5像素，使布局更紧凑
        control_layout.setAlignment(Qt.AlignTop)  # 设置顶部对齐，使内容向上靠拢
        
        # 控制设置区域 - 使用网格布局优化排列
        settings_container = QWidget()
        settings_layout = QGridLayout(settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)  # 移除外层容器的内边距
        settings_layout.setSpacing(6)  # 统一间距为6像素
        settings_layout.setAlignment(Qt.AlignTop)  # 设置顶部对齐
        
        # AI提示词输入容器
        prompt_container = QWidget()
        prompt_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)  # 设置容器高度为固定
        prompt_container.setStyleSheet("background-color: #0d1117;")  # 矩形无圆角
        prompt_layout = QHBoxLayout(prompt_container)
        prompt_layout.setContentsMargins(6, 6, 6, 6)  # 统一内边距为6px
        prompt_layout.setSpacing(6)  # 统一间距为6像素
        prompt_layout.setAlignment(Qt.AlignVCenter)  # 垂直居中对齐
        
        prompt_label = QLabel("文案提示:")
        prompt_label.setStyleSheet("color: #c9d1d9; font-size: 13px; font-weight: bold;")
        prompt_label.setFixedWidth(80)  # 设置标签宽度为80像素（4个汉字）
        prompt_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # 右对齐并垂直居中
        
        self.video_prompt_input = QTextEdit()
        self.video_prompt_input.setPlaceholderText("AI提示词...")
        # 设置固定高度为64像素，比其他控件高一倍
        self.video_prompt_input.setFixedHeight(64)
        self.video_prompt_input.setStyleSheet("""
            QTextEdit {
                padding: 8px;
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: #161b22;
                color: #c9d1d9;
                font-size: 12px;
            }
            QTextEdit:focus {
                border: 1px solid #58a6ff;
            }
        """)
        # 加载默认提示词
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_path, "video_tools", "ui_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                default_prompt = config.get("prompt", "")
            if default_prompt:
                self.video_prompt_input.setPlainText(default_prompt)
        # 添加垂直居中对齐
        self.video_prompt_input.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        prompt_layout.addWidget(prompt_label)
        prompt_layout.addWidget(self.video_prompt_input)
        control_layout.addWidget(prompt_container)
        
        # 控件容器
        controls_container = QWidget()
        controls_container.setStyleSheet("background-color: #0d1117; border-radius: 6px;")  # 添加背景色和圆角
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setContentsMargins(6, 6, 6, 6)  # 统一内边距为6px
        controls_layout.setSpacing(6)  # 统一间距为6像素
        controls_layout.setAlignment(Qt.AlignVCenter)  # 垂直居中对齐
        
        # 语音引擎选择
        tts_engine_label = QLabel("语音引擎:")
        tts_engine_label.setStyleSheet("color: #c9d1d9; font-size: 13px; font-weight: bold;")
        tts_engine_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # 右对齐并垂直居中
        tts_engine_label.setFixedWidth(80)  # 设置标签宽度为80像素（4个汉字）
        
        self.tts_engine_combo = QComboBox()
        self.tts_engine_combo.addItems(["阿里云百炼", "Edge-TTS"])
        self.tts_engine_combo.setMinimumHeight(32)
        self.tts_engine_combo.setFixedWidth(180)  # 设置宽度为180像素，与其他控件保持一致
        self.tts_engine_combo.setMinimumWidth(180)  # 设置最小宽度确保一致性
        self.tts_engine_combo.setStyleSheet("""
            QComboBox {
                padding: 5px 10px;
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: #0d1117;
                color: #c9d1d9;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #58a6ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #c9d1d9;
                width: 0;
                height: 0;
                margin-right: 5px;
            }
        """)
        # 添加垂直居中对齐
        self.tts_engine_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        # 音色选择
        voice_label = QLabel("音色选择:")
        voice_label.setStyleSheet("color: #c9d1d9; font-size: 13px; font-weight: bold;")
        voice_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # 右对齐并垂直居中
        voice_label.setFixedWidth(80)  # 设置标签宽度为80像素（4个汉字）
        
        self.voice_combo = QComboBox()
        self.voice_combo.addItems(["Cherry", "Alice", "Bob", "Yunyang (男声)"])
        self.voice_combo.setMinimumHeight(32)
        self.voice_combo.setFixedWidth(180)  # 设置宽度为180像素，与其他控件保持一致
        self.voice_combo.setMinimumWidth(180)  # 设置最小宽度确保一致性
        self.voice_combo.setStyleSheet("""
            QComboBox {
                padding: 5px 10px;
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: #0d1117;
                color: #c9d1d9;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #58a6ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #c9d1d9;
                width: 0;
                height: 0;
                margin-right: 5px;
            }
        """)
        # 添加垂直居中对齐
        self.voice_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        # 百炼API Key输入框
        api_key_label = QLabel("百炼API:")
        api_key_label.setStyleSheet("color: #c9d1d9; font-size: 13px; font-weight: bold;")
        api_key_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        api_key_label.setFixedWidth(80)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("输入阿里云百炼API Key")
        self.api_key_input.setMinimumHeight(32)
        self.api_key_input.setFixedWidth(180)
        self.api_key_input.setEchoMode(QLineEdit.Password)  # 密码模式显示
        self.api_key_input.setStyleSheet("""
            QLineEdit {
                padding: 5px 10px;
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: #0d1117;
                color: #c9d1d9;
                font-size: 13px;
            }
            QLineEdit:hover {
                border: 1px solid #58a6ff;
            }
            QLineEdit:focus {
                border: 1px solid #58a6ff;
                background-color: #161b22;
            }
            QLineEdit::placeholder {
                color: #6e7681;
            }
        """)
        self.api_key_input.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        

        
        # 生成按钮 - 添加占位标签以保持对齐
        generate_btn_placeholder_label = QLabel("")  # 空标签用于占位
        generate_btn_placeholder_label.setFixedWidth(100)  # 与标签宽度一致
        
        generate_btn = QPushButton("生成视频")
        generate_btn.clicked.connect(self.generate_video)
        # 为按钮添加点击效果
        self.add_button_click_effect(generate_btn)
        generate_btn.setMinimumHeight(32)
        generate_btn.setFixedWidth(180)  # 设置按钮宽度与选择音色下拉框一致
        generate_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 10px;
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: transparent;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0842b0;
                border: 1px solid #30363d;
            }
            QPushButton:pressed {
                background-color: #0a58ca;
                border: 1px solid #30363d;
            }
        """)
        # 添加垂直居中对齐
        generate_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        # 将所有控件添加到容器中
        controls_layout.addWidget(tts_engine_label)
        controls_layout.addWidget(self.tts_engine_combo)
        controls_layout.addWidget(voice_label)
        controls_layout.addWidget(self.voice_combo)
        controls_layout.addWidget(api_key_label)
        controls_layout.addWidget(self.api_key_input)
        controls_layout.addWidget(generate_btn_placeholder_label)  # 添加占位标签
        controls_layout.addWidget(generate_btn)
        
        # 布局控件
        settings_layout.addWidget(prompt_container, 0, 0, Qt.AlignTop)  # AI提示词容器放在第一行，顶部对齐
        settings_layout.addWidget(controls_container, 1, 0, Qt.AlignTop)  # 控件容器放在第二行，顶部对齐
        
        control_layout.addWidget(settings_container)
        
        # 添加分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #30363d;")
        separator.setFixedHeight(1)
        control_layout.addWidget(separator)
        
        # 视频设置区域（使用与上面相同的水平布局）
        video_settings_container = QWidget()
        video_settings_container.setStyleSheet("background-color: #0d1117; border-radius: 6px;")
        video_settings_layout = QHBoxLayout(video_settings_container)
        video_settings_layout.setContentsMargins(6, 6, 6, 6)
        video_settings_layout.setSpacing(6)
        video_settings_layout.setAlignment(Qt.AlignVCenter)
        
        # 视频保存目录设置
        video_save_path_label = QLabel("保存目录:")
        video_save_path_label.setStyleSheet("color: #c9d1d9; font-size: 13px; font-weight: bold;")
        video_save_path_label.setFixedWidth(80)  # 统一为80px，与上面的标签对齐
        video_save_path_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.video_save_path_input = QLineEdit()
        default_video_save_path = r"D:\FacebookSpider\FB推广系统\共享文件\注册账号\视频"
        saved_video_path = self.load_config_value("video_save_path", default_video_save_path)
        self.video_save_path_input.setText(saved_video_path)
        self.video_save_path_input.setPlaceholderText("例如: D:\\FacebookSpider\\FB推广系统\\共享文件\\注册账号\\视频")
        self.video_save_path_input.setMinimumHeight(32)
        self.video_save_path_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: #161b22;
                color: #c9d1d9;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #58a6ff;
            }
        """)
        
        video_settings_layout.addWidget(video_save_path_label)
        video_settings_layout.addWidget(self.video_save_path_input)
        
        # 自动生成视频设置
        auto_generate_label = QLabel("自动生成:")
        auto_generate_label.setStyleSheet("color: #c9d1d9; font-size: 13px; font-weight: bold;")
        auto_generate_label.setFixedWidth(80)
        auto_generate_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.auto_generate_checkbox = QCheckBox("")  # 去掉文字，只保留复选框
        self.auto_generate_checkbox.setStyleSheet("""
            QCheckBox {
                color: #c9d1d9;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #30363d;
                border-radius: 3px;
                background-color: #0d1117;
            }
            QCheckBox::indicator:checked {
                background-color: #58a6ff;
                border-color: #58a6ff;
            }
        """)
        
        video_settings_layout.addWidget(auto_generate_label)
        video_settings_layout.addWidget(self.auto_generate_checkbox)
        
        # 最小视频数量设置
        min_video_count_label = QLabel("最小数量:")
        min_video_count_label.setStyleSheet("color: #c9d1d9; font-size: 13px; font-weight: bold;")
        min_video_count_label.setFixedWidth(80)
        min_video_count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.min_video_count_spin = QSpinBox()
        self.min_video_count_spin.setRange(1, 100)
        self.min_video_count_spin.setValue(5)
        self.min_video_count_spin.setSuffix(" 个")
        self.min_video_count_spin.setFixedWidth(120)
        self.min_video_count_spin.setMinimumHeight(32)
        self.min_video_count_spin.setStyleSheet("""
            QSpinBox {
                padding: 5px 10px;
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: #0d1117;
                color: #c9d1d9;
                font-size: 13px;
            }
            QSpinBox:focus {
                border: 1px solid #58a6ff;
            }
        """)
        
        video_settings_layout.addWidget(min_video_count_label)
        video_settings_layout.addWidget(self.min_video_count_spin)
        
        # 保存按钮
        save_video_settings_btn = QPushButton("保存设置")
        save_video_settings_btn.clicked.connect(self.save_settings)
        self.add_button_click_effect(save_video_settings_btn)
        save_video_settings_btn.setMinimumHeight(32)
        save_video_settings_btn.setFixedWidth(120)
        save_video_settings_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 10px;
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: transparent;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0842b0;
                border: 1px solid #30363d;
            }
            QPushButton:pressed {
                background-color: #0a58ca;
                border: 1px solid #30363d;
            }
        """)
        save_video_settings_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        video_settings_layout.addWidget(save_video_settings_btn)
        video_settings_layout.addStretch()  # 添加弹簧，使控件靠左对齐
        
        control_layout.addWidget(video_settings_container)
        
        # 连接TTS引擎选择变化信号到更新音色选项的槽函数
        self.tts_engine_combo.currentTextChanged.connect(self._update_voice_options)
        
        # 连接视频配置控件的信号到保存配置的槽函数
        self.video_prompt_input.textChanged.connect(self.save_video_config)
        self.tts_engine_combo.currentTextChanged.connect(self.save_video_config)
        self.voice_combo.currentTextChanged.connect(self.save_video_config)
        self.api_key_input.textChanged.connect(self.save_video_config)
        
        control_container_layout.addWidget(control_group)
        video_layout.addWidget(control_container)
        
        # 创建一个水平布局容器来放置视频预览和生成日志区域
        bottom_container = QWidget()
        bottom_container.setStyleSheet("background-color: #0d1117;")
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 6, 0, 6)  # 设置上下边距为6，确保间距一致
        bottom_layout.setSpacing(6)  # 统一间距为6像素
        
        # 日志输出区域
        log_container = QWidget()  # 创建一个容器来控制边距
        log_container.setStyleSheet("background-color: #0d1117;")
        log_container_layout = QHBoxLayout(log_container)
        log_container_layout.setContentsMargins(12, 0, 0, 6)  # 左侧保持12px间距与视频生成控制栏对齐，下侧保持6px间距
        
        log_group = QGroupBox("生成日志")
        log_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 设置大小策略为扩展
        log_group.setStyleSheet("QGroupBox { border: 1px solid #30363d; border-radius: 8px; margin-top: 1ex; padding-top: 15px; font-size: 14px; font-weight: bold; background-color: #161b22; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 8px 0 8px; color: #58a6ff; }")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(6, 6, 6, 6)  # 统一GroupBox内边距为6px
        
        self.video_log_text_edit = QTextEdit()
        self.video_log_text_edit.setReadOnly(True)
        self.video_log_text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 设置大小策略为扩展
        self.video_log_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.video_log_text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.video_log_text_edit.setStyleSheet("""
            color: #8b949e; 
            padding: 8px;
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 5px;
            font-size: 12px;
            font-family: Consolas, Monaco, monospace;
        """)
        log_layout.addWidget(self.video_log_text_edit)
        
        log_container_layout.addWidget(log_group)
        
        # 视频预览区域 - 使用自定义控件保持9:16比例
        preview_container = QWidget()  # 创建一个容器来控制边距
        preview_container.setStyleSheet("background-color: #0d1117;")
        preview_container_layout = QHBoxLayout(preview_container)
        preview_container_layout.setContentsMargins(0, 0, 12, 6)  # 右侧保持12px间距，下侧保持6px间距
        
        preview_group = QGroupBox("")
        preview_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 设置大小策略为扩展
        preview_group.setStyleSheet("QGroupBox { border: 1px solid #30363d; border-radius: 8px; margin-top: 1ex; padding-top: 15px; font-size: 14px; font-weight: bold; background-color: #161b22; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 8px 0 8px; color: #58a6ff; }")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(6, 6, 6, 6)  # 统一GroupBox内边距为6px
        
        # 添加视频预览控件
        self.video_preview_container = VideoPreviewContainer()
        self.video_preview_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addWidget(self.video_preview_container)
        
        # 为了兼容性，也创建一个 video_preview_widget 引用
        self.video_preview_widget = self.video_preview_container
        
        preview_container_layout.addWidget(preview_group)
        
        # 将日志和预览区域添加到底部布局
        bottom_layout.addWidget(log_container, 1)  # 日志区域占1份
        bottom_layout.addWidget(preview_container, 1)  # 预览区域占1份
        
        video_layout.addWidget(bottom_container)
        
        # 将视频生成标签页添加到标签页控件中
        self.tab_widget.addTab(video_widget, "视频生成")
        
        # 添加视频预览按钮
        preview_btn = QPushButton("视频预览")
        preview_btn.clicked.connect(self.debug_test_preview)
        # 为按钮添加点击效果
        self.add_button_click_effect(preview_btn)
        preview_btn.setMinimumHeight(32)
        preview_btn.setFixedWidth(180)  # 设置按钮宽度与生成视频按钮一致
        preview_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 10px;
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: transparent;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0842b0;
                border: 1px solid #30363d;
            }
            QPushButton:pressed {
                background-color: #0a58ca;
                border: 1px solid #30363d;
            }
        """)
        # 添加垂直居中对齐
        preview_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        controls_layout.addWidget(preview_btn)
    
    # create_settings_tab 方法已删除，设置已分散到各功能分页
    
    def refresh_browser_cards(self):
        """刷新浏览器卡片显示（异步，不阻塞UI）"""
        if not BITBROWSER_AVAILABLE:
            return
        
        # 检查是否正在刷新（防抖）
        if hasattr(self, '_refreshing_browsers') and self._refreshing_browsers:
            return
        
        self._refreshing_browsers = True
        
        # 使用线程异步刷新，避免阻塞UI
        def _refresh():
            try:
                # 检查连接
                if not bit_browser.check_connection():
                    # 在主线程中清空卡片
                    QMetaObject.invokeMethod(self, "clear_browser_cards", Qt.QueuedConnection)
                    return
                
                # 获取浏览器列表
                result = bit_browser.get_browser_list()
                if result.get("success"):
                    browsers = result.get("data", {}).get("list", [])
                    
                    # 获取所有浏览器的运行状态（使用PID接口）
                    browser_ids = [b.get("id") for b in browsers if b.get("id")]
                    pids_result = bit_browser.get_alive_browser_pids(browser_ids)
                    running_pids = {}
                    
                    if pids_result.get("success"):
                        running_pids = pids_result.get("data", {})
                    
                    # 将PID信息添加到浏览器数据中
                    for browser in browsers:
                        browser_id = browser.get("id", "")
                        browser["is_running"] = browser_id in running_pids
                        browser["pid"] = running_pids.get(browser_id, 0)
                    
                    # 在主线程中更新卡片
                    QMetaObject.invokeMethod(
                        self, 
                        "_update_browser_cards_in_main_thread",
                        Qt.QueuedConnection,
                        Q_ARG(list, browsers)
                    )
                else:
                    QMetaObject.invokeMethod(self, "clear_browser_cards", Qt.QueuedConnection)
                    
            except Exception as e:
                # 静默处理错误，避免日志输出
                pass
            finally:
                # 重置刷新标志
                self._refreshing_browsers = False
        
        # 在后台线程中执行刷新
        import threading
        thread = threading.Thread(target=_refresh, daemon=True)
        thread.start()
    
    @pyqtSlot(list)
    def _update_browser_cards_in_main_thread(self, browsers):
        """在主线程中更新浏览器卡片"""
        self.update_browser_cards(browsers)
    
    @pyqtSlot()
    def clear_browser_cards(self):
        """清空所有浏览器卡片"""
        while self.browser_cards_layout.count():
            item = self.browser_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            # spacerItem 会被 takeAt 自动移除，不需要额外处理
    
    def update_browser_cards(self, browsers):
        """更新浏览器卡片（单行显示，水平滚动）"""
        # 保存浏览器列表，供窗口大小改变时使用
        self.current_browsers = browsers
        
        # 清空现有卡片
        self.clear_browser_cards()
        
        # 创建新卡片（单行排列）
        for index, browser in enumerate(browsers, 1):
            card = self.create_browser_card(browser, index)
            self.browser_cards_layout.addWidget(card)
        
        # 添加弹性空间，使卡片靠左对齐
        self.browser_cards_layout.addStretch()
    
    def relayout_browser_cards(self):
        """重新布局浏览器卡片（窗口大小改变时调用）"""
        if hasattr(self, 'current_browsers') and self.current_browsers:
            self.update_browser_cards(self.current_browsers)
    
    def create_browser_card(self, browser_info, index):
        """创建单个浏览器卡片"""
        card = QWidget()
        
        # 从browser_info中获取运行状态（已在refresh_browser_cards中设置）
        is_running = browser_info.get("is_running", False)
        browser_id = browser_info.get("id", "")
        pid = browser_info.get("pid", 0)
        
        # 获取浏览器名称（如果为空则使用ID前8位）
        browser_name = browser_info.get("name", "").strip()
        if not browser_name:
            browser_name = browser_id[:8] if browser_id else f"浏览器{index}"
        
        # 检查是否是"公共主页"浏览器（特殊显示）
        is_homepage = browser_name == "公共主页"
        
        if is_homepage:
            # 公共主页浏览器：使用金色/橙色主题
            bg_color = "#3a2a1a" if is_running else "#3a1a1a"  # 金色背景或红色背景
            border_color = "#f0ad4e" if is_running else "#f85149"  # 金色边框或红色边框
        else:
            # 普通账号浏览器：使用绿色/红色主题
            bg_color = "#1a3a1a" if is_running else "#3a1a1a"  # 绿色背景或红色背景
            border_color = "#3fb950" if is_running else "#f85149"  # 绿色边框或红色边框
        
        # 创建美化的工具提示（HTML格式，符合主题风格）
        status_icon = "🟢" if is_running else "🔴"
        status_text = "运行中" if is_running else "已停止"
        status_color = border_color
        
        # 公共主页浏览器的特殊提示
        browser_type = "📢 公共主页浏览器（专用发帖）" if is_homepage else f"👤 账号浏览器"
        
        tooltip_html = f"""
        <div style='background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); 
                    padding: 12px; 
                    border: 2px solid {status_color}; 
                    border-radius: 8px;
                    font-family: "Segoe UI", Arial, sans-serif;'>
            <div style='color: #e2e8f0; font-size: 13px; font-weight: bold; margin-bottom: 8px;'>
                {status_icon} {browser_name}
            </div>
            <div style='color: {status_color}; font-size: 11px; margin-bottom: 6px;'>
                {browser_type}
            </div>
            <div style='color: {status_color}; font-size: 12px; margin-bottom: 6px;'>
                ● 状态: {status_text}
            </div>
            {f"<div style='color: #94a3b8; font-size: 11px; margin-bottom: 4px;'>⚙️ PID: {pid}</div>" if is_running and pid > 0 else ""}
            <div style='color: #64748b; font-size: 10px; font-family: monospace;'>
                🔑 {browser_id[:16]}...
            </div>
        </div>
        """
        card.setToolTip(tooltip_html)
        
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 8px;
                min-width: 60px;
                min-height: 60px;
                max-width: 60px;
                max-height: 60px;
            }}
            QWidget:hover {{
                border-width: 3px;
                background-color: {bg_color}dd;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignCenter)
        
        # 如果是公共主页，显示"发帖"；否则显示编号
        if is_homepage:
            display_text = "发帖"
            font_size = 16  # 稍小的字体
        else:
            display_text = str(index)
            font_size = 24  # 大字体
        
        # 显示文字（编号或"发帖"）
        text_label = QLabel(display_text)
        text_label.setStyleSheet(f"""
            color: {border_color};
            font-size: {font_size}px;
            font-weight: bold;
            background-color: transparent;
        """)
        text_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(text_label)
        
        return card
    
    def start_browser_refresh_timer(self):
        """启动浏览器状态自动刷新定时器（每分钟）"""
        # 可以通过设置 ENABLE_AUTO_REFRESH = False 来禁用自动刷新
        ENABLE_AUTO_REFRESH = True  # 设置为 False 可禁用自动刷新
        
        if not ENABLE_AUTO_REFRESH:
            print("✓ 浏览器自动刷新已禁用（手动刷新模式）")
            return
        
        self.browser_refresh_timer = QTimer(self)
        self.browser_refresh_timer.timeout.connect(self.refresh_browser_cards)
        self.browser_refresh_timer.start(60000)  # 60秒 = 1分钟
        print("✓ 浏览器状态自动刷新已启动（每分钟）")
    
    def load_app_config(self):
        """加载应用配置文件"""
        config_file = "app_config.json"
        default_config = {
            "username": "",
            "monitor_path": r"D:\FacebookSpider\FB推广系统\账号管理",
            "video_save_path": r"D:\FacebookSpider\FB推广系统\共享文件\注册账号\视频",
            "auto_generate_video": False,
            "min_video_count": 5
        }
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置，确保所有键都存在
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
        except Exception as e:
            print(f"加载配置文件失败: {e}")
        return default_config
    
    def save_app_config(self, config):
        """保存应用配置文件"""
        config_file = "app_config.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            print(f"✓ 配置已保存到: {config_file}")
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def load_config_value(self, key, default=""):
        """从配置文件加载单个值"""
        config = self.load_app_config()
        return config.get(key, default)
    
    def load_username_from_simulator_config(self):
        """从 simulator_config.json 加载认证用户名"""
        try:
            config_file = "simulator_config.json"
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    username = config.get('username', '未认证')
                    return username
        except Exception as e:
            print(f"加载用户名失败: {e}")
        return "未认证"
    
    # refresh_home_browser_status 方法已删除，使用 refresh_browser_cards 代替
    
    def save_settings(self):
        """保存设置"""
        try:
            print("=" * 60)
            print("开始保存设置...")
            
            # 加载现有配置
            config = self.load_app_config()
            
            # 用户名从认证获取，无需保存
            # 远程地址已硬编码为 http://43.142.176.53:8805，无需保存
            # 账号管理路径已废弃（改用比特浏览器API）
            
            # 更新视频设置
            video_save_path = self.video_save_path_input.text().strip()
            
            # 验证并创建视频保存目录
            if video_save_path:
                try:
                    # 尝试创建目录
                    if not os.path.exists(video_save_path):
                        os.makedirs(video_save_path, exist_ok=True)
                        print(f"📁 已创建视频保存目录: {video_save_path}")
                    else:
                        print(f"📁 视频保存目录已存在: {video_save_path}")
                    
                    # 测试目录是否可写
                    test_file = os.path.join(video_save_path, "test_write.tmp")
                    try:
                        with open(test_file, 'w') as f:
                            f.write("test")
                        os.remove(test_file)
                        print(f"✅ 视频保存目录可写入")
                    except Exception as e:
                        print(f"⚠️ 视频保存目录不可写入: {e}")
                        
                except Exception as e:
                    print(f"❌ 创建视频保存目录失败: {e}")
                    QMessageBox.warning(self, "警告", f"无法创建视频保存目录:\n{video_save_path}\n\n错误: {e}\n\n请检查路径是否有效或权限是否足够")
            
            config["video_save_path"] = video_save_path
            
            # 保存自动生成视频设置
            auto_generate_enabled = self.auto_generate_checkbox.isChecked()
            min_video_count = self.min_video_count_spin.value()
            
            config["auto_generate_video"] = auto_generate_enabled
            config["min_video_count"] = min_video_count
            
            print(f"视频保存路径: {video_save_path}")
            print(f"自动生成视频: {auto_generate_enabled}")
            print(f"最小视频数量: {min_video_count}")
            
            # 启动或停止自动生成视频监控
            if auto_generate_enabled:
                self.start_auto_video_generation()
            else:
                self.stop_auto_video_generation()
            
            # 保存配置到文件
            self.save_app_config(config)
            
            print(f"配置已保存")
            print(f"完整配置: {json.dumps(config, ensure_ascii=False, indent=2)}")
            
            print("=" * 60)
            
            # 提示用户配置已立即生效
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("成功")
            msg.setText("设置已保存！")
            # 从配置文件加载用户名
            username = self.load_username_from_simulator_config()
            msg.setInformativeText(
                f"当前配置:\n"
                f"• 用户名: {username}\n"
                f"• 视频保存路径: {video_save_path}\n"
                f"• 自动生成视频: {'开启' if auto_generate_enabled else '关闭'}\n"
                f"• 最小视频数量: {min_video_count} 个"
            )
            msg.exec_()
        except Exception as e:
            print(f"保存设置时出错: {e}")
            QMessageBox.critical(self, "错误", f"保存设置失败: {str(e)}")

    def start_auto_video_generation(self):
        """启动自动生成视频监控"""
        try:
            # 停止现有的监控线程
            self.stop_auto_video_generation()
            
            # 获取配置
            video_save_path = self.video_save_path_input.text().strip()
            min_video_count = self.min_video_count_spin.value()
            
            if not video_save_path:
                print("❌ 视频保存路径为空，无法启动自动生成")
                return
                
            # 创建并启动监控线程
            self.auto_video_thread = AutoVideoGenerationThread(self)
            self.auto_video_thread.set_config(video_save_path, min_video_count)
            
            # 连接信号
            self.auto_video_thread.video_generated.connect(self.on_auto_video_generated)
            self.auto_video_thread.generation_failed.connect(self.on_auto_video_failed)
            self.auto_video_thread.status_updated.connect(self.on_auto_video_status_updated)
            
            # 启动线程
            self.auto_video_thread.start()
            
            print(f"✅ 自动生成视频监控已启动")
            print(f"📁 监控目录: {video_save_path}")
            print(f"📊 最小视频数量: {min_video_count}")
            
        except Exception as e:
            print(f"❌ 启动自动生成视频监控失败: {e}")
            
    def stop_auto_video_generation(self):
        """停止自动生成视频监控"""
        try:
            if self.auto_video_thread and self.auto_video_thread.isRunning():
                print("🛑 正在停止自动生成视频监控...")
                self.auto_video_thread.stop()
                self.auto_video_thread = None
                print("✅ 自动生成视频监控已停止")
        except Exception as e:
            print(f"❌ 停止自动生成视频监控失败: {e}")
            
    def on_auto_video_generated(self, video_path):
        """自动生成视频成功的回调"""
        print(f"🎬 自动生成视频成功: {video_path}")
        # 在日志中显示成功信息
        if hasattr(self, 'video_log_text_edit'):
            current_time = datetime.now().strftime("%H:%M:%S")
            filename = os.path.basename(video_path) if video_path else "未知"
            save_dir = os.path.dirname(video_path) if video_path else "未知"
            self.video_log_text_edit.append(f"[{current_time}] ✅ 自动生成成功")
            self.video_log_text_edit.append(f"[{current_time}] 📁 保存位置: {save_dir}")
            self.video_log_text_edit.append(f"[{current_time}] 📄 文件名: {filename}")
        
        # 更新视频预览
        if hasattr(self, 'update_video_preview') and video_path:
            self.update_video_preview(video_path)
            
    def on_auto_video_failed(self, error_msg):
        """自动生成视频失败的回调"""
        print(f"❌ 自动生成视频失败: {error_msg}")
        # 在日志中显示详细错误信息
        if hasattr(self, 'video_log_text_edit'):
            current_time = datetime.now().strftime("%H:%M:%S")
            self.video_log_text_edit.append(f"[{current_time}] 自动生成失败: {error_msg}")
            # 如果错误信息很长，分行显示
            if len(error_msg) > 100:
                lines = error_msg.split('\n')
                for line in lines:
                    if line.strip():
                        self.video_log_text_edit.append(f"[{current_time}] 详细信息: {line.strip()}")
            # 滚动到底部
            self.video_log_text_edit.moveCursor(self.video_log_text_edit.textCursor().End)
            
    def on_auto_video_status_updated(self, status_msg):
        """自动生成视频状态更新的回调"""
        print(f"📊 自动生成状态: {status_msg}")
        # 在日志中显示状态信息
        if hasattr(self, 'video_log_text_edit'):
            current_time = datetime.now().strftime("%H:%M:%S")
            self.video_log_text_edit.append(f"[{current_time}] {status_msg}")

    def load_auto_video_settings(self):
        """加载自动生成视频设置"""
        try:
            config = self.load_app_config()
            
            # 加载自动生成视频开关
            auto_generate_enabled = config.get("auto_generate_video", False)
            self.auto_generate_checkbox.setChecked(auto_generate_enabled)
            
            # 加载最小视频数量
            min_video_count = config.get("min_video_count", 5)
            self.min_video_count_spin.setValue(min_video_count)
            
            print(f"📋 已加载自动生成视频设置: 启用={auto_generate_enabled}, 最小数量={min_video_count}")
            
            # 如果启用了自动生成，启动监控
            if auto_generate_enabled:
                video_save_path = config.get("video_save_path", "")
                if video_save_path:
                    print(f"🎬 自动启动视频生成监控")
                    self.start_auto_video_generation()
                else:
                    print(f"⚠️ 视频保存路径为空，无法启动自动生成")
        except Exception as e:
            print(f"❌ 加载自动生成视频设置失败: {e}")

    def get_username(self):
        """获取用户名，用于API请求参数"""
        return self.load_config_value("username", "")
    
    def generate_video(self):
        """生成视频"""
        # 获取用户输入的参数
        prompt = self.video_prompt_input.toPlainText()
        tts_engine = self.tts_engine_combo.currentText()
        voice = self.voice_combo.currentText()
        
        # 立即显示反馈信息
        self.update_video_log("开始生成...")
        self.update_video_log(f"TTS引擎: {tts_engine}")
        self.update_video_log(f"音色: {voice}")
        
        # 使用Python threading而不是QThread，避免Qt线程问题
        import threading
        
        # 创建一个信号对象用于线程安全的日志更新
        class LogSignal(QObject):
            log_message = pyqtSignal(str)
        
        log_signal = LogSignal()
        log_signal.log_message.connect(self.update_video_log)
        
        def run_video_generation():
            """在Python线程中运行视频生成"""
            try:
                # 获取正确的基础路径
                if getattr(sys, 'frozen', False):
                    # 打包后的exe运行时
                    base_path = os.path.dirname(sys.executable)
                else:
                    # 开发环境下
                    base_path = os.path.dirname(os.path.abspath(__file__))
                
                # 导入视频生成器
                video_tools_path = os.path.join(base_path, "video_tools")
                sys.path.append(video_tools_path)
                from video_generator import VideoGenerator
                
                # 创建日志回调函数 - 使用信号发送到主线程
                def log_callback(message):
                    log_signal.log_message.emit(message)
                
                # 创建视频生成器实例
                generator = VideoGenerator(log_callback=log_callback)
                
                # 调用生成视频方法
                success = generator.generate_video(
                    prompt=prompt,
                    tts_engine=tts_engine,
                    voice_style=voice,
                    style="旅行"
                )
                
                if success:
                    log_signal.log_message.emit("视频生成完成!")
                    # 查找生成的视频文件
                    video_folder = os.path.join(base_path, "video_tools", "生成的视频")
                    log_signal.log_message.emit(f"🔍 查找视频文件夹: {video_folder}")
                    
                    if os.path.exists(video_folder):
                        video_files = [f for f in os.listdir(video_folder) if f.endswith('.mp4')]
                        log_signal.log_message.emit(f"📁 找到 {len(video_files)} 个视频文件")
                        
                        if video_files:
                            # 获取最新的视频文件
                            latest_video = max(video_files, key=lambda x: os.path.getctime(os.path.join(video_folder, x)))
                            video_path = os.path.join(video_folder, latest_video)
                            log_signal.log_message.emit(f"✅ 最新视频: {latest_video}")
                            
                            # 在主线程中复制视频到用户设置的保存目录
                            def copy_and_update():
                                try:
                                    print(f"📋 开始移动视频到保存目录...")
                                    log_signal.log_message.emit("📋 正在移动视频到保存目录...")
                                    
                                    # 获取保存目录
                                    save_dir = self.get_video_save_path()
                                    log_signal.log_message.emit(f"📁 目标目录: {save_dir}")
                                    
                                    # 移动视频文件（复制后删除原文件）
                                    moved_path = self.copy_video_to_save_path(video_path)
                                    if moved_path:
                                        log_signal.log_message.emit(f"✅ 视频已移动到: {os.path.dirname(moved_path)}")
                                        log_signal.log_message.emit(f"📄 文件名: {os.path.basename(moved_path)}")
                                        log_signal.log_message.emit("🗑️ 临时文件已清理")
                                        # 更新预览时使用移动后的路径
                                        print(f"🎬 自动更新视频预览: {moved_path}")
                                        self.update_video_preview(moved_path)
                                    else:
                                        log_signal.log_message.emit("⚠️ 视频移动失败，使用临时路径")
                                        # 如果移动失败，使用原路径
                                        print(f"🎬 自动更新视频预览: {video_path}")
                                        self.update_video_preview(video_path)
                                except Exception as e:
                                    print(f"❌ copy_and_update 执行失败: {e}")
                                    log_signal.log_message.emit(f"❌ 移动过程出错: {e}")
                                    # 出错时使用原路径
                                    self.update_video_preview(video_path)
                            
                            # 使用QTimer在主线程中执行，延迟确保日志更新完成
                            QTimer.singleShot(500, copy_and_update)
                        else:
                            log_signal.log_message.emit("❌ 视频文件夹中没有找到MP4文件")
                    else:
                        log_signal.log_message.emit(f"❌ 视频文件夹不存在: {video_folder}")
                else:
                    log_signal.log_message.emit("视频生成失败")
            except Exception as e:
                log_signal.log_message.emit(f"视频生成错误: {str(e)}")
        
        # 启动Python线程
        self.video_generation_thread = threading.Thread(target=run_video_generation, daemon=True)
        self.video_generation_thread.start()

    def generate_video_safe(self):
        """安全的视频生成方法，用于自动生成，确保不会阻塞UI和处理异常"""
        # 创建调试日志文件
        debug_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_video_generation.log")
        
        def debug_log(message):
            """写入调试日志并显示到UI"""
            try:
                with open(debug_log_path, "a", encoding="utf-8") as f:
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    f.write(f"[{timestamp}] {message}\n")
                    f.flush()
                print(message)  # 同时输出到控制台（如果有的话）
                
                # 同时发送到UI显示
                if hasattr(self, 'auto_video_thread') and self.auto_video_thread:
                    self.auto_video_thread.status_updated.emit(f"[调试] {message}")
            except Exception as e:
                print(f"调试日志写入失败: {e}")
                # 即使日志写入失败，也要尝试发送到UI
                try:
                    if hasattr(self, 'auto_video_thread') and self.auto_video_thread:
                        self.auto_video_thread.status_updated.emit(f"[调试] {message}")
                except:
                    pass
        
        debug_log("🎯 进入generate_video_safe方法")
        try:
            debug_log("🔍 开始获取参数...")
            # 获取参数
            prompt = self.video_prompt_input.toPlainText()
            tts_engine = self.tts_engine_combo.currentText()
            voice = self.voice_combo.currentText()
            
            debug_log(f"📝 原始提示词: '{prompt}'")
            debug_log(f"🎤 TTS引擎: '{tts_engine}'")
            debug_log(f"🗣️ 音色: '{voice}'")
            
            if not prompt.strip():
                debug_log("⚠️ 提示词为空，使用默认提示词")
                # 使用默认提示词
                prompt = "生成一个关于美丽风景的短视频，包含山川、河流和蓝天白云的画面。"
                debug_log(f"📝 使用默认提示词: {prompt}")
                
                # 同时更新UI中的提示词
                try:
                    self.video_prompt_input.setPlainText(prompt)
                    debug_log("✅ 已更新UI中的提示词")
                except Exception as e:
                    debug_log(f"⚠️ 更新UI提示词失败: {e}")
            
            debug_log(f"🎬 开始安全生成视频...")
            debug_log(f"📝 提示词: {prompt[:50]}...")
            debug_log(f"🎤 TTS引擎: {tts_engine}")
            debug_log(f"🗣️ 音色: {voice}")
            
            # 发送开始状态到UI
            if hasattr(self, 'auto_video_thread') and self.auto_video_thread:
                self.auto_video_thread.status_updated.emit(f"🎬 开始安全生成视频...")
                self.auto_video_thread.status_updated.emit(f"📝 提示词: {prompt[:50]}...")
                self.auto_video_thread.status_updated.emit(f"🎤 TTS引擎: {tts_engine}")
                self.auto_video_thread.status_updated.emit(f"🗣️ 音色: {voice}")
            
            # 使用独立的线程生成视频，避免阻塞
            import threading
            import queue
            import logging
            
            # 临时禁用werkzeug日志，避免线程冲突
            werkzeug_logger = logging.getLogger('werkzeug')
            original_level = werkzeug_logger.level
            werkzeug_logger.setLevel(logging.ERROR)
            
            result_queue = queue.Queue()
            
            def safe_video_generation():
                """安全的视频生成线程"""
                try:
                    # 在线程内部也禁用日志
                    import logging
                    logging.getLogger('werkzeug').setLevel(logging.ERROR)
                    logging.getLogger('urllib3').setLevel(logging.ERROR)
                    
                    debug_log("🚀 开始安全视频生成线程")
                    
                    # 获取正确的基础路径 - 修复：使用与手动生成相同的路径逻辑
                    debug_log("🔍 检查运行环境...")
                    if getattr(sys, 'frozen', False):
                        # 打包后的exe运行时 - 使用exe所在目录，不是临时目录
                        base_path = os.path.dirname(sys.executable)
                        debug_log(f"🔧 检测到打包环境，使用exe目录: {base_path}")
                    else:
                        # 开发环境下
                        base_path = os.path.dirname(os.path.abspath(__file__))
                        debug_log(f"🔧 开发环境，使用源码路径: {base_path}")
                    
                    # 检查基础路径是否存在
                    debug_log(f"📁 基础路径存在: {os.path.exists(base_path)}")
                    if os.path.exists(base_path):
                        try:
                            base_files = os.listdir(base_path)
                            debug_log(f"📋 基础目录内容: {base_files[:10]}...")  # 只显示前10个文件
                        except Exception as e:
                            debug_log(f"❌ 无法列出基础目录内容: {e}")
                    
                    # 导入视频生成器
                    video_tools_path = os.path.join(base_path, "video_tools")
                    debug_log(f"📁 video_tools路径: {video_tools_path}")
                    debug_log(f"📁 video_tools路径存在: {os.path.exists(video_tools_path)}")
                    
                    # 列出video_tools目录内容
                    if os.path.exists(video_tools_path):
                        try:
                            files = os.listdir(video_tools_path)
                            debug_log(f"📋 video_tools目录内容: {files}")
                            
                            # 检查关键文件是否存在
                            video_generator_py = os.path.join(video_tools_path, "video_generator.py")
                            debug_log(f"📄 video_generator.py存在: {os.path.exists(video_generator_py)}")
                            
                        except Exception as e:
                            debug_log(f"❌ 无法列出video_tools目录内容: {e}")
                    else:
                        debug_log("❌ video_tools目录不存在！")
                    
                    # 检查当前Python路径
                    debug_log(f"📋 当前Python路径数量: {len(sys.path)}")
                    debug_log(f"📋 前5个Python路径: {sys.path[:5]}")
                    
                    if video_tools_path not in sys.path:
                        sys.path.insert(0, video_tools_path)  # 使用insert确保优先级
                        debug_log(f"✅ 已添加video_tools到Python路径")
                    else:
                        debug_log(f"ℹ️ video_tools已在Python路径中")
                    
                    # 尝试导入VideoGenerator
                    debug_log("🔄 尝试导入VideoGenerator...")
                    VideoGenerator = None
                    
                    try:
                        from video_generator import VideoGenerator
                        debug_log(f"✅ VideoGenerator导入成功")
                    except Exception as import_error:
                        debug_log(f"❌ VideoGenerator导入失败: {import_error}")
                        debug_log(f"📋 错误类型: {type(import_error).__name__}")
                        
                        # 显示更详细的Python路径信息
                        debug_log(f"📋 完整Python路径:")
                        for i, path in enumerate(sys.path):
                            debug_log(f"  [{i}] {path}")
                        
                        # 尝试直接从当前目录导入
                        debug_log("🔄 尝试备用路径导入...")
                        try:
                            current_dir = os.path.dirname(os.path.abspath(__file__))
                            video_tools_fallback = os.path.join(current_dir, "video_tools")
                            debug_log(f"📁 备用路径: {video_tools_fallback}")
                            debug_log(f"📁 备用路径存在: {os.path.exists(video_tools_fallback)}")
                            
                            if os.path.exists(video_tools_fallback):
                                sys.path.insert(0, video_tools_fallback)
                                from video_generator import VideoGenerator
                                debug_log(f"✅ 使用备用路径导入成功")
                            else:
                                debug_log("❌ 备用路径也不存在")
                                
                                # 尝试使用importlib动态导入
                                debug_log("🔄 尝试importlib动态导入...")
                                try:
                                    import importlib.util
                                    video_generator_file = os.path.join(video_tools_path, "video_generator.py")
                                    if os.path.exists(video_generator_file):
                                        spec = importlib.util.spec_from_file_location("video_generator", video_generator_file)
                                        if spec and spec.loader:
                                            video_generator_module = importlib.util.module_from_spec(spec)
                                            spec.loader.exec_module(video_generator_module)
                                            VideoGenerator = video_generator_module.VideoGenerator
                                            debug_log(f"✅ importlib动态导入成功")
                                        else:
                                            debug_log("❌ importlib spec创建失败")
                                            raise ImportError("importlib spec创建失败")
                                    else:
                                        debug_log(f"❌ video_generator.py文件不存在: {video_generator_file}")
                                        raise ImportError("video_generator.py文件不存在")
                                except Exception as importlib_error:
                                    debug_log(f"❌ importlib导入失败: {importlib_error}")
                                    raise ImportError("所有导入方式都失败")
                                    
                        except Exception as fallback_error:
                            debug_log(f"❌ 备用导入也失败: {fallback_error}")
                            debug_log(f"📋 备用导入错误类型: {type(fallback_error).__name__}")
                            
                            # 提供详细的错误信息
                            error_msg = f"""
无法导入VideoGenerator模块，可能的原因：
1. 主导入失败: {import_error}
2. 备用导入失败: {fallback_error}
3. 打包时video_tools目录未正确包含
4. video_generator.py文件缺失或损坏
5. Python路径配置问题

请检查：
- 打包脚本中是否包含 --add-data video_tools;video_tools
- video_tools目录是否存在于源码中
- video_generator.py文件是否完整
"""
                            result_queue.put(('error', error_msg))
                            return
                    
                    # 验证VideoGenerator是否成功导入
                    if VideoGenerator is None:
                        debug_log("❌ VideoGenerator仍然为None")
                        result_queue.put(('error', "VideoGenerator导入失败，类为None"))
                        return
                    
                    # 创建日志回调函数，同时输出到控制台和UI
                    def log_callback(message):
                        debug_log(f"[视频生成器] {message}")
                    
                    debug_log("✅ VideoGenerator导入完成，开始创建实例...")
                    
                    # 创建视频生成器实例
                    generator = VideoGenerator(log_callback=log_callback)
                    
                    # 调用生成视频方法
                    debug_log("🎬 开始调用视频生成方法...")
                    debug_log(f"📝 参数 - 提示词: {prompt[:30]}...")
                    debug_log(f"🎤 参数 - TTS引擎: {tts_engine}")
                    debug_log(f"🗣️ 参数 - 音色: {voice}")
                    debug_log(f"🎨 参数 - 风格: 旅行")
                    
                    success = generator.generate_video(
                        prompt=prompt,
                        tts_engine=tts_engine,
                        voice_style=voice,
                        style="旅行"
                    )
                    
                    debug_log(f"📊 视频生成结果: {success}")
                    debug_log(f"📊 结果类型: {type(success)}")
                    
                    # 如果生成成功，查找并移动视频文件
                    video_path = None
                    if success:
                        debug_log("✅ 视频生成成功，开始查找视频文件...")
                        # 查找生成的视频文件
                        video_folder = os.path.join(base_path, "video_tools", "生成的视频")
                        debug_log(f"🔍 查找视频文件夹: {video_folder}")
                        debug_log(f"📁 视频文件夹存在: {os.path.exists(video_folder)}")
                        
                        if os.path.exists(video_folder):
                            try:
                                video_files = [f for f in os.listdir(video_folder) if f.lower().endswith(('.mp4', '.avi', '.mov'))]
                                debug_log(f"📋 找到视频文件: {video_files}")
                                
                                if video_files:
                                    # 获取最新的视频文件
                                    video_files.sort(key=lambda x: os.path.getmtime(os.path.join(video_folder, x)), reverse=True)
                                    latest_video = video_files[0]
                                    video_path = os.path.join(video_folder, latest_video)
                                    debug_log(f"✅ 找到最新视频: {latest_video}")
                                    
                                    # 移动视频到保存目录 - 使用与手动生成相同的方法
                                    try:
                                        debug_log(f"📋 开始移动视频到用户设置的保存目录...")
                                        debug_log(f"📁 临时视频路径: {video_path}")
                                        
                                        # 使用与手动生成完全相同的保存方法
                                        moved_path = self.copy_video_to_save_path(video_path)
                                        if moved_path:
                                            debug_log(f"✅ 视频已移动到: {os.path.dirname(moved_path)}")
                                            debug_log(f"📄 文件名: {os.path.basename(moved_path)}")
                                            debug_log("🗑️ 临时文件已清理")
                                            video_path = moved_path
                                        else:
                                            debug_log("⚠️ 视频移动失败，使用临时路径")
                                            # 如果移动失败，保持原路径
                                            
                                    except Exception as save_error:
                                        debug_log(f"❌ 移动视频过程出错: {save_error}")
                                        # 出错时保持原路径
                                else:
                                    debug_log("❌ 视频文件夹为空")
                            except Exception as list_error:
                                debug_log(f"❌ 列出视频文件失败: {list_error}")
                        else:
                            debug_log("❌ 视频文件夹不存在")
                    else:
                        debug_log("❌ 视频生成失败")
                    
                    debug_log(f"📊 最终结果 - 成功: {success}, 视频路径: {video_path}")
                    result_queue.put(('success', success, video_path))
                    
                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    debug_log(f"❌ 安全生成视频异常: {e}")
                    debug_log(f"📋 异常类型: {type(e).__name__}")
                    debug_log(f"📋 详细错误信息:\n{error_details}")
                    result_queue.put(('error', f"{str(e)}\n详细信息: {error_details}"))
            
            # 启动生成线程
            debug_log("🚀 启动视频生成线程...")
            generation_thread = threading.Thread(target=safe_video_generation, daemon=True)
            generation_thread.start()
            debug_log("✅ 线程已启动，等待完成...")
            
            # 等待生成完成，但设置超时避免无限等待
            generation_thread.join(timeout=300)  # 最多等待5分钟
            
            debug_log(f"📊 线程状态: {'运行中' if generation_thread.is_alive() else '已结束'}")
            debug_log(f"📊 结果队列状态: {'有结果' if not result_queue.empty() else '空'}")
            
            # 检查结果
            if not result_queue.empty():
                result = result_queue.get()
                if len(result) == 3:  # 新格式: (result_type, success, video_path)
                    result_type, success, video_path = result
                else:  # 旧格式兼容: (result_type, result_value)
                    result_type, success = result
                    video_path = None
                
                debug_log(f"📊 结果类型: {result_type}, 成功状态: {success}")
                
                if result_type == 'success':
                    if success:
                        debug_log("✅ 安全生成视频成功")
                        if video_path:
                            debug_log(f"📁 视频已保存到: {video_path}")
                            # 通知监控线程视频生成成功
                            if hasattr(self, 'auto_video_thread') and self.auto_video_thread:
                                self.auto_video_thread.video_generated.emit(video_path)
                        return True
                    else:
                        debug_log("❌ 安全生成视频失败")
                        # 发送详细的失败信息给监控线程
                        if hasattr(self, 'auto_video_thread') and self.auto_video_thread:
                            self.auto_video_thread.generation_failed.emit("视频生成器返回失败状态，可能是TTS或视频编辑过程出错")
                        return False
                else:
                    debug_log(f"❌ 安全生成视频出错: {success}")
                    # 如果有详细错误信息，也发送给监控线程
                    if hasattr(self, 'auto_video_thread') and self.auto_video_thread:
                        self.auto_video_thread.generation_failed.emit(f"生成出错: {success}")
                    return False
            else:
                debug_log("⏰ 安全生成视频超时")
                # 发送超时错误信息给监控线程
                if hasattr(self, 'auto_video_thread') and self.auto_video_thread:
                    self.auto_video_thread.generation_failed.emit("视频生成超时（超过5分钟），可能是网络问题或TTS服务响应慢")
                return False
                
        except Exception as e:
            debug_log(f"🚨 generate_video_safe方法发生异常!")
            debug_log(f"❌ 异常类型: {type(e).__name__}")
            debug_log(f"❌ 异常信息: {e}")
            import traceback
            error_details = traceback.format_exc()
            debug_log(f"📋 详细错误堆栈:\n{error_details}")
            # 发送异常错误信息给监控线程
            if hasattr(self, 'auto_video_thread') and self.auto_video_thread:
                self.auto_video_thread.generation_failed.emit(f"视频生成异常: {str(e)}\n详细信息: {error_details}")
            return False
        finally:
            # 恢复werkzeug日志级别
            try:
                if 'werkzeug_logger' in locals() and 'original_level' in locals():
                    werkzeug_logger.setLevel(original_level)
                    debug_log("🔧 已恢复werkzeug日志级别")
            except Exception as restore_error:
                debug_log(f"⚠️ 恢复日志级别失败: {restore_error}")

    def on_video_generation_finished(self):
        """视频生成完成后的处理"""
        self.video_preview_widget.setText("视频已生成\n(此处应显示视频预览)")
        
    def update_video_log(self, message):
        """更新视频生成日志"""
        if hasattr(self, 'video_log_text_edit'):
            # 获取当前文本
            current_text = self.video_log_text_edit.toPlainText()
            
            # 添加时间戳
            timestamp = datetime.now().strftime("%H:%M:%S")
            new_message = f"[{timestamp}] {message}"
            
            # 添加新消息
            if current_text:
                updated_text = current_text + "\n" + new_message
            else:
                updated_text = new_message
            
            # 更新文本
            self.video_log_text_edit.setPlainText(updated_text)
            
            # 滚动到底部
            cursor = self.video_log_text_edit.textCursor()
            cursor.movePosition(cursor.End)
            self.video_log_text_edit.setTextCursor(cursor)
    
    def update_video_preview(self, video_path):
        """更新视频预览"""
        try:
            print(f"🔄 开始更新视频预览: {video_path}")
            print(f"🔍 检查组件存在: hasattr(self, 'video_preview_widget') = {hasattr(self, 'video_preview_widget')}")
            
            if hasattr(self, 'video_preview_widget'):
                print(f"🔍 组件对象: {self.video_preview_widget}")
                print(f"🔍 组件类型: {type(self.video_preview_widget)}")
                
                if self.video_preview_widget:
                    print(f"🔍 检查文件存在: {os.path.exists(video_path)}")
                    
                    # 检查视频文件是否存在
                    if os.path.exists(video_path):
                        # 获取文件大小
                        file_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
                        print(f"📊 文件大小: {file_size:.1f} MB")
                        
                        # 更新预览组件显示视频路径
                        preview_text = f"✅ 视频已生成\n📁 {os.path.basename(video_path)}\n📊 大小: {file_size:.1f} MB\n🎬 点击打开文件夹查看"
                        print(f"📝 准备设置文本: {preview_text}")
                        
                        # 检查setText方法
                        print(f"🔍 检查setText方法: {hasattr(self.video_preview_widget, 'setText')}")
                        
                        # 添加点击事件打开文件夹
                        def open_video_folder():
                            try:
                                import subprocess
                                # 在Windows资源管理器中打开并选中文件
                                video_path_windows = video_path.replace('/', '\\')
                                subprocess.run(['explorer', '/select,', video_path_windows], 
                                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                                print(f"📂 已打开视频文件夹")
                            except Exception as e:
                                print(f"打开文件夹失败: {e}")
                        
                        # 更新预览文本
                        if hasattr(self.video_preview_widget, 'setText'):
                            print("📝 调用setText方法...")
                            self.video_preview_widget.setText(preview_text)
                            print("✅ setText调用完成")
                            
                            # 强制刷新UI
                            self.video_preview_widget.update()
                            if hasattr(self.video_preview_widget, 'repaint'):
                                self.video_preview_widget.repaint()
                            
                            # 延迟一下再绑定点击事件，确保setText完成
                            def bind_click_events():
                                self.bind_preview_click_events(open_video_folder)
                            
                            QTimer.singleShot(50, bind_click_events)
                            
                            print(f"✅ 视频预览已更新: {os.path.basename(video_path)}")
                        else:
                            print("❌ 预览组件不支持setText方法")
                            print(f"🔍 可用方法: {[m for m in dir(self.video_preview_widget) if not m.startswith('_')]}")
                    else:
                        error_text = "❌ 视频文件未找到\n请检查生成过程是否完成"
                        if hasattr(self.video_preview_widget, 'setText'):
                            self.video_preview_widget.setText(error_text)
                        print(f"❌ 视频文件不存在: {video_path}")
                else:
                    print("❌ video_preview_widget 为 None")
            else:
                print("❌ 视频预览组件未初始化")
        except Exception as e:
            print(f"更新视频预览失败: {e}")
            import traceback
            traceback.print_exc()
    
    def get_video_save_path(self):
        """获取视频保存路径，如果路径不存在则自动创建"""
        try:
            print(f"🔍 开始获取视频保存路径...")
            
            # 从UI设置中获取路径（模拟器配置已废弃）
            if hasattr(self, 'video_save_path_input'):
                config_path = self.video_save_path_input.text().strip()
                print(f"📋 UI设置中的路径: {config_path}")
                if config_path:
                    save_path = config_path
                else:
                    save_path = r"D:\FacebookSpider\FB推广系统\共享文件\注册账号\视频"
                    print(f"📋 UI设置为空，使用默认路径: {save_path}")
            else:
                save_path = r"D:\FacebookSpider\FB推广系统\共享文件\注册账号\视频"
                print(f"📋 无UI设置，使用默认路径: {save_path}")
            
            print(f"🎯 最终使用路径: {save_path}")
            
            # 注意：这里只返回路径，不创建目录
            # 目录创建将在copy_video_to_save_path中进行，以确保操作的原子性
            print(f"📋 返回配置的保存路径: {save_path}")
            return save_path
        except Exception as e:
            print(f"❌ 获取视频保存路径失败: {e}")
            import traceback
            traceback.print_exc()
            # 返回默认的备用路径
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            fallback_path = os.path.join(base_path, "video_tools", "生成的视频")
            try:
                if not os.path.exists(fallback_path):
                    os.makedirs(fallback_path, exist_ok=True)
            except:
                pass
            print(f"📁 使用备用目录: {fallback_path}")
            return fallback_path
    
    def copy_video_to_save_path(self, source_video_path):
        """将生成的视频移动到用户设置的保存目录（复制后删除原文件）"""
        try:
            print(f"🔍 开始移动视频: {source_video_path}")
            
            if not os.path.exists(source_video_path):
                print(f"❌ 源视频文件不存在: {source_video_path}")
                return False
            
            # 获取源文件大小用于验证
            source_size = os.path.getsize(source_video_path)
            print(f"📊 源文件大小: {source_size} 字节")
            
            # 获取保存目录
            save_dir = self.get_video_save_path()
            print(f"🎯 目标保存目录: {save_dir}")
            
            # 强制创建保存目录
            if not os.path.exists(save_dir):
                try:
                    print(f"📁 目录不存在，强制创建: {save_dir}")
                    os.makedirs(save_dir, exist_ok=True)
                    print(f"✅ 目录创建成功: {save_dir}")
                except Exception as e:
                    print(f"❌ 创建目录失败: {e}")
                    return False
            
            # 测试目录写入权限
            try:
                test_file = os.path.join(save_dir, "test_write_permission.tmp")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                print(f"✅ 目录写入权限验证成功")
            except Exception as e:
                print(f"❌ 目录写入权限验证失败: {e}")
                return False
            
            # 生成目标文件名
            video_filename = os.path.basename(source_video_path)
            target_path = os.path.join(save_dir, video_filename)
            print(f"📄 目标文件路径: {target_path}")
            
            # 如果目标文件已存在，生成新的文件名
            if os.path.exists(target_path):
                name, ext = os.path.splitext(video_filename)
                counter = 1
                while os.path.exists(target_path):
                    new_filename = f"{name}_{counter}{ext}"
                    target_path = os.path.join(save_dir, new_filename)
                    counter += 1
                print(f"📝 目标文件已存在，使用新文件名: {os.path.basename(target_path)}")
            
            # 复制文件
            import shutil
            print(f"📋 开始复制文件到目标位置...")
            shutil.copy2(source_video_path, target_path)
            print(f"✅ 文件复制完成: {target_path}")
            
            # 验证复制是否成功
            if os.path.exists(target_path):
                target_size = os.path.getsize(target_path)
                print(f"📊 目标文件大小: {target_size} 字节")
                
                # 比较文件大小确保复制完整
                if target_size == source_size:
                    print(f"✅ 文件大小验证成功，开始删除源文件")
                    
                    # 删除源文件
                    try:
                        os.remove(source_video_path)
                        print(f"🗑️ 源文件已删除: {source_video_path}")
                        print(f"✅ 视频已成功移动到: {target_path}")
                        return target_path
                    except Exception as e:
                        print(f"⚠️ 删除源文件失败: {e}")
                        print(f"✅ 视频已复制到: {target_path} (源文件保留)")
                        return target_path
                else:
                    print(f"❌ 文件大小不匹配，源文件: {source_size}, 目标文件: {target_size}")
                    # 删除不完整的目标文件
                    try:
                        os.remove(target_path)
                        print(f"🗑️ 已删除不完整的目标文件")
                    except:
                        pass
                    return False
            else:
                print(f"❌ 复制验证失败，目标文件不存在")
                return False
            
        except Exception as e:
            print(f"❌ 移动视频到保存目录失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def bind_preview_click_events(self, open_video_folder):
        """绑定预览区域的点击事件"""
        try:
            print("🔗 开始绑定预览点击事件")
            
            # 使用新的回调机制
            if hasattr(self.video_preview_widget, 'set_click_callback'):
                self.video_preview_widget.set_click_callback(open_video_folder)
                print("✅ 点击回调已设置")
            else:
                print("❌ 预览组件不支持点击回调")
        except Exception as e:
            print(f"绑定点击事件失败: {e}")
            import traceback
            traceback.print_exc()
    
    def debug_test_preview(self):
        """调试测试预览功能"""
        print("🧪 开始调试测试预览功能")
        
        # 首先测试配置读取
        print("🧪 测试配置读取...")
        save_path = self.get_video_save_path()
        print(f"📁 当前配置的保存路径: {save_path}")
        
        # 查找最新的视频文件进行测试
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        video_folder = os.path.join(base_path, "video_tools", "生成的视频")
        print(f"🔍 检查视频文件夹: {video_folder}")
        
        if os.path.exists(video_folder):
            video_files = [f for f in os.listdir(video_folder) if f.endswith('.mp4')]
            print(f"📁 找到 {len(video_files)} 个视频文件: {video_files}")
            
            if video_files:
                latest_video = max(video_files, key=lambda x: os.path.getctime(os.path.join(video_folder, x)))
                video_path = os.path.join(video_folder, latest_video)
                print(f"🎬 最新视频: {latest_video}")
                print(f"🎬 完整路径: {video_path}")
                
                # 测试移动功能
                print("🧪 测试移动功能...")
                moved_path = self.copy_video_to_save_path(video_path)
                if moved_path:
                    print(f"✅ 移动测试成功: {moved_path}")
                    # 使用移动后的路径更新预览
                    self.update_video_preview(moved_path)
                else:
                    print("❌ 移动测试失败")
                    # 使用原路径更新预览
                    self.update_video_preview(video_path)
            else:
                print("❌ 没有找到测试视频文件")
                # 测试错误情况
                self.update_video_preview("不存在的文件.mp4")
        else:
            print("❌ 视频文件夹不存在")
            # 测试错误情况
            self.update_video_preview("不存在的文件.mp4")

    def _update_voice_options(self, tts_engine):
        """根据选择的TTS引擎更新可用的音色选项"""
        # 获取当前选择的TTS引擎
        if isinstance(tts_engine, str):
            current_engine = tts_engine
        else:
            current_engine = self.tts_engine_combo.currentText()
        
        # 根据TTS引擎设置对应的音色选项
        if current_engine == "阿里云百炼":
            # 阿里云百炼音色选项
            voices = [
                "Cherry (活泼灵动，女声)", 
                "Chelsie (柔和亲切，女声)", 
                "Serena (优雅知性，女声)",
                "Ethan (沉稳磁性，男声)",
                "Dylan (北京话，男声)",
                "Jada (上海话，女声)",
                "Sunny (四川话，女声)"
            ]
            # 设置默认选中项
            default_voice = "Cherry (活泼灵动，女声)"
        else:  # Edge-TTS为默认选项
            # Edge-TTS音色选项
            voices = [
                "Xiaoxiao (女声)",
                "Yunxi (男声)",
                "Yunjian (男声)",
                "Xiaoyi (女声)",
                "Yunyang (男声)"
            ]
            # 设置默认选中项
            default_voice = "Xiaoxiao (女声)"
        
        # 更新音色下拉框的选项
        self.voice_combo.clear()
        self.voice_combo.addItems(voices)
        
        # 设置默认选中项
        if default_voice in voices:
            index = voices.index(default_voice)
            self.voice_combo.setCurrentIndex(index)
    
    def create_automation_tab(self):
        """创建自动化标签页 - 浏览器监控服务器"""
        from browser_monitor_server import BrowserMonitorServer
        
        # 创建浏览器监控服务器实例，传递认证客户端和主窗口引用
        self.browser_monitor = BrowserMonitorServer(auth_client=self.auth_client, main_window=self)
        
        # 将监控服务器作为自动化标签页添加到标签页控件中
        self.tab_widget.addTab(self.browser_monitor, "自动任务")
        
        # 创建代理属性，使旧代码能够正常工作
        self.automation_log = self.browser_monitor.log_text
        self.task_combo = None  # 不再使用
        self.task_params_input = None  # 不再使用
        self.browser_table = None  # 不再使用
        self.bit_connection_status = None  # 不再使用
    
    def create_homepage_posting_tab(self):
        """创建主页发帖标签页"""
        from homepage_browser import HomepageBrowser
        
        # 创建主页发帖浏览器实例
        self.homepage_browser = HomepageBrowser(self)
        
        # 将主页发帖标签页添加到标签页控件中
        self.tab_widget.addTab(self.homepage_browser, "主页发帖")
        
        print("✅ 主页发帖标签页已创建")
        
        # 创建代理管理标签页
        self.create_proxy_manager_tab()
    
    def create_proxy_manager_tab(self):
        """创建IP代理管理标签页（网页版 + 控制面板）"""
        try:
            from PyQt5.QtWebEngineWidgets import QWebEngineView
            from PyQt5.QtCore import QUrl, QObject, pyqtSignal, QTimer
            from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
            
            # 创建信号管理器
            class SignalManager(QObject):
                update_status_signal = pyqtSignal(dict)  # 状态更新信号
                restore_button_signal = pyqtSignal()     # 恢复按钮信号
                reload_page_signal = pyqtSignal()        # 刷新页面信号
            
            signal_mgr = SignalManager()
            
            # 创建容器
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)  # 减少间距
            
            # 创建控制面板
            control_panel = QWidget()
            control_panel.setMaximumHeight(45)  # 再增加一点高度
            control_layout = QHBoxLayout(control_panel)
            control_layout.setContentsMargins(10, 6, 10, 6)  # 增加上下边距
            control_layout.setSpacing(8)  # 设置按钮间距
            
            # 服务状态标签
            status_label = QLabel("服务状态: 检查中...")
            status_label.setStyleSheet("font-weight: bold; color: #666;")  # 恢复正常字体
            control_layout.addWidget(status_label)
            
            control_layout.addStretch()
            
            # 刷新按钮
            refresh_btn = QPushButton("🔄 刷新")
            refresh_btn.setToolTip("刷新页面")
            refresh_btn.setFixedSize(90, 32)  # 增加高度到32px
            control_layout.addWidget(refresh_btn)
            
            # 重启服务按钮
            restart_btn = QPushButton("🔁 重启服务")
            restart_btn.setToolTip("重启IP代理管理服务")
            restart_btn.setFixedSize(110, 32)  # 增加高度到32px
            control_layout.addWidget(restart_btn)
            
            # 打开浏览器按钮
            open_browser_btn = QPushButton("🌐 浏览器打开")
            open_browser_btn.setToolTip("在外部浏览器中打开")
            open_browser_btn.setFixedSize(110, 32)  # 增加高度到32px
            control_layout.addWidget(open_browser_btn)
            
            layout.addWidget(control_panel)
            
            # 创建网页视图
            web_view = QWebEngineView()
            
            # 配置WebEngine设置
            web_view.settings().setAttribute(web_view.settings().PluginsEnabled, True)
            web_view.settings().setAttribute(web_view.settings().JavascriptEnabled, True)
            web_view.settings().setAttribute(web_view.settings().LocalStorageEnabled, True)
            
            # 连接加载信号
            def on_load_started():
                print("[IP代理浏览器] 开始加载页面...")
            
            def on_load_progress(progress):
                if progress % 20 == 0:  # 减少日志量
                    print(f"[IP代理浏览器] 加载进度: {progress}%")
            
            def on_load_finished(ok):
                if ok:
                    print("[IP代理浏览器] ✓ 页面加载成功")
                else:
                    print("[IP代理浏览器] ❌ 页面加载失败")
            
            web_view.loadStarted.connect(on_load_started)
            web_view.loadProgress.connect(on_load_progress)
            web_view.loadFinished.connect(on_load_finished)
            
            web_view.setUrl(QUrl("http://127.0.0.1:5000"))
            layout.addWidget(web_view)
            self.proxy_web_view = web_view  # 保存引用以便在标签页切换时刷新
            
            # 连接信号到槽函数
            def on_update_status(status):
                """处理状态更新信号"""
                try:
                    if status['running']:
                        status_text = f"服务状态: ✓ 运行中"
                        if status.get('proxy_count') is not None:
                            status_text += f" | 代理: {status['active_count']}/{status['proxy_count']}"
                        status_label.setText(status_text)
                        status_label.setStyleSheet("font-weight: bold; color: #28a745;")
                    else:
                        status_label.setText("服务状态: ✗ 未运行")
                        status_label.setStyleSheet("font-weight: bold; color: #dc3545;")
                except Exception as e:
                    print(f"[错误] 更新状态UI失败: {e}")
            
            def on_restore_button():
                """处理恢复按钮信号"""
                try:
                    restart_btn.setEnabled(True)
                    restart_btn.setText("🔁 重启服务")
                    print("[调试] 按钮状态已恢复")
                except Exception as e:
                    print(f"[错误] 恢复按钮失败: {e}")
            
            def on_reload_page():
                """处理刷新页面信号"""
                try:
                    web_view.reload()
                    print("[调试] 页面已刷新")
                except Exception as e:
                    print(f"[错误] 刷新页面失败: {e}")
            
            signal_mgr.update_status_signal.connect(on_update_status)
            signal_mgr.restore_button_signal.connect(on_restore_button)
            signal_mgr.reload_page_signal.connect(on_reload_page)
            
            # 绑定按钮事件
            def refresh_page():
                web_view.reload()
                print("✓ 已刷新IP管理页面")
            
            def restart_service():
                """重启服务（使用信号机制）"""
                print("[调试] 重启服务按钮被点击")
                
                # 禁用按钮
                restart_btn.setEnabled(False)
                restart_btn.setText("重启中...")
                
                def do_restart():
                    try:
                        print("[调试] 开始重启服务...")
                        from proxy_service_manager import get_service_manager
                        manager = get_service_manager()
                        
                        # 重启服务
                        success = manager.restart()
                        print(f"[调试] 重启结果: {success}")
                        
                        if success:
                            print("✓ IP代理管理服务重启成功")
                            # 发送刷新页面信号
                            signal_mgr.reload_page_signal.emit()
                        else:
                            print("✗ IP代理管理服务重启失败")
                        
                        # 发送恢复按钮信号
                        signal_mgr.restore_button_signal.emit()
                        
                        # 更新状态
                        update_status()
                        
                    except Exception as e:
                        print(f"[错误] 重启服务异常: {e}")
                        import traceback
                        traceback.print_exc()
                        
                        # 确保按钮恢复
                        signal_mgr.restore_button_signal.emit()
                
                # 在后台线程执行
                import threading
                threading.Thread(target=do_restart, daemon=True).start()
            
            def open_in_browser():
                import webbrowser
                webbrowser.open("http://127.0.0.1:5000")
                print("✓ 已在外部浏览器打开")
            
            def update_status():
                """更新服务状态（使用信号）"""
                def do_update():
                    try:
                        from proxy_service_manager import get_service_manager
                        manager = get_service_manager()
                        status = manager.get_status()
                        
                        # 发送状态更新信号
                        signal_mgr.update_status_signal.emit(status)
                        
                    except Exception as e:
                        print(f"[错误] 获取状态失败: {e}")
                
                # 在后台线程执行
                import threading
                threading.Thread(target=do_update, daemon=True).start()
            
            refresh_btn.clicked.connect(refresh_page)
            restart_btn.clicked.connect(restart_service)
            open_browser_btn.clicked.connect(open_in_browser)
            
            # 延迟初始更新状态（避免启动时阻塞）
            QTimer.singleShot(1000, update_status)  # 1秒后更新
            
            # 定时更新状态（每15秒）
            status_timer = QTimer()
            status_timer.timeout.connect(update_status)
            status_timer.start(15000)  # 15秒
            
            # 添加到标签页
            self.tab_widget.addTab(container, "代理管理")
            
            print("✅ IP代理管理标签页已创建（增强版）")
        except ImportError as e:
            print(f"❌ 导入QtWebEngine失败: {e}")
            print("提示: 需要安装 PyQtWebEngine: pip install PyQtWebEngine")
        except Exception as e:
            print(f"❌ 创建IP管理标签页失败: {e}")
            import traceback
            traceback.print_exc()
    
    def log_automation(self, message: str):
        """添加自动化操作日志"""
        # 使用 browser_monitor 的日志功能
        if hasattr(self, 'browser_monitor') and self.browser_monitor:
            self.browser_monitor.log(message)
        else:
            # 如果 browser_monitor 还未初始化，直接打印
            print(f"[自动化] {message}")
    
    def reload_task_list(self):
        """重新加载任务列表（已废弃，保留以兼容旧代码）"""
        self.log_automation("⚠️ 此功能已集成到浏览器监控服务器中")
    
    def on_task_selected(self, task_name: str):
        """任务选择变化时的处理（已废弃，保留以兼容旧代码）"""
        pass
    
    def execute_selected_task(self):
        """执行选中的任务（已废弃，保留以兼容旧代码）"""
        self.log_automation("⚠️ 此功能已集成到浏览器监控服务器中")
        QMessageBox.information(self, "提示", "此功能已集成到浏览器监控服务器中，请使用自动化标签页的新界面")
    
    def check_bitbrowser_connection(self):
        """检查比特浏览器连接状态（已废弃，保留以兼容旧代码）"""
        self.log_automation("⚠️ 此功能已集成到浏览器监控服务器中")
    
    def refresh_browser_list(self):
        """刷新浏览器列表（已废弃，保留以兼容旧代码）"""
        self.log_automation("⚠️ 此功能已集成到浏览器监控服务器中")
    
    def get_selected_browser_ids(self) -> list:
        """获取选中的浏览器ID列表（已废弃，保留以兼容旧代码）"""
        return []
    
    def open_selected_browser(self):
        """打开选中的浏览器（已废弃，保留以兼容旧代码）"""
        self.log_automation("⚠️ 此功能已集成到浏览器监控服务器中")
    
    def close_selected_browser(self):
        """关闭选中的浏览器（已废弃，保留以兼容旧代码）"""
        self.log_automation("⚠️ 此功能已集成到浏览器监控服务器中")
    
    def on_tab_changed(self, index):
        """标签页切换事件处理 - 优化浏览器嵌入响应性"""
        # 获取当前标签页的名称
        current_tab_name = self.tab_widget.tabText(index)
        
        print(f"[标签页切换] 切换到: {current_tab_name} (索引: {index})")
        
        # 根据标签页显示/隐藏标题容器
        if hasattr(self, 'title_container'):
            if current_tab_name == "自动任务":
                # 在自动化标签页隐藏标题，节省空间
                self.title_container.hide()
                # 最大化窗口以获得更多空间
                if not self.isMaximized():
                    self.showMaximized()
            else:
                # 在其他标签页显示标题
                self.title_container.show()
        
        # 处理IP代理管理标签页
        if current_tab_name == "代理管理":
            print("[标签页切换] 进入IP代理管理标签页")
            
            # 获取当前标签页的widget（容器）
            current_widget = self.tab_widget.currentWidget()
            if current_widget:
                current_widget.show()
                current_widget.raise_()
                current_widget.update()
                print(f"[标签页切换] 容器已提升: {current_widget}")
                print(f"[标签页切换] 容器可见: {current_widget.isVisible()}")
            
            # 确保内嵌浏览器可见
            if hasattr(self, 'proxy_web_view'):
                self.proxy_web_view.show()
                self.proxy_web_view.raise_()
                
                # 强制重新加载页面，确保显示
                print("[标签页切换] 强制重新加载IP代理管理页面...")
                self.proxy_web_view.reload()
                
                # 强制更新和重绘
                self.proxy_web_view.update()
                self.proxy_web_view.repaint()
                # 强制处理事件
                QApplication.processEvents()
                print("[标签页切换] IP代理管理浏览器已显示")
                print(f"[标签页切换] 浏览器几何信息: {self.proxy_web_view.geometry()}")
                print(f"[标签页切换] 浏览器可见: {self.proxy_web_view.isVisible()}")
                print(f"[标签页切换] 浏览器Z-order: {self.proxy_web_view.windowFlags()}")
                print(f"[标签页切换] 当前URL: {self.proxy_web_view.url().toString()}")
            else:
                print("[标签页切换] ⚠️ IP代理管理浏览器尚未加载")
        
        # 处理测试标签页
        if current_tab_name == "🧪 测试":
            print("[标签页切换] 测试标签页已激活")
            if hasattr(self, 'test_web_view'):
                self.test_web_view.show()
                self.test_web_view.raise_()
                self.test_web_view.update()
                QApplication.processEvents()
                print(f"[标签页切换] 测试浏览器可见: {self.test_web_view.isVisible()}")
                print(f"[标签页切换] 测试浏览器几何: {self.test_web_view.geometry()}")
        else:
            # 离开测试标签页时，隐藏浏览器
            if hasattr(self, 'test_web_view'):
                self.test_web_view.hide()
        
        # 处理主页发帖分页的浏览器刷新
        if current_tab_name == "主页发帖":
            # 切换到主页发帖分页时，刷新嵌入的浏览器
            if hasattr(self, 'homepage_browser') and self.homepage_browser:
                if hasattr(self.homepage_browser, 'browser_container'):
                    container = self.homepage_browser.browser_container
                    if hasattr(container, '_refresh_browser'):
                        container._refresh_browser()
                        print("[UI] 切换到主页发帖分页，已刷新浏览器")
        else:
            # 切换离开主页发帖分页时，暂停浏览器刷新以节省资源
            if hasattr(self, 'homepage_browser') and self.homepage_browser:
                if hasattr(self.homepage_browser, 'browser_container'):
                    container = self.homepage_browser.browser_container
                    if hasattr(container, 'refresh_timer') and container.refresh_timer:
                        try:
                            container.refresh_timer.stop()
                            print("[UI] 离开主页发帖分页，已暂停浏览器刷新")
                        except:
                            pass
        
        # 智能窗口管理：
        # 1. 大多数 Selenium 操作不需要窗口可见，即使嵌入并隐藏也能正常工作
        # 2. 只在特殊情况下才需要释放窗口（如截图、手动干预等）
        # 3. 保持窗口嵌入状态，避免窗口到处飞的混乱情况
        
        # 如果有浏览器监控实例，记录标签页切换
        if hasattr(self, 'browser_monitor') and self.browser_monitor:
            self.browser_monitor.log(f"✓ 已切换到 {current_tab_name} 标签页")
    
    def load_video_config(self):
        """加载视频配置"""
        try:
            # 默认API Key
            default_api_key = "sk-e2bb42b9b5ee4892b80d70f71585da0f"
            
            video_config_file = "video_config.json"
            if os.path.exists(video_config_file):
                with open(video_config_file, 'r', encoding='utf-8') as f:
                    video_config = json.load(f)
                    # 恢复视频提示词
                    if "prompt" in video_config:
                        self.video_prompt_input.setPlainText(video_config["prompt"])
                    # 恢复TTS引擎选择
                    if "tts_engine" in video_config:
                        index = self.tts_engine_combo.findText(video_config["tts_engine"])
                        if index >= 0:
                            self.tts_engine_combo.setCurrentIndex(index)
                    # 恢复音色选择
                    if "voice" in video_config:
                        index = self.voice_combo.findText(video_config["voice"])
                        if index >= 0:
                            self.voice_combo.setCurrentIndex(index)
                    # 恢复API Key（如果配置文件中有，使用配置的；否则使用默认的）
                    if "api_key" in video_config and video_config["api_key"]:
                        self.api_key_input.setText(video_config["api_key"])
                    else:
                        self.api_key_input.setText(default_api_key)
            else:
                # 如果配置文件不存在，使用默认API Key
                self.api_key_input.setText(default_api_key)
        except Exception as e:
            print(f"加载视频配置失败: {e}")
            # 出错时也设置默认API Key
            self.api_key_input.setText("sk-e2bb42b9b5ee4892b80d70f71585da0f")
    
    def save_video_config(self):
        """保存视频配置"""
        try:
            video_config = {
                "prompt": self.video_prompt_input.toPlainText(),
                "tts_engine": self.tts_engine_combo.currentText(),
                "voice": self.voice_combo.currentText(),
                "api_key": self.api_key_input.text(),
                "last_modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open("video_config.json", 'w', encoding='utf-8') as f:
                json.dump(video_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存视频配置失败: {e}")
    
    # handle_simulator_limit_exceeded 方法已删除（模拟器功能已废弃）


# 添加视频生成工作线程类
class VideoGenerationWorker(QObject):
    """视频生成工作线程"""
    finished = pyqtSignal()
    progress = pyqtSignal(str)
    
    def __init__(self, prompt, tts_engine, voice):
        super().__init__()
        self.prompt = prompt
        self.tts_engine = tts_engine
        self.voice = voice
        self._in_progress_callback = False  # 防止递归调用
        
    def run(self):
        """执行视频生成任务"""
        try:
            # 记录日志
            self.progress.emit("开始生成视频")
            self.progress.emit(f"TTS引擎: {self.tts_engine}")
            self.progress.emit(f"音色: {self.voice}")
            
            # 获取正确的基础路径
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            
            # 导入视频生成器
            video_tools_path = os.path.join(base_path, "video_tools")
            sys.path.append(video_tools_path)
            from video_generator import VideoGenerator
            
            # 创建日志回调函数（使用线程安全的方式）
            def log_callback(message):
                # 防止递归调用
                if not self._in_progress_callback:
                    self._in_progress_callback = True
                    try:
                        # 使用QMetaObject.invokeMethod确保在主线程中发送信号
                        self.progress.emit(message)
                    finally:
                        self._in_progress_callback = False
            
            # 创建视频生成器实例
            # 注意：确保VideoGenerator不创建任何Qt GUI对象
            generator = VideoGenerator(log_callback=log_callback)
            
            # 调用生成视频方法
            # 这个方法应该是纯Python代码，不涉及Qt GUI
            success = generator.generate_video(
                prompt=self.prompt,
                tts_engine=self.tts_engine,
                voice_style=self.voice,
                style="旅行"  # 默认风格
            )
            
            if success:
                self.progress.emit("视频生成完成!")
            else:
                self.progress.emit("视频生成失败")
        except Exception as e:
            self.progress.emit(f"视频生成过程中出现错误: {str(e)}")
            import traceback
            self.progress.emit(f"错误详情: {traceback.format_exc()}")
        finally:
            self.finished.emit()


class GlowingLabel(QLabel):
    """自定义发光标签类，实现更好的文字发光效果"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.text_color = QColor(255, 255, 255)  # 文字颜色
        self.border_color = QColor(100, 180, 255)  # 调整为更协调的蓝色边框颜色
        self.font = QFont("Microsoft YaHei", 38, QFont.Bold)  # 再次调整字体大小
        self.original_font_size = 38  # 保存原始字体大小
        
        # 动画相关属性
        self.animation_phase = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(50)  # 50ms更新一次，实现平滑动画
        
        # 设置标签属性
        self.setAlignment(QtCore_Qt.AlignCenter)
        self.setStyleSheet("background-color: transparent; border: none; color: white;")
        self.setFont(self.font)
        
        # 创建更柔和的发光效果
        self.create_glow_effects()
        # 初始化发光效果
        self.update_glow_effect()
        
    def create_glow_effects(self):
        """创建更柔和的发光效果"""
        # 清除现有的效果
        self.setGraphicsEffect(None)
        
        # 创建更柔和的发光效果
        effect = QGraphicsDropShadowEffect()
        effect.setBlurRadius(20)  # 减小发光半径，使效果更集中
        effect.setXOffset(0)       # 无偏移
        effect.setYOffset(0)       # 无偏移
        effect.setColor(QColor(100, 180, 255, 100))  # 更柔和的蓝色 (#64B4FF) ，降低透明度
        self.setGraphicsEffect(effect)
        
    def update_animation(self):
        """更新动画相位"""
        self.animation_phase += 0.1
        # 重新创建发光效果以实现呼吸灯效果
        self.update_glow_effect()
        self.update()
        
    def update_glow_effect(self):
        """更新发光效果以实现呼吸灯动画"""
        effect = self.graphicsEffect()
        if effect and isinstance(effect, QGraphicsDropShadowEffect):
            # 计算呼吸灯效果的透明度变化
            # 使用sin函数创建平滑的忽明忽暗效果
            # 增加基础亮度和变化幅度，让最亮时更明显
            alpha = 120 + int(80 * math.sin(self.animation_phase))
            # 确保透明度在合理范围内（最暗40，最亮200）
            alpha = max(40, min(200, alpha))
            effect.setColor(QColor(100, 180, 255, alpha))
        
    def setTextColor(self, color):
        """设置文字颜色"""
        self.text_color = color
        self.setStyleSheet(f"background-color: transparent; border: none; color: {color.name()};")
        self.update()
        
    def setBorderColor(self, color):
        """设置边框颜色"""
        self.border_color = color
        self.update()
        
    def setGlowFont(self, font):
        """设置字体"""
        self.font = font
        self.setFont(font)
        self.update()
        
    def setGlowRadius(self, radius):
        """设置发光半径"""
        # 重新创建发光效果
        effect = self.graphicsEffect()
        if effect and isinstance(effect, QGraphicsDropShadowEffect):
            effect.setBlurRadius(radius)
        self.update()
        
    def setGlowColor(self, color):
        """设置发光颜色"""
        # 更新发光效果的颜色
        effect = self.graphicsEffect()
        if effect and isinstance(effect, QGraphicsDropShadowEffect):
            effect.setColor(color)
        self.update()
        
    def resizeEvent(self, event):
        """处理标签大小调整事件，自适应字体大小"""
        super().resizeEvent(event)
        # 如果设置了最大宽度限制（不是Qt默认的最大值），调整字体大小以适应
        # Qt的默认最大值是16777215，如果是这个值说明没有限制
        if self.maximumWidth() > 0 and self.maximumWidth() < 16777215:
            self.adjust_font_size()
        else:
            # 没有宽度限制时，确保使用原始字体大小
            if self.font.pointSize() != self.original_font_size:
                self.font.setPointSize(self.original_font_size)
                self.setFont(self.font)
                self.update()
    
    def adjust_font_size(self):
        """根据标签宽度调整字体大小"""
        if not self.text():
            return
            
        # 获取当前宽度
        current_width = self.width()
        if current_width <= 0:
            return
            
        # 使用原始字体大小计算文本宽度，避免循环依赖
        original_font = QFont(self.font)
        original_font.setPointSize(self.original_font_size)
        font_metrics = QFontMetrics(original_font)
        text_width = font_metrics.horizontalAdvance(self.text())
        
        # 如果文本宽度小于当前宽度，直接使用原始字体大小，不缩小
        if text_width <= current_width:
            new_font_size = self.original_font_size
        else:
            scale_factor = current_width / text_width
            new_font_size = max(12, int(self.original_font_size * scale_factor * 0.9))
        
        # 只有当字体大小变化超过1个点时才更新，避免微小变化导致的闪烁
        if abs(new_font_size - self.font.pointSize()) > 1:
            # 更新字体
            self.font.setPointSize(new_font_size)
            self.setFont(self.font)
            self.update()
        
    def paintEvent(self, a0):
        """重写绘制事件，添加文字边框效果"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 获取文本和字体信息
        text = self.text()
        font = self.font  # 正确获取字体对象
        
        # 设置字体和抗锯齿
        painter.setFont(font)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        # 计算文本位置
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)  # 使用horizontalAdvance替代已弃用的width方法
        x = (self.width() - text_width) // 2
        y = (self.height() + metrics.ascent() - metrics.descent()) // 2
        
        # 直接绘制文字本身（无描边）
        pen = QPen(self.text_color, 1)
        painter.setPen(pen)
        painter.drawText(x, y, text)
        
        # 发光效果由QGraphicsEffect处理
    
    def resizeEvent(self, event):
        """窗口大小改变时重新布局浏览器卡片"""
        super().resizeEvent(event)
        # 使用定时器防抖动，避免频繁调用
        if hasattr(self, 'browser_cards_container'):
            # 取消之前的定时器
            if hasattr(self, '_resize_timer') and self._resize_timer.isActive():
                self._resize_timer.stop()
            # 创建新的定时器
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self.relayout_browser_cards)
            self._resize_timer.start(300)  # 300ms后重新布局
    
    def closeEvent(self, event):
        """程序关闭时的清理工作（改进版 - 确保所有子进程被终止）"""
        print("=" * 60)
        print("正在关闭程序...")
        
        # 1. 关闭后端服务
        try:
            print("正在关闭后端服务...")
            
            # 1.1 发送关闭请求
            import requests
            try:
                requests.post('http://127.0.0.1:8805/shutdown', timeout=2)
                print("✓ 已发送关闭信号")
            except:
                pass
            
            # 1.2 等待后端线程停止
            if hasattr(self, 'backend_thread') and self.backend_thread:
                print("等待后端线程停止...")
                self.backend_thread.stop()
                self.backend_thread.wait(3000)  # 等待最多3秒
                
                # 1.3 如果线程还在运行，强制终止
                if self.backend_thread.isRunning():
                    print("⚠ 后端线程未响应，强制终止...")
                    self.backend_thread.terminate()
                    self.backend_thread.wait(1000)
                
                print("✓ 后端服务已关闭")
            
        except Exception as e:
            print(f"⚠ 关闭后端服务失败: {e}")
        
        # 2. 停止IP代理管理服务
        try:
            print("正在停止IP代理管理服务...")
            from proxy_service_manager import get_service_manager
            proxy_service = get_service_manager()
            proxy_service.stop()
            print("✓ IP代理管理服务已停止")
        except Exception as e:
            print(f"⚠ 停止IP代理管理服务失败: {e}")
        
        # 3. 保存配置
        try:
            self.save_video_config()
            self.save_config()
            print("✓ 配置已保存")
        except Exception as e:
            print(f"⚠ 保存配置失败: {e}")
        
        # 4. 清理浏览器监控服务器
        try:
            if hasattr(self, 'browser_monitor') and self.browser_monitor:
                self.browser_monitor.cleanup()
                print("✓ 浏览器监控已清理")
        except Exception as e:
            print(f"⚠ 清理浏览器监控失败: {e}")
        
        # 5. 强制终止所有子进程（最后的保险）
        try:
            import psutil
            current_process = psutil.Process()
            children = current_process.children(recursive=True)
            
            if children:
                print(f"发现 {len(children)} 个子进程，正在清理...")
                for child in children:
                    try:
                        child.terminate()
                    except:
                        pass
                
                # 等待子进程退出
                gone, alive = psutil.wait_procs(children, timeout=2)
                
                # 强制杀死仍然存活的进程
                for p in alive:
                    try:
                        p.kill()
                        print(f"✓ 强制终止子进程: {p.pid}")
                    except:
                        pass
                
                print(f"✓ 已清理 {len(children)} 个子进程")
        except ImportError:
            print("⚠ psutil未安装，跳过子进程清理")
        except Exception as e:
            print(f"⚠ 清理子进程失败: {e}")
        
        print("✓ 程序关闭")
        print("=" * 60)
        
        event.accept()
    
    


def set_app_icon(app):
    """设置应用程序图标"""
    try:
        icon_paths = []
        
        if getattr(sys, 'frozen', False):
            # 打包后的exe环境，尝试多个位置
            exe_dir = os.path.dirname(sys.executable)
            internal_dir = sys._MEIPASS
            
            # 优先尝试exe同级目录
            icon_paths.extend([
                os.path.join(exe_dir, "facebook_logo.png"),
                os.path.join(exe_dir, "facebook_logo.svg"),
                os.path.join(internal_dir, "facebook_logo.png"),
                os.path.join(internal_dir, "facebook_logo.svg")
            ])
        else:
            # 开发环境
            base_path = os.path.dirname(os.path.abspath(__file__))
            icon_paths.extend([
                os.path.join(base_path, "facebook_logo.png"),
                os.path.join(base_path, "facebook_logo.svg")
            ])
        
        # 尝试加载图标
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                icon = QIcon(icon_path)
                if not icon.isNull():
                    app.setWindowIcon(icon)
                    print(f"[OK] 应用程序图标已设置: {icon_path}")
                    return True
        
        print("[WARN] 未找到有效的应用程序图标文件")
        print(f"[DEBUG] 尝试的路径: {icon_paths}")
        return False
        
    except Exception as e:
        print(f"[ERROR] 设置应用程序图标失败: {e}")
        return False
# 在主程序 facebook_dashboard.py 的最开始添加
from ffmpeg_config import setup_ffmpeg, print_ffmpeg_info
from proxy_service_manager import get_service_manager

def main():
    """主程序入口"""
    # 写入文件日志（不依赖 stdout）
    try:
        with open("main_entry.log", "a", encoding="utf-8") as f:
            import datetime
            f.write(f"\n[{datetime.datetime.now()}] main() 函数被调用\n")
            f.flush()
    except:
        pass
    
    # 修复 stdout 问题（打包环境中 stdout 可能为 None）
    import sys
    if sys.stdout is None or not hasattr(sys.stdout, 'write'):
        # 创建一个文件作为 stdout
        try:
            sys.stdout = open("stdout.log", "a", encoding="utf-8", buffering=1)
            sys.stderr = sys.stdout
        except:
            # 如果连文件都打不开，创建一个虚拟的 stdout
            class DummyStdout:
                def write(self, text):
                    pass
                def flush(self):
                    pass
            sys.stdout = DummyStdout()
            sys.stderr = sys.stdout
    
    print("[main] ========== 主程序开始 ==========")
    print("[main] 进入 main() 函数")
    
    try:
        print("[main] 进入 try 块")
        
        # ============ FFmpeg配置（修复打包后视频功能）============
        print("\n" + "=" * 60)
        print("[main] 步骤1: 初始化FFmpeg配置...")
        print("=" * 60)
        try:
            setup_ffmpeg()
            print("[main] ✓ FFmpeg配置完成")
        except Exception as e:
            print(f"[main] ⚠ FFmpeg配置失败: {e}")
        print("=" * 60 + "\n")
        
        # ============ IP代理管理服务启动 ============
        print("=" * 60)
        print("[main] 步骤2: 启动IP代理管理服务...")
        print("=" * 60)
        try:
            proxy_service = get_service_manager()
            print("[main] ✓ 获取代理服务管理器成功")
            
            print("[main] 正在启动代理服务...")
            if proxy_service.start():
                print("[main] ✓ 代理服务启动成功")
                status = proxy_service.get_status()
                print(f"[main] ✓ 服务地址: {status['url']}")
                if status.get('proxy_count'):
                    print(f"[main] ✓ 代理总数: {status['proxy_count']}")
                    print(f"[main] ✓ 活跃代理: {status['active_count']}")
            else:
                print("[main] ⚠ IP代理管理服务启动失败，部分功能可能不可用")
        except Exception as e:
            print(f"[main] ⚠ 代理服务异常: {e}")
            import traceback
            traceback.print_exc()
        print("=" * 60 + "\n")
        
        # ============ Qt WebEngine配置（必须在QApplication之前）============
        print("[main] 步骤3: 配置 Qt WebEngine...")
        # 设置OpenGL上下文共享，解决QtWebEngine初始化问题
        from PyQt5.QtCore import Qt, QCoreApplication
        
        # 检查是否已经有 QApplication 实例（launcher.py 已创建）
        app = QApplication.instance()
        if app is None:
            # 如果没有，创建一个新的（开发环境）
            QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
            print("[main] ✓ Qt WebEngine OpenGL上下文共享已启用")
            app = QApplication(sys.argv)
            print("[main] ✓ 创建了新的 QApplication")
        else:
            # 使用已存在的实例（打包环境，launcher.py 已创建）
            print("[main] ✓ 使用已存在的 QApplication 实例")
        
        # 设置应用程序级别的图标（影响任务栏图标）
        print("[main] 正在设置应用图标...")
        try:
            set_app_icon(app)
            print("[main] ✓ 应用图标设置完成")
        except Exception as e:
            print(f"[main] ⚠ 设置应用图标失败: {e}")
        
        # ============ 用户认证 ============
        print("\n" + "=" * 60)
        print("[main] 步骤4: 开始用户认证...")
        print("=" * 60)
        
        # 创建认证客户端
        print("[main] 正在创建认证客户端...")
        auth_client = AuthClient("http://43.142.176.53:8805")  # 生产环境（8805端口）
        #auth_client = AuthClient("http://localhost")    # 测试环境（80端口）
        print("[main] ✓ 认证客户端创建成功")
        
        # 显示登录对话框（只显示一次）
        print("[main] 正在创建认证对话框...")
        auth_dialog = AuthDialog(auth_client)
        print("[main] ✓ 认证对话框创建成功")
        
        try:
            print("[main] 准备显示登录对话框...")
            login_result = auth_dialog.show_login_dialog()
            print(f"[main] 登录对话框返回结果: {login_result}")
            
            if not login_result:
                # 用户取消登录或认证失败
                print("[main] ❌ 认证失败或用户取消登录，程序退出")
                print("=" * 60 + "\n")
                
                # 清理资源
                try:
                    proxy_service.stop()
                except:
                    pass
                
                # 确保程序完全退出
                sys.exit(0)
                
        except Exception as e:
            print(f"❌ 认证过程发生异常: {e}")
            import traceback
            traceback.print_exc()
            print("=" * 60 + "\n")
            
            # 清理资源
            try:
                proxy_service.stop()
            except:
                pass
            
            # 确保程序完全退出
            sys.exit(1)
        
        # 认证成功，获取用户名并保存到配置
        认证用户名 = auth_client.user_info.get('username', '未知用户') if auth_client.user_info else '未知用户'
        print(f"✓ 认证成功，用户: {认证用户名}")
        print("=" * 60 + "\n")
        
        # 保存认证用户名到配置文件（供后端服务使用）
        try:
            import json
            import os
            config_file = "simulator_config.json"
            config = {}
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            config['username'] = 认证用户名
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"✓ 已保存用户名到配置文件")
        except Exception as e:
            print(f"⚠ 保存用户名失败: {e}")
        
        # 认证成功，创建主程序（传入auth_client，避免重复认证）
        print("[主程序] 正在创建主窗口...")
        dashboard = FacebookDashboard(auth_client)
        
        # 使用 QTimer 延迟显示窗口，确保所有初始化完成
        def show_dashboard():
            print("[主程序] 正在显示主窗口...")
            
            # 强制显示窗口的多种方法
            dashboard.setWindowState(Qt.WindowNoState)  # 先取消任何窗口状态
            dashboard.show()  # 先显示窗口
            dashboard.showNormal()  # 显示为正常状态
            dashboard.showMaximized()  # 然后最大化
            dashboard.raise_()  # 将窗口提升到最前面
            dashboard.activateWindow()  # 激活窗口
            dashboard.setFocus()  # 设置焦点
            
            # 确保窗口可见
            dashboard.setVisible(True)
            dashboard.setWindowOpacity(1.0)
            
            print(f"[主程序] ✓ 主窗口已显示")
            print(f"[主程序] 窗口可见性: {dashboard.isVisible()}")
            print(f"[主程序] 窗口状态: {dashboard.windowState()}")
            print(f"[主程序] 窗口大小: {dashboard.width()}x{dashboard.height()}")
            print(f"[主程序] 是否最大化: {dashboard.isMaximized()}")
            
            # 强制显示图表容器（如果存在）
            if hasattr(dashboard, 'charts_background'):
                print("[主程序] 强制显示图表容器...")
                dashboard.charts_background.show()
                dashboard.charts_background.setVisible(True)
            
            # 强制刷新窗口
            dashboard.update()
            dashboard.repaint()
        
        QTimer.singleShot(200, show_dashboard)  # 增加延迟到200ms
        
        # 程序退出时自动登出
        exit_code = 0
        try:
            exit_code = app.exec_()
        except Exception as e:
            print(f"程序异常: {e}")
        finally:
            # 在QApplication销毁之前登出
            try:
                if auth_client.is_authenticated():
                    auth_client.logout()
                    print("用户已登出")
            except Exception as e:
                print(f"登出时出错: {e}")
            
            # 停止IP代理管理服务
            try:
                print("正在停止IP代理管理服务...")
                proxy_service.stop()
            except Exception as e:
                print(f"停止服务时出错: {e}")
            
            # 强制退出，不等待任何清理
            try:
                import os
                os._exit(exit_code)
            except:
                pass
    
    except Exception as e:
        print(f"❌ 主程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 清理资源
        try:
            proxy_service.stop()
        except:
            pass
        
        # 确保程序完全退出
        sys.exit(1)

# 注意：不要在这里调用 main()！
# launcher_debug.py 会直接调用 main() 函数
# 如果在这里添加 if __name__ == '__main__': main()
# 在打包环境中可能导致无限重启循环！

# 为了兼容开发模式直接运行，添加以下代码
if __name__ == "__main__":
    # 检查是否为打包环境
    if not getattr(sys, 'frozen', False):
        # 开发环境，直接运行
        main()
    else:
        # 打包环境，通常由 launcher 启动
        # 如果是直接作为入口点启动，也可以运行
        pass
