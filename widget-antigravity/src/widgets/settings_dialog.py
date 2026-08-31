"""
Sword Art Online (SAO) System Configuration Dialog.
Aincrad-styled modal with cyan border, metallic obsidian plate, and orange actions.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QSlider,
    QSpinBox, QComboBox, QPushButton, QGroupBox, QFrame
)

from src.services.config_manager import ConfigManager


class SettingsDialog(QDialog):
    """SAO System Configuration dialog."""

    settings_changed = Signal()
    reset_position_requested = Signal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self._config = config_manager
        self.setWindowTitle("SAO // SYSTEM CONFIGURATION")
        self.setFixedSize(390, 490)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # 1. Update Interval Group
        interval_group = QGroupBox("[01] // AUTO-SYNC INTERVAL", self)
        interval_layout = QVBoxLayout(interval_group)
        interval_layout.setSpacing(8)

        int_row = QHBoxLayout()
        int_lbl = QLabel("SYNC CYCLE:", interval_group)
        int_lbl.setStyleSheet("font-weight: 700; font-size: 11px; color: #CBD5E1;")
        int_row.addWidget(int_lbl)
        self._interval_combo = QComboBox(interval_group)
        self._interval_combo.setStyleSheet("""
            QComboBox {
                background-color: #141B27;
                border: 1px solid #00E5FF;
                border-radius: 3px;
                padding: 4px 8px;
                color: #FFFFFF;
                font-weight: 800;
                font-size: 11px;
            }
            QComboBox:focus, QComboBox:on {
                border-color: #FF7800;
            }
            QComboBox QAbstractItemView {
                background-color: #0C1017;
                border: 2px solid #00E5FF;
                color: #FFFFFF;
                selection-background-color: #FF7800;
                selection-color: #FFFFFF;
                font-weight: 800;
                font-size: 11px;
                padding: 4px;
                outline: 0;
            }
            QComboBox QAbstractItemView::item {
                background-color: #0C1017;
                color: #FFFFFF;
                min-height: 26px;
                padding-left: 6px;
            }
            QComboBox QAbstractItemView::item:hover, QComboBox QAbstractItemView::item:selected {
                background-color: #FF7800;
                color: #FFFFFF;
            }
        """)
        from PySide6.QtWidgets import QListView
        list_view = QListView(self._interval_combo)
        list_view.setStyleSheet("background-color: #0C1017; color: #FFFFFF; selection-background-color: #FF7800; selection-color: #FFFFFF;")
        self._interval_combo.setView(list_view)

        self._intervals = [
            ("15 SECONDS (ULTRA-FAST)", 15),
            ("30 SECONDS (FAST)", 30),
            ("1 MINUTE", 60),
            ("2 MINUTES", 120),
            ("5 MINUTES (RECOMMENDED)", 300),
            ("10 MINUTES", 600),
        ]
        for text, sec in self._intervals:
            self._interval_combo.addItem(text, sec)

        current_sec = self._config.update_interval_sec
        for i, (_, sec) in enumerate(self._intervals):
            if sec == current_sec:
                self._interval_combo.setCurrentIndex(i)
                break

        int_row.addWidget(self._interval_combo)
        interval_layout.addLayout(int_row)
        main_layout.addWidget(interval_group)

        # 2. Window Behavior Group
        window_group = QGroupBox("[02] // HUD DISPLAY & BEHAVIOR", self)
        window_layout = QVBoxLayout(window_group)
        window_layout.setSpacing(10)

        self._always_on_top_cb = QCheckBox("ALWAYS ON TOP // PIN HUD OVER APPS", window_group)
        self._always_on_top_cb.setChecked(self._config.always_on_top)
        window_layout.addWidget(self._always_on_top_cb)

        self._compact_mode_cb = QCheckBox("START IN COMPACT HUD PILL MODE", window_group)
        self._compact_mode_cb.setChecked(self._config.compact_mode)
        window_layout.addWidget(self._compact_mode_cb)

        # Opacity Slider
        opacity_row = QHBoxLayout()
        opacity_lbl = QLabel("HOLO OPACITY:", window_group)
        opacity_lbl.setStyleSheet("font-weight: 700; font-size: 11px; color: #CBD5E1;")
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal, window_group)
        self._opacity_slider.setRange(50, 100)
        self._opacity_slider.setValue(int(self._config.opacity * 100))
        self._opacity_val_lbl = QLabel(f"{int(self._config.opacity * 100)}%", window_group)
        self._opacity_val_lbl.setStyleSheet("font-weight: 800; color: #00E5FF;")
        self._opacity_val_lbl.setFixedWidth(38)

        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_val_lbl.setText(f"{v}%")
        )

        opacity_row.addWidget(opacity_lbl)
        opacity_row.addWidget(self._opacity_slider)
        opacity_row.addWidget(self._opacity_val_lbl)
        window_layout.addLayout(opacity_row)

        main_layout.addWidget(window_group)

        # 3. System Integration Group
        system_group = QGroupBox("[03] // SYSTEM INTEGRATION", self)
        system_layout = QVBoxLayout(system_group)
        system_layout.setSpacing(10)

        self._start_windows_cb = QCheckBox("AUTO-LINK ON WINDOWS BOOT", system_group)
        self._start_windows_cb.setChecked(self._config.start_with_windows)
        system_layout.addWidget(self._start_windows_cb)

        reset_pos_btn = QPushButton("◆ RE-CENTER HUD TO SCREEN", system_group)
        reset_pos_btn.setProperty("class", "SecondaryBtn")
        reset_pos_btn.clicked.connect(self._on_reset_position)
        system_layout.addWidget(reset_pos_btn)

        main_layout.addWidget(system_group)

        main_layout.addStretch()

        # Bottom Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("CANCEL", self)
        cancel_btn.setProperty("class", "SecondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("SAVE CONFIG", self)
        save_btn.setProperty("class", "PrimaryBtn")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        main_layout.addLayout(btn_layout)

    def _on_reset_position(self):
        self.reset_position_requested.emit()

    def _on_save(self):
        idx = self._interval_combo.currentIndex()
        sec = self._intervals[idx][1]
        self._config.update_interval_sec = sec

        self._config.always_on_top = self._always_on_top_cb.isChecked()
        self._config.compact_mode = self._compact_mode_cb.isChecked()
        self._config.opacity = self._opacity_slider.value() / 100.0
        self._config.start_with_windows = self._start_windows_cb.isChecked()

        self._config.save()
        self.settings_changed.emit()
        self.accept()
