"""搜尋導航 mixin — 扁平搜尋 + eventFilter + 節點導航。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QEvent

if TYPE_CHECKING:
    from presentation.main_window import MainWindow


class NavigationMixin:
    """扁平搜尋（可列印字元觸發）+ 鍵盤事件攔截 + 節點導航。"""

    def eventFilter(self, obj, event):
        if obj is self._tree_view and event.type() == QEvent.KeyPress:
            text = event.text()
            mods = event.modifiers()
            # 可列印字元（無 Ctrl/Alt 修飾）→ 啟動扁平搜尋
            if (text and text.isprintable()
                    and not (mods & (Qt.ControlModifier | Qt.AltModifier))):
                self._tree_view.setVisible(False)
                self._flat_search.activate(text)
                return True
        return super().eventFilter(obj, event)

    def _on_flat_search_selected(self, rel_path: str) -> None:
        """使用者在扁平搜尋中選取項目 → 導航至樹節點。"""
        self._flat_search.deactivate()
        self._tree_view.setVisible(True)
        self._tree_view.setFocus()
        self._navigate_to_node(rel_path)

    def _on_flat_search_cancelled(self) -> None:
        """使用者按 Escape → 關閉扁平搜尋，回到樹。"""
        self._flat_search.deactivate()
        self._tree_view.setVisible(True)
        self._tree_view.setFocus()

    def _navigate_to_node(self, rel_path: str) -> None:
        """在樹中定位並選取指定 rel_path 的節點。"""
        if not self._tree_model:
            return
        node = self._tree_model._node_map.get(self._rel_path_to_db_id.get(rel_path))
        if not node:
            return
        idx = self._tree_model.createIndex(node.row, 0, node)
        parent = node.parent
        while parent and parent is not self._tree_model._root:
            parent_idx = self._tree_model.createIndex(parent.row, 0, parent)
            self._tree_view.expand(parent_idx)
            parent = parent.parent
        self._tree_view.setCurrentIndex(idx)
        self._tree_view.scrollTo(idx)
