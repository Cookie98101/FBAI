"""
IP代理管理器原生UI模块
直接使用PyQt5实现，调用Flask API
"""

import os
import sys
import json
import subprocess
import threading
import time
import requests
from pathlib import Path
from typing import Optional, List, Dict

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
                             QLineEdit, QTextEdit, QComboBox, QSpinBox, QGroupBox,
                             QGridLayout, QTabWidget, QProgressBar, QScrollArea, QFrame,
                             QDialog, QFormLayout, QDialogButtonBox, QInputDialog)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject
from PyQt5.QtGui import QFont, QColor, QIcon


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
            
            self.status_changed.emit(f"✓ 代理管理器已启动")
            
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


class ProxyManagerNativeUI(QWidget):
    """IP代理管理器原生UI"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager_thread = None
        self.api_base_url = "http://localhost:5000/api"
        self.init_ui()
        self.start_service_auto()
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout()
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        
        # 创建各个标签页
        self.create_dashboard_tab()
        self.create_proxies_tab()
        self.create_accounts_tab()
        self.create_sync_tab()
        
        main_layout.addWidget(self.tab_widget)
        self.setLayout(main_layout)
    
    def start_service_auto(self):
        """自动启动服务"""
        if self.manager_thread and self.manager_thread.is_running:
            return
        
        self.manager_thread = ProxyManagerThread()
        self.manager_thread.status_changed.connect(self.on_status_changed)
        self.manager_thread.error_occurred.connect(self.on_error)
        self.manager_thread.start()
        
        # 等待服务启动
        QTimer.singleShot(2000, self.refresh_all_data)
    
    def create_dashboard_tab(self):
        """创建仪表盘标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("IP代理管理系统")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # 统计卡片
        stats_layout = QHBoxLayout()
        
        # 代理统计
        proxy_group = QGroupBox("代理统计")
        proxy_layout = QVBoxLayout()
        self.proxy_total_label = QLabel("总数: 0")
        self.proxy_active_label = QLabel("活跃: 0")
        self.proxy_inactive_label = QLabel("不活跃: 0")
        proxy_layout.addWidget(self.proxy_total_label)
        proxy_layout.addWidget(self.proxy_active_label)
        proxy_layout.addWidget(self.proxy_inactive_label)
        proxy_group.setLayout(proxy_layout)
        stats_layout.addWidget(proxy_group)
        
        # 账号统计
        account_group = QGroupBox("账号统计")
        account_layout = QVBoxLayout()
        self.account_total_label = QLabel("总数: 0")
        self.account_bound_label = QLabel("已绑定: 0")
        self.account_unbound_label = QLabel("未绑定: 0")
        account_layout.addWidget(self.account_total_label)
        account_layout.addWidget(self.account_bound_label)
        account_layout.addWidget(self.account_unbound_label)
        account_group.setLayout(account_layout)
        stats_layout.addWidget(account_group)
        
        layout.addLayout(stats_layout)
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新数据")
        refresh_btn.clicked.connect(self.refresh_all_data)
        layout.addWidget(refresh_btn)
        
        layout.addStretch()
        widget.setLayout(layout)
        self.tab_widget.addTab(widget, "仪表盘")
    
    def create_proxies_tab(self):
        """创建代理管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("代理管理")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("添加代理")
        add_btn.clicked.connect(self.add_proxy)
        button_layout.addWidget(add_btn)
        
        batch_add_btn = QPushButton("批量添加")
        batch_add_btn.clicked.connect(self.batch_add_proxies)
        button_layout.addWidget(batch_add_btn)
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_proxies)
        button_layout.addWidget(refresh_btn)

        delete_all_btn = QPushButton("全部删除")
        delete_all_btn.clicked.connect(self.delete_all_proxies)
        button_layout.addWidget(delete_all_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 代理表格
        self.proxies_table = QTableWidget()
        self.proxies_table.setColumnCount(6)
        self.proxies_table.setHorizontalHeaderLabels([
            "ID", "协议", "地址", "端口", "状态", "操作"
        ])
        self.proxies_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.proxies_table)
        
        widget.setLayout(layout)
        self.tab_widget.addTab(widget, "代理管理")
    
    def create_accounts_tab(self):
        """创建账号管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("账号管理")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("创建账号")
        add_btn.clicked.connect(self.add_account)
        button_layout.addWidget(add_btn)
        
        batch_add_btn = QPushButton("批量创建")
        batch_add_btn.clicked.connect(self.batch_add_accounts)
        button_layout.addWidget(batch_add_btn)
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_accounts)
        button_layout.addWidget(refresh_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 账号表格
        self.accounts_table = QTableWidget()
        self.accounts_table.setColumnCount(5)
        self.accounts_table.setHorizontalHeaderLabels([
            "ID", "邮箱", "代理", "浏览器ID", "操作"
        ])
        self.accounts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.accounts_table)
        
        widget.setLayout(layout)
        self.tab_widget.addTab(widget, "账号管理")
    
    def create_sync_tab(self):
        """创建同步管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("同步管理")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        sync_btn = QPushButton("执行同步")
        sync_btn.clicked.connect(self.execute_sync)
        button_layout.addWidget(sync_btn)
        
        refresh_btn = QPushButton("刷新日志")
        refresh_btn.clicked.connect(self.refresh_sync_logs)
        button_layout.addWidget(refresh_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 同步日志表格
        self.sync_logs_table = QTableWidget()
        self.sync_logs_table.setColumnCount(4)
        self.sync_logs_table.setHorizontalHeaderLabels([
            "时间", "类型", "状态", "详情"
        ])
        self.sync_logs_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.sync_logs_table)
        
        widget.setLayout(layout)
        self.tab_widget.addTab(widget, "同步管理")
    
    def api_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """发送API请求"""
        try:
            url = f"{self.api_base_url}{endpoint}"
            
            if method == "GET":
                response = requests.get(url, timeout=10)
            elif method == "POST":
                response = requests.post(url, json=data or {}, timeout=10)
            elif method == "DELETE":
                response = requests.delete(url, timeout=10)
            elif method == "PUT":
                response = requests.put(url, json=data or {}, timeout=10)
            else:
                return {"success": False, "error": "未知的请求方法"}
            
            return response.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "无法连接到服务"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def refresh_all_data(self):
        """刷新所有数据"""
        self.refresh_dashboard()
        self.refresh_proxies()
        self.refresh_accounts()
        self.refresh_sync_logs()
    
    def refresh_dashboard(self):
        """刷新仪表盘"""
        # 获取代理统计
        result = self.api_request("GET", "/proxies")
        if result.get("success"):
            proxies = result.get("data", [])
            total = len(proxies)
            active = len([p for p in proxies if p.get("status") == "active"])
            inactive = total - active
            
            self.proxy_total_label.setText(f"总数: {total}")
            self.proxy_active_label.setText(f"活跃: {active}")
            self.proxy_inactive_label.setText(f"不活跃: {inactive}")
        
        # 获取账号统计
        result = self.api_request("GET", "/accounts")
        if result.get("success"):
            accounts = result.get("data", [])
            total = len(accounts)
            bound = len([a for a in accounts if a.get("proxy_config_id")])
            unbound = total - bound
            
            self.account_total_label.setText(f"总数: {total}")
            self.account_bound_label.setText(f"已绑定: {bound}")
            self.account_unbound_label.setText(f"未绑定: {unbound}")
    
    def refresh_proxies(self):
        """刷新代理列表"""
        result = self.api_request("GET", "/proxies")
        if result.get("success"):
            proxies = result.get("data", [])
            self.proxies_table.setRowCount(len(proxies))
            
            for row, proxy in enumerate(proxies):
                self.proxies_table.setItem(row, 0, QTableWidgetItem(str(proxy.get("id", ""))))
                self.proxies_table.setItem(row, 1, QTableWidgetItem(proxy.get("protocol", "")))
                self.proxies_table.setItem(row, 2, QTableWidgetItem(proxy.get("host", "")))
                self.proxies_table.setItem(row, 3, QTableWidgetItem(str(proxy.get("port", ""))))
                self.proxies_table.setItem(row, 4, QTableWidgetItem(proxy.get("status", "")))
                
                # 操作按钮
                op_widget = QWidget()
                op_layout = QHBoxLayout()
                
                delete_btn = QPushButton("删除")
                delete_btn.clicked.connect(lambda checked, pid=proxy.get("id"): self.delete_proxy(pid))
                op_layout.addWidget(delete_btn)
                
                op_widget.setLayout(op_layout)
                self.proxies_table.setCellWidget(row, 5, op_widget)
    
    def refresh_accounts(self):
        """刷新账号列表"""
        result = self.api_request("GET", "/accounts")
        if result.get("success"):
            accounts = result.get("data", [])
            self.accounts_table.setRowCount(len(accounts))
            
            for row, account in enumerate(accounts):
                self.accounts_table.setItem(row, 0, QTableWidgetItem(str(account.get("id", ""))))
                self.accounts_table.setItem(row, 1, QTableWidgetItem(account.get("email", "")))
                self.accounts_table.setItem(row, 2, QTableWidgetItem(str(account.get("proxy_config_id", ""))))
                self.accounts_table.setItem(row, 3, QTableWidgetItem(account.get("browser_id", "") or ""))
                
                # 操作按钮
                op_widget = QWidget()
                op_layout = QHBoxLayout()
                
                allocate_btn = QPushButton("分配代理")
                allocate_btn.clicked.connect(lambda checked, aid=account.get("id"): self.allocate_proxy(aid))
                op_layout.addWidget(allocate_btn)
                
                delete_btn = QPushButton("删除")
                delete_btn.clicked.connect(lambda checked, aid=account.get("id"): self.delete_account(aid))
                op_layout.addWidget(delete_btn)
                
                op_widget.setLayout(op_layout)
                self.accounts_table.setCellWidget(row, 4, op_widget)
    
    def refresh_sync_logs(self):
        """刷新同步日志"""
        result = self.api_request("GET", "/sync/logs")
        if result.get("success"):
            logs = result.get("data", [])
            self.sync_logs_table.setRowCount(len(logs))
            
            for row, log in enumerate(logs):
                self.sync_logs_table.setItem(row, 0, QTableWidgetItem(log.get("created_at", "")))
                self.sync_logs_table.setItem(row, 1, QTableWidgetItem(log.get("action", "")))
                self.sync_logs_table.setItem(row, 2, QTableWidgetItem(log.get("status", "")))
                self.sync_logs_table.setItem(row, 3, QTableWidgetItem(log.get("details", "")))
    
    def add_proxy(self):
        """添加代理"""
        url, ok = QInputDialog.getText(self, "添加代理", "输入代理URL:")
        if ok and url:
            result = self.api_request("POST", "/proxies", {"protocol_url": url})
            if result.get("success"):
                QMessageBox.information(self, "成功", "代理已添加")
                self.refresh_proxies()
            else:
                QMessageBox.critical(self, "错误", result.get("error", "添加失败"))
    
    def batch_add_proxies(self):
        """批量添加代理"""
        urls, ok = QInputDialog.getMultiLineText(self, "批量添加代理", "输入代理URL (每行一个):")
        if ok and urls:
            result = self.api_request("POST", "/proxies/batch", {"protocol_urls": urls})
            if result.get("success"):
                QMessageBox.information(self, "成功", "代理已批量添加")
                self.refresh_proxies()
            else:
                QMessageBox.critical(self, "错误", result.get("error", "添加失败"))
    
    def delete_proxy(self, proxy_id):
        """删除代理"""
        reply = QMessageBox.question(self, "确认", "确定要删除这个代理吗?")
        if reply == QMessageBox.Yes:
            result = self.api_request("DELETE", f"/proxies/{proxy_id}")
            if result.get("success"):
                QMessageBox.information(self, "成功", "代理已删除")
                self.refresh_proxies()
            else:
                QMessageBox.critical(self, "错误", result.get("error", "删除失败"))
    
    def add_account(self):
        """创建账号"""
        email, ok = QInputDialog.getText(self, "创建账号", "输入邮箱地址:")
        if ok and email:
            result = self.api_request("POST", "/accounts", {"email": email})
            if result.get("success"):
                QMessageBox.information(self, "成功", "账号已创建")
                self.refresh_accounts()
            else:
                QMessageBox.critical(self, "错误", result.get("error", "创建失败"))
    
    def batch_add_accounts(self):
        """批量创建账号"""
        emails, ok = QInputDialog.getMultiLineText(self, "批量创建账号", "输入邮箱地址 (每行一个):")
        if ok and emails:
            result = self.api_request("POST", "/accounts/batch", {"emails": emails})
            if result.get("success"):
                QMessageBox.information(self, "成功", "账号已批量创建")
                self.refresh_accounts()
            else:
                QMessageBox.critical(self, "错误", result.get("error", "创建失败"))
    
    def delete_account(self, account_id):
        """删除账号"""
        reply = QMessageBox.question(self, "确认", "确定要删除这个账号吗?")
        if reply == QMessageBox.Yes:
            result = self.api_request("DELETE", f"/accounts/{account_id}")
            if result.get("success"):
                QMessageBox.information(self, "成功", "账号已删除")
                self.refresh_accounts()
            else:
                QMessageBox.critical(self, "错误", result.get("error", "删除失败"))
    
    def allocate_proxy(self, account_id):
        """分配代理"""
        result = self.api_request("POST", f"/accounts/{account_id}/allocate")
        if result.get("success"):
            QMessageBox.information(self, "成功", "代理已分配")
            self.refresh_accounts()
        else:
            QMessageBox.critical(self, "错误", result.get("error", "分配失败"))
    
    def execute_sync(self):
        """执行同步"""
        result = self.api_request("POST", "/sync/execute")
        if result.get("success"):
            QMessageBox.information(self, "成功", "同步已执行")
            self.refresh_sync_logs()
        else:
            QMessageBox.critical(self, "错误", result.get("error", "同步失败"))
    
    def on_status_changed(self, message: str):
        """状态变化回调"""
        pass
    
    def on_error(self, error: str):
        """错误回调"""
        QMessageBox.critical(self, "错误", error)
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.manager_thread and self.manager_thread.is_running:
            self.manager_thread.stop()
            self.manager_thread.wait()
        event.accept()
