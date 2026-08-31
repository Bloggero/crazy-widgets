"""
Centralized Logging and Crash Protection Service for Antigravity Quota Monitor.
Provides rotating file logs, global unhandled exception trapping, and Qt message interception.
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import traceback
from typing import Optional

from PySide6.QtCore import qInstallMessageHandler, QtMsgType

APP_NAME = "AntigravityQuotaMonitor"
_logger: Optional[logging.Logger] = None


def get_log_dir() -> str:
    """Returns the directory where application logs are stored."""
    app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
    log_dir = os.path.join(app_data, APP_NAME, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def get_logger() -> logging.Logger:
    """Retrieves the global application logger."""
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger


def _qt_message_handler(msg_type: QtMsgType, context, message: str):
    """Intercepts internal Qt messages and routes them to the application logger."""
    logger = get_logger()
    if msg_type == QtMsgType.QtDebugMsg:
        logger.debug(f"[Qt] {message}")
    elif msg_type == QtMsgType.QtInfoMsg:
        logger.info(f"[Qt] {message}")
    elif msg_type == QtMsgType.QtWarningMsg:
        logger.warning(f"[Qt] {message}")
    elif msg_type == QtMsgType.QtCriticalMsg:
        logger.error(f"[Qt Critical] {message}")
    elif msg_type == QtMsgType.QtFatalMsg:
        logger.critical(f"[Qt Fatal] {message}")


def _global_exception_hook(exc_type, exc_value, exc_traceback):
    """
    Global unhandled exception hook.
    Logs full traceback to crash log so the app never fails silently.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger = get_logger()
    tb_lines = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.critical(f"UNHANDLED EXCEPTION:\n{tb_lines}")

    # Also write directly to emergency crash.log
    try:
        crash_log_file = os.path.join(get_log_dir(), "crash.log")
        with open(crash_log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\nCRASH REPORT - {traceback.format_exc()}\n{'='*60}\n")
    except Exception:
        pass


def setup_logging(force_reset: bool = False) -> logging.Logger:
    """Initializes rotating file logger and registers exception/Qt handlers."""
    global _logger
    log_dir = get_log_dir()
    log_file = os.path.join(log_dir, "app.log")

    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.DEBUG)

    if force_reset or not logger.handlers:
        # Clear existing handlers if force_reset
        for h in list(logger.handlers):
            logger.removeHandler(h)
            h.close()

        # 1. Rotating File Handler (Max 5MB, keeps 3 backups)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

        # 2. Console Handler (for dev/terminal debugging)
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            "[%(levelname)s] %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)

    # Register global exception hook
    sys.excepthook = _global_exception_hook

    # Register Qt message handler
    try:
        qInstallMessageHandler(_qt_message_handler)
    except Exception:
        pass

    _logger = logger
    logger.info(f"=== Antigravity Quota Monitor logging initialized (Log: {log_file}) ===")
    return logger
