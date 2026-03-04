"""HighlightDelegate — QStyledItemDelegate 繪製匹配字元高亮。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QModelIndex, QRectF
from PySide6.QtGui import QPainter, QColor, QTextDocument, QAbstractTextDocumentLayout
from PySide6.QtWidgets import (
    QStyledItemDelegate, QStyleOptionViewItem, QApplication, QStyle,
)

HIGHLIGHT_COLOR = "#f9e2af"  # Catppuccin yellow


class HighlightDelegate(QStyledItemDelegate):
    """將 item 文字中指定位置的字元以高亮色彩繪製。

    每筆 item 的 Qt.UserRole+1 應存放 list[int]（匹配位置索引）。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._doc = QTextDocument()
        self._html_cache: dict[tuple, str] = {}  # (text, positions_tuple) → html

    def clear_cache(self) -> None:
        """清除 HTML 快取。"""
        self._html_cache.clear()

    def _build_html(self, text: str, positions: list[int]) -> str:
        key = (text, tuple(positions))
        cached = self._html_cache.get(key)
        if cached is not None:
            return cached
        pos_set = set(positions)
        html_parts: list[str] = []
        for i, ch in enumerate(text):
            escaped = ch.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if i in pos_set:
                html_parts.append(
                    f'<span style="color:{HIGHLIGHT_COLOR};font-weight:bold">'
                    f'{escaped}</span>'
                )
            else:
                html_parts.append(escaped)
        html = "".join(html_parts)
        self._html_cache[key] = html
        return html

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index: QModelIndex) -> None:
        positions = index.data(Qt.UserRole + 1)
        text = index.data(Qt.DisplayRole) or ""

        if not positions or not text:
            super().paint(painter, option, index)
            return

        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter, option.widget)

        html = self._build_html(text, positions)

        doc = self._doc
        doc.setDefaultFont(option.font)
        doc.setHtml(html)
        doc.setTextWidth(option.rect.width())

        painter.save()
        painter.translate(option.rect.topLeft())
        painter.setClipRect(QRectF(0, 0, option.rect.width(), option.rect.height()))
        doc.drawContents(painter)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem,
                 index: QModelIndex):
        return super().sizeHint(option, index)
