"""FlatSearchWidget — 扁平化模糊搜尋面板，取代樹篩選。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListView,
)

from domain.services.fuzzy_match import fuzzy_score_positions
from presentation.widgets.highlight_delegate import HighlightDelegate


class FlatSearchWidget(QWidget):
    """扁平化搜尋：輸入框 + 結果列表，模糊匹配 + 高亮。

    Signals:
        selected(str): 使用者按 Enter 選取項目時發射，參數為 rel_path。
        cancelled(): 使用者按 Escape 時發射。
    """

    selected = Signal(str)   # rel_path
    cancelled = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._flat_cache: list[dict] = []  # [{"name": ..., "rel_path": ...}, ...]

        # 搜尋防抖計時器
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(80)  # 80ms 防抖
        self._debounce.timeout.connect(self._do_search)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._input = QLineEdit()
        self._input.setPlaceholderText("搜尋檔案…")
        self._input.setFixedHeight(28)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.installEventFilter(self)
        layout.addWidget(self._input)

        self._list = QListView()
        self._model = QStandardItemModel()
        self._list.setModel(self._model)
        self._delegate = HighlightDelegate(self._list)
        self._list.setItemDelegate(self._delegate)
        self._list.setEditTriggers(QListView.NoEditTriggers)
        self._list.doubleClicked.connect(self._on_activated)
        layout.addWidget(self._list)

    def set_flat_cache(self, items: list[dict]) -> None:
        """設定扁平快取（通常在載入專案時呼叫）。"""
        self._flat_cache = items

    def activate(self, initial_text: str = "") -> None:
        """顯示並聚焦搜尋框。"""
        self.setVisible(True)
        self._input.setText(initial_text)
        self._input.setFocus()
        self._input.selectAll()

    def deactivate(self) -> None:
        """隱藏搜尋面板。"""
        self._debounce.stop()
        self._input.clear()
        self._model.clear()
        self._delegate.clear_cache()
        self.setVisible(False)

    def eventFilter(self, obj, event):
        if obj is self._input and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key_Escape:
                self.cancelled.emit()
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._select_current()
                return True
            if key == Qt.Key_Down:
                idx = self._list.currentIndex()
                next_row = idx.row() + 1 if idx.isValid() else 0
                if next_row < self._model.rowCount():
                    self._list.setCurrentIndex(self._model.index(next_row, 0))
                return True
            if key == Qt.Key_Up:
                idx = self._list.currentIndex()
                prev_row = idx.row() - 1 if idx.isValid() else 0
                if prev_row >= 0:
                    self._list.setCurrentIndex(self._model.index(prev_row, 0))
                return True
        return super().eventFilter(obj, event)

    def _on_text_changed(self, text: str) -> None:
        if not text.strip():
            self._debounce.stop()
            self._model.clear()
            return
        self._debounce.start()

    def _do_search(self) -> None:
        pattern = self._input.text().strip()
        if not pattern:
            self._model.clear()
            return
        results: list[tuple[int, str, str, list[int]]] = []
        for item in self._flat_cache:
            name = item.get("name", "")
            score, positions = fuzzy_score_positions(pattern, name)
            if score >= 0:
                results.append((score, name, item.get("rel_path", ""), positions))
        results.sort(key=lambda x: x[0], reverse=True)
        # 批次更新：先清空再一次加入，避免逐筆 appendRow 觸發 N 次 layout
        self._model.setRowCount(0)
        items = []
        for score, name, rel_path, positions in results[:50]:
            si = QStandardItem(name)
            si.setData(rel_path, Qt.UserRole)       # rel_path
            si.setData(positions, Qt.UserRole + 1)   # match positions
            si.setToolTip(rel_path)
            items.append(si)
        if items:
            self._model.invisibleRootItem().appendRows(items)
        if self._model.rowCount() > 0:
            self._list.setCurrentIndex(self._model.index(0, 0))

    def _on_activated(self, index) -> None:
        rel_path = index.data(Qt.UserRole)
        if rel_path:
            self.selected.emit(rel_path)

    def _select_current(self) -> None:
        idx = self._list.currentIndex()
        if idx.isValid():
            rel_path = idx.data(Qt.UserRole)
            if rel_path:
                self.selected.emit(rel_path)
