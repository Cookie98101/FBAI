"""
IP代理管理器UI集成模块
将ip_proxy_manager_v3_fixed集成到facebook_dashboard中
"""

import os
import sys
import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
                             QLineEdit, QTextEdit, QComboBox, QSpinBox, QGroupBox,
                             QGridLayout, QTabWidget, QProgressBar, QScrollArea, QFrame)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject, QUrl
from PyQt5.QtGui import QFont, QColor, QIcon
from PyQt5.QtWebEngineWidgets import QWebEngineView


class ProxyManagerThread(QThread):
    """代理管理器后台线程"""
    
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.process = None
        self.is_running = False
        self.port = 5000
    
    def run(self):
        """运行代理管理器服务"""
        try:
            self.is_running = True
            self.status_changed.emit(f"正在启动代理管理器 (端口 {self.port})...")
            
            # 获取代理管理器路径
            proxy_manager_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'ip_proxy_manager_v3_fixed',
                'ip_proxy_manager_v3_fixed'
            )
            
            if not os.path.exists(proxy_manager_dir):
                self.error_occurred.emit(f"代理管理器目录不存在: {proxy_manager_dir}")
                return
            
            # 启动Flask应用
            self.process = subprocess.Popen(
                [sys.executable, 'app.py'],
                cwd=proxy_manager_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
            )
            
            self.status_changed.emit(f"✓ 代理管理器已启动 (http://localhost:{self.port})")
            
            # 等待进程
            self.process.wait()
            
        except Exception as e:
            self.error_occurred.emit(f"启动失败: {str(e)}")
        finally:
            self.is_running = False
    
    def stop(self):
        """停止代理管理器"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                self.process.kill()
            self.is_running = False


class ProxyManagerUI(QWidget):
    """IP代理管理器UI"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager_thread = None
        self.web_view = None
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout()
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        
        # 第1个标签页: 服务控制
        self.create_control_tab()
        
        # 第2个标签页: Web管理界面
        self.create_web_tab()
        
        main_layout.addWidget(self.tab_widget)
        self.setLayout(main_layout)
    
    def create_control_tab(self):
        """创建服务控制标签页"""
        control_widget = QWidget()
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("IP代理管理系统")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # 状态显示
        status_group = QGroupBox("服务状态")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("未启动")
        self.status_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        self.status_progress = QProgressBar()
        self.status_progress.setVisible(False)
        status_layout.addWidget(self.status_progress)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("启动服务")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.start_btn.clicked.connect(self.start_service)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止服务")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #ba0000;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_service)
        button_layout.addWidget(self.stop_btn)
        
        self.open_btn = QPushButton("打开管理界面")
        self.open_btn.setEnabled(False)
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.open_btn.clicked.connect(self.open_web_interface)
        button_layout.addWidget(self.open_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 功能说明
        info_group = QGroupBox("功能说明")
        info_layout = QVBoxLayout()
        
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd;")
        info_text.setText("""
IP代理管理系统功能：

✓ 代理管理
  - 添加/删除代理配置
  - 支持多种协议 (SS, SSR, V2Ray, VLESS, Trojan)
  - 代理可用性检测
  - 代理使用统计

✓ 账号管理
  - 创建/删除账号
  - 为账号分配代理
  - 账号与代理绑定关系管理

✓ 浏览器集成
  - 与BitBrowser集成
  - 自动为浏览器分配代理
  - 浏览器代理同步

✓ 代理转发
  - 基于Xray的代理转发
  - 支持多协议转发
  - 本地端口映射

✓ 数据管理
  - 数据库备份/恢复
  - 配置导入/导出
  - 同步日志查看
        """)
        info_layout.addWidget(info_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        layout.addStretch()
        control_widget.setLayout(layout)
        self.tab_widget.addTab(control_widget, "服务控制")
    
    def create_web_tab(self):
        """创建Web管理界面标签页"""
        web_widget = QWidget()
        layout = QVBoxLayout()
        
        # 创建Web视图
        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl("about:blank"))
        
        layout.addWidget(self.web_view)
        web_widget.setLayout(layout)
        self.tab_widget.addTab(web_widget, "管理界面")
    
    def start_service(self):
        """启动服务"""
        if self.manager_thread and self.manager_thread.is_running:
            QMessageBox.warning(self, "警告", "服务已在运行中")
            return
        
        self.manager_thread = ProxyManagerThread()
        self.manager_thread.status_changed.connect(self.on_status_changed)
        self.manager_thread.error_occurred.connect(self.on_error)
        self.manager_thread.start()
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_progress.setVisible(True)
        
        # 3秒后启用打开按钮
        QTimer.singleShot(3000, lambda: self.open_btn.setEnabled(True))
    
    def stop_service(self):
        """停止服务"""
        if self.manager_thread:
            self.manager_thread.stop()
            self.manager_thread.wait()
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.status_progress.setVisible(False)
        self.status_label.setText("已停止")
        self.status_label.setStyleSheet("color: #999; font-weight: bold;")
    
    def open_web_interface(self):
        """打开Web管理界面"""
        if self.web_view:
            # 在内置浏览器中加载URL
            self.web_view.setUrl(QUrl("http://localhost:5000"))
            # 切换到管理界面标签页
            self.tab_widget.setCurrentIndex(1)
    
    def on_status_changed(self, message: str):
        """状态变化回调"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
    
    def on_error(self, error: str):
        """错误回调"""
        self.status_label.setText(f"错误: {error}")
        self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.status_progress.setVisible(False)
        QMessageBox.critical(self, "错误", error)
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.manager_thread and self.manager_thread.is_running:
            reply = QMessageBox.question(
                self, 
                "确认", 
                "代理管理器仍在运行，是否停止？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.stop_service()
        event.accept()
