"""
Sword Art Online (SAO) Tactical Quota History Chart Widget.
Holographic HUD grid with cyan/orange curves, diamond data markers, and time filters.
Includes full bounds protection and exception shielding for zero-crash painting.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import dateutil.parser

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QLinearGradient, QPen, QBrush, QFont, QPainterPath, QMouseEvent, QPolygonF
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
)

from src.services.history_store import HistoryStore


class SAOHistoryCanvas(QWidget):
    """Draws holographic SAO tactical HUD chart."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setMouseTracking(True)
        self._data: List[Dict[str, Any]] = []
        self._hover_pos: Optional[QPointF] = None
        self._hover_point: Optional[Dict[str, Any]] = None

    def set_data(self, data: List[Dict[str, Any]]):
        self._data = data or []
        self._hover_point = None
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        self._hover_pos = event.position()
        self._find_hover_point()
        self.update()

    def leaveEvent(self, event):
        self._hover_pos = None
        self._hover_point = None
        self.update()

    def _find_hover_point(self):
        if not self._data or not self._hover_pos:
            self._hover_point = None
            return

        w = max(10.0, self.width() - 50.0)
        left_pad = 40.0

        closest_dist = float('inf')
        closest_pt = None

        count = max(1, len(self._data) - 1)
        for i, pt in enumerate(self._data):
            x = left_pad + (i / count) * w
            dist = abs(self._hover_pos.x() - x)
            if dist < closest_dist and dist < 30:
                closest_dist = dist
                closest_pt = pt

        self._hover_point = closest_pt

    def paintEvent(self, event):
        w = float(self.width())
        h = float(self.height())
        if w < 50.0 or h < 50.0:
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            left_pad = 36.0
            right_pad = 14.0
            top_pad = 12.0
            bottom_pad = 22.0

            plot_w = max(10.0, w - left_pad - right_pad)
            plot_h = max(10.0, h - top_pad - bottom_pad)

            # 1. Background (Dark Metallic Plate with border)
            painter.fillRect(QRectF(0, 0, w, h), QColor(10, 14, 22, 230))
            painter.setPen(QPen(QColor(0, 229, 255, 80), 1))
            painter.drawRect(QRectF(1, 1, w - 2, h - 2))

            # 2. Gridlines (Holographic cyan dotted lines)
            grid_pen = QPen(QColor(0, 229, 255, 45), 1, Qt.PenStyle.DashLine)
            text_font = QFont("Segoe UI", 8, QFont.Weight.Bold)
            painter.setFont(text_font)

            for pct in [0, 25, 50, 75, 100]:
                y = top_pad + plot_h - (pct / 100.0) * plot_h
                painter.setPen(grid_pen)
                painter.drawLine(QPointF(left_pad, y), QPointF(left_pad + plot_w, y))

                painter.setPen(QColor(0, 229, 255, 180))
                painter.drawText(QRectF(0, y - 6, left_pad - 4, 12), Qt.AlignmentFlag.AlignRight, f"{pct}%")

            if not self._data:
                painter.setPen(QColor(148, 163, 184))
                painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "NO TACTICAL DATA RECORDED")
                return

            # Separate data by bucket
            buckets_data: Dict[str, List[Dict[str, Any]]] = {}
            for row in self._data:
                bname = row.get("bucket_name", "Default")
                if bname not in buckets_data:
                    buckets_data[bname] = []
                buckets_data[bname].append(row)

            palette = [
                (QColor(0, 229, 255), QColor(0, 229, 255, 50)),   # SAO Cyan
                (QColor(255, 120, 0), QColor(255, 120, 0, 50)),   # SAO Orange
                (QColor(0, 255, 136), QColor(0, 255, 136, 50)),   # SAO Green
            ]

            b_idx = 0
            for bname, points in buckets_data.items():
                line_color, fill_color = palette[b_idx % len(palette)]
                b_idx += 1

                if len(points) == 1:
                    pt = points[0]
                    pct = float(pt.get("percentage", 100.0))
                    cx = left_pad + plot_w / 2.0
                    cy = top_pad + plot_h - (pct / 100.0) * plot_h
                    self._draw_diamond(painter, cx, cy, 4, line_color)
                    continue

                path = QPainterPath()
                fill_path = QPainterPath()

                pts_coords = []
                count = max(1, len(points) - 1)
                for i, pt in enumerate(points):
                    pct = max(0.0, min(100.0, float(pt.get("percentage", 100.0))))
                    x = left_pad + (i / count) * plot_w
                    y = top_pad + plot_h - (pct / 100.0) * plot_h
                    pts_coords.append((x, y))

                path.moveTo(pts_coords[0][0], pts_coords[0][1])
                fill_path.moveTo(pts_coords[0][0], top_pad + plot_h)
                fill_path.lineTo(pts_coords[0][0], pts_coords[0][1])

                for i in range(1, len(pts_coords)):
                    path.lineTo(pts_coords[i][0], pts_coords[i][1])
                    fill_path.lineTo(pts_coords[i][0], pts_coords[i][1])

                fill_path.lineTo(pts_coords[-1][0], top_pad + plot_h)
                fill_path.closeSubpath()

                # Gradient Under Curve
                grad = QLinearGradient(0, top_pad, 0, top_pad + plot_h)
                grad.setColorAt(0.0, fill_color)
                grad.setColorAt(1.0, QColor(0, 0, 0, 0))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(grad))
                painter.drawPath(fill_path)

                # Glowing Line
                painter.setPen(QPen(line_color, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

                # Diamond markers on points
                for x, y in pts_coords:
                    self._draw_diamond(painter, x, y, 3, line_color)

            # Hover Tooltip (SAO Floating System Badge)
            if self._hover_point and self._hover_pos:
                bname = self._hover_point.get("bucket_name", "")
                pct = float(self._hover_point.get("percentage", 0.0))
                t_str = self._hover_point.get("timestamp", "")
                try:
                    dt = dateutil.parser.isoparse(t_str).astimezone()
                    time_fmt = dt.strftime("%H:%M")
                except Exception:
                    time_fmt = str(t_str)

                tip_text = f"◆ {bname.upper()}\nHP: {pct:.1f}% [{time_fmt}]"
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))

                tip_w = 120.0
                tip_h = 36.0
                tip_x = min(w - tip_w - 6.0, max(6.0, self._hover_pos.x() - tip_w / 2.0))
                tip_y = max(6.0, self._hover_pos.y() - tip_h - 10.0)

                # SAO Card Box with Orange Border
                painter.setPen(QPen(QColor(255, 120, 0), 1.2))
                painter.setBrush(QBrush(QColor(16, 22, 32, 245)))
                painter.drawRoundedRect(QRectF(tip_x, tip_y, tip_w, tip_h), 3, 3)

                painter.setPen(QColor(255, 255, 255))
                painter.drawText(QRectF(tip_x + 4, tip_y + 4, tip_w - 8, tip_h - 8), Qt.AlignmentFlag.AlignCenter, tip_text)
        finally:
            painter.end()

    def _draw_diamond(self, painter: QPainter, cx: float, cy: float, radius: float, color: QColor):
        poly = QPolygonF([
            QPointF(cx, cy - radius),
            QPointF(cx + radius, cy),
            QPointF(cx, cy + radius),
            QPointF(cx - radius, cy),
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPolygon(poly)


class HistoryChartWidget(QWidget):
    """SAO Tactical Chart with range selector buttons."""

    def __init__(self, history_store: HistoryStore, parent=None):
        super().__init__(parent)
        self._history_store = history_store
        self._selected_hours = 24
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Top Bar: Title + Range Buttons
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("◆ TACTICAL HUD // HISTORY", self)
        title.setStyleSheet("font-size: 11px; font-weight: 900; color: #00E5FF; letter-spacing: 1px;")
        top_layout.addWidget(title)
        top_layout.addStretch()

        self._btn_group = []
        for hours, label in [(1, "1H"), (6, "6H"), (24, "24H"), (168, "7D")]:
            btn = QPushButton(label, self)
            btn.setFixedHeight(20)
            btn.setFixedWidth(34)
            btn.setStyleSheet(self._btn_style(hours == self._selected_hours))
            btn.clicked.connect(lambda checked, h=hours: self._on_range_clicked(h))
            top_layout.addWidget(btn)
            self._btn_group.append((hours, btn))

        layout.addLayout(top_layout)

        # Chart Canvas
        self._canvas = SAOHistoryCanvas(self)
        layout.addWidget(self._canvas)

    def _btn_style(self, active: bool) -> str:
        if active:
            return "background: #FF7800; color: #FFFFFF; border: 1px solid #FFA500; border-radius: 2px; font-size: 9px; font-weight: 900; letter-spacing: 0.5px;"
        return "background: rgba(22, 29, 43, 0.8); color: #00E5FF; border: 1px solid rgba(0, 229, 255, 0.4); border-radius: 2px; font-size: 9px; font-weight: 700;"

    def _on_range_clicked(self, hours: int):
        self._selected_hours = hours
        for h, btn in self._btn_group:
            btn.setStyleSheet(self._btn_style(h == hours))
        self.refresh_chart()

    def refresh_chart(self):
        try:
            data = self._history_store.get_history(hours=self._selected_hours)
            self._canvas.set_data(data)
        except Exception:
            self._canvas.set_data([])
