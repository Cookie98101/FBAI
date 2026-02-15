"""
3D旋转地球组件
使用PyQt5绘制动态旋转的地球，展示国际化风格
"""
import math
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QPainter, QColor, QRadialGradient, QPen, QBrush, QLinearGradient, QPainterPath


class RotatingGlobe(QWidget):
    """动态旋转的3D地球组件"""
    
    def __init__(self, parent=None, size=200):
        super().__init__(parent)
        self.size = size
        self.setFixedSize(size, size)
        
        # 旋转角度
        self.rotation_angle = 0
        
        # 地球参数
        self.radius = size * 0.4  # 地球半径
        self.center_x = size / 2
        self.center_y = size / 2
        
        # 经纬线参数
        self.num_meridians = 8   # 经线数量（优化：从12减少到8）
        self.num_parallels = 6   # 纬线数量（优化：从8减少到6）
        
        # 大陆轮廓点（简化版世界地图）
        self.continents = self._create_continents()
        
        # 可见性标志（优化：窗口隐藏时停止动画）
        self.is_visible = True
        
        # 启动动画定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_rotation)
        self.timer.start(33)  # 30 FPS（优化：从20ms改为33ms，降低CPU占用）
        
    def _create_continents(self):
        """创建简化的大陆轮廓数据"""
        continents = []
        
        # 非洲（简化）
        africa = [
            (20, 0), (30, -10), (35, -20), (30, -30), (20, -35),
            (10, -30), (5, -20), (10, -10), (15, 0)
        ]
        continents.append(africa)
        
        # 欧洲（简化）
        europe = [
            (-10, 40), (0, 45), (10, 43), (15, 35), (10, 30),
            (0, 32), (-10, 35)
        ]
        continents.append(europe)
        
        # 亚洲（简化）
        asia = [
            (20, 30), (40, 35), (60, 30), (70, 20), (75, 10),
            (70, 0), (60, -5), (50, 0), (40, 10), (30, 20)
        ]
        continents.append(asia)
        
        # 北美洲（简化）
        north_america = [
            (-120, 60), (-110, 65), (-100, 68), (-80, 65), (-70, 55),
            (-75, 45), (-85, 35), (-95, 30), (-110, 35), (-120, 50)
        ]
        continents.append(north_america)
        
        # 南美洲（简化）
        south_america = [
            (-70, 10), (-60, 5), (-55, -10), (-58, -25), (-65, -35),
            (-70, -30), (-75, -20), (-73, -5)
        ]
        continents.append(south_america)
        
        # 澳大利亚（简化）
        australia = [
            (120, -15), (135, -12), (145, -18), (150, -28), (145, -35),
            (130, -32), (120, -25)
        ]
        continents.append(australia)
        
        return continents
    
    def update_rotation(self):
        """更新旋转角度"""
        # 优化：只在可见时更新
        if not self.is_visible:
            return
        
        self.rotation_angle += 1.0  # 旋转速度 - 更快的旋转
        if self.rotation_angle >= 360:
            self.rotation_angle -= 360
        self.update()
    
    def showEvent(self, event):
        """窗口显示时启动动画"""
        super().showEvent(event)
        self.is_visible = True
        if hasattr(self, 'timer') and not self.timer.isActive():
            self.timer.start(33)
    
    def hideEvent(self, event):
        """窗口隐藏时停止动画"""
        super().hideEvent(event)
        self.is_visible = False
        if hasattr(self, 'timer'):
            self.timer.stop()
    
    def project_3d_to_2d(self, lon, lat):
        """
        将经纬度坐标投影到2D平面（正射投影）
        lon: 经度（-180到180）
        lat: 纬度（-90到90）
        返回: (x, y, visible) - visible表示是否在可见半球
        """
        # 考虑旋转角度
        lon_rad = math.radians(lon + self.rotation_angle)
        lat_rad = math.radians(lat)
        
        # 正射投影
        x = self.radius * math.cos(lat_rad) * math.sin(lon_rad)
        y = -self.radius * math.sin(lat_rad)
        
        # 判断是否在可见半球（前半球）
        z = self.radius * math.cos(lat_rad) * math.cos(lon_rad)
        visible = z >= 0
        
        # 转换到窗口坐标
        x += self.center_x
        y += self.center_y
        
        return x, y, visible
    
    def draw_meridian(self, painter, longitude):
        """绘制一条经线"""
        points = []
        visible_points = []
        
        # 从北极到南极
        for lat in range(-90, 91, 5):
            x, y, visible = self.project_3d_to_2d(longitude, lat)
            points.append((x, y, visible))
        
        # 绘制可见的线段
        path = QPainterPath()
        drawing = False
        
        for i, (x, y, visible) in enumerate(points):
            if visible:
                if not drawing:
                    path.moveTo(x, y)
                    drawing = True
                else:
                    path.lineTo(x, y)
            else:
                drawing = False
        
        painter.drawPath(path)
    
    def draw_parallel(self, painter, latitude):
        """绘制一条纬线"""
        points = []
        
        # 绕地球一圈
        for lon in range(-180, 181, 5):
            x, y, visible = self.project_3d_to_2d(lon, latitude)
            if visible:
                points.append((x, y))
        
        # 绘制可见的圆弧
        if len(points) > 1:
            path = QPainterPath()
            path.moveTo(points[0][0], points[0][1])
            for x, y in points[1:]:
                path.lineTo(x, y)
            painter.drawPath(path)
    
    def draw_continent(self, painter, continent_points):
        """绘制大陆轮廓"""
        visible_segments = []
        
        # 投影所有点
        projected = []
        for lon, lat in continent_points:
            x, y, visible = self.project_3d_to_2d(lon, lat)
            projected.append((x, y, visible))
        
        # 绘制可见的线段
        path = QPainterPath()
        drawing = False
        
        for i in range(len(projected)):
            x, y, visible = projected[i]
            if visible:
                if not drawing:
                    path.moveTo(x, y)
                    drawing = True
                else:
                    path.lineTo(x, y)
            else:
                drawing = False
        
        # 闭合路径（如果需要）
        if drawing and len(projected) > 0:
            x0, y0, v0 = projected[0]
            if v0:
                path.lineTo(x0, y0)
        
        painter.drawPath(path)
    
    def paintEvent(self, event):
        """绘制地球"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景阴影
        shadow_gradient = QRadialGradient(
            self.center_x + 5, self.center_y + 5, self.radius * 1.2
        )
        shadow_gradient.setColorAt(0, QColor(0, 0, 0, 80))
        shadow_gradient.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(shadow_gradient))
        painter.drawEllipse(
            int(self.center_x - self.radius + 5),
            int(self.center_y - self.radius + 5),
            int(self.radius * 2),
            int(self.radius * 2)
        )
        
        # 绘制地球球体（海洋 - 深色调，接近背景色）
        ocean_gradient = QRadialGradient(
            self.center_x - self.radius * 0.3,
            self.center_y - self.radius * 0.3,
            self.radius * 1.5
        )
        ocean_gradient.setColorAt(0, QColor(25, 35, 50, 200))    # 深蓝灰色
        ocean_gradient.setColorAt(0.7, QColor(15, 25, 40, 220))  # 更深的蓝灰色
        ocean_gradient.setColorAt(1, QColor(10, 18, 28, 240))    # 接近背景色的深色
        
        painter.setBrush(QBrush(ocean_gradient))
        painter.setPen(QPen(QColor(40, 60, 80, 150), 2))
        painter.drawEllipse(
            int(self.center_x - self.radius),
            int(self.center_y - self.radius),
            int(self.radius * 2),
            int(self.radius * 2)
        )
        
        # 绘制经线（更淡）
        painter.setPen(QPen(QColor(255, 255, 255, 25), 1))
        for i in range(self.num_meridians):
            longitude = -180 + (360 / self.num_meridians) * i
            self.draw_meridian(painter, longitude)
        
        # 绘制纬线（更淡）
        for i in range(1, self.num_parallels):
            latitude = -90 + (180 / self.num_parallels) * i
            self.draw_parallel(painter, latitude)
        
        # 绘制赤道（稍微明显一点）
        painter.setPen(QPen(QColor(255, 255, 255, 50), 2))
        self.draw_parallel(painter, 0)
        
        # 绘制大陆（深绿色，更低调）
        painter.setPen(QPen(QColor(25, 80, 50, 180), 2))
        painter.setBrush(QBrush(QColor(30, 90, 60, 150)))
        
        for continent in self.continents:
            self.draw_continent(painter, continent)
        
        # 绘制高光效果（更柔和）
        highlight_gradient = QRadialGradient(
            self.center_x - self.radius * 0.4,
            self.center_y - self.radius * 0.4,
            self.radius * 0.6
        )
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 30))
        highlight_gradient.setColorAt(0.5, QColor(255, 255, 255, 10))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(highlight_gradient))
        painter.drawEllipse(
            int(self.center_x - self.radius),
            int(self.center_y - self.radius),
            int(self.radius * 2),
            int(self.radius * 2)
        )
        
        # 绘制外发光效果（更柔和）
        glow_gradient = QRadialGradient(
            self.center_x, self.center_y, self.radius * 1.3
        )
        glow_gradient.setColorAt(0, QColor(88, 166, 255, 0))
        glow_gradient.setColorAt(0.85, QColor(88, 166, 255, 0))
        glow_gradient.setColorAt(0.95, QColor(88, 166, 255, 35))
        glow_gradient.setColorAt(1, QColor(88, 166, 255, 0))
        
        painter.setBrush(QBrush(glow_gradient))
        painter.drawEllipse(
            int(self.center_x - self.radius * 1.3),
            int(self.center_y - self.radius * 1.3),
            int(self.radius * 2.6),
            int(self.radius * 2.6)
        )

