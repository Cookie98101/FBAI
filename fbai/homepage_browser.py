"""
主页发帖浏览器组件 - BitBrowser版本
- 左侧嵌入浏览器窗口
- 右侧显示发帖设置
- 支持配置保存
"""

import os
import json
import random
import ctypes
from ctypes import wintypes
from typing import Optional
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer, pyqtSlot
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QTextEdit, QFileDialog, QMessageBox,
                             QLineEdit, QGroupBox, QSplitter, QFrame)

# Windows API
user32 = ctypes.windll.user32
GWL_STYLE = -16
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000


class BrowserContainer(QWidget):
    """浏览器嵌入容器"""
    
    def __init__(self, browser_name: str = "公共主页", parent=None):
        super().__init__(parent)
        self.browser_name = browser_name
        self.browser_hwnd = None
        self.driver = None
        self.refresh_timer = None  # 浏览器刷新定时器
        
        self.setStyleSheet("background-color: #1a1a2e; border: none;")
        self.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 标题栏
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #21262d; border: none;")
        title_bar.setFixedHeight(30)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 0, 10, 0)
        
        self.title_label = QLabel(f"🌐 {browser_name}")
        self.title_label.setStyleSheet("color: #c9d1d9; font-size: 13px; font-weight: bold;")
        title_layout.addWidget(self.title_label)
        
        title_layout.addStretch()
        
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        title_layout.addWidget(self.status_label)
        
        layout.addWidget(title_bar)
        
        # 浏览器区域
        self.browser_area = QWidget()
        self.browser_area.setStyleSheet("background-color: #ffffff; border: none;")
        layout.addWidget(self.browser_area, 1)
    
    def set_status(self, status: str, color: str = "#8b949e"):
        """设置状态"""
        self.status_label.setText(status)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
    
    def embed_browser(self, hwnd: int) -> bool:
        """改进的浏览器嵌入方法"""
        if not hwnd or not user32.IsWindow(hwnd):
            return False
        
        self.browser_hwnd = hwnd
        
        try:
            # 1. 设置窗口样式
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            new_style = (style | WS_CHILD | WS_VISIBLE) & ~0x00C00000
            user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)
            
            # 2. 设置父窗口
            user32.SetParent(hwnd, int(self.browser_area.winId()))
            
            # 3. 调整大小
            self._resize_browser()
            
            # 4. 强制重绘
            user32.InvalidateRect(hwnd, None, True)
            user32.UpdateWindow(hwnd)
            
            # 5. 启动定时器定期检查和重绘
            self._start_browser_refresh_timer()
            
            self.set_status("已嵌入", "#58a6ff")
            return True
        except Exception as e:
            print(f"❌ 嵌入浏览器失败: {e}")
            self.set_status("嵌入失败", "#f87171")
            return False
    
    def _start_browser_refresh_timer(self):
        """启动浏览器刷新定时器"""
        if not self.refresh_timer:
            self.refresh_timer = QTimer()
            self.refresh_timer.timeout.connect(self._refresh_browser)
        
        self.refresh_timer.start(1000)  # 每秒刷新一次
    
    def _refresh_browser(self):
        """定期刷新浏览器窗口"""
        if not self.browser_hwnd or not user32.IsWindow(self.browser_hwnd):
            if self.refresh_timer:
                self.refresh_timer.stop()
            return
        
        try:
            # 强制重绘
            user32.InvalidateRect(self.browser_hwnd, None, False)
            user32.UpdateWindow(self.browser_hwnd)
        except:
            pass
    
    def _resize_browser(self):
        """调整浏览器窗口大小"""
        if not self.browser_hwnd or not user32.IsWindow(self.browser_hwnd):
            return
        
        rect = self.browser_area.rect()
        user32.MoveWindow(
            self.browser_hwnd,
            0, 0,
            rect.width(), rect.height(),
            True
        )
    
    def resizeEvent(self, event):
        """窗口大小改变时调整浏览器"""
        super().resizeEvent(event)
        self._resize_browser()
    
    def release(self):
        """正确释放浏览器"""
        # 1. 停止刷新定时器
        if self.refresh_timer:
            try:
                self.refresh_timer.stop()
            except:
                pass
        
        # 2. 恢复窗口样式
        if self.browser_hwnd and user32.IsWindow(self.browser_hwnd):
            try:
                # 恢复为顶级窗口
                style = user32.GetWindowLongW(self.browser_hwnd, GWL_STYLE)
                new_style = style | 0x00C00000  # 恢复标题栏
                user32.SetWindowLongW(self.browser_hwnd, GWL_STYLE, new_style)
                
                # 移除父窗口
                user32.SetParent(self.browser_hwnd, 0)
                
                # 强制刷新
                user32.InvalidateRect(self.browser_hwnd, None, True)
                user32.UpdateWindow(self.browser_hwnd)
            except Exception as e:
                print(f"⚠️ 恢复窗口样式失败: {e}")
        
        # 3. 清空引用
        self.browser_hwnd = None
        self.driver = None
        self.set_status("已释放", "#8b949e")


class HomepageBrowser(QWidget):
    """主页发帖浏览器组件"""
    
    # 信号
    post_success = pyqtSignal(str)
    post_failed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 配置文件路径
        self.config_dir = os.path.join(os.path.dirname(__file__), "data", "homepage_browser")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, "config.json")
        
        # BitBrowser ID
        self.browser_id = None
        self.browser_container = None
        
        # 初始化UI
        self._init_ui()
        
        # 加载配置
        self._load_config()
        
        # 自动获取BitBrowser ID
        self._auto_get_browser_id()
    
    def _init_ui(self):
        """初始化UI - 左侧浏览器+右侧设置"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #21262d;
                width: 2px;
            }
        """)
        
        # 左侧：浏览器容器
        self.browser_container = BrowserContainer("公共主页")
        splitter.addWidget(self.browser_container)
        
        # 右侧：设置面板
        settings_panel = self._create_settings_panel()
        splitter.addWidget(settings_panel)
        
        # 设置初始比例 (70% 浏览器, 30% 设置)
        splitter.setSizes([700, 300])
        
        main_layout.addWidget(splitter)
    
    def _create_settings_panel(self):
        """创建右侧设置面板"""
        panel = QWidget()
        panel.setStyleSheet("background-color: #0d1117;")
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(500)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("📝 发帖设置")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #58a6ff;
            padding: 5px 0;
        """)
        layout.addWidget(title_label)
        
        # 状态显示
        self.status_label = QLabel("状态: 正在查找浏览器...")
        self.status_label.setStyleSheet("""
            font-size: 11px;
            color: #58a6ff;
            padding: 3px 0;
        """)
        layout.addWidget(self.status_label)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #30363d;")
        layout.addWidget(line)
        
        # 发帖文本（缩小）
        text_label = QLabel("发帖内容（AI提示词）:")
        text_label.setStyleSheet("color: #c9d1d9; font-size: 13px; font-weight: bold;")
        layout.addWidget(text_label)
        
        self.post_text_edit = QTextEdit()
        self.post_text_edit.setPlaceholderText("输入AI提示词...")
        self.post_text_edit.setStyleSheet("""
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
        """)
        self.post_text_edit.setMinimumHeight(60)
        self.post_text_edit.setMaximumHeight(80)
        self.post_text_edit.textChanged.connect(self._save_config)
        layout.addWidget(self.post_text_edit)
        
        # 联系方式（紧凑）
        contact_label = QLabel("联系方式:")
        contact_label.setStyleSheet("color: #c9d1d9; font-size: 13px; font-weight: bold; margin-top: 5px;")
        layout.addWidget(contact_label)
        
        self.contact_input = QLineEdit()
        self.contact_input.setPlaceholderText("输入联系方式...")
        self.contact_input.setStyleSheet("""
            QLineEdit {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #58a6ff;
            }
        """)
        self.contact_input.textChanged.connect(self._save_config)
        layout.addWidget(self.contact_input)
        
        # 媒体文件夹（紧凑）
        media_label = QLabel("媒体文件夹:")
        media_label.setStyleSheet("color: #c9d1d9; font-size: 13px; font-weight: bold; margin-top: 5px;")
        layout.addWidget(media_label)
        
        folder_layout = QHBoxLayout()
        folder_layout.setSpacing(5)
        self.media_folder_input = QLineEdit()
        self.media_folder_input.setPlaceholderText("选择媒体文件夹...")
        self.media_folder_input.setStyleSheet("""
            QLineEdit {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #58a6ff;
            }
        """)
        self.media_folder_input.textChanged.connect(self._save_config)
        folder_layout.addWidget(self.media_folder_input)
        
        browse_btn = QPushButton("浏览")
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #30363d;
                border-color: #58a6ff;
            }
        """)
        browse_btn.clicked.connect(self._browse_media_folder)
        folder_layout.addWidget(browse_btn)
        
        layout.addLayout(folder_layout)
        
        # 提示文字（缩小）
        hint_label = QLabel("💡 随机选择媒体文件并自动修改MD5")
        hint_label.setStyleSheet("color: #6e7681; font-size: 10px; margin-top: 3px;")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
        
        # 发帖按钮
        post_btn = QPushButton("开始发帖")
        post_btn.setStyleSheet("""
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
        """)
        post_btn.clicked.connect(self._auto_post_with_bitbrowser)
        layout.addWidget(post_btn)
        
        # 日志输出区域
        log_label = QLabel("📋 日志输出:")
        log_label.setStyleSheet("color: #c9d1d9; font-size: 13px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(log_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px;
                font-size: 11px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)
        self.log_output.setMinimumHeight(150)
        layout.addWidget(self.log_output)
        
        return panel

    def _get_auto_post_result_path(self) -> str:
        """获取自动发帖结果共享文件路径（项目根目录下 auto_post_result.txt）。"""
        try:
            # 本文件位于项目根目录下，自动发帖管理器位于 automation/scripts
            # 为保持一致，这里也写入到 project_root/automation/auto_post_result.txt
            project_root = os.path.dirname(os.path.abspath(__file__))
            automation_dir = os.path.join(project_root, "automation")
            return os.path.join(automation_dir, "auto_post_result.txt")
        except Exception:
            # 兜底：当前工作目录
            return os.path.join(os.getcwd(), "auto_post_result.txt")

    def _write_auto_post_result(self, content: str):
        """将发帖结果写入共享文件。
        content:
            - "PENDING": 发帖流程已启动
            - "NO": 发帖失败或未获取到URL
            - 其他非空字符串: 视为帖子URL
        """
        try:
            path = self._get_auto_post_result_path()
            with open(path, "w", encoding="utf-8") as f:
                f.write(content.strip() if isinstance(content, str) else "")
        except Exception as e:
            print(f"⚠️ 写入自动发帖结果文件失败: {e}")
    
    def _load_config(self):
        """加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                    # 恢复发帖内容（AI提示词）
                    if 'post_text' in config:
                        self.post_text_edit.setPlainText(config['post_text'])
                    
                    # 恢复联系方式
                    if 'contact' in config:
                        self.contact_input.setText(config['contact'])
                    
                    # 恢复媒体文件夹
                    if 'media_folder' in config:
                        self.media_folder_input.setText(config['media_folder'])
                    
                    print("✅ 已加载配置")
        except Exception as e:
            print(f"⚠️ 加载配置失败: {e}")
    
    def _save_config(self):
        """保存配置"""
        try:
            config = {
                'post_text': self.post_text_edit.toPlainText(),
                'contact': self.contact_input.text(),
                'media_folder': self.media_folder_input.text()
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存配置失败: {e}")
    
    def _auto_get_browser_id(self):
        """自动获取名为"公共主页"的浏览器ID并嵌入"""
        try:
            from bitbrowser_api import BitBrowserAPI
            
            api = BitBrowserAPI()
            
            # 检查连接
            if not api.check_connection():
                self.status_label.setText("状态: ❌ 无法连接到BitBrowser")
                self.status_label.setStyleSheet("font-size: 12px; color: #f85149; padding: 5px 0;")
                self.browser_container.set_status("未连接", "#f85149")
                return
            
            # 获取浏览器列表
            result = api.get_browser_list(page=0, page_size=100)
            
            if not result.get("success"):
                self.status_label.setText("状态: ❌ 获取浏览器列表失败")
                self.status_label.setStyleSheet("font-size: 12px; color: #f85149; padding: 5px 0;")
                self.browser_container.set_status("获取失败", "#f85149")
                return
            
            # 查找名为"公共主页"的浏览器
            data = result.get("data", {})
            browser_list = data.get("list", [])
            
            for browser in browser_list:
                name = browser.get("name", "")
                if name == "公共主页":
                    self.browser_id = browser.get("id")
                    print(f"✅ 找到浏览器: {name}, ID: {self.browser_id}")
                    self.status_label.setText(f"状态: ✅ 已找到浏览器")
                    self.status_label.setStyleSheet("font-size: 12px; color: #58a6ff; padding: 5px 0;")
                    self.browser_container.set_status("已找到", "#58a6ff")
                    
                    # 自动打开并嵌入浏览器
                    QTimer.singleShot(1000, self._open_and_embed_browser)
                    return
            
            # 未找到
            self.status_label.setText("状态: ❌ 未找到「公共主页」浏览器")
            self.status_label.setStyleSheet("font-size: 12px; color: #f85149; padding: 5px 0;")
            self.browser_container.set_status("未找到", "#f85149")
            
        except Exception as e:
            print(f"❌ 获取浏览器ID失败: {e}")
            self.status_label.setText(f"状态: ❌ 错误")
            self.status_label.setStyleStyle("font-size: 12px; color: #f85149; padding: 5px 0;")
            self.browser_container.set_status("错误", "#f85149")
    
    def _open_and_embed_browser(self):
        """打开并嵌入浏览器"""
        if not self.browser_id:
            return
        
        try:
            from bitbrowser_api import BitBrowserAPI
            
            api = BitBrowserAPI()
            self.browser_container.set_status("正在打开...", "#f0883e")
            
            # 打开浏览器
            result = api.open_browser(self.browser_id)
            
            if not result.get("success"):
                self.browser_container.set_status("打开失败", "#f85149")
                return
            
            # 获取窗口句柄
            data = result.get("data", {})
            
            # 等待窗口出现
            QTimer.singleShot(2000, lambda: self._find_and_embed_window())
            
        except Exception as e:
            print(f"❌ 打开浏览器失败: {e}")
            self.browser_container.set_status("打开失败", "#f85149")
    
    def _find_and_embed_window(self):
        """查找并嵌入浏览器窗口"""
        try:
            # 查找包含"公共主页"的窗口
            results = []
            
            def enum_windows_callback(hwnd, lParam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buffer = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buffer, length + 1)
                        title = buffer.value
                        if "公共主页" in title or "BitBrowser" in title:
                            results.append((hwnd, title))
                return True
            
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
            user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)
            
            if results:
                hwnd, title = results[0]
                print(f"找到窗口: {title} (HWND: {hwnd})")
                
                if self.browser_container.embed_browser(hwnd):
                    self.browser_container.set_status("已嵌入", "#58a6ff")
                    print("✅ 浏览器已嵌入")
                else:
                    self.browser_container.set_status("嵌入失败", "#f85149")
            else:
                self.browser_container.set_status("未找到窗口", "#f85149")
                print("❌ 未找到浏览器窗口")
                
        except Exception as e:
            print(f"❌ 嵌入浏览器失败: {e}")
            import traceback
            traceback.print_exc()
            self.browser_container.set_status("嵌入失败", "#f85149")
    
    def _browse_media_folder(self):
        """浏览并选择媒体文件夹"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择媒体文件夹", "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder_path:
            self.media_folder_input.setText(folder_path)
            print(f"📁 已选择媒体文件夹: {folder_path}")
    
    def _get_random_media_file(self, folder_path: str) -> Optional[str]:
        """从文件夹中随机选择一个媒体文件"""
        if not folder_path or not os.path.exists(folder_path):
            return None
        
        # 支持的媒体文件扩展名
        image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
        all_exts = image_exts | video_exts
        
        # 收集所有媒体文件
        media_files = []
        try:
            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                if os.path.isfile(file_path):
                    ext = os.path.splitext(file)[1].lower()
                    if ext in all_exts:
                        media_files.append(file_path)
        except Exception as e:
            print(f"❌ 读取文件夹失败: {e}")
            return None
        
        if not media_files:
            return None
        
        # 随机选择一个
        selected = random.choice(media_files)
        print(f"🎲 随机选择媒体文件: {os.path.basename(selected)}")
        return selected
    
    @pyqtSlot()
    def _auto_post_with_bitbrowser(self):
        """使用BitBrowser + Selenium完全自动化发帖"""
        prompt_text = self.post_text_edit.toPlainText().strip()
        contact_text = self.contact_input.text().strip()
        folder_path = self.media_folder_input.text().strip()
        
        # 检查是否已获取到浏览器ID
        if not self.browser_id:
            QMessageBox.warning(self, "提示", "未找到浏览器\n\n请确保：\n1. BitBrowser已启动\n2. 已创建名为「公共主页」的浏览器")
            self._auto_get_browser_id()
            return
        
        # 获取随机媒体文件
        media_path = None
        if folder_path:
            media_path = self._get_random_media_file(folder_path)
        
        if not prompt_text and not media_path:
            QMessageBox.warning(self, "提示", "请输入AI提示词或选择媒体文件夹")
            return
        
        print(f"🤖 开始BitBrowser自动化发帖:")
        print(f"  浏览器ID: {self.browser_id}")
        print(f"  AI提示词: {prompt_text}")
        print(f"  联系方式: {contact_text}")
        print(f"  媒体: {media_path}")
        
        # 发帖开始前，将结果文件置为 PENDING，供自动化主程序监控
        try:
            self._write_auto_post_result("PENDING")
        except Exception:
            pass
        
        # 在后台线程执行
        class BitBrowserPostThread(QThread):
            finished = pyqtSignal(bool, str)
            progress = pyqtSignal(str)
            
            def __init__(self, browser_id, prompt_text, contact_text, media_path, parent=None):
                super().__init__(parent)
                self.browser_id = browser_id
                self.prompt_text = prompt_text
                self.contact_text = contact_text
                self.media_path = media_path
            
            def run(self):
                try:
                    import sys
                    import time
                    
                    # 添加路径
                    project_root = os.path.dirname(os.path.abspath(__file__))
                    if project_root not in sys.path:
                        sys.path.insert(0, project_root)
                    
                    script_dir = os.path.join(project_root, "automation", "scripts", "tasks")
                    if script_dir not in sys.path:
                        sys.path.insert(0, script_dir)
                    
                    self.progress.emit("正在导入模块...")
                    
                    from bitbrowser_api import BitBrowserAPI
                    from selenium import webdriver
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.chrome.service import Service
                    from selenium.webdriver.chrome.options import Options
                    
                    import importlib
                    if '主页发帖' in sys.modules:
                        importlib.reload(sys.modules['主页发帖'])
                    from 主页发帖 import 主页发帖
                    
                    self.progress.emit("正在连接浏览器...")
                    
                    api = BitBrowserAPI()
                    result = api.open_browser(self.browser_id)
                    
                    if not result.get("success"):
                        self.finished.emit(False, f"打开浏览器失败: {result.get('msg')}")
                        return
                    
                    # 获取连接信息
                    data = result.get("data", {})
                    driver_path = data.get("driver") or result.get("driver")
                    debug_port = data.get("http") or result.get("http")
                    
                    if not driver_path or not debug_port:
                        self.finished.emit(False, "获取连接信息失败")
                        return
                    
                    # 连接浏览器
                    options = Options()
                    options.add_experimental_option("debuggerAddress", debug_port)
                    options.add_argument("--no-sandbox")
                    options.add_argument("--disable-dev-shm-usage")
                    
                    driver = webdriver.Chrome(service=Service(driver_path), options=options)
                    
                    self.progress.emit("检查浏览器标签页...")
                    time.sleep(2)
                    
                    # 检查并关闭BitBrowser工作台标签页
                    try:
                        all_handles = driver.window_handles
                        self.progress.emit(f"找到 {len(all_handles)} 个标签页")
                        
                        # 关闭包含"- 工作台"或BitBrowser控制台的标签页
                        for handle in all_handles[:]:  # 使用切片创建副本
                            try:
                                driver.switch_to.window(handle)
                                title = driver.title
                                url = driver.current_url
                                
                                # 检查是否是BitBrowser工作台
                                if "- 工作台" in title or url.startswith("https://console.bitbrowser.net/?id="):
                                    self.progress.emit(f"关闭工作台标签: {title}")
                                    driver.close()
                                    time.sleep(0.5)
                            except:
                                pass
                        
                        # 切换到剩余的第一个标签页
                        remaining_handles = driver.window_handles
                        if remaining_handles:
                            driver.switch_to.window(remaining_handles[0])
                            self.progress.emit(f"切换到标签页: {driver.title}")
                        else:
                            self.finished.emit(False, "所有标签页都被关闭了")
                            return
                        
                        # 检查当前URL是否是Facebook首页
                        current_url = driver.current_url
                        
                        # 更精确的首页检测：只有这些URL才算首页
                        is_homepage = (
                            current_url == "https://www.facebook.com/" or
                            current_url == "https://www.facebook.com" or
                            current_url == "http://www.facebook.com/" or
                            current_url == "http://www.facebook.com" or
                            current_url.startswith("https://www.facebook.com/?") or
                            current_url.startswith("https://www.facebook.com/#")
                        )
                        
                        if not is_homepage:
                            self.progress.emit(f"不在Facebook首页（当前: {current_url}），尝试返回...")
                            
                            # 查找并点击Facebook Logo（SVG图标）
                            try:
                                # 方法1: 通过aria-label查找
                                logo = driver.find_element(By.CSS_SELECTOR, "a[aria-label='Facebook']")
                                driver.execute_script("arguments[0].click();", logo)
                                self.progress.emit("已点击Facebook Logo")
                                time.sleep(4)
                            except:
                                try:
                                    # 方法2: 查找包含Facebook SVG的链接
                                    logo = driver.find_element(By.XPATH, "//a[.//svg]")
                                    driver.execute_script("arguments[0].click();", logo)
                                    self.progress.emit("已点击Facebook Logo（SVG）")
                                    time.sleep(4)
                                except:
                                    try:
                                        # 方法3: 直接导航到Facebook首页
                                        driver.get("https://www.facebook.com")
                                        self.progress.emit("直接导航到Facebook首页")
                                        time.sleep(4)
                                    except Exception as nav_error:
                                        self.progress.emit(f"返回首页失败: {nav_error}")
                        else:
                            self.progress.emit("✓ 已在Facebook首页")
                        
                        # 处理浏览器权限弹窗（通知权限等）
                        self.progress.emit("处理浏览器权限弹窗...")
                        try:
                            # 方法1: 使用 CDP 拒绝权限请求
                            try:
                                driver.execute_cdp_cmd('Browser.grantPermissions', {
                                    "origin": "https://www.facebook.com",
                                    "permissions": []
                                })
                                self.progress.emit("✓ 已通过 CDP 拒绝权限请求")
                            except:
                                # 方法2: 按 Escape 键
                                from selenium.webdriver.common.keys import Keys
                                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                                self.progress.emit("✓ 已按 Escape 键关闭弹窗")
                            
                            time.sleep(2)
                            
                            # 刷新浏览器
                            self.progress.emit("刷新浏览器...")
                            driver.refresh()
                            time.sleep(3)
                            
                        except Exception as e:
                            self.progress.emit(f"⚠️ 权限弹窗处理异常: {e}")
                            time.sleep(2)
                        
                    except Exception as tab_error:
                        self.progress.emit(f"标签页检查失败: {tab_error}")
                    
                    self.progress.emit("开始发帖...")
                    time.sleep(2)
                    
                    # 调用发帖函数
                    success, 帖子URL = 主页发帖(
                        driver=driver,
                        提示词=self.prompt_text,
                        log_func=lambda msg: self.progress.emit(msg),
                        使用AI=True,
                        debug=True,
                        媒体文件路径=self.media_path,
                        联系方式=self.contact_text
                    )
                    
                    if success:
                        if 帖子URL:
                            self.finished.emit(True, f"发帖成功！\n帖子URL: {帖子URL}")
                        else:
                            self.finished.emit(True, "发帖成功！")
                    else:
                        self.finished.emit(False, "发帖失败")
                    
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self.finished.emit(False, str(e))
        
        # 创建并启动线程
        self.bitbrowser_thread = BitBrowserPostThread(self.browser_id, prompt_text, contact_text, media_path, None)
        # 使用 Qt.QueuedConnection 确保回调在主线程中执行
        self.bitbrowser_thread.finished.connect(self._on_post_finished, Qt.QueuedConnection)
        self.bitbrowser_thread.progress.connect(self._on_progress_update, Qt.QueuedConnection)
        self.bitbrowser_thread.start()
        
        # 清空日志
        self.log_output.clear()
        self.log_output.append("🚀 开始发帖流程...")
    
    def _on_progress_update(self, message):
        """进度更新回调（在主线程中执行）"""
        # 输出到控制台
        print(f"[进度] {message}")
        
        # 直接更新UI（已经在主线程中）
        self.log_output.append(message)
        
        # 同步一份日志到“自动化”分页，方便集中查看
        try:
            parent = self.parent()
            # MainWindow 提供了 log_automation 方法，内部会写入 browser_monitor
            if parent is not None and hasattr(parent, "log_automation"):
                parent.log_automation(f"[主页发帖] {message}")
        except Exception:
            # 日志同步失败不影响发帖流程
            pass
        
        # 自动滚动到底部
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _on_post_finished(self, success, message):
        """发帖完成回调（在主线程中执行）"""
        if success:
            print(f"✅ {message}")
            self.log_output.append(f"\n✅ {message}")
            self.log_output.append("=" * 50)
            
            # 提取帖子URL
            帖子URL = None
            if "帖子URL:" in message:
                try:
                    帖子URL = message.split("帖子URL:")[1].strip().split("\n")[0].strip()
                    print(f"📎 提取到帖子URL: {帖子URL}")
                    
                    # 发送成功信号，携带帖子URL
                    self.post_success.emit(帖子URL)
                except Exception as e:
                    print(f"⚠️ 提取帖子URL失败: {e}")
                    # 即使没有URL也发送成功信号
                    self.post_success.emit("")
            else:
                # 没有URL，发送空字符串
                self.post_success.emit("")
            
            # 将最终结果写入共享文件：有URL则写URL，没URL则写 NO
            try:
                if "帖子URL:" in message:
                    try:
                        url = message.split("帖子URL:")[1].strip().split("\n")[0].strip()
                        self._write_auto_post_result(url or "NO")
                    except Exception:
                        self._write_auto_post_result("NO")
                else:
                    self._write_auto_post_result("NO")
            except Exception:
                pass
        else:
            print(f"❌ {message}")
            self.log_output.append(f"\n❌ {message}")
            self.log_output.append("=" * 50)
            
            # 发送失败信号
            self.post_failed.emit(message)
            
            # 写入失败标记
            try:
                self._write_auto_post_result("NO")
            except Exception:
                pass

        # 兜底：直接调用自动发帖管理器的回调，确保自动化分页一定能收到发帖结果
        try:
            parent = self.parent()
            log_auto = None
            if parent is not None and hasattr(parent, "log_automation"):
                log_auto = parent.log_automation

            if log_auto:
                log_auto("[主页发帖] 🔍 调试：发帖线程完成，开始尝试调用自动发帖管理器回调")

            controller = None
            if parent is not None and hasattr(parent, "browser_monitor") and parent.browser_monitor:
                bm = parent.browser_monitor
                if hasattr(bm, "controller") and bm.controller is not None:
                    controller = bm.controller
                    if log_auto:
                        log_auto("[主页发帖] 🔍 调试：从 browser_monitor 获取到 controller 实例")
                else:
                    if log_auto:
                        log_auto("[主页发帖] ⚠️ 调试：browser_monitor.controller 为空，无法直连自动发帖管理器")
            else:
                if log_auto:
                    log_auto("[主页发帖] ⚠️ 调试：parent.browser_monitor 不可用，无法直连自动发帖管理器")

            # 从 controller 中找到发帖管理器
            发帖管理器 = None
            if controller is not None and hasattr(controller, "发帖管理器"):
                发帖管理器 = controller.发帖管理器
                if log_auto:
                    log_auto("[主页发帖] 🔍 调试：已从 controller 获取到 发帖管理器")
            else:
                if log_auto and controller is not None:
                    log_auto("[主页发帖] ⚠️ 调试：controller 上未找到 发帖管理器 属性")

            if 发帖管理器 is not None:
                try:
                    if success:
                        # 与 post_success.emit 时保持一致的 URL 解析逻辑
                        帖子URL = ""
                        if "帖子URL:" in message:
                            try:
                                帖子URL = message.split("帖子URL:")[1].strip().split("\n")[0].strip()
                            except Exception:
                                帖子URL = ""
                        if log_auto:
                            log_auto(f"[主页发帖] 📡 调试：调用 发帖管理器._on_post_success(URL={帖子URL})")
                        发帖管理器._on_post_success(帖子URL)
                    else:
                        if log_auto:
                            log_auto(f"[主页发帖] 📡 调试：调用 发帖管理器._on_post_failed(错误={message})")
                        发帖管理器._on_post_failed(message)
                except Exception as e:
                    if log_auto:
                        log_auto(f"[主页发帖] ❌ 调试：调用发帖管理器回调时出错: {e}")
            else:
                if log_auto:
                    log_auto("[主页发帖] ⚠️ 调试：未能获取到 发帖管理器，跳过直连回调")
        except Exception as e:
            # 兜底回调失败不影响发帖结果
            try:
                parent = self.parent()
                if parent is not None and hasattr(parent, "log_automation"):
                    parent.log_automation(f"[主页发帖] ❌ 调试：兜底调用自动发帖管理器回调时发生异常: {e}")
            except Exception:
                pass
        
        # 发帖结果（无论成功或失败）都尝试将主窗口切回“自动化”标签页
        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, "tab_widget"):
                from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
                tab_widget = parent.tab_widget

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

                    # 通过主窗口的自动化日志输出一条说明
                    if hasattr(parent, "log_automation"):
                        parent.log_automation("[主页发帖] ✓ 发帖流程结束，已自动切回“自动化”标签页")
        except Exception:
            # 切换失败不影响发帖结果
            pass

        # 自动滚动到底部
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
