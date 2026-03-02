"""外觀主題定義與套用工具."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

# ── 主題定義（色彩調色盤）──────────────────────────────────────────

_STYLESHEET_TEMPLATE = """
    QMainWindow, QWidget {{
        background-color: {base};
        color: {text};
        font-size: 13px;
    }}
    QTreeView {{
        background-color: {mantle};
        border: 1px solid {surface0};
        border-radius: 4px;
        padding: 4px;
    }}
    QTreeView::item {{
        padding: 4px 2px;
        border-radius: 3px;
    }}
    QTreeView::item:selected {{
        background-color: {surface1};
    }}
    QTreeView::item:hover {{
        background-color: {surface0};
    }}
    QListWidget {{
        background-color: {mantle};
        border: 1px solid {surface0};
        border-radius: 4px;
        padding: 4px;
    }}
    QListWidget::item {{
        padding: 6px 4px;
        border-radius: 3px;
    }}
    QListWidget::item:selected {{
        background-color: {surface1};
    }}
    QListWidget::item:hover {{
        background-color: {surface0};
    }}
    QPushButton {{
        background-color: {surface0};
        border: 1px solid {surface1};
        border-radius: 6px;
        padding: 6px 14px;
        color: {text};
    }}
    QPushButton:hover {{
        background-color: {surface1};
    }}
    QPushButton:pressed {{
        background-color: {surface2};
    }}
    QLabel {{
        color: {subtext0};
        font-weight: bold;
        padding: 2px;
    }}
    QMenuBar {{
        background-color: {base};
        color: {text};
    }}
    QMenuBar::item:selected {{
        background-color: {surface0};
    }}
    QMenu {{
        background-color: {base};
        border: 1px solid {surface0};
    }}
    QMenu::item:selected {{
        background-color: {surface1};
    }}
    QStatusBar {{
        background-color: {mantle};
        color: {overlay0};
    }}
    QSplitter::handle {{
        background-color: {surface0};
        width: 2px;
    }}
    QInputDialog, QMessageBox {{
        background-color: {base};
        color: {text};
    }}
    QLineEdit, QTextEdit, QComboBox, QSpinBox {{
        background-color: {mantle};
        border: 1px solid {surface0};
        border-radius: 4px;
        color: {text};
        padding: 3px 6px;
    }}
    QTableWidget {{
        background-color: {mantle};
        border: 1px solid {surface0};
        gridline-color: {surface0};
        color: {text};
    }}
    QHeaderView::section {{
        background-color: {surface0};
        color: {subtext0};
        border: none;
        padding: 4px;
    }}
    QScrollBar:vertical {{
        background: {mantle};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {surface1};
        border-radius: 4px;
    }}
    QCheckBox {{
        color: {text};
    }}
    QDialog {{
        background-color: {base};
    }}
"""

THEMES: dict[str, dict[str, str]] = {
    "Catppuccin Mocha（預設）": {
        "base":     "#1e1e2e",
        "mantle":   "#181825",
        "surface0": "#313244",
        "surface1": "#45475a",
        "surface2": "#585b70",
        "text":     "#cdd6f4",
        "subtext0": "#a6adc8",
        "overlay0": "#6c7086",
    },
    "Catppuccin Latte（淺色）": {
        "base":     "#eff1f5",
        "mantle":   "#e6e9ef",
        "surface0": "#ccd0da",
        "surface1": "#bcc0cc",
        "surface2": "#acb0be",
        "text":     "#4c4f69",
        "subtext0": "#6c6f85",
        "overlay0": "#9ca0b0",
    },
    "Nord 深色": {
        "base":     "#2e3440",
        "mantle":   "#242933",
        "surface0": "#3b4252",
        "surface1": "#434c5e",
        "surface2": "#4c566a",
        "text":     "#eceff4",
        "subtext0": "#d8dee9",
        "overlay0": "#616e88",
    },
    "Solarized 深色": {
        "base":     "#002b36",
        "mantle":   "#073642",
        "surface0": "#083f4d",
        "surface1": "#094d5e",
        "surface2": "#0a5a70",
        "text":     "#839496",
        "subtext0": "#657b83",
        "overlay0": "#586e75",
    },
    "Ranger Phosphor（磷光綠）": {
        "base":     "#050a05",
        "mantle":   "#030703",
        "surface0": "#0c1a0c",
        "surface1": "#0f240f",
        "surface2": "#142a14",
        "text":     "#b8ffb8",
        "subtext0": "#4a7a4a",
        "overlay0": "#2a4a2a",
        "_extras": """
    QMainWindow, QWidget {
        font-family: "JetBrains Mono", "Cascadia Code", "Fira Code",
                     "Consolas", "Menlo", "Courier New", monospace;
    }
    QTreeView::item:selected {
        border-left: 2px solid #39ff14;
        color: #39ff14;
    }
    QListWidget::item:selected {
        border-left: 2px solid #39ff14;
    }
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
        border-color: #39ff14;
    }
    QStatusBar {
        font-size: 12px;
        letter-spacing: 0.05em;
    }
""",
    },
}


def build_stylesheet(theme_name: str) -> str:
    """依主題名稱產生 Qt stylesheet 字串。"""
    palette = THEMES.get(theme_name, THEMES["Catppuccin Mocha（預設）"])
    css = _STYLESHEET_TEMPLATE.format_map(palette)
    if extras := palette.get("_extras", ""):
        css += extras
    return css


def apply_theme(theme_name: str) -> None:
    """立即將主題套用至目前 QApplication。"""
    app = QApplication.instance()
    if app:
        app.setStyleSheet(build_stylesheet(theme_name))


def theme_names() -> list[str]:
    """回傳所有主題名稱列表。"""
    return list(THEMES.keys())
