"""外觀主題定義與套用工具 — Graphite Pro 單一主題."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

# ── Stylesheet ───────────────────────────────────────────────────

STYLESHEET = """
    QMainWindow, QWidget {
        background-color: #16161a;
        color: #e0e0e6;
        font-size: 13px;
        font-family: "Segoe UI Variable", "SF Pro Display",
                     "Noto Sans CJK TC", "Microsoft JhengHei UI",
                     system-ui, sans-serif;
        letter-spacing: 0.01em;
    }
    QTreeView {
        background-color: #111114;
        border: none;
        border-radius: 4px;
        padding: 4px;
    }
    QTreeView::item {
        padding: 4px 2px;
        border-radius: 3px;
    }
    QTreeView::item:selected {
        background-color: rgba(212, 160, 84, 0.15);
        border-left: 2px solid #d4a054;
        color: #f0e6d6;
    }
    QTreeView::item:hover {
        background-color: rgba(255, 255, 255, 0.04);
    }
    QListWidget {
        background-color: #111114;
        border: none;
        border-radius: 0;
        padding: 2px 0;
        outline: none;
    }
    QListWidget::item {
        padding: 5px 7px;
        border-radius: 0;
        border: 1px solid transparent;
        border-left: 2px solid transparent;
    }
    QListWidget::item:selected {
        background-color: #1e1e24;
        border-left: 2px solid #d4a054;
        color: #e8dcc8;
    }
    QListWidget::item:focus {
        border: 2px dashed rgba(160, 160, 175, 0.3);
        border-left: 2px solid transparent;
        padding: 4px 6px;
    }
    QListWidget::item:selected:focus {
        border: 2px dashed rgba(212, 160, 84, 0.4);
        border-left: 2px solid #d4a054;
        padding: 4px 6px;
    }
    QListWidget::item:hover:!selected {
        background-color: rgba(255, 255, 255, 0.03);
    }
    QListWidget::item:selected:hover {
        background-color: #222228;
    }
    QListWidget:focus {
        outline: none;
    }
    QPushButton {
        background-color: #232329;
        border: none;
        border-radius: 6px;
        padding: 6px 14px;
        color: #e0e0e6;
        font-weight: 500;
    }
    QPushButton:hover {
        background-color: #2e2e36;
        color: #f0e6d6;
    }
    QPushButton:pressed {
        background-color: rgba(212, 160, 84, 0.12);
    }
    QLabel {
        color: #a0a0af;
        font-weight: bold;
        padding: 2px;
    }
    QMenuBar {
        background-color: #16161a;
        color: #e0e0e6;
    }
    QMenuBar::item:selected {
        background-color: #232329;
    }
    QMenu {
        background-color: #16161a;
        border: none;
    }
    QMenu::item:selected {
        background-color: rgba(212, 160, 84, 0.18);
    }
    QStatusBar {
        background-color: #111114;
        color: #6b6b7a;
        font-size: 12px;
    }
    QSplitter::handle {
        background-color: #232329;
        width: 1px;
    }
    QInputDialog, QMessageBox {
        background-color: #16161a;
        color: #e0e0e6;
    }
    QLineEdit, QTextEdit, QComboBox, QSpinBox {
        background-color: #111114;
        border: none;
        border-radius: 4px;
        color: #e0e0e6;
        padding: 3px 6px;
    }
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
        border-color: #d4a054;
    }
    QTableWidget {
        background-color: #111114;
        border: none;
        gridline-color: #232329;
        color: #e0e0e6;
    }
    QHeaderView::section {
        background-color: #1c1c22;
        color: #a0a0af;
        border: none;
        padding: 4px;
        font-weight: 600;
    }
    QScrollBar:vertical {
        background: #111114;
        width: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: #3a3a44;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical:hover {
        background: #d4a054;
    }
    QCheckBox {
        color: #e0e0e6;
    }
    QDialog {
        background-color: #16161a;
    }
    QTabBar::tab {
        background-color: #1c1c22;
        color: #a0a0af;
        border: none;
        padding: 6px 14px;
    }
    QTabBar::tab:selected {
        color: #e0e0e6;
        border-bottom: 2px solid #d4a054;
    }
    QTabBar::tab:hover {
        color: #e0e0e6;
    }
    QProgressBar {
        background-color: #232329;
        border: none;
        border-radius: 3px;
        text-align: center;
        color: #a0a0af;
    }
    QProgressBar::chunk {
        background-color: #d4a054;
        border-radius: 3px;
    }
"""


def build_stylesheet(theme_name: str | None = None) -> str:
    """回傳唯一的 Graphite Pro stylesheet。theme_name 參數保留向後相容但已忽略。"""
    return STYLESHEET


def apply_theme(theme_name: str | None = None) -> None:
    """立即將 Graphite Pro 主題套用至目前 QApplication。"""
    app = QApplication.instance()
    if app:
        app.setStyleSheet(STYLESHEET)


def theme_names() -> list[str]:
    """回傳主題名稱列表（僅 Graphite Pro）。"""
    return ["Graphite Pro（專業深色）"]
