"""DualPanelWidget — 雙面板檔案樹，F6 切換第二面板（僅即時模式）。"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QSplitter, QWidget, QVBoxLayout, QComboBox,
    QTreeView, QAbstractItemView,
)

from database import list_projects, list_project_roots
from presentation.tree_model import ProjectTreeModel, setup_tree_header


class _TreePanel(QWidget):
    """單一面板：專案選擇器 + QTreeView。"""

    project_changed = Signal(int)  # 發射 project_id

    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._project_id: int | None = None
        self._model: ProjectTreeModel | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._combo = QComboBox()
        self._combo.setFixedHeight(24)
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self._combo)

        self.tree = QTreeView()
        self.tree.setHeaderHidden(False)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setAnimated(False)
        self.tree.setIndentation(20)
        layout.addWidget(self.tree)

    def load_projects(self) -> None:
        """重新載入專案列表到 combo。"""
        self._combo.blockSignals(True)
        self._combo.clear()
        for row in list_projects(self._conn):
            self._combo.addItem(row["name"], row["id"])
        self._combo.blockSignals(False)

    def select_project(self, project_id: int) -> None:
        """程式化選取指定專案。"""
        for i in range(self._combo.count()):
            if self._combo.itemData(i) == project_id:
                self._combo.setCurrentIndex(i)
                return

    def _on_combo_changed(self, index: int) -> None:
        if index < 0:
            return
        pid = self._combo.itemData(index)
        if pid is None:
            return
        self._project_id = pid
        self._model = ProjectTreeModel(self._conn, pid)
        self.tree.setModel(self._model)
        setup_tree_header(self.tree.header())
        self.project_changed.emit(pid)

    @property
    def project_id(self) -> int | None:
        return self._project_id

    @property
    def model(self) -> ProjectTreeModel | None:
        return self._model


