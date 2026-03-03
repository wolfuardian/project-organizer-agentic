"""Project Organizer — 桌面專案整理工具."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from infrastructure.database import get_connection, init_db
from infrastructure.repositories.settings_repo import SqliteSettingsRepository
from presentation.themes import theme_names, build_stylesheet


def _load_startup_theme(settings_repo) -> str:
    """從 settings 表格讀取上次儲存的主題。"""
    try:
        return settings_repo.get_setting("theme", theme_names()[0])
    except Exception:
        return theme_names()[0]


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

    # Repositories
    settings_repo = SqliteSettingsRepository(conn)

    # Theme
    theme = _load_startup_theme(settings_repo)
    app.setStyleSheet(build_stylesheet(theme))

    # UI（MainWindow 目前仍透過 shim 使用舊 import 路徑，後續再改為完整注入）
    from main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
