"""
账号阶段管理器
用于管理账号的运行天数和阶段
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox,
    QMessageBox, QComboBox, QLineEdit, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
import sys
import os
import time
import datetime

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from automation.scripts.database.db import Database


class AccountStageManager(QDialog):
    """账号阶段管理器"""
    
    def __init__(self, parent=None):
        print("[账号阶段管理] 开始初始化...")
        super().__init__(parent)
        print("[账号阶段管理] QDialog 初始化完成")
        
        self.db = Database()
        print("[账号阶段管理] 数据库连接完成")
        
        self.setWindowTitle("账号阶段管理")
        
        # 设置窗口标志：独立窗口（不使用 WindowStaysOnTopHint，避免阻塞操作）
        self.setWindowFlags(
            Qt.Window | 
            Qt.WindowCloseButtonHint |  # 显示关闭按钮
            Qt.WindowMinMaxButtonsHint  # 显示最小化/最大化按钮
        )
        print("[账号阶段管理] 窗口标志设置完成")
        
        # 设置窗口属性
        self.setAttribute(Qt.WA_DeleteOnClose, True)  # 关闭时删除，释放资源
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)  # 显示时激活
        
        # 设置窗口大小和位置
        self.resize(1400, 800)
        print("[账号阶段管理] 窗口大小设置完成")
        
        # 应用样式表（确保渲染）
        self.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
                color: #c9d1d9;
            }
        """)
        print("[账号阶段管理] 样式表应用完成")
        
        print("[账号阶段管理] 开始初始化UI...")
        self.init_ui()
        print("[账号阶段管理] UI初始化完成")
        
        print("[账号阶段管理] 开始加载账号...")
        self.load_accounts()
        print("[账号阶段管理] 账号加载完成")
        
        print("[账号阶段管理] ✅ 初始化全部完成")
    
    def _show_message(self, title, message, icon=QMessageBox.Information):
        """显示消息框（带深色主题样式）"""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(icon)
        
        # 设置深色主题样式
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #0d1117;
                color: #c9d1d9;
            }
            QMessageBox QLabel {
                color: #c9d1d9;
                font-size: 13px;
            }
            QMessageBox QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 16px;
                min-width: 60px;
            }
            QMessageBox QPushButton:hover {
                background-color: #30363d;
            }
            QMessageBox QPushButton:pressed {
                background-color: #161b22;
            }
        """)
        
        return msg.exec_()
    
    def _show_question(self, title, message):
        """显示确认对话框（带深色主题样式）"""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(QMessageBox.Question)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        
        # 设置深色主题样式
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #0d1117;
                color: #c9d1d9;
            }
            QMessageBox QLabel {
                color: #c9d1d9;
                font-size: 13px;
            }
            QMessageBox QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 16px;
                min-width: 60px;
            }
            QMessageBox QPushButton:hover {
                background-color: #30363d;
            }
            QMessageBox QPushButton:pressed {
                background-color: #161b22;
            }
        """)
        
        return msg.exec_()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("🎯 账号阶段管理")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #58a6ff;
                padding: 10px;
            }
        """)
        layout.addWidget(title_label)
        
        # 说明
        desc_label = QLabel("修改账号的运行天数和阶段，影响任务配置和操作策略")
        desc_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #8b949e;
                padding: 0px 10px 10px 10px;
            }
        """)
        layout.addWidget(desc_label)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        # 筛选器
        filter_label = QLabel("筛选阶段:")
        self.stage_filter = QComboBox()
        self.stage_filter.addItems([
            "全部阶段",
            "阶段1 (0-3天)",
            "阶段2 (4-7天)",
            "阶段3 (8-15天)",
            "阶段4 (16-25天)",
            "阶段5 (26-45天)",
            "阶段6 (45天+)"
        ])
        self.stage_filter.currentTextChanged.connect(self.filter_accounts)
        
        # 搜索框
        search_label = QLabel("搜索:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入浏览器ID或用户名")
        self.search_input.textChanged.connect(self.filter_accounts)
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.load_accounts)
        
        toolbar.addWidget(filter_label)
        toolbar.addWidget(self.stage_filter)
        toolbar.addWidget(search_label)
        toolbar.addWidget(self.search_input)
        toolbar.addStretch()
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "浏览器ID", "用户名", "创建时间", "运行天数", "阶段",
            "修改天数", "备份时间", "操作", "状态"
        ])
        
        # 设置行高
        self.table.verticalHeader().setDefaultSectionSize(50)  # 设置默认行高为50px
        
        # 设置列宽
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 浏览器ID
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 用户名
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 创建时间
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 运行天数
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 阶段
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 修改天数
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 备份时间
        self.table.setColumnWidth(7, 200)  # 操作列固定宽度200px
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # 状态
        
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # 设置样式
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #c9d1d9;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #21262d;
            }
            QTableWidget::item:selected {
                background-color: #1f6feb;
            }
            QHeaderView::section {
                background-color: #161b22;
                color: #c9d1d9;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #30363d;
                font-weight: bold;
            }
        """)
        
        layout.addWidget(self.table)
        
        # 底部按钮
        bottom_layout = QHBoxLayout()
        
        help_btn = QPushButton("❓ 帮助")
        help_btn.clicked.connect(self.show_help)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        
        bottom_layout.addWidget(help_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(close_btn)
        
        layout.addLayout(bottom_layout)
    
    def load_accounts(self):
        """加载账号列表"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # 查询所有账号
            cursor.execute("""
                SELECT 
                    browser_id,
                    username,
                    created_at,
                    backup_created_at,
                    status
                FROM accounts
                ORDER BY created_at DESC
            """)
            
            accounts = cursor.fetchall()
            conn.close()
            
            self.table.setRowCount(len(accounts))
            
            for i, account in enumerate(accounts):
                browser_id = account['browser_id']
                username = account['username'] or ''
                created_at = account['created_at']
                backup_created_at = account['backup_created_at']
                status = account['status'] or 'active'
                
                # 计算运行天数
                running_days = self.calculate_running_days(created_at)
                stage = self.calculate_stage(running_days)
                
                # 浏览器ID
                self.table.setItem(i, 0, QTableWidgetItem(browser_id[:8]))
                
                # 用户名
                self.table.setItem(i, 1, QTableWidgetItem(username))
                
                # 创建时间
                self.table.setItem(i, 2, QTableWidgetItem(created_at))
                
                # 运行天数
                days_item = QTableWidgetItem(str(running_days))
                days_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, 3, days_item)
                
                # 阶段
                stage_item = QTableWidgetItem(f"阶段{stage}")
                stage_item.setTextAlignment(Qt.AlignCenter)
                stage_item.setForeground(self.get_stage_color(stage))
                self.table.setItem(i, 4, stage_item)
                
                # 修改天数输入框
                days_spinbox = QSpinBox()
                days_spinbox.setRange(0, 365)
                days_spinbox.setValue(running_days)
                days_spinbox.setStyleSheet("""
                    QSpinBox {
                        background-color: #161b22;
                        color: #c9d1d9;
                        border: 1px solid #30363d;
                        border-radius: 4px;
                        padding: 5px;
                    }
                """)
                self.table.setCellWidget(i, 5, days_spinbox)
                
                # 备份时间
                backup_text = backup_created_at if backup_created_at else "无备份"
                backup_item = QTableWidgetItem(backup_text)
                backup_item.setTextAlignment(Qt.AlignCenter)
                if not backup_created_at:
                    backup_item.setForeground(QColor("#8b949e"))
                self.table.setItem(i, 6, backup_item)
                
                # 操作按钮
                btn_widget = QWidget()
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(5, 2, 5, 2)
                btn_layout.setSpacing(5)
                
                # 应用按钮
                apply_btn = QPushButton("✓ 应用")
                apply_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #238636;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 5px 10px;
                    }
                    QPushButton:hover {
                        background-color: #2ea043;
                    }
                """)
                apply_btn.clicked.connect(lambda checked, row=i: self.apply_changes(row))
                btn_layout.addWidget(apply_btn)
                
                # 还原按钮
                restore_btn = QPushButton("↶ 还原")
                restore_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1f6feb;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 5px 10px;
                    }
                    QPushButton:hover {
                        background-color: #388bfd;
                    }
                """)
                restore_btn.setEnabled(backup_created_at is not None)
                restore_btn.clicked.connect(lambda checked, row=i: self.restore_backup(row))
                btn_layout.addWidget(restore_btn)
                
                self.table.setCellWidget(i, 7, btn_widget)
                
                # 状态
                status_item = QTableWidgetItem(status)
                status_item.setTextAlignment(Qt.AlignCenter)
                if status == 'active':
                    status_item.setForeground(QColor("#238636"))
                elif status == 'blocked':
                    status_item.setForeground(QColor("#da3633"))
                else:
                    status_item.setForeground(QColor("#8b949e"))
                self.table.setItem(i, 8, status_item)
            
            print(f"[账号阶段管理] 加载了 {len(accounts)} 个账号")
            
        except Exception as e:
            self._show_message("错误", f"加载账号失败: {e}", QMessageBox.Warning)
            print(f"[账号阶段管理] 加载失败: {e}")
    
    def calculate_running_days(self, created_at: str) -> int:
        """计算运行天数"""
        try:
            created_time = datetime.datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            now = datetime.datetime.now()
            delta = now - created_time
            return delta.days
        except:
            return 0
    
    def calculate_stage(self, running_days: int) -> int:
        """计算阶段"""
        if running_days <= 3:
            return 1
        elif running_days <= 7:
            return 2
        elif running_days <= 15:
            return 3
        elif running_days <= 25:
            return 4
        elif running_days <= 45:
            return 5
        else:
            return 6
    
    def get_stage_color(self, stage: int) -> QColor:
        """获取阶段颜色"""
        colors = {
            1: QColor("#f85149"),  # 红色 - 新手期
            2: QColor("#d29922"),  # 黄色 - 适应期
            3: QColor("#58a6ff"),  # 蓝色 - 成长期
            4: QColor("#79c0ff"),  # 浅蓝 - 稳定期
            5: QColor("#56d364"),  # 绿色 - 活跃期
            6: QColor("#238636"),  # 深绿 - 成熟期
        }
        return colors.get(stage, QColor("#c9d1d9"))
    
    def apply_changes(self, row: int):
        """应用修改"""
        try:
            # 获取浏览器ID
            browser_id_item = self.table.item(row, 0)
            if not browser_id_item:
                return
            
            browser_id_short = browser_id_item.text()
            
            # 获取完整的浏览器ID
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT browser_id, created_at, backup_created_at
                FROM accounts
                WHERE browser_id LIKE ?
            """, (f"{browser_id_short}%",))
            
            account = cursor.fetchone()
            if not account:
                self._show_message("错误", "找不到账号", QMessageBox.Warning)
                conn.close()
                return
            
            browser_id = account['browser_id']
            current_created_at = account['created_at']
            backup_created_at = account['backup_created_at']
            
            # 获取新的天数
            days_spinbox = self.table.cellWidget(row, 5)
            new_days = days_spinbox.value()
            
            # 计算新的创建时间
            now = datetime.datetime.now()
            new_created_time = now - datetime.timedelta(days=new_days)
            new_created_at = new_created_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 如果没有备份，先备份原始值
            if not backup_created_at:
                cursor.execute("""
                    UPDATE accounts
                    SET backup_created_at = ?
                    WHERE browser_id = ?
                """, (current_created_at, browser_id))
                print(f"[账号阶段管理] 备份原始创建时间: {current_created_at}")
            
            # 更新创建时间
            cursor.execute("""
                UPDATE accounts
                SET created_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE browser_id = ?
            """, (new_created_at, browser_id))
            
            conn.commit()
            conn.close()
            
            # 重新加载
            self.load_accounts()
            
            new_stage = self.calculate_stage(new_days)
            self._show_message(
                "成功",
                f"已修改账号阶段\n\n"
                f"浏览器ID: {browser_id_short}\n"
                f"运行天数: {new_days} 天\n"
                f"当前阶段: 阶段{new_stage}",
                QMessageBox.Information
            )
            
            print(f"[账号阶段管理] 已修改: {browser_id_short} -> {new_days}天 (阶段{new_stage})")
            
        except Exception as e:
            self._show_message("错误", f"应用修改失败: {e}", QMessageBox.Warning)
            print(f"[账号阶段管理] 应用失败: {e}")
    
    def restore_backup(self, row: int):
        """还原备份"""
        try:
            # 获取浏览器ID
            browser_id_item = self.table.item(row, 0)
            if not browser_id_item:
                return
            
            browser_id_short = browser_id_item.text()
            
            # 确认还原
            reply = self._show_question(
                "确认还原",
                f"确定要还原账号 {browser_id_short} 的原始创建时间吗？"
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # 获取完整的浏览器ID和备份时间
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT browser_id, backup_created_at
                FROM accounts
                WHERE browser_id LIKE ?
            """, (f"{browser_id_short}%",))
            
            account = cursor.fetchone()
            if not account:
                self._show_message("错误", "找不到账号", QMessageBox.Warning)
                conn.close()
                return
            
            browser_id = account['browser_id']
            backup_created_at = account['backup_created_at']
            
            if not backup_created_at:
                self._show_message("错误", "没有备份数据", QMessageBox.Warning)
                conn.close()
                return
            
            # 还原创建时间
            cursor.execute("""
                UPDATE accounts
                SET created_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE browser_id = ?
            """, (backup_created_at, browser_id))
            
            conn.commit()
            conn.close()
            
            # 重新加载
            self.load_accounts()
            
            self._show_message("成功", f"已还原账号 {browser_id_short} 的原始创建时间", QMessageBox.Information)
            print(f"[账号阶段管理] 已还原: {browser_id_short} -> {backup_created_at}")
            
        except Exception as e:
            self._show_message("错误", f"还原失败: {e}", QMessageBox.Warning)
            print(f"[账号阶段管理] 还原失败: {e}")
    
    def filter_accounts(self):
        """筛选账号"""
        stage_text = self.stage_filter.currentText()
        search_text = self.search_input.text().lower()
        
        for i in range(self.table.rowCount()):
            show = True
            
            # 阶段筛选
            if stage_text != "全部阶段":
                stage_item = self.table.item(i, 4)
                if stage_item and stage_text.split()[0] not in stage_item.text():
                    show = False
            
            # 搜索筛选
            if search_text:
                browser_id = self.table.item(i, 0).text().lower()
                username = self.table.item(i, 1).text().lower()
                if search_text not in browser_id and search_text not in username:
                    show = False
            
            self.table.setRowHidden(i, not show)
    
    def show_help(self):
        """显示帮助"""
        help_text = """
<h3>账号阶段管理 - 使用说明</h3>

<h4>功能说明</h4>
<p>通过修改账号的创建时间来改变运行天数和阶段，从而影响任务配置和操作策略。</p>

<h4>阶段划分</h4>
<ul>
<li><b>阶段1 (0-3天)</b>: 新手期 - 任务量少，操作谨慎</li>
<li><b>阶段2 (4-7天)</b>: 适应期 - 增加评论，开始加好友</li>
<li><b>阶段3 (8-15天)</b>: 成长期 - 增加转发，加入小组</li>
<li><b>阶段4 (16-25天)</b>: 稳定期 - 任务量稳定，操作多样化</li>
<li><b>阶段5 (26-45天)</b>: 活跃期 - 任务量达到峰值</li>
<li><b>阶段6 (45天+)</b>: 成熟期 - 维持高活跃度，风险最低</li>
</ul>

<h4>操作步骤</h4>
<ol>
<li>在"修改天数"列输入新的运行天数</li>
<li>点击"✓ 应用"按钮保存修改</li>
<li>系统会自动备份原始创建时间（首次修改时）</li>
<li>如需还原，点击"↶ 还原"按钮</li>
</ol>

<h4>注意事项</h4>
<ul>
<li>修改后立即生效，下次运行任务时使用新阶段</li>
<li>原始创建时间会自动备份，可随时还原</li>
<li>建议根据账号实际情况合理设置阶段</li>
<li>新账号建议从阶段1开始，逐步提升</li>
</ul>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("帮助")
        msg.setTextFormat(Qt.RichText)
        msg.setText(help_text)
        msg.setIcon(QMessageBox.Information)
        
        # 设置深色主题样式
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #0d1117;
                color: #c9d1d9;
            }
            QMessageBox QLabel {
                color: #c9d1d9;
                font-size: 13px;
            }
            QMessageBox QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 16px;
                min-width: 60px;
            }
            QMessageBox QPushButton:hover {
                background-color: #30363d;
            }
            QMessageBox QPushButton:pressed {
                background-color: #161b22;
            }
        """)
        
        msg.exec_()


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 设置全局样式
    app.setStyleSheet("""
        QDialog {
            background-color: #0d1117;
            color: #c9d1d9;
        }
        QPushButton {
            background-color: #21262d;
            color: #c9d1d9;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 14px;
        }
        QPushButton:hover {
            background-color: #30363d;
        }
        QComboBox, QLineEdit, QSpinBox {
            background-color: #0d1117;
            color: #c9d1d9;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 6px;
        }
        QLabel {
            color: #c9d1d9;
        }
    """)
    
    dialog = AccountStageManager()
    dialog.show()
    
    sys.exit(app.exec_())
