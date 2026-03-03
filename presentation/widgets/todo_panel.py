"""TODO 面板 — 嵌入左側欄."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QInputDialog, QMenu,
)

from database import list_todos, add_todo, toggle_todo, delete_todo


class TodoPanel(QWidget):
    """顯示當前專案的 TODO 清單，支援新增、勾選、刪除。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._project_id: int | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("TODO"))
        hdr.addStretch()
        btn_add = QPushButton("＋")
        btn_add.setMaximumWidth(28)
        btn_add.setToolTip("新增 TODO")
        btn_add.clicked.connect(self._add_item)
        hdr.addWidget(btn_add)
        layout.addLayout(hdr)

        self._list = QListWidget()
        self._list.setMaximumHeight(140)
        self._list.itemChanged.connect(self._on_check_changed)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._ctx_menu)
        layout.addWidget(self._list)

    def set_project(self, project_id: int | None) -> None:
        self._project_id = project_id
        self._refresh()

    def _refresh(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        if self._project_id is None:
            self._list.blockSignals(False)
            return
        for row in list_todos(self._conn, self._project_id):
            item = QListWidgetItem(row["title"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if row["done"] else Qt.Unchecked)
            item.setData(Qt.UserRole, row["id"])
            if row["done"]:
                from PySide6.QtGui import QColor
                item.setForeground(QColor("#6c7086"))
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _on_check_changed(self, item: QListWidgetItem) -> None:
        todo_id = item.data(Qt.UserRole)
        if todo_id is not None:
            toggle_todo(self._conn, todo_id)
            self._refresh()

    def _add_item(self) -> None:
        if self._project_id is None:
            return
        title, ok = QInputDialog.getText(self, "新增 TODO", "內容：")
        if ok and title.strip():
            add_todo(self._conn, self._project_id, title.strip())
            self._refresh()

    def _ctx_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_del = menu.addAction("刪除")
        act_del.triggered.connect(lambda: self._delete_item(item))
        menu.exec_(self._list.viewport().mapToGlobal(pos))

    def _delete_item(self, item: QListWidgetItem) -> None:
        todo_id = item.data(Qt.UserRole)
        if todo_id is not None:
            delete_todo(self._conn, todo_id)
            self._refresh()
