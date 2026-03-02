"""Project Organizer — 桌面專案整理工具."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from main_window import MainWindow
from themes import apply_theme, theme_names, build_stylesheet


def _load_startup_theme() -> str:
    """從 settings 表格讀取上次儲存的主題；失敗時回傳預設主題。"""
    try:
        from backup import get_setting
        from database import get_connection
        conn = get_connection()
        return get_setting(conn, "theme", theme_names()[0])
    except Exception:
        return theme_names()[0]


def main():
    # High-DPI 支援
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Project Organizer")
    app.setOrganizationName("EOSWolf")

    # 套用主題（從 settings 讀取，預設 Catppuccin Mocha）
    theme = _load_startup_theme()
    app.setStyleSheet(build_stylesheet(theme))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
