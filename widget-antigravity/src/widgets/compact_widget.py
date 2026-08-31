"""
Sword Art Online (SAO) Compact Mini HUD Widget for Antigravity Quota Monitor.
Displays floating mini SAO player HP bar with live health gauges and numeric values.
Includes in-place updates to avoid layout churn and memory leaks.
"""
from typing import Optional, List, Dict
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QMouseEvent, QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGraphicsDropShadowEffect
)

from src.models import QuotaSnapshot, QuotaBucket, QuotaGroup
from src.widgets.progress_bar import SAOHPGauge


class CompactRowWidget(QWidget):
    """Sub-row rendering a single model line in compact HUD."""

    def __init__(self, short_name: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._name_lbl = QLabel(short_name, self)
        self._name_lbl.setStyleSheet("font-size: 10px; color: #FFFFFF; font-weight: 800; letter-spacing: 0.5px;")
        self._name_lbl.setFixedWidth(50)
        layout.addWidget(self._name_lbl)

        self._gauge = SAOHPGauge(self)
        layout.addWidget(self._gauge, 1)

        self._pct_lbl = QLabel("--%", self)
        self._pct_lbl.setStyleSheet("font-size: 11px; font-weight: 900; color: #00FF88;")
        self._pct_lbl.setFixedWidth(32)
        self._pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._pct_lbl)

    def update_bucket(self, bucket: QuotaBucket):
        self._pct_lbl.setText(f"{bucket.percentage_int}%")
        self._pct_lbl.setStyleSheet(f"font-size: 11px; font-weight: 900; color: {bucket.status_color};")
        self._gauge.set_value(bucket.percentage, animate=True)


class CompactWidget(QWidget):
    """Floating mini SAO HUD pill with authentic health gauges."""

    expand_requested = Signal()
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._drag_pos: Optional[QPoint] = None
        self._rows: Dict[str, CompactRowWidget] = {}
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("CompactContainer")
        self.setFixedSize(240, 92)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(4)

        # Header: SAO Icon + Title + Expand Button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        title_lbl = QLabel("⚔ SAO // AG HUD", self)
        title_lbl.setStyleSheet("font-size: 11px; font-weight: 900; color: #00E5FF; letter-spacing: 1px;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        expand_btn = QLabel("⤢", self)
        expand_btn.setToolTip("Expand to Full SAO Monitor")
        expand_btn.setStyleSheet("font-size: 13px; font-weight: 800; color: #FF7800;")
        expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(expand_btn)

        main_layout.addLayout(header_layout)

        # Rows Container
        self._rows_container = QVBoxLayout()
        self._rows_container.setContentsMargins(0, 0, 0, 0)
        self._rows_container.setSpacing(3)
        main_layout.addLayout(self._rows_container)

        # Build initial persistent rows
        self._gemini_row = CompactRowWidget("GEMINI", self)
        self._claude_row = CompactRowWidget("CLAUDE", self)
        self._rows_container.addWidget(self._gemini_row)
        self._rows_container.addWidget(self._claude_row)

        self._status_lbl = QLabel("LINK START...", self)
        self._status_lbl.setStyleSheet("color: #94A3B8; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
        self._status_lbl.setVisible(False)
        self._rows_container.addWidget(self._status_lbl)

        # Holographic Orange Drop Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(255, 120, 0, 140))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

    def update_data(self, snapshot: QuotaSnapshot):
        """Updates compact HUD in-place with latest snapshot data."""
        if not snapshot.is_success:
            self._gemini_row.setVisible(False)
            self._claude_row.setVisible(False)
            self._status_lbl.setText("⚠ SERVER OFFLINE")
            self._status_lbl.setStyleSheet("color: #FF3344; font-size: 10px; font-weight: 800; letter-spacing: 0.5px;")
            self._status_lbl.setVisible(True)
            return

        if not snapshot.groups:
            self._gemini_row.setVisible(False)
            self._claude_row.setVisible(False)
            self._status_lbl.setText("NO DATA")
            self._status_lbl.setStyleSheet("color: #94A3B8; font-size: 10px;")
            self._status_lbl.setVisible(True)
            return

        self._status_lbl.setVisible(False)
        self._gemini_row.setVisible(True)
        self._claude_row.setVisible(True)

        for g in snapshot.groups:
            b = g.five_hour_bucket or (g.buckets[0] if g.buckets else None)
            if not b:
                continue
            if "gemini" in g.display_name.lower():
                self._gemini_row.update_bucket(b)
            else:
                self._claude_row.update_bucket(b)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.expand_requested.emit()
            event.accept()
