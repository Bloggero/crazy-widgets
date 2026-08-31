"""
Sword Art Online (SAO) Style Animated HP / Quota Gauge for Antigravity Quota Monitor.
Features authentic SAO angled chamfered HP bars, level diamonds, segmented ticks,
and health-state color transitions (Green -> Amber -> Red).
Includes safe lifecycle and animation cancellation to prevent access violations.
"""
from PySide6.QtCore import Qt, Property, QPropertyAnimation, QEasingCurve, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QLinearGradient, QBrush, QPen, QFont, QPainterPath, QPolygonF
)
from PySide6.QtWidgets import QWidget, QSizePolicy


class SAOHPGauge(QWidget):
    """Authentic SAO-styled HP / Quota bar with chamfered geometry and glowing health levels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value: float = 0.0
        self._target_value: float = 0.0
        self.setMinimumHeight(10)
        self.setMaximumHeight(14)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Smooth animation
        self._anim = QPropertyAnimation(self, b"animated_value", self)
        self._anim.setDuration(400)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_animated_value(self) -> float:
        return self._value

    def set_animated_value(self, val: float):
        self._value = max(0.0, min(100.0, float(val)))
        self.update()

    animated_value = Property(float, get_animated_value, set_animated_value)

    def set_value(self, target: float, animate: bool = True):
        target = max(0.0, min(100.0, float(target)))
        self._target_value = target
        if animate and self.isVisible():
            if self._anim.state() == QPropertyAnimation.State.Running:
                self._anim.stop()
            self._anim.setStartValue(self._value)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            if self._anim.state() == QPropertyAnimation.State.Running:
                self._anim.stop()
            self._value = target
            self.update()

    def hideEvent(self, event):
        if self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        if self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.stop()
        super().closeEvent(event)

    def _get_health_colors(self, pct: float):
        """Returns SAO HP colors (Green -> Yellow/Amber -> Critical Red)."""
        if pct >= 50.0:
            # Green (High HP)
            start = QColor(0, 225, 120)       # Bright SAO Green
            end = QColor(0, 255, 160)
            glow = QColor(0, 225, 120, 90)
            text_color = QColor(0, 255, 160)
        elif pct >= 20.0:
            # Yellow / Amber (Warning HP)
            start = QColor(255, 180, 0)      # SAO Warning Orange-Yellow
            end = QColor(255, 210, 50)
            glow = QColor(255, 180, 0, 90)
            text_color = QColor(255, 200, 0)
        else:
            # Red (Critical HP)
            start = QColor(255, 40, 50)       # SAO Danger Red
            end = QColor(255, 90, 100)
            glow = QColor(255, 40, 50, 110)
            text_color = QColor(255, 70, 80)
        return start, end, glow, text_color

    def paintEvent(self, event):
        w = float(self.width())
        h = float(self.height())
        if w < 10.0 or h < 4.0:
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Chamfer cut angle on the right edge (iconic SAO angled HP bar)
            chamfer = 6.0
            bar_h = max(2.0, h - 2.0)
            bar_y = 1.0

            # 1. Background Track (Dark metallic slot with subtle border)
            track_path = QPainterPath()
            track_path.moveTo(0, bar_y)
            track_path.lineTo(w - chamfer, bar_y)
            track_path.lineTo(w, bar_y + bar_h)
            track_path.lineTo(0, bar_y + bar_h)
            track_path.lineTo(0, bar_y)
            track_path.closeSubpath()

            # Fill Track
            painter.setPen(QPen(QColor(40, 55, 75, 200), 1.0))
            painter.setBrush(QBrush(QColor(12, 16, 24, 250)))
            painter.drawPath(track_path)

            # 2. Segmented / Filled Health Bar
            fill_ratio = max(0.0, min(1.0, self._value / 100.0))
            if fill_ratio > 0.005:
                fill_w = max(4.0, w * fill_ratio)
                start_col, end_col, glow_col, _ = self._get_health_colors(self._value)

                fill_path = QPainterPath()
                fill_path.moveTo(0, bar_y)
                if fill_w >= w - chamfer:
                    cut = chamfer * (w - fill_w) / chamfer if fill_w < w else chamfer
                    fill_path.lineTo(fill_w - cut, bar_y)
                    fill_path.lineTo(fill_w, bar_y + bar_h)
                else:
                    fill_path.lineTo(fill_w, bar_y)
                    fill_path.lineTo(fill_w, bar_y + bar_h)
                fill_path.lineTo(0, bar_y + bar_h)
                fill_path.lineTo(0, bar_y)
                fill_path.closeSubpath()

                # Outer Glow
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(glow_col))
                painter.drawPath(fill_path)

                # Gradient Bar Fill
                grad = QLinearGradient(0, bar_y, fill_w, bar_y)
                grad.setColorAt(0.0, start_col)
                grad.setColorAt(1.0, end_col)

                painter.setPen(QPen(QColor(255, 255, 255, 100), 0.5))
                painter.setBrush(QBrush(grad))
                painter.drawPath(fill_path)

                # Highlight specular shine on top half
                shine_path = QPainterPath()
                shine_path.moveTo(1, bar_y + 1)
                shine_path.lineTo(max(1, fill_w - 2), bar_y + 1)
                shine_path.lineTo(max(1, fill_w - 2), bar_y + bar_h * 0.45)
                shine_path.lineTo(1, bar_y + bar_h * 0.45)
                shine_path.closeSubpath()

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(255, 255, 255, 90)))
                painter.drawPath(shine_path)

            # 3. SAO Segment Tick Marks across the bar (every 25%)
            painter.setPen(QPen(QColor(10, 14, 20, 220), 1.2))
            for tick in [0.25, 0.50, 0.75]:
                tx = w * tick
                painter.drawLine(int(tx), int(bar_y), int(tx), int(bar_y + bar_h))
        finally:
            painter.end()
