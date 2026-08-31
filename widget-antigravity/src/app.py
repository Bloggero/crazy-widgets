"""
Application Controller for Antigravity Quota Monitor.
Manages system tray integration, single-instance enforcement,
asynchronous background polling loop, compact/expanded mode switching, and live system clock.
"""
import os
import sys
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QObject, Slot, QTime, QThread, Signal
from PySide6.QtGui import QIcon, QAction, QFont
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from src.models import QuotaSnapshot
from src.services.config_manager import ConfigManager
from src.services.history_store import HistoryStore
from src.services.quota_fetcher import QuotaFetcher
from src.services.logger import get_logger
from src.widgets.monitor_widget import MonitorWidget
from src.widgets.compact_widget import CompactWidget
from src.widgets.settings_dialog import SettingsDialog

SINGLE_INSTANCE_SERVER_NAME = "AntigravityQuotaMonitor_SingleInstance_Mutex"


class FetchWorker(QThread):
    """Background worker thread to query Language Server without freezing UI."""
    # IMPORTANT: Do NOT name this 'finished' — it collides with QThread.finished
    # which Qt emits automatically (no args) when run() returns, causing signal delivery failures.
    fetch_completed = Signal(QuotaSnapshot)

    def __init__(self, fetcher: QuotaFetcher, force_rediscover: bool = False, parent=None):
        super().__init__(parent)
        self._fetcher = fetcher
        self._force_rediscover = force_rediscover
        self.result_snapshot: Optional[QuotaSnapshot] = None  # Fallback access

    def run(self):
        try:
            snapshot = self._fetcher.fetch(force_rediscover=self._force_rediscover)
            self.result_snapshot = snapshot
            self.fetch_completed.emit(snapshot)
        except Exception as e:
            from datetime import datetime, timezone
            err_snapshot = QuotaSnapshot(
                timestamp=datetime.now(timezone.utc),
                is_success=False,
                error_message=f"Worker Error: {str(e)}"
            )
            self.result_snapshot = err_snapshot
            self.fetch_completed.emit(err_snapshot)


class AppController(QObject):
    """Orchestrates UI widgets, background polling, system tray, and settings."""

    def __init__(self, app: QApplication):
        super().__init__()
        self._logger = get_logger()
        self._app = app
        self._config = ConfigManager()
        self._history = HistoryStore()
        self._fetcher = QuotaFetcher()

        self._current_snapshot: Optional[QuotaSnapshot] = None
        self._seconds_to_next_update: int = self._config.update_interval_sec
        self._is_fetching: bool = False
        self._fetch_worker: Optional[FetchWorker] = None
        self._fetch_safety_timer: Optional[QTimer] = None

        # Load Stylesheet
        self._load_stylesheet()

        # Build UI Components
        self._monitor_widget = MonitorWidget(self._config, self._history)
        self._compact_widget = CompactWidget()
        self._settings_dialog: Optional[SettingsDialog] = None

        # Setup System Tray & Timers
        self._init_tray_icon()
        self._connect_signals()
        self._init_timers()

        # Apply Startup Mode & Perform Initial Fetch
        self._apply_mode()
        self.refresh_data(force_rediscover=True)

    def _resolve_resource(self, filename: str) -> Optional[str]:
        if getattr(sys, "frozen", False):
            base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        candidates = [
            os.path.join(base_dir, "src", "resources", filename),
            os.path.join(base_dir, "resources", filename),
            os.path.join(base_dir, filename),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    def _load_stylesheet(self):
        qss_path = self._resolve_resource("styles.qss")
        if qss_path and os.path.exists(qss_path):
            try:
                with open(qss_path, "r", encoding="utf-8") as f:
                    self._app.setStyleSheet(f.read())
            except Exception as e:
                self._logger.warning(f"Failed to load stylesheet: {e}")

    def _get_app_icon(self) -> QIcon:
        ico_path = self._resolve_resource("icon.ico")
        png_path = self._resolve_resource("icon.png")
        if ico_path and os.path.exists(ico_path):
            return QIcon(ico_path)
        elif png_path and os.path.exists(png_path):
            return QIcon(png_path)
        return QIcon()

    def _init_tray_icon(self):
        icon = self._get_app_icon()
        self._tray_icon = QSystemTrayIcon(icon, self._app)
        self._tray_icon.setToolTip("Antigravity Quota Monitor")

        # Tray Menu
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #0C1017;
                color: #F3F4F6;
                border: 1px solid #00E5FF;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #FF7800;
                color: #FFFFFF;
            }
            QMenu::separator {
                height: 1px;
                background: #1E2D42;
                margin: 4px 8px;
            }
        """)

        # Header Title
        header_action = QAction("⚔ SAO // Quota Monitor", menu)
        header_action.setEnabled(False)
        menu.addAction(header_action)
        menu.addSeparator()

        # Toggle Show / Hide
        self._show_action = QAction("Show Monitor", menu)
        self._show_action.triggered.connect(self.toggle_visibility)
        menu.addAction(self._show_action)

        # Mode Switch
        self._mode_action = QAction("Switch to Compact Mode", menu)
        self._mode_action.triggered.connect(self.toggle_compact_mode)
        menu.addAction(self._mode_action)

        # Refresh
        refresh_action = QAction("↻ Sync Now", menu)
        refresh_action.triggered.connect(lambda: self.refresh_data(force_rediscover=True))
        menu.addAction(refresh_action)

        menu.addSeparator()

        # Settings
        settings_action = QAction("⚙ Settings", menu)
        settings_action.triggered.connect(self.show_settings)
        menu.addAction(settings_action)

        # Start with Windows (Checkable)
        self._start_win_action = QAction("Start with Windows", menu, checkable=True)
        self._start_win_action.setChecked(self._config.start_with_windows)
        self._start_win_action.triggered.connect(self._on_toggle_start_windows)
        menu.addAction(self._start_win_action)

        menu.addSeparator()

        # Exit
        exit_action = QAction("✕ Exit", menu)
        exit_action.triggered.connect(self.quit)
        menu.addAction(exit_action)

        self._tray_icon.setContextMenu(menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _connect_signals(self):
        # Monitor Widget
        self._monitor_widget.refresh_requested.connect(lambda: self.refresh_data(force_rediscover=True))
        self._monitor_widget.settings_requested.connect(self.show_settings)
        self._monitor_widget.compact_requested.connect(self.toggle_compact_mode)
        self._monitor_widget.close_requested.connect(self.hide_windows)

        # Compact Widget
        self._compact_widget.expand_requested.connect(self.toggle_compact_mode)
        self._compact_widget.refresh_requested.connect(lambda: self.refresh_data(force_rediscover=True))

    def _init_timers(self):
        # Master 1-second heartbeat timer for System Clock, Countdown, and Auto-Sync trigger
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._on_heartbeat_tick)
        self._heartbeat_timer.start(1000)
        self._seconds_to_next_update = self._config.update_interval_sec

        # Initialize labels
        self._monitor_widget.set_system_time(QTime.currentTime().toString("hh:mm:ss"))
        self._monitor_widget.set_next_update_countdown(self._seconds_to_next_update)

    def _update_poll_interval(self):
        """Called when settings interval is changed by user."""
        self._seconds_to_next_update = self._config.update_interval_sec
        self._monitor_widget.set_next_update_countdown(self._seconds_to_next_update)

    def _on_heartbeat_tick(self):
        """Fires every 1 second: updates live system clock and triggers auto-sync."""
        # 1. Update live system clock every second
        current_time_str = QTime.currentTime().toString("hh:mm:ss")
        self._monitor_widget.set_system_time(current_time_str)

        # 2. Manage countdown and trigger auto-sync
        if self._is_fetching:
            self._monitor_widget.set_next_update_countdown(0, is_syncing=True)
            return

        if self._seconds_to_next_update > 0:
            self._seconds_to_next_update -= 1
            self._monitor_widget.set_next_update_countdown(self._seconds_to_next_update, is_syncing=False)
        else:
            # Countdown reached 0 -> Reset countdown FIRST, then auto-sync
            self._seconds_to_next_update = self._config.update_interval_sec
            self.refresh_data(force_rediscover=False)

    @Slot()
    def refresh_data(self, force_rediscover: bool = False):
        """Asynchronously queries Language Server in a background worker thread."""
        if self._is_fetching:
            return

        # Clean up any previous worker that might still be referenced
        if self._fetch_worker is not None:
            if self._fetch_worker.isRunning():
                return
            try:
                self._fetch_worker.fetch_completed.disconnect(self._on_fetch_completed)
            except (RuntimeError, TypeError):
                pass
            try:
                self._fetch_worker.finished.disconnect(self._on_worker_thread_finished)
            except (RuntimeError, TypeError):
                pass
            self._fetch_worker = None

        self._is_fetching = True
        self._fetch_signal_received = False  # Track whether custom signal was delivered
        self._monitor_widget.set_syncing_state(True)
        self._monitor_widget.set_next_update_countdown(0, is_syncing=True)

        # Start safety timeout — if worker doesn't complete in 15s, force-reset state
        self._start_safety_timer()

        self._fetch_worker = FetchWorker(self._fetcher, force_rediscover=force_rediscover, parent=None)
        self._fetch_worker.fetch_completed.connect(self._on_fetch_completed)
        # Also connect to QThread's native finished() as safety backup
        self._fetch_worker.finished.connect(self._on_worker_thread_finished)
        self._fetch_worker.start()

    def _start_safety_timer(self):
        """Starts a one-shot safety timer that force-resets syncing state if worker hangs."""
        self._cancel_safety_timer()
        self._fetch_safety_timer = QTimer(self)
        self._fetch_safety_timer.setSingleShot(True)
        self._fetch_safety_timer.timeout.connect(self._on_safety_timeout)
        self._fetch_safety_timer.start(15000)  # 15 seconds max

    def _cancel_safety_timer(self):
        """Cancels the safety timer if active."""
        if self._fetch_safety_timer is not None:
            self._fetch_safety_timer.stop()
            self._fetch_safety_timer.deleteLater()
            self._fetch_safety_timer = None

    def _on_safety_timeout(self):
        """Force-resets syncing state when worker takes too long or silently fails."""
        self._logger.warning("Safety timeout: fetch worker did not complete within 15s. Force-resetting state.")
        self._is_fetching = False

        # Kill hung worker
        if self._fetch_worker is not None:
            if self._fetch_worker.isRunning():
                self._fetch_worker.quit()
                self._fetch_worker.wait(2000)
                if self._fetch_worker.isRunning():
                    self._fetch_worker.terminate()
            self._fetch_worker = None

        # Reset UI to ready state
        self._monitor_widget.set_syncing_state(False)
        self._seconds_to_next_update = self._config.update_interval_sec
        self._monitor_widget.set_next_update_countdown(self._seconds_to_next_update, is_syncing=False)
        self._fetch_safety_timer = None

    def _on_worker_thread_finished(self):
        """Safety fallback: QThread.finished() fires when run() returns.
        If fetch_completed signal was not received, process the result here."""
        if not self._fetch_signal_received and self._is_fetching:
            self._logger.warning("fetch_completed signal was NOT received, but QThread.finished fired. Using fallback.")
            snapshot = None
            if self._fetch_worker and self._fetch_worker.result_snapshot:
                snapshot = self._fetch_worker.result_snapshot
            else:
                from datetime import datetime, timezone
                snapshot = QuotaSnapshot(
                    timestamp=datetime.now(timezone.utc),
                    is_success=False,
                    error_message="Signal delivery failed — fallback recovery."
                )
            self._on_fetch_completed(snapshot)

        # Cleanup the worker
        if self._fetch_worker is not None:
            self._fetch_worker.deleteLater()
            self._fetch_worker = None

    def _on_fetch_completed(self, snapshot: QuotaSnapshot):
        """Receives quota snapshot from background thread and updates UI."""
        self._fetch_signal_received = True
        self._cancel_safety_timer()
        if not self._is_fetching:
            return  # Already processed via fallback, skip duplicate
        self._is_fetching = False
        self._current_snapshot = snapshot

        try:
            # If successful, record snapshot in history store
            if snapshot.is_success and snapshot.groups:
                self._history.record_snapshot(snapshot)
        except Exception as e:
            self._logger.error(f"History recording error: {e}")

        try:
            # Update Widgets
            self._monitor_widget.update_data(snapshot)
            self._compact_widget.update_data(snapshot)
            self._monitor_widget.set_syncing_state(False)

            # Update Tray Tooltip
            self._update_tray_tooltip(snapshot)

            # Reset Countdown to configured interval
            self._seconds_to_next_update = self._config.update_interval_sec
            self._monitor_widget.set_next_update_countdown(self._seconds_to_next_update, is_syncing=False)
        except Exception as e:
            self._logger.error(f"UI update error: {e}")
            # Even if UI update fails, make sure the widget is not stuck in syncing state
            self._monitor_widget.set_syncing_state(False)
            self._seconds_to_next_update = self._config.update_interval_sec
            self._monitor_widget.set_next_update_countdown(self._seconds_to_next_update, is_syncing=False)

    def _update_tray_tooltip(self, snapshot: QuotaSnapshot):
        if snapshot.is_success and snapshot.groups:
            parts = []
            for g in snapshot.groups:
                b = g.five_hour_bucket or (g.buckets[0] if g.buckets else None)
                if b:
                    short = "Gemini" if "gemini" in g.display_name.lower() else "Claude/GPT"
                    parts.append(f"{short}: {b.percentage_int}%")
            summary = " | ".join(parts)
            self._tray_icon.setToolTip(f"Antigravity Quota\n{summary}")
        else:
            self._tray_icon.setToolTip("Antigravity Quota Monitor\n⚠ Not detected")

    def _apply_mode(self):
        """Applies compact or expanded mode based on configuration without unnecessary flag recreation."""
        opacity = self._config.opacity
        always_on_top = self._config.always_on_top

        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow
        if always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint

        if self._config.compact_mode:
            self._monitor_widget.hide()
            if self._compact_widget.windowFlags() != flags:
                self._compact_widget.setWindowFlags(flags)
            self._compact_widget.setWindowOpacity(opacity)
            self._compact_widget.show()
            self._mode_action.setText("Switch to Expanded Mode")
        else:
            self._compact_widget.hide()
            if self._monitor_widget.windowFlags() != flags:
                self._monitor_widget.setWindowFlags(flags)
            self._monitor_widget.setWindowOpacity(opacity)
            self._monitor_widget.show()
            self._mode_action.setText("Switch to Compact Mode")

    @Slot()
    def toggle_compact_mode(self):
        self._config.compact_mode = not self._config.compact_mode
        self._config.save()
        self._apply_mode()

    @Slot()
    def toggle_visibility(self):
        target = self._compact_widget if self._config.compact_mode else self._monitor_widget

        if target.isVisible():
            target.hide()
            self._show_action.setText("Show Monitor")
        else:
            target.show()
            target.raise_()
            target.activateWindow()
            self._show_action.setText("Hide Monitor")

    @Slot()
    def hide_windows(self):
        self._monitor_widget.hide()
        self._compact_widget.hide()
        self._show_action.setText("Show Monitor")

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.toggle_visibility()

    @Slot()
    def show_settings(self):
        if not self._settings_dialog:
            self._settings_dialog = SettingsDialog(self._config)
            self._settings_dialog.settings_changed.connect(self._on_settings_changed)
            self._settings_dialog.reset_position_requested.connect(self._on_reset_position)

        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _on_settings_changed(self):
        self._update_poll_interval()
        self._apply_mode()
        self._start_win_action.setChecked(self._config.start_with_windows)

    def _on_toggle_start_windows(self, checked: bool):
        self._config.start_with_windows = checked

    def _on_reset_position(self):
        screen = self._app.primaryScreen().availableGeometry()
        mw = self._monitor_widget
        x = screen.x() + (screen.width() - mw.width()) // 2
        y = screen.y() + (screen.height() - mw.height()) // 2
        mw.move(x, y)
        self._compact_widget.move(x, y)
        self._config.save_window_geometry(x, y, mw.width(), mw.height())
        self._logger.info(f"Window positions reset to center ({x}, {y})")

    def quit(self):
        self._logger.info("Application quitting initiated by user.")
        self._heartbeat_timer.stop()
        if self._fetch_worker and self._fetch_worker.isRunning():
            self._fetch_worker.quit()
            self._fetch_worker.wait(1000)
        self._history.close()
        self._tray_icon.hide()
        self._app.quit()
