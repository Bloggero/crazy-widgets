"""
Main Entry Point for Antigravity Quota Monitor.
Enforces single-instance execution, sets up crash logging, and starts the Qt Application Event Loop.
"""
import sys
import os
import ctypes

# Ensure src package is importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from src.services.logger import setup_logging, get_logger
from src.app import AppController, SINGLE_INSTANCE_SERVER_NAME


def main():
    # 1. Initialize Rotating Crash Logger & Exception Traps
    logger = setup_logging()

    # Set explicit AppUserModelID on Windows for proper shell/taskbar identity
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "AntigravityTools.QuotaMonitor.SAO.1.0"
            )
        except Exception as e:
            logger.debug(f"SetCurrentProcessExplicitAppUserModelID note: {e}")

    # 2. Single Instance Check via QLocalSocket
    test_socket = QLocalSocket()
    test_socket.connectToServer(SINGLE_INSTANCE_SERVER_NAME)
    if test_socket.waitForConnected(500):
        # Already running! Send bring-to-front message and exit
        try:
            test_socket.write(b"SHOW")
            test_socket.waitForBytesWritten(500)
            test_socket.disconnectFromServer()
        except Exception:
            pass
        logger.info("Antigravity Quota Monitor is already running. Brought existing instance to front.")
        sys.exit(0)

    # 3. High-DPI & App Properties
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Antigravity Quota Monitor")
    app.setApplicationDisplayName("Antigravity Quota Monitor")
    app.setOrganizationName("AntigravityTools")
    app.setApplicationVersion("1.0.0")
    app.setQuitOnLastWindowClosed(False)  # Keep running in system tray

    # App Icon
    ico_path = os.path.join(BASE_DIR, "resources", "icon.ico")
    if os.path.exists(ico_path):
        app.setWindowIcon(QIcon(ico_path))

    # 4. Create Single-Instance Local Server
    server = QLocalServer(app)
    QLocalServer.removeServer(SINGLE_INSTANCE_SERVER_NAME)
    server.listen(SINGLE_INSTANCE_SERVER_NAME)

    controller = AppController(app)

    def on_new_connection():
        try:
            sock = server.nextPendingConnection()
            if sock:
                def on_ready_read():
                    try:
                        data = sock.readAll().data().decode("utf-8", errors="ignore")
                        if "SHOW" in data:
                            controller.toggle_visibility()
                    except Exception as e:
                        logger.warning(f"IPC socket read error: {e}")
                    finally:
                        sock.disconnectFromServer()
                        sock.deleteLater()

                sock.readyRead.connect(on_ready_read)
                # Fallback if already ready
                if sock.bytesAvailable() > 0:
                    on_ready_read()
        except Exception as e:
            logger.error(f"Error handling IPC connection: {e}")

    server.newConnection.connect(on_new_connection)

    # 5. Start Event Loop
    logger.info("Entering Qt application event loop.")
    exit_code = app.exec()
    logger.info(f"Qt application event loop terminated with exit code {exit_code}.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
