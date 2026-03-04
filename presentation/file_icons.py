"""Material 風格檔案類型圖示 — 內嵌 SVG，零外部依賴。"""

from __future__ import annotations

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QIcon, QPixmap

# ── SVG 模板 ─────────────────────────────────────────────

_SVGS: dict[str, str] = {
    "folder": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<path d="M1 3h5l2 2h7v8H1z" fill="{c}" opacity="0.9"/>'
        '</svg>'
    ),
    "virtual": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<path d="M1 3h5l2 2h7v8H1z" fill="none" stroke="{c}" '
        'stroke-width="1.2" stroke-dasharray="2,1.5"/>'
        '</svg>'
    ),
    "image": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<rect x="1" y="2" width="14" height="12" rx="1.5" fill="#2a2040"/>'
        '<circle cx="5" cy="6" r="1.8" fill="{c}"/>'
        '<path d="M1 11l4-4 3 3 2-2 5 4H1z" fill="{c}" opacity="0.7"/>'
        '</svg>'
    ),
    "video": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<rect x="1" y="3" width="14" height="10" rx="2" fill="#2a2020"/>'
        '<path d="M6 6v4l4.5-2z" fill="{c}"/>'
        '</svg>'
    ),
    "audio": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<circle cx="6" cy="11" r="2.5" fill="{c}"/>'
        '<path d="M8.5 11V3l5-1.5v2L8.5 5" fill="none" stroke="{c}" '
        'stroke-width="1.5" stroke-linecap="round"/>'
        '</svg>'
    ),
    "code": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<path d="M5 4L1.5 8 5 12" fill="none" stroke="{c}" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M11 4l3.5 4L11 12" fill="none" stroke="{c}" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="9" y1="2.5" x2="7" y2="13.5" stroke="{c}" '
        'stroke-width="1.2" opacity="0.6"/>'
        '</svg>'
    ),
    "document": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<path d="M3 1h7l3 3v11H3z" fill="#2a2a20"/>'
        '<path d="M10 1v3h3" fill="none" stroke="{c}" stroke-width="0.8"/>'
        '<line x1="5" y1="7" x2="11" y2="7" stroke="{c}" stroke-width="1" opacity="0.7"/>'
        '<line x1="5" y1="9.5" x2="11" y2="9.5" stroke="{c}" stroke-width="1" opacity="0.5"/>'
        '<line x1="5" y1="12" x2="9" y2="12" stroke="{c}" stroke-width="1" opacity="0.35"/>'
        '</svg>'
    ),
    "archive": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<rect x="2" y="1" width="12" height="14" rx="1.5" fill="#2a2010"/>'
        '<rect x="6.5" y="1" width="3" height="2" fill="{c}" opacity="0.6"/>'
        '<rect x="6.5" y="4" width="3" height="2" fill="{c}" opacity="0.6"/>'
        '<rect x="6.5" y="7" width="3" height="2" fill="{c}" opacity="0.6"/>'
        '<rect x="5.5" y="10" width="5" height="3" rx="0.8" fill="none" '
        'stroke="{c}" stroke-width="1"/>'
        '</svg>'
    ),
    "data": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<rect x="1" y="2" width="14" height="12" rx="1.5" fill="#1a2030"/>'
        '<line x1="6" y1="2" x2="6" y2="14" stroke="{c}" stroke-width="0.6" opacity="0.4"/>'
        '<line x1="11" y1="2" x2="11" y2="14" stroke="{c}" stroke-width="0.6" opacity="0.4"/>'
        '<line x1="1" y1="6" x2="15" y2="6" stroke="{c}" stroke-width="0.6" opacity="0.4"/>'
        '<line x1="1" y1="10" x2="15" y2="10" stroke="{c}" stroke-width="0.6" opacity="0.4"/>'
        '<rect x="1" y="2" width="14" height="12" rx="1.5" fill="none" '
        'stroke="{c}" stroke-width="0.8"/>'
        '</svg>'
    ),
    "font": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<text x="8" y="13" font-family="serif" font-size="13" '
        'font-weight="bold" text-anchor="middle" fill="{c}">A</text>'
        '</svg>'
    ),
    "3d": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<path d="M8 1L2 4.5v7L8 15l6-3.5v-7z" fill="none" stroke="{c}" '
        'stroke-width="1.2" stroke-linejoin="round"/>'
        '<path d="M8 8L2 4.5M8 8l6-3.5M8 8v7" fill="none" stroke="{c}" '
        'stroke-width="0.8" opacity="0.5"/>'
        '</svg>'
    ),
    "other": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<path d="M3 1h7l3 3v11H3z" fill="#282828"/>'
        '<path d="M10 1v3h3" fill="none" stroke="{c}" stroke-width="0.8"/>'
        '</svg>'
    ),
}

# 分類 → 主色
_COLORS: dict[str, str] = {
    "folder":   "#5fd7ff",
    "virtual":  "#5fd7ff",
    "image":    "#d787ff",
    "video":    "#ff875f",
    "audio":    "#ffaf00",
    "code":     "#87ff87",
    "document": "#ffffaf",
    "archive":  "#ff8700",
    "data":     "#afd7ff",
    "font":     "#d7afd7",
    "3d":       "#afffaf",
    "other":    "#c8c8c8",
}

# 類別層級快取（只渲染一次）
_icon_cache: dict[str, QIcon] = {}


def get_category_icon(category: str) -> QIcon:
    """回傳檔案分類對應的 Material 風格 QIcon（快取）。"""
    icon = _icon_cache.get(category)
    if icon is not None:
        return icon
    svg_tpl = _SVGS.get(category, _SVGS["other"])
    color = _COLORS.get(category, _COLORS["other"])
    svg_bytes = svg_tpl.format(c=color).encode("utf-8")
    pm = QPixmap()
    pm.loadFromData(QByteArray(svg_bytes))
    icon = QIcon(pm)
    _icon_cache[category] = icon
    return icon
