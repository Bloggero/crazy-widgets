"""
Configuration Manager for Antigravity Quota Monitor.
Provides thread-safe atomic JSON persistence, multi-monitor coordinate sanitization,
and Windows startup registry integration.
"""
import os
import sys
import json
import winreg
from typing import Dict, Any, List, Optional, Tuple

from PySide6.QtGui import QGuiApplication
from src.services.logger import get_logger

APP_NAME = "AntigravityQuotaMonitor"
DEFAULT_CONFIG = {
    "update_interval_sec": 300,  # 5 minutes default
    "always_on_top": True,
    "start_with_windows": False,
    "compact_mode": False,
    "opacity": 0.95,
    "theme": "dark",
    "window_x": None,
    "window_y": None,
    "window_width": 420,
    "window_height": 530,
    "hidden_buckets": [],
    "enable_notifications": True,
    "warning_threshold": 30,
    "critical_threshold": 15,
}


class ConfigManager:
    """Manages application configuration, atomic persistence, and multi-monitor resilience."""

    def __init__(self):
        self._logger = get_logger()
        self._config_dir = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            APP_NAME
        )
        os.makedirs(self._config_dir, exist_ok=True)
        self._config_file = os.path.join(self._config_dir, "config.json")
        self._config: Dict[str, Any] = self._load()

    @property
    def config_dir(self) -> str:
        return self._config_dir

    def _load(self) -> Dict[str, Any]:
        config = DEFAULT_CONFIG.copy()
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        config.update(saved)
            except Exception as e:
                self._logger.warning(f"Error reading config: {e}. Using defaults.")
        
        # Ensure default width is at least 380 for proper layout
        if not config.get("window_width") or config["window_width"] < 380:
            config["window_width"] = 420
        # Sanity check for interval
        if config.get("update_interval_sec", 300) < 15:
            config["update_interval_sec"] = 15

        return config

    def save(self) -> None:
        """Atomically saves configuration to disk to prevent corruption."""
        temp_file = f"{self._config_file}.tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, self._config_file)
        except Exception as e:
            self._logger.error(f"Failed to atomically save config: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        self._config[key] = value
        if auto_save:
            self.save()

    @property
    def update_interval_sec(self) -> int:
        return int(self.get("update_interval_sec", 300))

    @update_interval_sec.setter
    def update_interval_sec(self, val: int):
        self.set("update_interval_sec", max(15, int(val)))

    @property
    def always_on_top(self) -> bool:
        return bool(self.get("always_on_top", True))

    @always_on_top.setter
    def always_on_top(self, val: bool):
        self.set("always_on_top", bool(val))

    @property
    def start_with_windows(self) -> bool:
        return bool(self.get("start_with_windows", False))

    @start_with_windows.setter
    def start_with_windows(self, val: bool):
        val = bool(val)
        self.set("start_with_windows", val)
        self.apply_start_with_windows(val)

    @property
    def compact_mode(self) -> bool:
        return bool(self.get("compact_mode", False))

    @compact_mode.setter
    def compact_mode(self, val: bool):
        self.set("compact_mode", bool(val))

    @property
    def opacity(self) -> float:
        return float(self.get("opacity", 0.95))

    @opacity.setter
    def opacity(self, val: float):
        self.set("opacity", max(0.4, min(1.0, float(val))))

    @property
    def theme(self) -> str:
        return str(self.get("theme", "dark"))

    @theme.setter
    def theme(self, val: str):
        self.set("theme", val)

    @property
    def window_geometry(self) -> Dict[str, Any]:
        return {
            "x": self.get("window_x"),
            "y": self.get("window_y"),
            "width": self.get("window_width", 420),
            "height": self.get("window_height", 530),
        }

    def sanitize_coordinates(self, x: Optional[int], y: Optional[int], width: int = 420, height: int = 530) -> Tuple[int, int]:
        """
        Validates whether (x, y) is visible within any currently connected screen.
        If off-screen or None (e.g. disconnected monitor), re-centers on the primary screen.
        """
        screens = QGuiApplication.screens() if QGuiApplication.instance() else []
        if not screens or x is None or y is None:
            # Center on primary or default 100, 100
            if screens:
                primary = screens[0].availableGeometry()
                return (
                    primary.x() + (primary.width() - width) // 2,
                    primary.y() + (primary.height() - height) // 2,
                )
            return (100, 100)

        # Check if point (x, y) or at least 50px of window is visible on any active screen
        for screen in screens:
            geom = screen.availableGeometry()
            # If the top bar of the widget is inside this screen's bounds
            if geom.intersects(geom.adjusted(-width + 50, -height + 50, width - 50, height - 50)):
                if (geom.left() - width + 50 <= x <= geom.right() - 50 and
                        geom.top() <= y <= geom.bottom() - 50):
                    return (x, y)

        # Off-screen! Reposition to primary screen
        primary = screens[0].availableGeometry()
        self._logger.info(f"Saved coordinates ({x}, {y}) off-screen. Re-centering to primary display.")
        return (
            primary.x() + (primary.width() - width) // 2,
            primary.y() + (primary.height() - height) // 2,
        )

    def save_window_geometry(self, x: int, y: int, width: int, height: int):
        self._config["window_x"] = x
        self._config["window_y"] = y
        self._config["window_width"] = max(380, width)
        self._config["window_height"] = max(400, height)
        self.save()

    @property
    def hidden_buckets(self) -> List[str]:
        return list(self.get("hidden_buckets", []))

    @hidden_buckets.setter
    def hidden_buckets(self, val: List[str]):
        self.set("hidden_buckets", list(val))

    def apply_start_with_windows(self, enable: bool) -> bool:
        if sys.platform != "win32":
            return False

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        if getattr(sys, 'frozen', False):
            app_exe = sys.executable
        else:
            app_exe = f'"{sys.executable}" "{os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))}"'

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{app_exe}"' if not app_exe.startswith('"') else app_exe)
                    self._logger.info("Windows Startup entry registered successfully.")
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                        self._logger.info("Windows Startup entry removed.")
                    except FileNotFoundError:
                        pass
            return True
        except Exception as e:
            self._logger.error(f"Registry update error: {e}")
            return False
