"""Material 風格檔案類型圖示 — 從 res/ 目錄載入 SVG。"""

from __future__ import annotations

import pathlib

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QIcon, QPixmap

_RES_DIR = pathlib.Path(__file__).parent / "res"

# 分類 → 主色
_COLORS: dict[str, str] = {
    "folder":     "#5fd7ff",
    "virtual":    "#5fd7ff",
    "image":      "#d787ff",
    "video":      "#ff875f",
    "audio":      "#ffaf00",
    "code":       "#87ff87",
    "document":   "#ffffaf",
    "archive":    "#ff8700",
    "data":       "#afd7ff",
    "font":       "#d7afd7",
    "3d":         "#afffaf",
    "other":      "#c8c8c8",
    "folder_add": "#5fd7ff",
    "drive":      "#87afff",
}

# SVG 範本快取（原始字串，含 {c} 佔位符）
_svg_tpl_cache: dict[str, str] = {}
# QIcon 快取（渲染後，只建立一次）
_icon_cache: dict[str, QIcon] = {}


def _load_svg_tpl(category: str) -> str:
    """從 res/ 目錄讀取 SVG 範本字串，並快取原始內容。"""
    tpl = _svg_tpl_cache.get(category)
    if tpl is not None:
        return tpl
    path = _RES_DIR / f"{category}.svg"
    if not path.exists():
        path = _RES_DIR / "other.svg"
    tpl = path.read_text(encoding="utf-8")
    _svg_tpl_cache[category] = tpl
    return tpl


def get_category_icon(category: str) -> QIcon:
    """回傳檔案分類對應的 Material 風格 QIcon（快取）。"""
    icon = _icon_cache.get(category)
    if icon is not None:
        return icon
    tpl = _load_svg_tpl(category)
    color = _COLORS.get(category, _COLORS["other"])
    svg_bytes = tpl.format(c=color).encode("utf-8")
    pm = QPixmap()
    pm.loadFromData(QByteArray(svg_bytes))
    icon = QIcon(pm)
    _icon_cache[category] = icon
    return icon
