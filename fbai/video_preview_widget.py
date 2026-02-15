from PyQt5.QtWidgets import QLabel, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy, QGroupBox
from PyQt5.QtCore import Qt


class VideoPreviewWidget(QWidget):
    """自定义视频预览控件，保持9:16的竖版比例"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置策略以填充可用空间
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建标签
        self.label = QLabel("视频预览区域\n(视频生成后将在此显示)")
        self.label.setAlignment(Qt.AlignCenter)
        # 启用鼠标事件接收
        self.label.setAttribute(Qt.WA_Hover, True)
        self.label.setMouseTracking(True)
        self.label.setStyleSheet("""
            color: #8b949e;
            background-color: #161b22;
            border: 1px dashed #30363d;
            border-radius: 10px;
            padding: 20px;
        """)
        
        # 设置鼠标光标为手型，表示可点击
        self.label.setCursor(Qt.PointingHandCursor)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        main_layout.addWidget(self.label)
        
        self.setMinimumHeight(300)  # 确保最小高度为300像素
        
    def resizeEvent(self, event):
        """重写resizeEvent以保持9:16的比例"""
        super().resizeEvent(event)
        # 移除固定尺寸限制，让控件自然填充可用空间
        # self.update_preview_size()
        
    def update_preview_size(self):
        """根据自身尺寸更新预览区域尺寸，保持9:16比例"""
        # 获取当前控件的尺寸
        width = self.width()
        height = self.height()
        
        # 计算保持9:16比例的尺寸
        # 9:16 = width:height
        ideal_height = int(width * 16 / 9)
        ideal_width = int(height * 9 / 16)
        
        # 确保最小高度为300像素
        if ideal_height < 300:
            target_height = 300
            target_width = int(target_height * 9 / 16)
        else:
            # 选择合适的尺寸以保持比例并适应容器
            if ideal_height <= height:
                # 使用当前宽度，调整高度以保持9:16比例
                target_width = width
                target_height = ideal_height
            else:
                # 使用当前高度，调整宽度以保持9:16比例
                target_width = ideal_width
                target_height = height
            
        # 设置控件本身的尺寸
        self.setFixedSize(target_width, target_height)
            
    def setText(self, text):
        """设置显示文本"""
        self.label.setText(text)
        # 更新文本后重新设置光标
        self.label.setCursor(Qt.PointingHandCursor)
    
    def set_click_callback(self, callback):
        """设置点击回调函数"""
        self.click_callback = callback
    
    def mousePressEvent(self, event):
        """处理鼠标点击事件"""
        print("🖱️ VideoPreviewWidget 被点击")
        if hasattr(self, 'click_callback') and self.click_callback:
            self.click_callback()
        super().mousePressEvent(event)


class VideoPreviewContainer(QWidget):
    """视频预览容器，保持整个预览栏9:16比例"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建GroupBox
        self.group_box = QGroupBox("视频预览")
        self.group_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.group_box.setStyleSheet("QGroupBox { background-color: #0d1117; border: 1px solid #30363d; border-radius: 8px; margin-top: 1ex; padding-top: 15px; font-size: 14px; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 8px 0 8px; color: #58a6ff; }")
        group_layout = QVBoxLayout(self.group_box)
        group_layout.setContentsMargins(6, 6, 6, 6)
        group_layout.setSpacing(0)
        
        # 创建预览控件
        self.preview_widget = VideoPreviewWidget()
        self.preview_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        group_layout.addWidget(self.preview_widget)
        
        main_layout.addWidget(self.group_box)
        
        self.setMinimumHeight(300)
        
    def resizeEvent(self, event):
        """重写resizeEvent以保持9:16的比例"""
        super().resizeEvent(event)
        # 不再限制容器尺寸，让其自然填充可用空间
        # self.update_container_size()
        
    def update_container_size(self):
        """根据自身尺寸更新容器尺寸，保持9:16比例"""
        # 获取当前控件的尺寸
        width = self.width()
        height = self.height()
        
        # 计算保持9:16比例的尺寸
        # 9:16 = width:height
        ideal_height = int(width * 16 / 9)
        ideal_width = int(height * 9 / 16)
        
        # 确保最小高度为300像素
        if ideal_height < 300:
            target_height = 300
            target_width = int(target_height * 9 / 16)
        else:
            # 选择合适的尺寸以保持比例并适应容器
            if ideal_height <= height:
                # 使用当前宽度，调整高度以保持9:16比例
                target_width = width
                target_height = ideal_height
            else:
                # 使用当前高度，调整宽度以保持9:16比例
                target_width = ideal_width
                target_height = height
            
        # 设置控件本身的尺寸
        self.setFixedSize(target_width, target_height)
            
    def setText(self, text):
        """设置显示文本"""
        self.preview_widget.setText(text)
    
    def set_click_callback(self, callback):
        """设置点击回调函数"""
        self.preview_widget.set_click_callback(callback)