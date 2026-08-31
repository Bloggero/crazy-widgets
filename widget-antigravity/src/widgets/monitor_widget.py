"""
Main Desktop Floating Monitor Widget for Antigravity Quota Monitor (SAO Master Edition).
Renders the 2 Model Groups (Gemini Models & Claude/GPT Models) with Weekly & 5-Hour Limits.
Features in-place updates, smooth transitions, and multi-monitor coordinate resilience.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple

from PySide6.QtCore import Qt, Signal, QPoint, QSize, QTimer
from PySide6.QtGui import (
    QMouseEvent, QColor, QFont, QIcon, QPainter, QLinearGradient, QBrush, QPen
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGraphicsDropShadowEffect, QSizePolicy, QSizeGrip
)

from src.models import QuotaSnapshot, QuotaGroup, QuotaBucket, UserInfo
from src.services.config_manager import ConfigManager
from src.services.history_store import HistoryStore
from src.services.logger import get_logger
from src.widgets.progress_bar import SAOHPGauge
from src.widgets.history_chart import HistoryChartWidget


class SAOLimitRow(QWidget):
    """Sub-row rendering a specific limit (Weekly or 5-Hour) with in-place HP Gauge updates."""

    def __init__(self, bucket: QuotaBucket, parent=None):
        super().__init__(parent)
        self._bucket = bucket
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 4)
        layout.setSpacing(3)

        # 1. Info Row
        info_row = QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)
        info_row.setSpacing(6)

        is_weekly = self._bucket.window == "weekly"
        title_text = "WEEKLY LIMIT" if is_weekly else "5-HOUR LIMIT"
        self._title_lbl = QLabel(title_text, self)
        self._title_lbl.setStyleSheet("font-size: 10px; font-weight: 800; color: #CBD5E1; letter-spacing: 0.5px; background: transparent;")
        info_row.addWidget(self._title_lbl, 1)

        # Percentage
        self._pct_lbl = QLabel(f"{self._bucket.percentage_int}%", self)
        self._pct_lbl.setStyleSheet(f"font-size: 13px; font-weight: 900; color: {self._bucket.status_color}; background: transparent;")
        info_row.addWidget(self._pct_lbl, 0)

        # SAO Level Badge
        status_text = "NORMAL" if self._bucket.status_level == "normal" else ("CAUTION" if self._bucket.status_level == "warning" else "CRITICAL")
        badge_class = "BadgeNormal" if self._bucket.status_level == "normal" else ("BadgeWarning" if self._bucket.status_level == "warning" else "BadgeCritical")
        self._status_badge = QLabel(status_text, self)
        self._status_badge.setProperty("class", badge_class)
        info_row.addWidget(self._status_badge, 0)

        # Reset Countdown
        self._reset_lbl = QLabel("", self)
        self._reset_lbl.setProperty("class", "BucketReset")
        reset_text = self._bucket.time_until_reset()
        if reset_text:
            self._reset_lbl.setText(f"⏳ {reset_text.upper()}")
            self._reset_lbl.setVisible(True)
        else:
            self._reset_lbl.setVisible(False)
        info_row.addWidget(self._reset_lbl, 0)

        layout.addLayout(info_row)

        # 2. SAO Chamfered HP Gauge Bar
        self._hp_gauge = SAOHPGauge(self)
        self._hp_gauge.set_value(self._bucket.percentage, animate=False)
        layout.addWidget(self._hp_gauge)

    def update_bucket(self, bucket: QuotaBucket):
        """Updates row data in place with smooth animation."""
        self._bucket = bucket
        self._pct_lbl.setText(f"{bucket.percentage_int}%")
        self._pct_lbl.setStyleSheet(f"font-size: 13px; font-weight: 900; color: {bucket.status_color}; background: transparent;")

        status_text = "NORMAL" if bucket.status_level == "normal" else ("CAUTION" if bucket.status_level == "warning" else "CRITICAL")
        badge_class = "BadgeNormal" if bucket.status_level == "normal" else ("BadgeWarning" if bucket.status_level == "warning" else "BadgeCritical")
        self._status_badge.setText(status_text)
        self._status_badge.setProperty("class", badge_class)
        self._status_badge.style().unpolish(self._status_badge)
        self._status_badge.style().polish(self._status_badge)

        reset_text = bucket.time_until_reset()
        if reset_text:
            self._reset_lbl.setText(f"⏳ {reset_text.upper()}")
            self._reset_lbl.setVisible(True)
        else:
            self._reset_lbl.setVisible(False)

        self._hp_gauge.set_value(bucket.percentage, animate=True)


class SAOGroupCard(QFrame):
    """SAO HUD Card representing a Model Group containing Weekly & 5H Gauges."""

    def __init__(self, group: QuotaGroup, parent=None):
        super().__init__(parent)
        self.setObjectName("BucketCard")
        self.setProperty("class", "BucketCard")
        self._group = group
        self._row_widgets: List[SAOLimitRow] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # Group Header
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self._title_lbl = QLabel(f"◆ {self._group.display_name.upper()}", self)
        self._title_lbl.setStyleSheet("font-size: 12px; font-weight: 900; color: #FFFFFF; letter-spacing: 0.8px; background: transparent;")
        header_row.addWidget(self._title_lbl, 1)

        # Model Info Tooltip Tag
        models_tag = QLabel("SHARED POOL", self)
        models_tag.setStyleSheet("font-size: 9px; font-weight: 800; color: #00E5FF; background-color: #0E1E2B; border: 1px solid #00E5FF; border-radius: 2px; padding: 1px 5px;")
        models_tag.setToolTip(self._group.description)
        header_row.addWidget(models_tag, 0)

        layout.addLayout(header_row)

        # Add Weekly and 5-Hour Limit Rows
        for bucket in self._group.buckets:
            row_widget = SAOLimitRow(bucket, self)
            self._row_widgets.append(row_widget)
            layout.addWidget(row_widget)

    def update_group(self, group: QuotaGroup):
        """Updates all bucket rows in place without rebuilding DOM/layout."""
        self._group = group
        self._title_lbl.setText(f"◆ {group.display_name.upper()}")
        for i, bucket in enumerate(group.buckets):
            if i < len(self._row_widgets):
                self._row_widgets[i].update_bucket(bucket)


class MonitorWidget(QWidget):
    """Sword Art Online (SAO) Styled Floating Quota Monitor (Zero Scroll)."""

    refresh_requested = Signal()
    settings_requested = Signal()
    compact_requested = Signal()
    close_requested = Signal()

    def __init__(self, config_manager: ConfigManager, history_store: HistoryStore, parent=None):
        super().__init__(parent)
        self._logger = get_logger()
        self._config = config_manager
        self._history_store = history_store
        self._drag_pos: Optional[QPoint] = None
        self._last_snapshot: Optional[QuotaSnapshot] = None
        self._show_history = False
        self._group_cards: Dict[str, SAOGroupCard] = {}

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumWidth(380)

        # Multi-monitor safe initial placement
        saved_x = self._config.get("window_x")
        saved_y = self._config.get("window_y")
        safe_x, safe_y = self._config.sanitize_coordinates(saved_x, saved_y, 420, 530)
        self.move(safe_x, safe_y)

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(0)

        # Container Frame (Aincrad HUD Plate)
        self._container = QFrame(self)
        self._container.setObjectName("MainContainer")
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # 1. SAO Header Bar (Draggable)
        self._header = QFrame(self._container)
        self._header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(10, 6, 8, 6)
        header_layout.setSpacing(6)

        title_lbl = QLabel("⚔ SAO // AG QUOTA MONITOR", self._header)
        title_lbl.setObjectName("AppTitle")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        # Action Buttons
        self._history_btn = QPushButton("📊", self._header)
        self._history_btn.setObjectName("HeaderBtn")
        self._history_btn.setToolTip("SAO Tactical Quota Chart")
        self._history_btn.setFixedSize(24, 24)
        self._history_btn.clicked.connect(self._toggle_history_chart)
        header_layout.addWidget(self._history_btn)

        compact_btn = QPushButton("🗗", self._header)
        compact_btn.setObjectName("HeaderBtn")
        compact_btn.setToolTip("Switch to Mini HUD Pill")
        compact_btn.setFixedSize(24, 24)
        compact_btn.clicked.connect(self.compact_requested.emit)
        header_layout.addWidget(compact_btn)

        settings_btn = QPushButton("⚙", self._header)
        settings_btn.setObjectName("HeaderBtn")
        settings_btn.setToolTip("SAO System Settings")
        settings_btn.setFixedSize(24, 24)
        settings_btn.clicked.connect(self.settings_requested.emit)
        header_layout.addWidget(settings_btn)

        min_btn = QPushButton("—", self._header)
        min_btn.setObjectName("HeaderBtn")
        min_btn.setToolTip("Minimize to Tray")
        min_btn.setFixedSize(24, 24)
        min_btn.clicked.connect(self.hide)
        header_layout.addWidget(min_btn)

        close_btn = QPushButton("✕", self._header)
        close_btn.setObjectName("CloseBtn")
        close_btn.setToolTip("Close Monitor")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.close_requested.emit)
        header_layout.addWidget(close_btn)

        container_layout.addWidget(self._header)

        # 2. SAO Player Info Bar
        self._user_bar = QFrame(self._container)
        self._user_bar.setObjectName("UserBar")
        user_layout = QHBoxLayout(self._user_bar)
        user_layout.setContentsMargins(10, 4, 10, 4)
        user_layout.setSpacing(6)

        self._user_lbl = QLabel("PLAYER: CONNECTING...", self._user_bar)
        self._user_lbl.setObjectName("UserNameLabel")
        user_layout.addWidget(self._user_lbl, 1)

        self._tier_badge = QLabel("[LV. 99 // PRO]", self._user_bar)
        self._tier_badge.setObjectName("TierBadge")
        user_layout.addWidget(self._tier_badge, 0)

        container_layout.addWidget(self._user_bar)

        # 3. SAO Warning Banner
        self._error_banner = QFrame(self._container)
        self._error_banner.setObjectName("ErrorBanner")
        err_layout = QHBoxLayout(self._error_banner)
        err_layout.setContentsMargins(8, 6, 8, 6)
        self._err_lbl = QLabel("", self._error_banner)
        self._err_lbl.setWordWrap(True)
        err_layout.addWidget(self._err_lbl)
        self._error_banner.setVisible(False)
        container_layout.addWidget(self._error_banner)

        # 4. Direct Cards Container (Zero Scroll)
        self._cards_container = QWidget(self._container)
        self._cards_container.setObjectName("CardsContainer")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(8, 6, 8, 6)
        self._cards_layout.setSpacing(6)
        container_layout.addWidget(self._cards_container)

        # 5. History Chart Widget
        self._chart_widget = HistoryChartWidget(self._history_store, self._container)
        self._chart_widget.setVisible(False)
        container_layout.addWidget(self._chart_widget)

        # 6. SAO Footer Bar: Clock + Sync Now Button
        self._footer = QFrame(self._container)
        self._footer.setObjectName("FooterBar")
        footer_layout = QHBoxLayout(self._footer)
        footer_layout.setContentsMargins(10, 6, 10, 6)
        footer_layout.setSpacing(8)

        status_vbox = QVBoxLayout()
        status_vbox.setSpacing(1)
        self._last_update_lbl = QLabel("SYS CLOCK: [--:--:--]", self._footer)
        self._last_update_lbl.setStyleSheet("font-size: 10px; font-weight: 800; color: #94A3B8; letter-spacing: 0.5px; background: transparent;")
        status_vbox.addWidget(self._last_update_lbl)

        self._next_update_lbl = QLabel("NEXT SYNC: [5M 00S]", self._footer)
        self._next_update_lbl.setStyleSheet("font-size: 10px; font-weight: 800; color: #00E5FF; letter-spacing: 0.5px; background: transparent;")
        status_vbox.addWidget(self._next_update_lbl)

        footer_layout.addLayout(status_vbox, 1)

        # SAO Orange Sync Button
        self._refresh_btn = QPushButton("↻ SYNC NOW", self._footer)
        self._refresh_btn.setObjectName("SyncBtn")
        self._refresh_btn.setProperty("class", "PrimaryBtn")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        footer_layout.addWidget(self._refresh_btn, 0)

        # Resize grip
        size_grip = QSizeGrip(self._footer)
        size_grip.setFixedSize(12, 12)
        footer_layout.addWidget(size_grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        container_layout.addWidget(self._footer)

        main_layout.addWidget(self._container)

        # Holographic Cyan Drop Shadow Effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 229, 255, 140))
        shadow.setOffset(0, 3)
        self._container.setGraphicsEffect(shadow)

    def _toggle_history_chart(self):
        self._show_history = not self._show_history
        self._chart_widget.setVisible(self._show_history)
        if self._show_history:
            self._chart_widget.refresh_chart()
            self._history_btn.setStyleSheet("background-color: #FF7800; border-color: #FFA500; color: #FFFFFF;")
        else:
            self._history_btn.setStyleSheet("")
        self.adjustSize()

    def _clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                sub_layout = item.layout()
                if sub_layout is not None:
                    self._clear_layout(sub_layout)

    def _on_refresh_clicked(self):
        self._refresh_btn.setText("↻ SYNCING...")
        self._refresh_btn.setEnabled(False)
        self.refresh_requested.emit()

    def update_data(self, snapshot: QuotaSnapshot):
        """Renders official quota summary data onto SAO UI with in-place updates."""
        self._last_snapshot = snapshot

        # User Profile
        if snapshot.user_info and snapshot.user_info.name:
            plan = snapshot.user_info.plan_name or "Pro"
            self._user_lbl.setText(f"⚔ PLAYER: {snapshot.user_info.name.upper()}")
            self._tier_badge.setText(f"[LV. 99 // {plan.upper()}]")
            self._user_bar.setVisible(True)
        else:
            self._user_bar.setVisible(False)

        # Error State
        if not snapshot.is_success:
            self._error_banner.setVisible(True)
            self._err_lbl.setText(f"⚠ SYSTEM ALERT // {snapshot.error_message}")
        else:
            self._error_banner.setVisible(False)

        # Check if we can update cards in-place without tearing down layouts
        incoming_keys = [g.display_name for g in snapshot.groups]
        existing_keys = list(self._group_cards.keys())

        if snapshot.groups and incoming_keys == existing_keys:
            # Safe in-place update
            for g in snapshot.groups:
                card = self._group_cards.get(g.display_name)
                if card:
                    card.update_group(g)
        else:
            # Rebuild cards only when structure changes
            self._clear_layout(self._cards_layout)
            self._group_cards.clear()

            if snapshot.groups:
                for g in snapshot.groups:
                    card = SAOGroupCard(g, self._cards_container)
                    self._group_cards[g.display_name] = card
                    self._cards_layout.addWidget(card)
            elif not snapshot.is_success:
                empty_lbl = QLabel("AINCRAD SERVER OFFLINE\nOpen Antigravity IDE to establish link.", self._cards_container)
                empty_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 700; padding: 14px 0; letter-spacing: 0.5px;")
                empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._cards_layout.addWidget(empty_lbl)

        if self._show_history:
            self._chart_widget.refresh_chart()

        self.adjustSize()

    def set_system_time(self, time_str: str):
        """Updates live SYS CLOCK text."""
        self._last_update_lbl.setText(f"SYS CLOCK: [{time_str}]")

    def set_next_update_countdown(self, seconds_remaining: int, is_syncing: bool = False):
        """Updates live NEXT SYNC countdown text."""
        if is_syncing:
            self._next_update_lbl.setText("NEXT SYNC: [SYNCING...]")
            return

        mins = seconds_remaining // 60
        secs = seconds_remaining % 60
        if mins > 0:
            self._next_update_lbl.setText(f"NEXT SYNC: [{mins}M {secs:02d}S]")
        else:
            self._next_update_lbl.setText(f"NEXT SYNC: [{secs}S]")

    def set_syncing_state(self, is_syncing: bool):
        """Updates the sync button text and enabled state."""
        if is_syncing:
            self._refresh_btn.setText("↻ SYNCING...")
            self._refresh_btn.setEnabled(False)
        else:
            self._refresh_btn.setText("↻ SYNC NOW")
            self._refresh_btn.setEnabled(True)

    # Mouse Drag Handling
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._header.geometry().contains(event.position().toPoint()):
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        pos = self.pos()
        size = self.size()
        self._config.save_window_geometry(pos.x(), pos.y(), size.width(), size.height())
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        pos = self.pos()
        size = self.size()
        self._config.save_window_geometry(pos.x(), pos.y(), size.width(), size.height())
