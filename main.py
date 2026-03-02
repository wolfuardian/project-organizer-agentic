"""Project Organizer — 桌面專案整理工具."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from main_window import MainWindow


def main():
    # High-DPI 支援
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Project Organizer")
    app.setOrganizationName("EOSWolf")

    # 基本深色主題
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #1e1e2e;
            color: #cdd6f4;
            font-size: 13px;
        }
        QTreeView {
            background-color: #181825;
            border: 1px solid #313244;
            border-radius: 4px;
            padding: 4px;
        }
        QTreeView::item {
            padding: 4px 2px;
            border-radius: 3px;
        }
        QTreeView::item:selected {
            background-color: #45475a;
        }
        QTreeView::item:hover {
            background-color: #313244;
        }
        QListWidget {
            background-color: #181825;
            border: 1px solid #313244;
            border-radius: 4px;
            padding: 4px;
        }
        QListWidget::item {
            padding: 6px 4px;
            border-radius: 3px;
        }
        QListWidget::item:selected {
            background-color: #45475a;
        }
        QListWidget::item:hover {
            background-color: #313244;
        }
        QPushButton {
            background-color: #313244;
            border: 1px solid #45475a;
            border-radius: 6px;
            padding: 6px 14px;
            color: #cdd6f4;
        }
        QPushButton:hover {
            background-color: #45475a;
        }
        QPushButton:pressed {
            background-color: #585b70;
        }
        QLabel {
            color: #a6adc8;
            font-weight: bold;
            padding: 2px;
        }
        QMenuBar {
            background-color: #1e1e2e;
            color: #cdd6f4;
        }
        QMenuBar::item:selected {
            background-color: #313244;
        }
        QMenu {
            background-color: #1e1e2e;
            border: 1px solid #313244;
        }
        QMenu::item:selected {
            background-color: #45475a;
        }
        QStatusBar {
            background-color: #181825;
            color: #6c7086;
        }
        QSplitter::handle {
            background-color: #313244;
            width: 2px;
        }
        QInputDialog, QMessageBox {
            background-color: #1e1e2e;
            color: #cdd6f4;
        }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
