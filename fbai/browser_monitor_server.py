"""
浏览器监控服务器
- 提供 HTTP API 供外部脚本调用
- UI 常驻，浏览器状态持久化
"""

import sys
import os
import time
import json
import ctypes
from ctypes import wintypes
from typing import Dict, Optional
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGridLayout, QScrollArea, QTextEdit, QSplitter,
    QCheckBox, QSpinBox, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QMetaObject, Q_ARG

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# 动态查找脚本配置目录
def _find_scripts_config_dir():
    """查找脚本配置目录"""
    possible_dirs = [
        # 打包后的位置1：exe所在目录/automation/scripts/脚本配置/
        os.path.join(os.path.dirname(sys.executable), "automation", "scripts", "脚本配置"),
        # 打包后的位置2：exe所在目录/automation_scripts/脚本配置/（兼容旧版）
        os.path.join(os.path.dirname(sys.executable), "automation_scripts", "脚本配置"),
        # 开发时的位置
        os.path.join(os.path.dirname(__file__), "automation", "scripts", "脚本配置"),
        # 当前工作目录
        os.path.join(os.getcwd(), "automation", "scripts", "脚本配置"),
    ]
    
    for dir_path in possible_dirs:
        if os.path.exists(dir_path):
            return dir_path
    
    # 默认使用第一个位置
    return possible_dirs[0]

# 脚本配置目录
脚本配置目录 = _find_scripts_config_dir()

# 运行配置文件路径
运行配置路径 = os.path.join(脚本配置目录, "运行配置.json")

# Windows API
user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_POPUP = 0x80000000
WS_BORDER = 0x00800000
WS_DLGFRAME = 0x00400000
WS_VSCROLL = 0x00200000
WS_HSCROLL = 0x00100000
WS_EX_CLIENTEDGE = 0x00000200
WS_EX_WINDOWEDGE = 0x00000100
WS_EX_STATICEDGE = 0x00020000
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040
SW_SHOW = 5
SW_RESTORE = 9
DWMWA_NCRENDERING_POLICY = 2
DWMNCRP_DISABLED = 1

try:
    from bitbrowser_api import bit_browser
    BITBROWSER_AVAILABLE = True
except ImportError:
    BITBROWSER_AVAILABLE = False

# 全局监控实例
_monitor = None
API_PORT = 5678


class BrowserContainer(QWidget):
    """浏览器嵌入容器"""
    released = pyqtSignal(str)
    
    def __init__(self, browser_id: str, browser_name: str, parent=None):
        super().__init__(parent)
        self.browser_id = browser_id
        self.browser_name = browser_name
        self.browser_hwnd = None
        self.original_style = None
        self.original_parent = None
        self.driver = None
        self._status = "就绪"
        self.driver_path = ""
        self.debugger_address = ""
        self._tasks = []  # 任务列表
        self._index = None  # 编号
        
        # 尝试从浏览器名称中提取编号（如 "#4 hokejely" -> 4）
        import re
        match = re.match(r'^#(\d+)', browser_name)
        if match:
            self._index = int(match.group(1))
        
        self.setStyleSheet("background-color: #1a1a2e; border: none;")
        self.setMinimumSize(300, 200)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 标题栏
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #21262d; border: none;")
        title_bar.setFixedHeight(24)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(6, 0, 6, 0)
        
        # 只显示编号，不显示浏览器名称
        self.title_label = QLabel("")
        self.title_label.setStyleSheet("color: #c9d1d9; font-size: 11px; font-weight: bold;")
        title_layout.addWidget(self.title_label)
        
        title_layout.addStretch()
        
        self.status_label = QLabel(self._status)
        self.status_label.setStyleSheet("color: #8b949e; font-size: 10px;")
        title_layout.addWidget(self.status_label)
        
        # 释放按钮（蓝色圆点）
        release_btn = QPushButton("●")
        release_btn.setFixedSize(6, 12)
        release_btn.setToolTip("释放浏览器窗口")
        release_btn.setStyleSheet("""
            QPushButton { 
                background: transparent; 
                color: #0969da; 
                border: none; 
                border-radius: 6px; 
                font-size: 6px;
                padding: 0px;
                font-family: Arial;
            } 
            QPushButton:hover { 
                color: #1f6feb;
                background: rgba(9, 105, 218, 0.1);
            }
        """)
        release_btn.clicked.connect(lambda: (self.release(), self.released.emit(self.browser_id)))
        title_layout.addWidget(release_btn)
        
        layout.addWidget(title_bar)
        
        self.browser_area = QWidget()
        # 改成白色背景，这样即使浏览器窗口有黑边也不明显
        self.browser_area.setStyleSheet("background-color: #ffffff; border: none;")
        layout.addWidget(self.browser_area, 1)
        
        # 初始化标题显示
        self._update_title()
    
    @property
    def status(self):
        return self._status
    
    @status.setter
    def status(self, value):
        self._status = value
        self.status_label.setText(value)
        color = "#3fb950" if "完成" in value else "#f0883e" if "运行" in value else "#f85149" if "失败" in value else "#8b949e"
        self.status_label.setStyleSheet(f"color: {color}; font-size: 10px;")
    
    @property
    def tasks(self):
        """获取任务列表"""
        return self._tasks
    
    @tasks.setter
    def tasks(self, value):
        """设置任务列表并更新显示"""
        self._tasks = value if isinstance(value, list) else []
        self._update_title()
    
    def add_task(self, task_name: str):
        """添加任务"""
        if task_name not in self._tasks:
            self._tasks.append(task_name)
            self._update_title()
    
    def remove_task(self, task_name: str):
        """移除任务（任务完成时调用）"""
        if task_name in self._tasks:
            self._tasks.remove(task_name)
            self._update_title()
    
    def clear_tasks(self):
        """清空任务列表"""
        self._tasks = []
        self._update_title()
    
    def _update_title(self):
        """更新标题显示：编号 + 任务列表"""
        # 从browser_info中获取编号
        index = getattr(self, '_index', '')
        
        # 构建显示文本：#编号 【任务1】【任务2】...
        if index:
            title_text = f"#{index}"
        else:
            title_text = ""
        
        # 添加任务列表
        if self._tasks:
            tasks_text = "".join([f"【{task}】" for task in self._tasks])
            title_text = f"{title_text} {tasks_text}".strip()
        
        self.title_label.setText(title_text)
    
    def set_index(self, index: int):
        """设置浏览器编号（如果名称中没有编号才使用）"""
        if self._index is None:
            self._index = index
            self._update_title()
    
    def _open_devtools(self):
        hwnd = self.browser_hwnd
        self.release()
        self.released.emit(self.browser_id)
        if hwnd and user32.IsWindow(hwnd):
            user32.SetForegroundWindow(hwnd)
            user32.keybd_event(0x7B, 0, 0, 0)
            user32.keybd_event(0x7B, 0, 0x0002, 0)
    
    def connect_selenium(self, driver_path: str, debugger_address: str) -> bool:
        self.driver_path = driver_path
        self.debugger_address = debugger_address
        try:
            opts = Options()
            opts.add_experimental_option("debuggerAddress", debugger_address)
            self.driver = webdriver.Chrome(service=Service(driver_path), options=opts)
            
            # 注入 CSS 隐藏滚动条（更激进的方式）
            self._inject_scrollbar_css()
            
            # 自动导出 Cookie 并保存到数据库
            self._export_and_save_cookies()
            
            # 设置页面缩放为50%（在Cookie导出后设置，确保生效）
            self._set_zoom_level(0.5)
            
            return True
        except Exception as e:
            print(f"[Selenium连接] 连接失败: {e}")
            return False
    
    def _export_and_save_cookies(self):
        """导出 Cookie 并保存到数据库"""
        if not self.driver or not self.browser_id:
            return
        
        try:
            import json
            import time
            
            # 等待页面加载完成
            time.sleep(2)
            
            # 获取当前 URL，确保在 Facebook 域名下
            current_url = self.driver.current_url
            if "facebook.com" not in current_url:
                # 如果不在 Facebook 页面，先访问 Facebook
                self.driver.get("https://www.facebook.com")
                time.sleep(2)
            
            # 获取所有 Cookie
            cookies = self.driver.get_cookies()
            
            if not cookies:
                print(f"[Cookie导出] 浏览器 {self.browser_id} 没有 Cookie")
                return
            
            # 转换为 JSON 格式
            cookie_json = json.dumps(cookies, ensure_ascii=False)
            
            # 提取 c_user（用于验证）
            c_user = None
            for cookie in cookies:
                if cookie.get("name") == "c_user":
                    c_user = cookie.get("value")
                    break
            
            # 保存到数据库
            try:
                # 导入数据库
                import sys
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                sys.path.insert(0, current_dir)
                
                from automation.scripts.database.db import Database
                db = Database()
                
                # 获取账号
                account = db.get_account_by_browser_id(self.browser_id)
                
                if account:
                    # 更新 Cookie
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE accounts 
                        SET cookie = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE browser_id = ?
                    ''', (cookie_json, self.browser_id))
                    conn.commit()
                    conn.close()
                    
                    print(f"[Cookie导出] ✓ 已保存 Cookie 到数据库")
                    print(f"  浏览器ID: {self.browser_id}")
                    print(f"  c_user: {c_user}")
                    print(f"  Cookie数量: {len(cookies)}")
                else:
                    # 账号不存在，创建新账号
                    db.add_account(
                        browser_id=self.browser_id,
                        username=c_user or "",
                        password="",
                        cookie=cookie_json
                    )
                    print(f"[Cookie导出] ✓ 已创建账号并保存 Cookie")
                    print(f"  浏览器ID: {self.browser_id}")
                    print(f"  c_user: {c_user}")
                    print(f"  Cookie数量: {len(cookies)}")
                
            except Exception as e:
                print(f"[Cookie导出] 保存到数据库失败: {e}")
                import traceback
                traceback.print_exc()
        
        except Exception as e:
            print(f"[Cookie导出] 导出失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _set_zoom_level(self, zoom: float = 0.5):
        """设置页面缩放级别
        
        Args:
            zoom: 缩放比例，0.5表示50%，1.0表示100%
        """
        if not self.driver:
            return
        
        try:
            import time
            # 等待页面稳定
            time.sleep(0.5)
            
            # 方法1: 使用Chrome DevTools Protocol设置缩放（最可靠）
            try:
                self.driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                    'width': 0,
                    'height': 0,
                    'deviceScaleFactor': 0,
                    'mobile': False,
                    'scale': zoom
                })
                print(f"[缩放] ✓ 浏览器 {self.browser_id} 已设置缩放为 {int(zoom * 100)}% (CDP方法)")
                return
            except Exception as e1:
                print(f"[缩放] CDP方法1失败: {e1}")
            
            # 方法2: 使用setPageScaleFactor
            try:
                self.driver.execute_cdp_cmd('Emulation.setPageScaleFactor', {
                    'pageScaleFactor': zoom
                })
                print(f"[缩放] ✓ 浏览器 {self.browser_id} 已设置缩放为 {int(zoom * 100)}% (PageScale方法)")
                return
            except Exception as e2:
                print(f"[缩放] CDP方法2失败: {e2}")
            
            # 方法3: 使用JavaScript CSS zoom
            try:
                zoom_percent = int(zoom * 100)
                self.driver.execute_script(f"""
                    document.body.style.zoom = '{zoom_percent}%';
                    document.documentElement.style.zoom = '{zoom_percent}%';
                """)
                print(f"[缩放] ✓ 浏览器 {self.browser_id} 已通过JS设置缩放为 {zoom_percent}%")
                return
            except Exception as e3:
                print(f"[缩放] JS方法失败: {e3}")
            
            print(f"[缩放] ⚠ 所有缩放方法都失败")
            
        except Exception as e:
            print(f"[缩放] 设置缩放时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _inject_scrollbar_css(self):
        """注入CSS隐藏滚动条"""
        if not self.driver:
            return
        try:
            # 使用 CDP (Chrome DevTools Protocol) 注入CSS，这样可以在所有页面生效
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': """
                    (function() {
                        const style = document.createElement('style');
                        style.textContent = `
                            * {
                                scrollbar-width: none !important;
                            }
                            *::-webkit-scrollbar {
                                display: none !important;
                                width: 0px !important;
                                height: 0px !important;
                            }
                            body, html {
                                overflow: overlay !important;
                                -ms-overflow-style: none !important;
                            }
                        `;
                        if (document.head) {
                            document.head.appendChild(style);
                        } else {
                            document.addEventListener('DOMContentLoaded', () => {
                                document.head.appendChild(style);
                            });
                        }
                    })();
                """
            })
            
            # 同时在当前页面注入
            self.driver.execute_script("""
                const style = document.createElement('style');
                style.textContent = `
                    * {
                        scrollbar-width: none !important;
                    }
                    *::-webkit-scrollbar {
                        display: none !important;
                        width: 0px !important;
                        height: 0px !important;
                    }
                    body, html {
                        overflow: overlay !important;
                        -ms-overflow-style: none !important;
                    }
                `;
                document.head.appendChild(style);
            """)
        except Exception as e:
            # 如果注入失败也不影响主要功能
            pass
    
    def embed_window(self, hwnd: int) -> bool:
        if not hwnd or not user32.IsWindow(hwnd):
            return False
        try:
            self.browser_hwnd = hwnd
            self.original_style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            self.original_parent = user32.GetParent(hwnd)
            
            # 先隐藏窗口，避免在修改样式时出现闪烁或边框
            user32.ShowWindow(hwnd, 0)  # SW_HIDE
            
            container_hwnd = ctypes.c_void_p(int(self.browser_area.winId())).value
            
            # 去掉所有边框、标题栏和滚动条样式
            new_style = (self.original_style & ~WS_POPUP & ~WS_CAPTION & ~WS_THICKFRAME & ~WS_BORDER & ~WS_DLGFRAME & ~WS_VSCROLL & ~WS_HSCROLL) | WS_CHILD | WS_VISIBLE
            user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)
            
            # 去掉扩展样式中的边框
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_ex_style = ex_style & ~WS_EX_CLIENTEDGE & ~WS_EX_WINDOWEDGE & ~WS_EX_STATICEDGE
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_ex_style)
            
            # 禁用DWM窗口阴影效果
            try:
                policy = ctypes.c_int(DWMNCRP_DISABLED)
                dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_NCRENDERING_POLICY, ctypes.byref(policy), ctypes.sizeof(policy))
            except:
                pass  # 如果失败也不影响主要功能
            
            user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
            user32.SetParent.restype = wintypes.HWND
            user32.SetParent(hwnd, container_hwnd)
            
            # 立即调整大小，让浏览器窗口稍微大一点，边框会被裁剪
            width = self.width() + 4  # 左右各多2像素
            height = self.browser_area.height() + 4  # 上下各多2像素
            user32.MoveWindow(hwnd, -2, -2, width, height, True)
            user32.SetWindowPos(hwnd, 0, -2, -2, width, height, SWP_FRAMECHANGED | SWP_SHOWWINDOW)
            
            # 延迟再次调整，确保生效
            QTimer.singleShot(100, self._resize)
            return True
        except:
            return False
    
    def _resize(self):
        if self.browser_hwnd and user32.IsWindow(self.browser_hwnd):
            # 让浏览器窗口比容器稍微大一点，这样边框会被裁剪掉
            width = self.width() + 4  # 左右各多2像素
            height = self.browser_area.height() + 4  # 上下各多2像素
            # 位置从(-2, -2)开始，这样边框会被容器边缘裁剪
            user32.MoveWindow(self.browser_hwnd, -2, -2, width, height, True)
    
    def release(self):
        if self.browser_hwnd and user32.IsWindow(self.browser_hwnd):
            try:
                if self.original_style:
                    user32.SetWindowLongW(self.browser_hwnd, GWL_STYLE, self.original_style)
                user32.SetParent(self.browser_hwnd, self.original_parent or 0)
                user32.SetWindowPos(self.browser_hwnd, 0, 100, 100, 1280, 800, SWP_FRAMECHANGED)
            except:
                pass
        self.browser_hwnd = None
        self.driver = None
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(50, self._resize)


class BrowserMonitorServer(QWidget):
    """浏览器监控服务器主窗口"""
    
    log_signal = pyqtSignal(str)
    add_browser_signal = pyqtSignal(str, str)
    set_status_signal = pyqtSignal(str, str)
    remove_browser_signal = pyqtSignal(str, bool)  # 新增：移除浏览器信号 (browser_id, close)
    close_all_signal = pyqtSignal()  # 新增：关闭所有浏览器信号
    
    # 任务管理信号
    set_tasks_signal = pyqtSignal(str, list)  # 设置任务列表 (browser_id, tasks)
    add_task_signal = pyqtSignal(str, str)  # 添加任务 (browser_id, task)
    remove_task_signal = pyqtSignal(str, str)  # 移除任务 (browser_id, task)
    clear_tasks_signal = pyqtSignal(str)  # 清空任务 (browser_id)
    
    def __init__(self, auth_client=None, main_window=None, parent=None):
        super().__init__(parent)
        self.auth_client = auth_client  # 保存认证客户端引用
        self.main_window = main_window  # 保存主窗口引用
        self.containers: Dict[str, BrowserContainer] = {}
        self.browser_info: Dict[str, dict] = {}
        self.cols = 2
        self.http_server = None
        self.controller = None  # 新增：保存自动化控制器实例
        
        self.log_signal.connect(self._append_log)
        self.add_browser_signal.connect(self._add_browser_slot)
        self.set_status_signal.connect(self._set_status_slot)
        self.remove_browser_signal.connect(self._remove_browser_slot)  # 新增：连接移除信号
        self.close_all_signal.connect(self._close_all_slot)  # 新增：连接关闭所有信号
        
        # 连接任务管理信号
        self.set_tasks_signal.connect(self._set_tasks_slot)
        self.add_task_signal.connect(self._add_task_slot)
        self.remove_task_signal.connect(self._remove_task_slot)
        self.clear_tasks_signal.connect(self._clear_tasks_slot)
        
        self._init_ui()
        self._start_http_server()
    
    def _init_ui(self):
        # 不设置窗口标题和几何，因为这是一个嵌入式Widget
        self.setStyleSheet("""
            QWidget { background-color: #0d1117; color: #c9d1d9; }
            QTextEdit { background-color: #161b22; border: 1px solid #30363d; font-family: Consolas; font-size: 13px; }
            QSplitter::handle { background-color: #30363d; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 浏览器区域
        browser_widget = QWidget()
        browser_layout = QVBoxLayout(browser_widget)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(2)
        scroll.setWidget(self.grid_widget)
        browser_layout.addWidget(scroll)
        
        splitter.addWidget(browser_widget)
        
        # 日志区域
        log_widget = QWidget()
        log_widget.setMaximumWidth(280)  # 减小到 280 像素
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(3, 8, 3, 5)  # 减小左右边距
        
        # 控制栏：垂直排列按钮
        control_layout = QVBoxLayout()
        control_layout.setSpacing(8)
        control_layout.setContentsMargins(0, 0, 0, 0)
        
        # 统一的按钮样式
        button_style = """
            QPushButton {
                padding: 6px;
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
            QPushButton:disabled {
                background-color: #161b22;
                color: #6e7681;
                border-color: #21262d;
            }
        """
        
        # 1. 开始运行按钮
        self.start_btn = QPushButton("开始运行")
        self.start_btn.setMinimumHeight(32)
        self.start_btn.setStyleSheet(button_style)
        self.start_btn.clicked.connect(self._start_automation)
        control_layout.addWidget(self.start_btn)
        
        # 2. 测试发帖按钮（新增）
        self.test_post_btn = QPushButton("测试发帖")
        self.test_post_btn.setMinimumHeight(32)
        self.test_post_btn.setToolTip("立即触发一次发帖测试\n\n⚠️ 需要先点击「开始运行」")
        self.test_post_btn.setStyleSheet("""
            QPushButton {
                padding: 6px;
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: transparent;
                color: #f0ad4e;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3a2a1a;
                border: 1px solid #f0ad4e;
            }
            QPushButton:pressed {
                background-color: #2a1a0a;
                border: 1px solid #f0ad4e;
            }
            QPushButton:disabled {
                background-color: #161b22;
                color: #6e7681;
                border-color: #21262d;
            }
        """)
        self.test_post_btn.clicked.connect(self._test_post)
        self.test_post_btn.setEnabled(False)  # 初始禁用，启动后才能用
        control_layout.addWidget(self.test_post_btn)
        
        # 3. 清空日志按钮
        clear_btn = QPushButton("清空日志")
        clear_btn.setMinimumHeight(32)
        clear_btn.setStyleSheet(button_style)
        clear_btn.clicked.connect(self._clear_log)
        control_layout.addWidget(clear_btn)
        
        # 4. 运行设置按钮
        settings_btn = QPushButton("运行设置")
        settings_btn.setMinimumHeight(32)
        settings_btn.setToolTip("自动化设置")
        settings_btn.setStyleSheet(button_style)
        settings_btn.clicked.connect(self._show_settings_dialog)
        control_layout.addWidget(settings_btn)
        
        log_layout.addLayout(control_layout)
        log_layout.addSpacing(8)  # 控制栏和日志文本之间的间距
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        # 移除最大高度限制，让日志区域自动填充剩余空间
        log_layout.addWidget(self.log_text)
        
        splitter.addWidget(log_widget)
        # 调整分割器比例
        splitter.setSizes([1720, 280])
        
        layout.addWidget(splitter, 1)
    
    def _load_config(self) -> dict:
        """读取运行配置"""
        try:
            if os.path.exists(运行配置路径):
                with open(运行配置路径, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {"线程数": 1, "手动打码": False}
    
    def _load_text_config(self, filename: str) -> str:
        """读取文本配置文件"""
        try:
            filepath = os.path.join(脚本配置目录, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            self.log(f"读取配置文件失败 {filename}: {e}")
        return ""
    
    def _save_text_config(self, filename: str, content: str):
        """保存文本配置文件"""
        try:
            os.makedirs(脚本配置目录, exist_ok=True)
            filepath = os.path.join(脚本配置目录, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            self.log(f"保存配置文件失败 {filename}: {e}")
    
    def _save_config(self, config: dict):
        """保存运行配置"""
        try:
            # 保留说明字段
            existing = self._load_config()
            if "说明" in existing:
                config["说明"] = existing["说明"]
            
            os.makedirs(os.path.dirname(运行配置路径), exist_ok=True)
            with open(运行配置路径, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.log(f"保存配置失败: {e}")
    
    def _load_join_group_config(self) -> dict:
        """读取加入小组配置"""
        try:
            config_path = os.path.join(脚本配置目录, "加入小组配置.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.log(f"读取加入小组配置失败: {e}")
        
        # 返回默认配置
        return {
            "最小成员数": 100,
            "启用成员数过滤": True,
            "启用阶段配额": True,
            "启用AI验证问题": True
        }
    
    def _save_join_group_config(self, config: dict):
        """保存加入小组配置"""
        try:
            os.makedirs(脚本配置目录, exist_ok=True)
            config_path = os.path.join(脚本配置目录, "加入小组配置.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.log("✓ 小组配置已保存")
        except Exception as e:
            self.log(f"保存加入小组配置失败: {e}")
    
    def _show_settings_dialog(self):
        """显示设置对话框"""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, 
                                     QCheckBox, QPushButton, QDialogButtonBox, QTextEdit,
                                     QGroupBox, QScrollArea, QWidget, QLineEdit)
        from PyQt5.QtCore import Qt
        
        dialog = QDialog(self)
        dialog.setWindowTitle("自动化设置")
        # 设置为全屏显示
        dialog.showMaximized()
        # 设置无边框窗口，使用自定义标题栏样式
        dialog.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
                color: #c9d1d9;
            }
            QLabel {
                color: #c9d1d9;
                font-size: 13px;
            }
            QSpinBox, QLineEdit {
                background: #21262d;
                border: 1px solid #30363d;
                padding: 6px;
                border-radius: 6px;
                color: #c9d1d9;
                font-size: 13px;
            }
            QTextEdit {
                background: #21262d;
                border: 1px solid #30363d;
                padding: 8px;
                border-radius: 6px;
                color: #c9d1d9;
                font-size: 13px;
            }
            QCheckBox {
                color: #c9d1d9;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #30363d;
                border-radius: 4px;
                background: #21262d;
            }
            QCheckBox::indicator:checked {
                background: #0842b0;
                border-color: #0842b0;
            }
            QPushButton {
                padding: 6px 16px;
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: transparent;
                color: #ffffff;
                font-size: 13px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #21262d;
            }
            QPushButton:pressed {
                background-color: #161b22;
            }
            QGroupBox {
                border: 1px solid #30363d;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                font-size: 13px;
                color: #58a6ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        # 创建自定义标题栏
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
        
        # 标题文字
        title_label = QLabel("自动化设置")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #c9d1d9; background: transparent; border: none;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(40, 30)
        close_btn.setStyleSheet("""
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
        close_btn.clicked.connect(dialog.reject)
        title_layout.addWidget(close_btn)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # ========== 基础设置组 ==========
        basic_group = QGroupBox("基础设置")
        basic_layout = QVBoxLayout()
        
        # 窗口数量和手动打码设置（放在同一行）
        settings_layout = QHBoxLayout()
        
        # 允许使用的浏览器数量（文字标签形式）
        window_label = QLabel("允许使用的浏览器数量:")
        settings_layout.addWidget(window_label)
        
        # 从认证信息获取浏览器数量
        max_workers = 1  # 默认值
        if self.auth_client and hasattr(self.auth_client, 'user_info') and self.auth_client.user_info:
            max_workers = self.auth_client.user_info.get('max_simulators', 1)
        
        # 显示浏览器数量（文字标签）
        window_value = QLabel(f"{max_workers}")
        window_value.setStyleSheet("font-weight: bold; font-size: 14px; color: #58a6ff;")
        settings_layout.addWidget(window_value)
        
        settings_layout.addSpacing(30)
        
        # 手动打码设置
        captcha_cb = QCheckBox("启用手动打码")
        captcha_cb.setChecked(self._load_config().get("手动打码", False))
        settings_layout.addWidget(captcha_cb)
        
        settings_layout.addSpacing(30)
        
        # 数据管理按钮
        db_manager_btn = QPushButton("📊 数据管理")
        db_manager_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: #0969da;
                color: #ffffff;
                font-size: 13px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #1f6feb;
            }
            QPushButton:pressed {
                background-color: #0842b0;
            }
        """)
        db_manager_btn.clicked.connect(self._show_database_manager)
        settings_layout.addWidget(db_manager_btn)
        
        settings_layout.addStretch()
        basic_layout.addLayout(settings_layout)
        
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)
        
        # ========== 内容配置组 ==========
        content_group = QGroupBox("内容配置")
        content_layout = QVBoxLayout()
        
        # 统一的输入框样式
        text_edit_style = """
            QTextEdit {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }
            QTextEdit:focus {
                border: 1px solid #58a6ff;
            }
        """
        
        line_edit_style = """
            QLineEdit {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #58a6ff;
            }
        """
        
        # 产品类目
        content_layout.addWidget(QLabel("产品类目（每行一个）:"))
        product_edit = QTextEdit()
        product_edit.setPlaceholderText("例如：\n汽车\n手表\n摩托车")
        product_edit.setMaximumHeight(80)
        product_edit.setStyleSheet(text_edit_style)
        product_edit.setText(self._load_text_config("产品类目.txt"))
        content_layout.addWidget(product_edit)
        
        # 主页名称
        content_layout.addWidget(QLabel("主页名称:"))
        page_name_edit = QLineEdit()
        page_name_edit.setPlaceholderText("例如：Taizhou Baoge Machinery")
        page_name_edit.setStyleSheet(line_edit_style)
        page_name_edit.setText(self._load_text_config("主页名称.txt").strip())
        content_layout.addWidget(page_name_edit)
        
        # 公共主页链接
        content_layout.addWidget(QLabel("公共主页链接:"))
        page_link_edit = QLineEdit()
        page_link_edit.setPlaceholderText("例如：https://m.facebook.com/profile.php?id=...")
        page_link_edit.setStyleSheet(line_edit_style)
        page_link_edit.setText(self._load_text_config("公共主页链接").strip())
        content_layout.addWidget(page_link_edit)
        
        content_group.setLayout(content_layout)
        layout.addWidget(content_group)
        
        # ========== 关键词配置组 ==========
        keyword_group = QGroupBox("关键词配置")
        keyword_layout = QVBoxLayout()
        
        # 搜索关键词
        keyword_layout.addWidget(QLabel("搜索关键词（每行一个）:"))
        search_edit = QTextEdit()
        search_edit.setPlaceholderText("例如：\n汽车\n摩托车")
        search_edit.setMaximumHeight(80)
        search_edit.setStyleSheet(text_edit_style)
        search_edit.setText(self._load_text_config("搜索关键词.txt"))
        keyword_layout.addWidget(search_edit)
        
        # 好友关键词
        keyword_layout.addWidget(QLabel("好友关键词（每行一个）:"))
        friend_edit = QTextEdit()
        friend_edit.setPlaceholderText("例如：\nmotorcycle enthusiast\nbike lover")
        friend_edit.setMaximumHeight(80)
        friend_edit.setStyleSheet(text_edit_style)
        friend_edit.setText(self._load_text_config("好友关键词.txt"))
        keyword_layout.addWidget(friend_edit)
        
        # 小组关键词
        keyword_layout.addWidget(QLabel("小组关键词（每行一个）:"))
        group_edit = QTextEdit()
        group_edit.setPlaceholderText("例如：\n汽车\n摩托车")
        group_edit.setMaximumHeight(80)
        group_edit.setStyleSheet(text_edit_style)
        group_edit.setText(self._load_text_config("小组关键词.txt"))
        keyword_layout.addWidget(group_edit)
        
        keyword_group.setLayout(keyword_layout)
        layout.addWidget(keyword_group)
        
        # ========== 小组配置组 ==========
        group_config_group = QGroupBox("小组配置")
        group_config_layout = QVBoxLayout()
        
        # 读取加入小组配置
        join_group_config = self._load_join_group_config()
        
        # 最小成员数
        min_members_layout = QHBoxLayout()
        min_members_layout.addWidget(QLabel("最小成员数:"))
        min_members_spin = QSpinBox()
        min_members_spin.setRange(0, 1000000)
        min_members_spin.setValue(join_group_config.get("最小成员数", 100))
        min_members_spin.setStyleSheet("""
            QSpinBox {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px;
                font-size: 12px;
                min-width: 120px;
            }
            QSpinBox:focus {
                border: 1px solid #58a6ff;
            }
        """)
        min_members_layout.addWidget(min_members_spin)
        min_members_layout.addWidget(QLabel("（过滤成员数少于此值的小组）"))
        min_members_layout.addStretch()
        group_config_layout.addLayout(min_members_layout)
        
        # 启用成员数过滤
        enable_member_filter_cb = QCheckBox("启用成员数过滤")
        enable_member_filter_cb.setChecked(join_group_config.get("启用成员数过滤", True))
        group_config_layout.addWidget(enable_member_filter_cb)
        
        # 启用阶段配额
        enable_stage_quota_cb = QCheckBox("启用阶段配额（根据账号运行天数控制加入配额）")
        enable_stage_quota_cb.setChecked(join_group_config.get("启用阶段配额", True))
        group_config_layout.addWidget(enable_stage_quota_cb)
        
        # 启用AI验证问题
        enable_ai_questions_cb = QCheckBox("启用AI验证问题（自动回答小组验证问题）")
        enable_ai_questions_cb.setChecked(join_group_config.get("启用AI验证问题", True))
        group_config_layout.addWidget(enable_ai_questions_cb)
        
        group_config_group.setLayout(group_config_layout)
        layout.addWidget(group_config_group)
        
        # ========== AI配置组 ==========
        ai_group = QGroupBox("AI配置")
        ai_layout = QVBoxLayout()
        
        # Qwen2 API Key
        ai_layout.addWidget(QLabel("API Key（用于AI评论生成）:"))
        qwen_key_edit = QLineEdit()
        qwen_key_edit.setPlaceholderText("例如：sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        qwen_key_edit.setEchoMode(QLineEdit.Password)  # 密码模式显示
        qwen_key_edit.setStyleSheet(line_edit_style)
        qwen_key_edit.setText(self._load_text_config("qwen_api_key.txt").strip())
        ai_layout.addWidget(qwen_key_edit)
        
        # 格式说明
        ai_info_label = QLabel("💡 此API Key用于AI生成评论、视频文案等功能")
        ai_info_label.setStyleSheet("color: #8b949e; font-size: 11px; padding: 5px 0;")
        ai_layout.addWidget(ai_info_label)
        
        # 添加分隔线
        ai_layout.addSpacing(10)
        
        # 加入小组提示词
        ai_layout.addWidget(QLabel("加入小组提示词（AI判断小组是否符合产品类目）:"))
        join_group_prompt_edit = QTextEdit()
        join_group_prompt_edit.setMaximumHeight(120)
        join_group_prompt_edit.setStyleSheet(text_edit_style)
        # 读取配置文件，如果为空则使用默认提示词
        join_group_prompt_content = self._load_text_config("加入小组提示词.txt")
        if not join_group_prompt_content.strip():
            # 配置文件为空，使用默认提示词
            join_group_prompt_content = """你是一名专业的Facebook小组评估专家。请判断以下小组是否与"{产品类目}"相关。

小组信息：
名称：{小组名称}
简介：{小组简介}

判断标准：
1. 小组主题是否与"{产品类目}"直接相关
2. 小组成员是否可能对"{产品类目}"感兴趣
3. 小组是否适合推广"{产品类目}"

输出格式：
- 如果相关且适合：输出【YES】
- 如果不相关或不适合：输出【NO|原因】

示例：
- 【YES】
- 【NO|小组主题是宠物，与产品无关】
- 【NO|小组禁止商业推广】

请严格按照格式输出，不要添加其他内容。"""
        join_group_prompt_edit.setText(join_group_prompt_content)
        ai_layout.addWidget(join_group_prompt_edit)
        
        # 提示词说明
        join_group_info = QLabel("💡 支持占位符：{产品类目}、{小组名称}、{小组简介}。输出格式：【YES】或【NO|原因】")
        join_group_info.setStyleSheet("color: #8b949e; font-size: 11px; padding: 5px 0;")
        ai_layout.addWidget(join_group_info)
        
        # 添加分隔线
        ai_layout.addSpacing(10)
        
        # 加好友提示词
        ai_layout.addWidget(QLabel("加好友提示词（AI判断用户是否可能对产品感兴趣）:"))
        add_friend_prompt_edit = QTextEdit()
        add_friend_prompt_edit.setMaximumHeight(120)
        add_friend_prompt_edit.setStyleSheet(text_edit_style)
        # 读取配置文件，如果为空则使用默认提示词
        add_friend_prompt_content = self._load_text_config("加好友提示词.txt")
        if not add_friend_prompt_content.strip():
            # 配置文件为空，使用默认提示词
            add_friend_prompt_content = """你是一名专业的Facebook用户评估专家。请判断以下用户是否可能对"{产品类目}"感兴趣。

用户信息：
姓名：{用户名称}
简介：{用户简介}
最近帖子：{最近帖子}

判断标准：
1. 用户的兴趣爱好是否与"{产品类目}"相关
2. 用户是否可能成为潜在客户
3. 用户是否活跃且真实（非机器人账号）

输出格式：
- 如果适合添加：输出【YES】
- 如果不适合：输出【NO|原因】

示例：
- 【YES】
- 【NO|用户兴趣与产品无关】
- 【NO|疑似机器人账号】

请严格按照格式输出，不要添加其他内容。"""
        add_friend_prompt_edit.setText(add_friend_prompt_content)
        ai_layout.addWidget(add_friend_prompt_edit)
        
        # 提示词说明
        add_friend_info = QLabel("💡 支持占位符：{产品类目}、{用户名称}、{用户简介}、{最近帖子}。输出格式：【YES】或【NO|原因】")
        add_friend_info.setStyleSheet("color: #8b949e; font-size: 11px; padding: 5px 0;")
        ai_layout.addWidget(add_friend_info)
        
        ai_group.setLayout(ai_layout)
        layout.addWidget(ai_group)
        
        # ========== 账号配置组 ==========
        account_group = QGroupBox("账号配置（登录用）")
        account_layout = QVBoxLayout()
        
        # 账号列表
        account_layout.addWidget(QLabel("账号列表（每行一个，格式：c_user----密码----2FA码----邮箱----cookie----token）:"))
        account_edit = QTextEdit()
        account_edit.setPlaceholderText("例如：\n123456789----mypassword----ABCD1234----email@example.com----")
        account_edit.setMaximumHeight(100)
        account_edit.setStyleSheet(text_edit_style)
        account_edit.setText(self._load_text_config("账号.txt"))
        account_layout.addWidget(account_edit)
        
        # 格式说明
        format_label = QLabel("📝 格式说明：c_user----密码----2FA码----邮箱----cookie----token（用 ---- 分隔，可省略后面的字段）")
        format_label.setStyleSheet("color: #8b949e; font-size: 11px; padding: 5px 0;")
        account_layout.addWidget(format_label)
        
        account_group.setLayout(account_layout)
        layout.addWidget(account_group)
        
        # ========== 路径配置组 ==========
        path_group = QGroupBox("路径配置")
        path_layout = QVBoxLayout()
        
        # 获取默认路径
        def get_default_avatar_path():
            """获取默认头像路径"""
            try:
                from automation.scripts.tasks.设置头像 import 脚本配置目录
                return os.path.join(脚本配置目录, "头像图片")
            except:
                # 备用方案
                possible_dirs = [
                    os.path.join(os.path.dirname(sys.executable), "_internal", "automation", "scripts", "脚本配置", "头像图片"),
                    os.path.join(os.path.dirname(sys.executable), "automation", "scripts", "脚本配置", "头像图片"),
                    os.path.join(os.path.dirname(__file__), "automation", "scripts", "脚本配置", "头像图片"),
                ]
                for dir_path in possible_dirs:
                    if os.path.exists(dir_path):
                        return dir_path
                return os.path.join(os.path.dirname(__file__), "automation", "scripts", "脚本配置", "头像图片")
        
        def get_default_comment_image_path():
            """获取默认评论图片路径"""
            try:
                from automation.scripts.tasks.设置头像 import 脚本配置目录
                return os.path.join(脚本配置目录, "评论图片")
            except:
                # 备用方案
                possible_dirs = [
                    os.path.join(os.path.dirname(sys.executable), "_internal", "automation", "scripts", "脚本配置", "评论图片"),
                    os.path.join(os.path.dirname(sys.executable), "automation", "scripts", "脚本配置", "评论图片"),
                    os.path.join(os.path.dirname(__file__), "automation", "scripts", "脚本配置", "评论图片"),
                ]
                for dir_path in possible_dirs:
                    if os.path.exists(dir_path):
                        return dir_path
                return os.path.join(os.path.dirname(__file__), "automation", "scripts", "脚本配置", "评论图片")
        
        # 头像图片路径
        path_layout.addWidget(QLabel("头像图片路径:"))
        avatar_path_layout = QHBoxLayout()
        avatar_path_edit = QLineEdit()
        avatar_path_edit.setPlaceholderText("头像图片存放目录")
        avatar_path_edit.setStyleSheet(line_edit_style)
        # 读取配置，如果为空则使用默认路径
        saved_avatar_path = self._load_text_config("头像路径.txt").strip()
        avatar_path_edit.setText(saved_avatar_path if saved_avatar_path else get_default_avatar_path())
        avatar_path_layout.addWidget(avatar_path_edit)
        
        # 浏览按钮
        avatar_browse_btn = QPushButton("📁 浏览")
        avatar_browse_btn.setFixedWidth(80)
        avatar_browse_btn.clicked.connect(lambda: self._browse_folder(avatar_path_edit, "选择头像目录"))
        avatar_path_layout.addWidget(avatar_browse_btn)
        
        # 打开目录按钮
        avatar_open_btn = QPushButton("📂 打开")
        avatar_open_btn.setFixedWidth(80)
        avatar_open_btn.clicked.connect(lambda: self._open_folder(avatar_path_edit.text()))
        avatar_path_layout.addWidget(avatar_open_btn)
        
        path_layout.addLayout(avatar_path_layout)
        
        path_layout.addSpacing(10)
        
        # 评论图片路径
        path_layout.addWidget(QLabel("评论图片路径:"))
        comment_path_layout = QHBoxLayout()
        comment_path_edit = QLineEdit()
        comment_path_edit.setPlaceholderText("评论图片存放目录")
        comment_path_edit.setStyleSheet(line_edit_style)
        # 读取配置，如果为空则使用默认路径
        saved_comment_path = self._load_text_config("评论图片路径.txt").strip()
        comment_path_edit.setText(saved_comment_path if saved_comment_path else get_default_comment_image_path())
        comment_path_layout.addWidget(comment_path_edit)
        
        # 浏览按钮
        comment_browse_btn = QPushButton("📁 浏览")
        comment_browse_btn.setFixedWidth(80)
        comment_browse_btn.clicked.connect(lambda: self._browse_folder(comment_path_edit, "选择评论图片目录"))
        comment_path_layout.addWidget(comment_browse_btn)
        
        # 打开目录按钮
        comment_open_btn = QPushButton("📂 打开")
        comment_open_btn.setFixedWidth(80)
        comment_open_btn.clicked.connect(lambda: self._open_folder(comment_path_edit.text()))
        comment_path_layout.addWidget(comment_open_btn)
        
        path_layout.addLayout(comment_path_layout)
        
        path_group.setLayout(path_layout)
        layout.addWidget(path_group)
        
        # 说明文字
        info_label = QLabel("💡 提示：修改设置后点击确定保存，配置会立即生效")
        info_label.setStyleSheet("color: #8b949e; font-size: 11px; padding: 10px 0;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        scroll.setWidget(scroll_widget)
        
        # 主布局
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 添加自定义标题栏
        main_layout.addWidget(title_bar)
        
        # 添加滚动区域
        main_layout.addWidget(scroll)
        
        # 底部按钮区域
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(10, 10, 10, 10)
        
        # 左侧：账号阶段管理按钮（低调样式，不显眼）
        stage_manager_btn = QPushButton("账号阶段管理")
        stage_manager_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                background-color: transparent;
                color: #484f58;
                font-size: 11px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #21262d;
                color: #8b949e;
            }
            QPushButton:pressed {
                background-color: #161b22;
            }
        """)
        
        # 测试：先打印日志确认按钮点击
        def test_button_click():
            print("=" * 60)
            print("按钮被点击了！")
            print("=" * 60)
            self.log("🔘 账号阶段管理按钮被点击")
            self._show_account_stage_manager()
        
        stage_manager_btn.clicked.connect(test_button_click)
        bottom_layout.addWidget(stage_manager_btn)
        
        bottom_layout.addStretch()
        
        # 右侧：OK和Cancel按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(lambda: self._save_settings_from_dialog(
            max_workers,  # 使用从认证信息获取的浏览器数量
            captcha_cb.isChecked(),
            product_edit.toPlainText(),
            page_name_edit.text(),
            page_link_edit.text(),
            search_edit.toPlainText(),
            friend_edit.toPlainText(),
            group_edit.toPlainText(),
            qwen_key_edit.text(),  # 添加Qwen API Key参数
            join_group_prompt_edit.toPlainText(),  # 添加加入小组提示词
            add_friend_prompt_edit.toPlainText(),  # 添加加好友提示词
            account_edit.toPlainText(),
            avatar_path_edit.text(),  # 添加头像路径
            comment_path_edit.text(),  # 添加评论图片路径
            min_members_spin.value(),  # 添加最小成员数
            enable_member_filter_cb.isChecked(),  # 添加启用成员数过滤
            enable_stage_quota_cb.isChecked(),  # 添加启用阶段配额
            enable_ai_questions_cb.isChecked(),  # 添加启用AI验证问题
            dialog
        ))
        button_box.rejected.connect(dialog.reject)
        bottom_layout.addWidget(button_box)
        
        main_layout.addLayout(bottom_layout)
        
        dialog.exec_()
    
    def _show_database_manager(self):
        """显示数据库管理对话框"""
        try:
            from database_manager_dialog import DatabaseManagerDialog
            
            dialog = DatabaseManagerDialog(self)
            dialog.exec_()
            
        except Exception as e:
            self.log(f"打开数据库管理失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_account_stage_manager(self):
        """显示账号阶段管理对话框"""
        self.log("开始打开账号阶段管理器...")
        
        try:
            # 动态导入，支持打包后的路径查找
            import sys
            import os
            
            self.log("准备导入模块...")
            
            # 尝试多个可能的路径
            possible_paths = [
                # 开发环境：当前目录
                os.path.dirname(os.path.abspath(__file__)),
                # 打包后：exe所在目录
                os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else None,
                # 打包后：_internal目录
                os.path.join(os.path.dirname(sys.executable), '_internal') if getattr(sys, 'frozen', False) else None,
            ]
            
            # 添加路径到sys.path
            for path in possible_paths:
                if path and path not in sys.path:
                    sys.path.insert(0, path)
                    self.log(f"添加路径: {path}")
            
            # 导入账号阶段管理器
            self.log("正在导入 AccountStageManager...")
            from account_stage_manager import AccountStageManager
            self.log("导入成功")
            
            # 创建新窗口并保存引用（避免被垃圾回收）
            self.log("正在创建对话框...")
            # 不传递 parent，创建独立窗口
            self._stage_manager_dialog = AccountStageManager(parent=None)
            self.log("对话框创建成功")
            
            # 非模态显示（不阻塞主线程）
            self.log("正在显示对话框...")
            self._stage_manager_dialog.show()
            
            # 强制激活窗口，确保在最前面
            self._stage_manager_dialog.raise_()
            self._stage_manager_dialog.activateWindow()
            
            # Windows 特定：强制窗口到前台
            try:
                import ctypes
                hwnd = int(self._stage_manager_dialog.winId())
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                self.log("已使用 Windows API 激活窗口")
            except:
                pass
            
            self.log("✅ 账号阶段管理器已打开")
            
        except ImportError as e:
            self.log(f"❌ 无法导入账号阶段管理器: {e}")
            self.log("请确保 account_stage_manager.py 文件存在")
            import traceback
            self.log(traceback.format_exc())
        except Exception as e:
            self.log(f"❌ 打开账号阶段管理失败: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    def _browse_folder(self, line_edit, title="选择文件夹"):
        """浏览并选择文件夹"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            
            # 获取当前路径作为起始目录
            current_path = line_edit.text()
            if not current_path or not os.path.exists(current_path):
                current_path = os.path.dirname(__file__)
            
            # 打开文件夹选择对话框
            folder = QFileDialog.getExistingDirectory(
                self,
                title,
                current_path,
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            
            if folder:
                line_edit.setText(folder)
                self.log(f"已选择文件夹: {folder}")
        except Exception as e:
            self.log(f"选择文件夹失败: {e}")
    
    def _open_folder(self, folder_path):
        """在文件管理器中打开文件夹"""
        try:
            import subprocess
            import platform
            
            if not folder_path or not os.path.exists(folder_path):
                self.log(f"⚠️ 文件夹不存在: {folder_path}")
                return
            
            system = platform.system()
            if system == "Windows":
                os.startfile(folder_path)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", folder_path])
            else:  # Linux
                subprocess.run(["xdg-open", folder_path])
            
            self.log(f"已打开文件夹: {folder_path}")
        except Exception as e:
            self.log(f"打开文件夹失败: {e}")
    
    def _save_settings_from_dialog(self, thread_count: int, manual_captcha: bool, 
                                   product_categories: str, page_name: str, page_link: str,
                                   search_keywords: str, friend_keywords: str, group_keywords: str,
                                   qwen_api_key: str,  # 添加Qwen API Key参数
                                   join_group_prompt: str,  # 添加加入小组提示词
                                   add_friend_prompt: str,  # 添加加好友提示词
                                   accounts: str,
                                   avatar_path: str,  # 添加头像路径
                                   comment_image_path: str,  # 添加评论图片路径
                                   min_members: int,  # 添加最小成员数
                                   enable_member_filter: bool,  # 添加启用成员数过滤
                                   enable_stage_quota: bool,  # 添加启用阶段配额
                                   enable_ai_questions: bool,  # 添加启用AI验证问题
                                   dialog):
        """从对话框保存设置"""
        # 保存运行配置
        config = self._load_config()
        config["线程数"] = thread_count
        config["手动打码"] = manual_captcha
        self._save_config(config)
        
        # 保存文本配置
        self._save_text_config("产品类目.txt", product_categories)
        self._save_text_config("主页名称.txt", page_name)
        self._save_text_config("公共主页链接", page_link)
        self._save_text_config("搜索关键词.txt", search_keywords)
        self._save_text_config("好友关键词.txt", friend_keywords)
        self._save_text_config("小组关键词.txt", group_keywords)
        self._save_text_config("qwen_api_key.txt", qwen_api_key)  # 保存Qwen API Key
        self._save_text_config("加入小组提示词.txt", join_group_prompt)  # 保存加入小组提示词
        self._save_text_config("加好友提示词.txt", add_friend_prompt)  # 保存加好友提示词
        self._save_text_config("账号.txt", accounts)
        
        # 保存小组配置
        join_group_config = {
            "最小成员数": min_members,
            "启用成员数过滤": enable_member_filter,
            "启用阶段配额": enable_stage_quota,
            "启用AI验证问题": enable_ai_questions
        }
        self._save_join_group_config(join_group_config)
        self._save_text_config("头像路径.txt", avatar_path)  # 保存头像路径
        self._save_text_config("评论图片路径.txt", comment_image_path)  # 保存评论图片路径
        
        # 统计账号数量
        account_count = len([line for line in accounts.strip().split('\n') if line.strip() and not line.strip().startswith('#')])
        
        self.log("=" * 50)
        self.log("✅ 设置已保存")
        self.log(f"📊 允许使用的浏览器数量: {thread_count} (由管理员授权)")
        self.log(f"🔐 手动打码: {'开启' if manual_captcha else '关闭'}")
        self.log(f"📦 产品类目: {len(product_categories.strip().split(chr(10)))} 个")
        self.log(f"📄 主页名称: {page_name if page_name else '(未设置)'}")
        self.log(f"🔗 主页链接: {page_link if page_link else '(未设置)'}")
        self.log(f"🔍 搜索关键词: {len(search_keywords.strip().split(chr(10)))} 个")
        self.log(f"👥 好友关键词: {len(friend_keywords.strip().split(chr(10)))} 个")
        self.log(f"👪 小组关键词: {len(group_keywords.strip().split(chr(10)))} 个")
        self.log(f"🤖 Qwen API Key: {'已设置' if qwen_api_key else '(未设置)'}")
        self.log(f"🤖 加入小组提示词: {'已设置' if join_group_prompt.strip() else '(使用默认)'}")
        self.log(f"🤖 加好友提示词: {'已设置' if add_friend_prompt.strip() else '(使用默认)'}")
        self.log(f"🔑 登录账号: {account_count} 个")
        self.log(f"🖼️ 头像路径: {avatar_path if avatar_path else '(使用默认)'}")
        self.log(f"📷 评论图片路径: {comment_image_path if comment_image_path else '(使用默认)'}")
        self.log("=" * 50)
        
        dialog.accept()
    
    def _on_thread_changed(self, value: int):
        """保存线程数配置"""
        config = self._load_config()
        config["线程数"] = value
        self._save_config(config)
        self.log(f"线程数已设置为: {value}")
    
    def _on_manual_captcha_changed(self, state: int):
        """保存手动打码配置"""
        config = self._load_config()
        config["手动打码"] = (state == Qt.Checked)
        self._save_config(config)
        status_text = "开启" if state == Qt.Checked else "关闭"
        self.log(f"手动打码已{status_text}")
    
    def _start_automation(self):
        """启动自动化脚本（使用 bootstrap 加载）"""
        # 禁用按钮，防止重复点击
        self.start_btn.setEnabled(False)
        self.start_btn.setText("运行中...")
        
        self.log("=" * 50)
        self.log("🚀 启动自动化脚本...")
        self.log("=" * 50)
        
        try:
            # 使用 bootstrap 加载 main.py（避免重新初始化导致认证弹窗）
            import sys
            import os
            
            # 添加 automation 目录到路径
            automation_dir = os.path.join(os.path.dirname(__file__), "automation")
            if automation_dir not in sys.path:
                sys.path.insert(0, automation_dir)
            
            self.log(f"✓ automation 目录: {automation_dir}")
            
            # 导入 bootstrap
            try:
                from automation.bootstrap import AutomationBootstrap
                self.log("✓ 成功导入 AutomationBootstrap")
            except ImportError as e:
                # 打包后的路径
                self.log(f"⚠ 从 automation.bootstrap 导入失败: {e}")
                sys.path.insert(0, os.path.dirname(__file__))
                from bootstrap import AutomationBootstrap
                self.log("✓ 从打包路径导入 AutomationBootstrap")
            
            self.log("✓ 正在加载自动化脚本...")
            
            # 创建 bootstrap 实例（传递日志回调）
            bootstrap = AutomationBootstrap(log_callback=self.log)
            
            # 输出脚本目录信息
            self.log(f"✓ 脚本目录: {bootstrap.scripts_dir}")
            
            # 检查 main.py 是否存在
            main_py = os.path.join(bootstrap.scripts_dir, "main.py")
            main_pyc = os.path.join(bootstrap.scripts_dir, "main.pyc")
            if os.path.exists(main_py):
                self.log(f"✓ 找到 main.py: {main_py}")
            elif os.path.exists(main_pyc):
                self.log(f"✓ 找到 main.pyc: {main_pyc}")
            else:
                self.log(f"❌ 未找到 main.py 或 main.pyc")
                self.log(f"   脚本目录: {bootstrap.scripts_dir}")
                self.start_btn.setEnabled(True)
                self.start_btn.setText("开始运行")
                return
            
            # 加载 main 模块
            main_module = bootstrap.load_main()
            
            if not main_module:
                self.log("❌ 加载 main.py 失败")
                self.start_btn.setEnabled(True)
                self.start_btn.setText("开始运行")
                return
            
            self.log("✓ 自动化脚本已加载")
            
            # 获取控制器实例
            controller = bootstrap.get_controller()
            if not controller:
                self.log("❌ 获取控制器实例失败")
                self.start_btn.setEnabled(True)
                self.start_btn.setText("开始运行")
                return
            
            # 保存控制器实例（用于测试按钮）
            self.controller = controller
            
            # 设置认证客户端（用于账号数量检查）
            if self.auth_client:
                controller.set_auth_client(self.auth_client)
                self.log("✓ 已设置认证客户端")
            
            # 设置主窗口引用到发帖管理器
            if hasattr(controller, '发帖管理器') and controller.发帖管理器 and self.main_window:
                controller.发帖管理器.main_window = self.main_window
                self.log("✓ 已设置主窗口引用到发帖管理器")
            
            # 启用测试发帖按钮（使用 QMetaObject 确保在 UI 线程中执行）
            QMetaObject.invokeMethod(
                self.test_post_btn,
                "setEnabled",
                Qt.QueuedConnection,
                Q_ARG(bool, True)
            )
            self.log("✓ 测试发帖按钮已启用（可以点击测试了）")
            
            # 在后台线程中运行
            import threading
            
            def run_automation():
                try:
                    self.log("▶ 正在启动自动化任务...")
                    
                    # 调用 main() 函数
                    if hasattr(main_module, 'main'):
                        main_module.main()
                    else:
                        self.log("❌ main.py 中没有 main() 函数")
                    
                    self.log("✅ 自动化任务执行完成")
                    
                except Exception as e:
                    self.log(f"❌ 执行出错: {e}")
                    import traceback
                    self.log(traceback.format_exc())
                
                finally:
                    # 恢复按钮状态
                    self.start_btn.setEnabled(True)
                    self.start_btn.setText("开始运行")
            
            # 启动后台线程
            thread = threading.Thread(target=run_automation, daemon=True)
            thread.start()
            
            self.log("✓ 自动化脚本已在后台启动")
            
        except Exception as e:
            self.log(f"❌ 启动失败: {e}")
            import traceback
            self.log(traceback.format_exc())
            
            # 恢复按钮状态
            self.start_btn.setEnabled(True)
            self.start_btn.setText("开始运行")
    
    def _test_post(self):
        """测试发帖功能（立即触发一次发帖）"""
        if not self.controller:
            self.log("❌ 控制器未初始化，请先点击「开始运行」")
            return
        
        if not hasattr(self.controller, '发帖管理器') or not self.controller.发帖管理器:
            self.log("❌ 自动发帖管理器未初始化")
            return
        
        self.log("")
        self.log("=" * 50)
        self.log("🧪 开始测试发帖...")
        self.log("=" * 50)
        self.log("✓ 测试发帖已触发")
        self.log("   - 正在后台执行发帖...")
        self.log("   - 发帖成功后会自动触发账号互动")
        self.log("   - 请查看下方日志了解详细进度")
        
        # 在后台线程中执行发帖，避免阻塞UI
        def _执行发帖():
            try:
                self.controller.发帖管理器.手动发帖()
            except Exception as e:
                self.log(f"❌ 测试发帖失败: {e}")
                import traceback
                self.log(traceback.format_exc())
        
        threading.Thread(target=_执行发帖, daemon=True).start()
    
    def _append_log(self, msg: str):
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
    
    def log(self, msg: str):
        self.log_signal.emit(msg)
    
    def _clear_log(self):
        """清除日志"""
        self.log_text.clear()
        self.log("日志已清除")
    
    def _update_status(self):
        # 状态标签已移除，不需要更新
        pass
    
    def _rearrange(self):
        """重新排列浏览器容器，使用智能网格布局"""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        
        # 计算最优的行列布局
        total = len(self.containers)
        if total == 0:
            return
        
        # 根据浏览器数量智能计算列数
        if total == 1:
            cols = 1  # 1个：1列
        elif total == 2:
            cols = 2  # 2个：2列
        elif total == 3:
            cols = 3  # 3个：3列
        elif total == 4:
            cols = 2  # 4个：2列（2x2）
        elif total == 5:
            cols = 3  # 5个：3列（第一行3个，第二行2个）
        elif total == 6:
            cols = 3  # 6个：3列（2x3）
        elif total <= 9:
            cols = 3  # 7-9个：3列
        elif total <= 12:
            cols = 4  # 10-12个：4列
        else:
            cols = 4  # 更多：4列
        
        # 按网格排列
        for i, container in enumerate(self.containers.values()):
            # 设置浏览器编号（从1开始）
            container.set_index(i + 1)
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(container, row, col)
    
    def _find_window(self, browser_name: str) -> Optional[int]:
        """查找浏览器窗口，排除比特浏览器主程序"""
        found = []
        
        # 需要排除的关键词（比特浏览器主程序、IDE、监控窗口等）
        exclude_keywords = [
            "Kiro", "监控", "BitBrowser", "比特浏览器", 
            "bit browser", "浏览器管理", "账号管理", "窗口同步",
            "代理管理", "分组管理", "团队管理", "设置"
        ]
        
        def callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls, 256)
                if "Chrome_WidgetWin" in cls.value:
                    title = ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(hwnd, title, 256)
                    title_str = title.value
                    
                    # 排除已嵌入的窗口
                    if hwnd in [c.browser_hwnd for c in self.containers.values()]:
                        return True
                    
                    # 排除比特浏览器主程序和其他不需要的窗口
                    if any(kw.lower() in title_str.lower() for kw in exclude_keywords):
                        return True
                    
                    # 排除空标题窗口（可能是子窗口）
                    if not title_str.strip():
                        return True
                    
                    found.append((hwnd, title_str))
            return True
        
        user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(callback), 0)
        
        # 优先匹配浏览器名称
        for hwnd, title in found:
            if browser_name in title:
                return hwnd
        
        # 其次匹配工作台（新打开的浏览器默认标题）
        for hwnd, title in found:
            if "工作台" in title:
                return hwnd
        
        # 最后返回第一个找到的（如果有的话）
        return found[0][0] if found else None
    
    # ========== HTTP API 处理 ==========
    
    def _start_http_server(self):
        """启动 HTTP 服务器"""
        server = self
        
        class APIHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # 禁用默认日志
            
            def _send_json(self, data, status=200):
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
            
            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path
                
                if path == '/api/status':
                    self._send_json({
                        'success': True,
                        'browsers': len(server.containers),
                        'browser_ids': list(server.containers.keys())
                    })
                
                elif path == '/api/browsers':
                    browsers = []
                    for bid, container in server.containers.items():
                        browsers.append({
                            'id': bid,
                            'name': container.browser_name,
                            'status': container.status,
                            'driver_path': container.driver_path,
                            'debugger_address': container.debugger_address,
                            'has_driver': container.driver is not None
                        })
                    self._send_json({'success': True, 'browsers': browsers})
                
                elif path == '/api/list':
                    # 获取比特浏览器列表
                    if BITBROWSER_AVAILABLE:
                        result = bit_browser.get_browser_list()
                        self._send_json(result)
                    else:
                        self._send_json({'success': False, 'msg': 'BitBrowser API not available'})
                
                else:
                    self._send_json({'success': False, 'msg': 'Unknown endpoint'}, 404)
            
            def do_POST(self):
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
                try:
                    data = json.loads(body) if body else {}
                except:
                    data = {}
                
                path = urlparse(self.path).path
                
                if path == '/api/add':
                    browser_id = data.get('id')
                    browser_name = data.get('name')
                    if not browser_id:
                        self._send_json({'success': False, 'msg': 'Missing browser id'})
                        return
                    server.add_browser_signal.emit(browser_id, browser_name or '')
                    self._send_json({'success': True, 'msg': 'Browser adding...'})
                
                elif path == '/api/remove':
                    browser_id = data.get('id')
                    close = data.get('close', False)
                    if browser_id and browser_id in server.containers:
                        # 使用信号触发移除操作（确保在主线程中执行UI更新）
                        server.remove_browser_signal.emit(browser_id, close)
                        self._send_json({'success': True})
                    else:
                        self._send_json({'success': False, 'msg': 'Browser not found'})
                
                elif path == '/api/status':
                    browser_id = data.get('id')
                    status = data.get('status')
                    if browser_id and status:
                        server.set_status_signal.emit(browser_id, status)
                        self._send_json({'success': True})
                    else:
                        self._send_json({'success': False, 'msg': 'Missing id or status'})
                
                elif path == '/api/tasks':
                    # 设置任务列表
                    browser_id = data.get('id')
                    tasks = data.get('tasks', [])
                    print(f"[API] 收到设置任务列表请求: {browser_id} -> {tasks}")
                    if browser_id:
                        server.set_tasks_signal.emit(browser_id, tasks)
                        self._send_json({'success': True})
                    else:
                        self._send_json({'success': False, 'msg': 'Missing id'})
                
                elif path == '/api/task/add':
                    # 添加任务
                    browser_id = data.get('id')
                    task = data.get('task', '')
                    if browser_id and task:
                        server.add_task_signal.emit(browser_id, task)
                        self._send_json({'success': True})
                    else:
                        self._send_json({'success': False, 'msg': 'Missing id or task'})
                
                elif path == '/api/task/remove':
                    # 移除任务（任务完成时调用）
                    browser_id = data.get('id')
                    task = data.get('task', '')
                    if browser_id and task:
                        server.remove_task_signal.emit(browser_id, task)
                        self._send_json({'success': True})
                    else:
                        self._send_json({'success': False, 'msg': 'Missing id or task'})
                
                elif path == '/api/task/clear':
                    # 清空任务列表
                    browser_id = data.get('id')
                    if browser_id:
                        server.clear_tasks_signal.emit(browser_id)
                        self._send_json({'success': True})
                    else:
                        self._send_json({'success': False, 'msg': 'Missing id'})
                
                elif path == '/api/log':
                    msg = data.get('msg', '')
                    if msg:
                        server.log(msg)
                    self._send_json({'success': True})
                
                elif path == '/api/columns':
                    cols = data.get('cols', 2)
                    server.cols = max(1, min(6, cols))
                    server._rearrange()
                    self._send_json({'success': True})
                
                elif path == '/api/close_all':
                    # 使用信号触发关闭所有操作（确保在主线程中执行UI更新）
                    server.close_all_signal.emit()
                    self._send_json({'success': True})
                
                else:
                    self._send_json({'success': False, 'msg': 'Unknown endpoint'}, 404)
        
        def run_server():
            self.http_server = HTTPServer(('localhost', API_PORT), APIHandler)
            self.log(f"HTTP API 服务已启动: http://localhost:{API_PORT}")
            self.http_server.serve_forever()
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
    
    # ========== 浏览器管理 ==========
    
    def _add_browser_slot(self, browser_id: str, browser_name: str):
        self._do_add_browser(browser_id, browser_name)
    
    def _set_status_slot(self, browser_id: str, status: str):
        if browser_id in self.containers:
            self.containers[browser_id].status = status
    
    def _set_tasks_slot(self, browser_id: str, tasks: list):
        """设置任务列表的槽函数"""
        print(f"[槽函数] 设置任务列表: {browser_id} -> {tasks}")
        if browser_id in self.containers:
            self.containers[browser_id].tasks = tasks
            print(f"[槽函数] 任务列表已设置")
        else:
            print(f"[槽函数] 容器不存在: {browser_id}, 现有容器: {list(self.containers.keys())}")
    
    def _add_task_slot(self, browser_id: str, task: str):
        """添加任务的槽函数"""
        if browser_id in self.containers:
            self.containers[browser_id].add_task(task)
    
    def _remove_task_slot(self, browser_id: str, task: str):
        """移除任务的槽函数（任务完成时调用）"""
        if browser_id in self.containers:
            self.containers[browser_id].remove_task(task)
    
    def _clear_tasks_slot(self, browser_id: str):
        """清空任务列表的槽函数"""
        if browser_id in self.containers:
            self.containers[browser_id].clear_tasks()
    
    def _remove_browser_slot(self, browser_id: str, close: bool):
        """
        移除浏览器的槽函数（在主线程中执行）
        
        Args:
            browser_id: 浏览器ID
            close: 是否关闭浏览器
        """
        if browser_id not in self.containers:
            return
        
        container = self.containers[browser_id]
        
        # 1. 立即从容器字典中删除（主线程，快速）
        del self.containers[browser_id]
        if browser_id in self.browser_info:
            del self.browser_info[browser_id]
        
        # 2. 立即更新UI（主线程，快速）
        self._rearrange()
        self._update_status()
        
        # 3. 异步释放和关闭（后台线程，慢速操作）
        import threading
        def release_and_close_async():
            try:
                # 释放窗口（恢复原始状态）
                if container.browser_hwnd and user32.IsWindow(container.browser_hwnd):
                    try:
                        if container.original_style:
                            user32.SetWindowLongW(container.browser_hwnd, GWL_STYLE, container.original_style)
                        user32.SetParent(container.browser_hwnd, container.original_parent or 0)
                        user32.SetWindowPos(container.browser_hwnd, 0, 100, 100, 1280, 800, SWP_FRAMECHANGED)
                    except:
                        pass
                
                # 关闭浏览器（如果需要）
                if close and bit_browser:
                    try:
                        bit_browser.close_browser(browser_id)
                    except:
                        pass
            except Exception as e:
                print(f"释放/关闭浏览器失败: {e}")
        
        threading.Thread(target=release_and_close_async, daemon=True).start()
    
    def _close_all_slot(self):
        """
        关闭所有浏览器的槽函数（在主线程中执行）
        """
        # 1. 保存要关闭的容器列表
        containers_to_close = list(self.containers.items())
        
        # 2. 立即清空容器和信息（主线程，快速）
        self.containers.clear()
        self.browser_info.clear()
        
        # 3. 立即更新UI（主线程，快速）
        self._rearrange()
        self._update_status()
        self.log("正在关闭所有浏览器...")
        
        # 4. 异步关闭所有浏览器（后台线程，慢速操作）
        import threading
        def close_all_async():
            try:
                for bid, container in containers_to_close:
                    try:
                        # 释放窗口
                        if container.browser_hwnd and user32.IsWindow(container.browser_hwnd):
                            try:
                                if container.original_style:
                                    user32.SetWindowLongW(container.browser_hwnd, GWL_STYLE, container.original_style)
                                user32.SetParent(container.browser_hwnd, container.original_parent or 0)
                                user32.SetWindowPos(container.browser_hwnd, 0, 100, 100, 1280, 800, SWP_FRAMECHANGED)
                            except:
                                pass
                        
                        # 关闭浏览器
                        if bit_browser:
                            try:
                                bit_browser.close_browser(bid)
                            except:
                                pass
                    except Exception as e:
                        print(f"关闭浏览器 {bid} 失败: {e}")
            except Exception as e:
                print(f"关闭所有浏览器失败: {e}")
        
        threading.Thread(target=close_all_async, daemon=True).start()
    
    def _do_add_browser(self, browser_id: str, browser_name: str):
        if browser_id in self.containers:
            self.log(f"浏览器已存在: {browser_id}")
            return
        
        if not BITBROWSER_AVAILABLE:
            self.log("比特浏览器 API 不可用")
            return
        
        # 获取名称
        if not browser_name:
            result = bit_browser.get_browser_list()
            if result.get("success"):
                for b in result.get("data", {}).get("list", []):
                    if b.get("id") == browser_id:
                        browser_name = b.get("name", browser_id)
                        break
            browser_name = browser_name or browser_id
        
        self.log(f"打开浏览器: {browser_name}...")
        
        # ⭐ 异步打开浏览器（避免阻塞UI）
        import threading
        def open_browser_async():
            try:
                result = bit_browser.open_browser(browser_id)
                if not result.get("success"):
                    self.log(f"打开失败: {result.get('msg')}")
                    return
                
                data = result.get("data", {})
                driver_path = data.get("driver", "")
                debugger_address = data.get("http", "")
                self.browser_info[browser_id] = {"driver": driver_path, "http": debugger_address}
                
                # 在主线程中创建容器
                QMetaObject.invokeMethod(
                    self,
                    "_create_container_slot",
                    Qt.QueuedConnection,
                    Q_ARG(str, browser_id),
                    Q_ARG(str, browser_name),
                    Q_ARG(str, driver_path),
                    Q_ARG(str, debugger_address)
                )
            except Exception as e:
                self.log(f"打开浏览器失败: {e}")
        
        threading.Thread(target=open_browser_async, daemon=True).start()
    
    @pyqtSlot(str, str, str, str)
    def _create_container_slot(self, browser_id: str, browser_name: str, driver_path: str, debugger_address: str):
        """在主线程中创建容器（槽函数）"""
        # 创建容器并保存 driver 信息
        container = BrowserContainer(browser_id, browser_name)
        container.driver_path = driver_path
        container.debugger_address = debugger_address
        self.containers[browser_id] = container
        self._rearrange()
        self._update_status()
        
        # 延迟嵌入窗口
        QTimer.singleShot(2000, lambda: self._embed_browser(browser_id, browser_name))
    
    def _get_hwnd_from_debugger_port(self, debugger_address: str) -> Optional[int]:
        """通过 debugger 端口找到浏览器进程，再找到窗口"""
        try:
            import subprocess
            
            # 解析端口，格式: 127.0.0.1:xxxxx
            if ':' in debugger_address:
                port = debugger_address.split(':')[1]
            else:
                return None
            
            # 用 netstat 找到占用该端口的进程 PID
            result = subprocess.run(
                f'netstat -ano | findstr ":{port}"',
                shell=True, capture_output=True, text=True
            )
            
            pid = None
            for line in result.stdout.strip().split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if parts:
                        pid = int(parts[-1])
                        break
            
            if not pid:
                return None
            
            # 通过 PID 找窗口
            return self._find_window_by_pid(pid)
            
        except Exception as e:
            self.log(f"通过端口查找窗口失败: {e}")
            return None
    
    def _find_window_by_pid(self, pid: int) -> Optional[int]:
        """通过进程ID查找主窗口"""
        found_hwnd = None
        found_size = 0
        
        def callback(hwnd, _):
            nonlocal found_hwnd, found_size
            if user32.IsWindowVisible(hwnd):
                # 获取窗口进程ID
                window_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                
                if window_pid.value == pid:
                    cls = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, cls, 256)
                    if "Chrome_WidgetWin" in cls.value:
                        # 排除已嵌入的窗口
                        if hwnd not in [c.browser_hwnd for c in self.containers.values()]:
                            # 获取窗口大小，选择最大的（主窗口）
                            rect = wintypes.RECT()
                            user32.GetWindowRect(hwnd, ctypes.byref(rect))
                            size = (rect.right - rect.left) * (rect.bottom - rect.top)
                            if size > found_size:
                                found_size = size
                                found_hwnd = hwnd
            return True
        
        user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(callback), 0)
        return found_hwnd
    
    def _embed_browser(self, browser_id: str, browser_name: str):
        """异步嵌入浏览器（避免阻塞UI）"""
        if browser_id not in self.containers:
            self.log(f"容器不存在: {browser_id}")
            return
        
        container = self.containers[browser_id]
        info = self.browser_info.get(browser_id, {})
        driver_path = info.get("driver", "")
        debugger_address = info.get("http", "")
        
        if not driver_path or not debugger_address:
            self.log("缺少 driver 信息")
            return
        
        # ⭐ 在后台线程中执行耗时操作（查找窗口、嵌入窗口）
        import threading
        def embed_async():
            try:
                # 1. 通过 debugger 端口找到浏览器窗口（最可靠）- 后台线程
                hwnd = self._get_hwnd_from_debugger_port(debugger_address)
                
                if not hwnd:
                    self.log("通过端口找不到窗口，尝试其他方法...")
                    hwnd = self._find_window(browser_name)
                
                if not hwnd:
                    self.log("找不到浏览器窗口")
                    return
                
                # 2. 在主线程中嵌入窗口（UI操作必须在主线程）
                QMetaObject.invokeMethod(
                    self,
                    "_do_embed_window",
                    Qt.QueuedConnection,
                    Q_ARG(str, browser_id),
                    Q_ARG(str, browser_name),
                    Q_ARG(int, hwnd),
                    Q_ARG(str, driver_path),
                    Q_ARG(str, debugger_address)
                )
                
            except Exception as e:
                self.log(f"嵌入浏览器异常: {e}")
        
        threading.Thread(target=embed_async, daemon=True).start()
    
    @pyqtSlot(str, str, int, str, str)
    def _do_embed_window(self, browser_id: str, browser_name: str, hwnd: int, driver_path: str, debugger_address: str):
        """在主线程中执行嵌入窗口操作"""
        if browser_id not in self.containers:
            return
        
        container = self.containers[browser_id]
        
        # 嵌入窗口
        if not container.embed_window(hwnd):
            self.log("嵌入失败")
            return
        
        self.log(f"✓ 已嵌入: {browser_name}")
        container.released.connect(self._on_released)
        self._rearrange()
        
        # 后台连接 Selenium（不阻塞）
        def connect_selenium():
            if container.connect_selenium(driver_path, debugger_address):
                self.log(f"✓ Selenium 连接成功")
            else:
                self.log("Selenium 连接失败")
        
        import threading
        threading.Thread(target=connect_selenium, daemon=True).start()
    
    def _on_released(self, browser_id: str):
        if browser_id in self.containers:
            del self.containers[browser_id]
        if browser_id in self.browser_info:
            del self.browser_info[browser_id]
        self._rearrange()
        self._update_status()
    
    def cleanup(self):
        """清理资源（当父窗口关闭时调用）"""
        if self.http_server:
            self.http_server.shutdown()
        for container in self.containers.values():
            container.release()


def main():
    global _monitor
    app = QApplication(sys.argv)
    _monitor = BrowserMonitorServer()
    _monitor.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
