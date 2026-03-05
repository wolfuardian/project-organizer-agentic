"""Project Organizer — 桌面專案整理工具."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from infrastructure.database import get_connection, init_db
from presentation.themes import STYLESHEET


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Project Organizer")
    app.setOrganizationName("EOSWolf")

    # Infrastructure
    conn = get_connection()
    init_db(conn)

    # Theme
    app.setStyleSheet(STYLESHEET)

    # UI（MainWindow 目前仍透過 shim 使用舊 import 路徑，後續再改為完整注入）
    from main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
