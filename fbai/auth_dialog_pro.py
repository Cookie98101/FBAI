#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox, QApplication,
                             QFrame, QGraphicsDropShadowEffect, QCheckBox, QWidget)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtCore import Qt as QtCore_Qt
from PyQt5.QtGui import QFont, QIcon, QColor, QPainter, QPalette, QBrush, QPen

class FacebookLogoWidget(QWidget):
    """自定义Facebook Logo控件 - 反向效果（圆形背景为白色50%透明度，字母f是透明的）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)  # 认证页面的logo稍大一些
        
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
        painter.setFont(QFont("Arial", 32, QFont.Bold))  # 增大字体
        
        # 计算文字位置，更好地居中
        font_metrics = painter.fontMetrics()
        text_width = font_metrics.horizontalAdvance("f")
        text_height = font_metrics.height()
        
        x = (rect.width() - text_width) // 2
        y = (rect.height() + text_height) // 2 - 2  # 调整垂直位置
        
        # 绘制透明的"f"
        painter.drawText(x, y, "f")

class ProAuthDialog(QDialog):
    """专业认证对话框 - 完美显示版本"""
    
    # 登录信息保存文件
    LOGIN_CONFIG_FILE = "login_config.json"
    
    def __init__(self, auth_client, parent=None):
        super().__init__(parent)
        self.auth_client = auth_client
        self._ui_initialized = False  # 防止重复初始化UI
        
        # 设置抗锯齿
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.setWindowTitle("用户认证")
        self.setFixedSize(420, 580)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        
        # 设置窗口图标
        try:
            self.setWindowIcon(QIcon("facebook_logo.png"))
        except:
            pass
        
        self.init_ui()
        self.center_on_screen()
        
        # 加载保存的登录信息
        self.load_login_info()
        
    def center_on_screen(self):
        """窗口居中显示"""
        screen = QApplication.desktop().screenGeometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )
        
    def paintEvent(self, event):
        """重写绘制事件以启用抗锯齿"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.TextAntialiasing)
        super().paintEvent(event)
        
    def init_ui(self):
        """初始化用户界面"""
        # 防止重复初始化
        if self._ui_initialized:
            print("[ProAuthDialog] ⚠ UI已初始化，跳过重复初始化")
            return
        
        print("[ProAuthDialog] ✓ 开始初始化UI")
        self._ui_initialized = True
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(0)
        
        # 创建主容器
        self.main_container = QFrame()
        self.main_container.setObjectName("mainContainer")
        
        # 精致的样式表 - 深色主题
        self.setStyleSheet("""
            QDialog {
                background: transparent;
            }
            
            QFrame#mainContainer {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 15px;
            }
            
            QLabel {
                color: #c9d1d9;
                background: transparent;
            }
            
            QLabel#titleLabel {
                font-size: 28px;
                font-weight: bold;
                padding: 5px;
                color: #58a6ff;
            }
            
            QLabel#subtitleLabel {
                font-size: 14px;
                padding: 3px;
                color: #8b949e;
            }
            
            QLabel#fieldLabel {
                font-size: 13px;
                font-weight: bold;
                padding: 8px 0px 5px 0px;
                color: #c9d1d9;
            }
            
            QLineEdit {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 13px;
                color: #c9d1d9;
                min-height: 25px;
            }
            
            QLineEdit:focus {
                border: 1px solid #58a6ff;
                background: #0d1117;
            }
            
            QLineEdit::placeholder {
                color: #6e7681;
            }
            
            QPushButton {
                background-color: #0969da;
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                min-height: 25px;
            }
            
            QPushButton:hover {
                background-color: #1f6feb;
            }
            
            QPushButton:pressed {
                background-color: #0969da;
            }
            
            QPushButton:disabled {
                background-color: #21262d;
                color: #6e7681;
            }
            
            QPushButton#cancelButton {
                background-color: #21262d;
                border: 1px solid #30363d;
            }
            
            QPushButton#cancelButton:hover {
                background-color: #30363d;
            }
            
            QPushButton#closeButton {
                background-color: #0969da;
                border-radius: 12px;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }
            
            QPushButton#closeButton:hover {
                background-color: #1f6feb;
            }
            
            QCheckBox {
                color: #c9d1d9;
                font-size: 12px;
                spacing: 6px;
                padding: 5px;
            }
            
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #30363d;
                background: #161b22;
            }
            
            QCheckBox::indicator:checked {
                background: #0969da;
                border: 1px solid #0969da;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEwIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDRMMyA2TDkgMSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+Cg==);
            }
            
            QLabel#statusLabel {
                font-size: 11px;
                font-weight: bold;
                padding: 6px;
                border-radius: 5px;
                min-height: 0px;
                max-height: 30px;
            }
            
            QLabel#deviceLabel {
                font-size: 11px;
                padding: 6px;
                background: rgba(0, 0, 0, 0.15);
                border-radius: 5px;
            }
        """)
        
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 6)
        self.main_container.setGraphicsEffect(shadow)
        
        # 容器布局 - 精确的间距控制
        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(35, 30, 35, 30)
        container_layout.setSpacing(0)
        
        # Logo和标题区域
        logo_title_layout = QVBoxLayout()
        logo_title_layout.setSpacing(10)
        logo_title_layout.setAlignment(Qt.AlignCenter)
        
        # Facebook Logo
        logo_widget = FacebookLogoWidget()
        logo_container = QHBoxLayout()
        logo_container.addStretch()
        logo_container.addWidget(logo_widget)
        logo_container.addStretch()
        logo_title_layout.addLayout(logo_container)
        
        # 标题
        title_label = QLabel("欢迎使用")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignCenter)
        logo_title_layout.addWidget(title_label)
        
        # 副标题
        subtitle_label = QLabel("请输入您的登录凭据")
        subtitle_label.setObjectName("subtitleLabel")
        subtitle_label.setAlignment(Qt.AlignCenter)
        logo_title_layout.addWidget(subtitle_label)
        
        container_layout.addLayout(logo_title_layout)
        container_layout.addSpacing(25)
        
        # 用户名区域（标签和输入框在同一行）
        username_layout = QHBoxLayout()
        username_layout.setSpacing(10)
        
        username_label = QLabel("用户名")
        username_label.setObjectName("fieldLabel")
        username_label.setFixedWidth(60)  # 固定标签宽度
        username_layout.addWidget(username_label)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名")
        username_layout.addWidget(self.username_input)
        
        container_layout.addLayout(username_layout)
        container_layout.addSpacing(15)
        
        # 密码区域（标签和输入框在同一行）
        password_layout = QHBoxLayout()
        password_layout.setSpacing(10)
        
        password_label = QLabel("密码")
        password_label.setObjectName("fieldLabel")
        password_label.setFixedWidth(60)  # 固定标签宽度，与用户名标签对齐
        password_layout.addWidget(password_label)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        password_layout.addWidget(self.password_input)
        
        container_layout.addLayout(password_layout)
        container_layout.addSpacing(15)
        
        # 记住密码
        self.remember_checkbox = QCheckBox("记住登录信息")
        self.remember_checkbox.setChecked(True)
        container_layout.addWidget(self.remember_checkbox)
        container_layout.addSpacing(15)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.clicked.connect(self.handle_cancel)
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.cancel_button)
        
        self.login_button = QPushButton("登录")
        self.login_button.clicked.connect(self.handle_login)
        self.login_button.setDefault(True)
        self.login_button.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.login_button)
        
        container_layout.addLayout(button_layout)
        container_layout.addSpacing(8)  # 从15缩小到8
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        container_layout.addWidget(self.status_label)
        
        # 添加到主布局
        main_layout.addWidget(self.main_container)
        self.setLayout(main_layout)
        
        # 连接回车键
        self.username_input.returnPressed.connect(self.handle_login)
        self.password_input.returnPressed.connect(self.handle_login)
        
    def handle_cancel(self):
        """处理取消按钮 - 直接退出程序"""
        # 退出整个应用程序
        QApplication.quit()
        sys.exit(0)
    
    def handle_login(self):
        """处理登录"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username:
            self.show_status("请输入用户名", "error")
            self.username_input.setFocus()
            return
            
        if not password:
            self.show_status("请输入密码", "error")
            self.password_input.setFocus()
            return
        
        # 开始登录
        self.login_button.setEnabled(False)
        self.login_button.setText("认证中...")
        self.cancel_button.setEnabled(False)
        self.show_status("正在验证...", "info")
        
        # 延迟执行登录
        QTimer.singleShot(200, lambda: self.do_login(username, password))
        
    def do_login(self, username, password):
        """执行登录操作"""
        try:
            success, message = self.auth_client.login(username, password)
            
            if success:
                self.show_status("认证成功！", "success")
                self.login_button.setText("成功 ✓")
                
                # 保存登录信息（如果勾选了记住）
                if self.remember_checkbox.isChecked():
                    self.save_login_info(username, password)
                
                # 显示用户信息
                user_info = self.auth_client.get_user_info()
                QTimer.singleShot(600, lambda: self.show_success_message(user_info))
                
            else:
                self.show_status(f"失败: {message}", "error")
                self.reset_login_button()
                
        except Exception as e:
            self.show_status(f"异常: {str(e)[:30]}...", "error")
            self.reset_login_button()
            
    def show_success_message(self, user_info):
        """显示成功消息"""
        msg = QMessageBox(self)
        msg.setWindowTitle("认证成功")
        msg.setIcon(QMessageBox.Information)
        
        # 设置主标题文本（使用HTML格式来控制颜色）
        msg.setText(f'<span style="color: #c9d1d9; font-size: 14px; font-weight: bold;">欢迎, {user_info["username"]}!</span>')
        
        # 格式化信息
        expire_date = user_info['expire_date'].split()[0] if ' ' in user_info['expire_date'] else user_info['expire_date']
        
        # 计算授权剩余时间
        try:
            from datetime import datetime
            expire_datetime = datetime.strptime(user_info['expire_date'], '%Y-%m-%d %H:%M:%S')
            remaining_days = (expire_datetime - datetime.now()).days
            remaining_hours = int((expire_datetime - datetime.now()).total_seconds() / 3600)
            
            if remaining_days > 0:
                remaining_text = f"{remaining_days}天"
            elif remaining_hours > 0:
                remaining_text = f"{remaining_hours}小时"
            else:
                remaining_text = "即将到期"
        except:
            remaining_text = "未知"
        
        # 获取授权信息 - 从网络获取，不使用本地缓存
        # 优先使用 max_windows（窗口数量），如果没有则使用 max_simulators（浏览器数量）
        max_windows = user_info.get('max_windows', user_info.get('max_simulators', 4))
        max_browsers = user_info.get('max_simulators', 10)
        
        info_text = (
            f"📅 到期时间: {expire_date}\n"
            f"🪟 窗口数量: {max_windows} 个\n"
            f"🌐 浏览器数量: {max_browsers} 个\n"
            f"⏰ 授权剩余: {remaining_text}"
        )
        msg.setInformativeText(info_text)
        
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
            QMessageBox QLabel {
                color: #c9d1d9;
                font-size: 13px;
                padding: 5px;
            }
            QMessageBox QPushButton {
                background-color: #0969da;
                border: none;
                border-radius: 5px;
                padding: 6px 15px;
                color: white;
                font-weight: bold;
                font-size: 12px;
                min-width: 60px;
            }
            QMessageBox QPushButton:hover {
                background-color: #1f6feb;
            }
        """)
        msg.exec_()
        self.accept()
        
    def reset_login_button(self):
        """重置登录按钮"""
        self.login_button.setEnabled(True)
        self.login_button.setText("登录")
        self.cancel_button.setEnabled(True)
        
    def show_status(self, message, status_type="info"):
        """显示状态信息"""
        # 输出到控制台，方便调试
        status_prefix = {
            "info": "ℹ️",
            "success": "✅",
            "error": "❌"
        }
        prefix = status_prefix.get(status_type, "ℹ️")
        print(f"\n{prefix} 认证状态:")
        print(f"{message}")
        print("-" * 50)
        
        colors = {
            "info": "#3498db",
            "success": "#0969da",  # 改为蓝色，与主UI按钮颜色一致
            "error": "#e74c3c"
        }
        
        color = colors.get(status_type, colors["info"])
        
        self.status_label.setText(message)
        
        # 根据消息长度和换行符数量动态调整高度
        # 计算实际行数
        line_count = message.count('\n') + 1  # 换行符数量 + 1
        
        # 如果没有换行符，根据字符长度估算（每行约35个字符，考虑中文）
        if line_count == 1:
            # 估算字符宽度（中文算2个字符）
            char_width = sum(2 if ord(c) > 127 else 1 for c in message)
            estimated_lines = max(1, (char_width // 35) + (1 if char_width % 35 > 0 else 0))
            line_count = max(line_count, estimated_lines)
        
        # 每行约18px高度（字体11px + 行间距），加上padding
        line_height = 18
        padding = 16
        calculated_height = line_count * line_height + padding
        
        # 最小30px，最大150px
        max_height = max(30, min(150, calculated_height))
        
        print(f"  消息长度: {len(message)} 字符")
        print(f"  换行符数: {message.count(chr(10))}")
        print(f"  预估行数: {line_count}")
        print(f"  计算高度: {max_height}px")
        
        self.status_label.setStyleSheet(f"""
            QLabel#statusLabel {{
                background: {color};
                color: white;
                font-weight: bold;
                font-size: 11px;
                line-height: 1.5;
                border-radius: 5px;
                padding: 8px 12px;
                min-height: 0px;
                max-height: {max_height}px;
            }}
        """)
        
        # 5秒后清除状态（除非是成功状态），给用户更多时间阅读
        if status_type != "success":
            QTimer.singleShot(5000, lambda: self.status_label.setText(""))
    
    def save_login_info(self, username, password):
        """保存登录信息到文件"""
        try:
            login_data = {
                "username": username,
                "password": password,
                "remember": True
            }
            with open(self.LOGIN_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(login_data, f, ensure_ascii=False, indent=2)
            print(f"✓ 登录信息已保存到 {self.LOGIN_CONFIG_FILE}")
        except Exception as e:
            print(f"保存登录信息失败: {e}")
    
    def load_login_info(self):
        """从文件加载登录信息"""
        try:
            if os.path.exists(self.LOGIN_CONFIG_FILE):
                with open(self.LOGIN_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    login_data = json.load(f)
                
                # 填充到输入框
                if login_data.get("remember"):
                    self.username_input.setText(login_data.get("username", ""))
                    self.password_input.setText(login_data.get("password", ""))
                    self.remember_checkbox.setChecked(True)
                    print(f"✓ 已从 {self.LOGIN_CONFIG_FILE} 加载登录信息")
            else:
                # 如果没有保存的信息，设置默认测试账号
                self.username_input.setText("test_user")
                self.password_input.setText("123456")
                print("未找到保存的登录信息，使用默认测试账号")
        except Exception as e:
            print(f"加载登录信息失败: {e}")
            # 出错时使用默认值
            self.username_input.setText("test_user")
            self.password_input.setText("123456")
    
    def clear_saved_login_info(self):
        """清除保存的登录信息"""
        try:
            if os.path.exists(self.LOGIN_CONFIG_FILE):
                os.remove(self.LOGIN_CONFIG_FILE)
                print(f"✓ 已清除保存的登录信息")
        except Exception as e:
            print(f"清除登录信息失败: {e}")

def test_pro_login():
    """测试专业登录界面"""
    app = QApplication(sys.argv)
    
    # 启用高DPI支持
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    # 导入认证客户端
    from auth_client import AuthClient
    
    auth_client = AuthClient("http://localhost")
    
    dialog = ProAuthDialog(auth_client)
    
    if dialog.exec_() == QDialog.Accepted:
        print("登录成功！")
    else:
        print("登录取消或失败")
    
    sys.exit()

if __name__ == "__main__":
    test_pro_login()
