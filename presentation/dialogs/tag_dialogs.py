"""標籤管理對話框."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QDialogButtonBox, QInputDialog, QMessageBox,
    QTreeWidget, QTreeWidgetItem,
)

from database import list_tags, create_tag, delete_tag


class TagManagerDialog(QDialog):
    """建立 / 刪除標籤，支援多層級（父標籤）。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("管理標籤")
        self.resize(500, 380)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["標籤名稱", "顏色"])
        self._tree.setColumnWidth(0, 260)
        layout.addWidget(self._tree)

        btn_row = QHBoxLayout()
        for label, slot in [
            ("＋ 新增標籤",   self._add_tag),
            ("＋ 新增子標籤", self._add_child_tag),
            ("－ 刪除",       self._delete_tag),
        ]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load(self) -> None:
        self._tree.clear()
        self._item_map: dict[int, QTreeWidgetItem] = {}

        def _add_rows(parent_id, parent_item):
            for row in list_tags(self._conn, parent_id):
                item = QTreeWidgetItem(
                    parent_item if parent_item else self._tree,
                    [row["name"], row["color"]],
                )
                item.setData(0, Qt.UserRole, row["id"])
                from PySide6.QtGui import QColor
                item.setForeground(1, QColor(row["color"]))
                self._item_map[row["id"]] = item
                _add_rows(row["id"], item)

        _add_rows(None, None)
        self._tree.expandAll()

    def _add_tag(self, parent_id: int = None) -> None:
        name, ok = QInputDialog.getText(self, "新增標籤", "標籤名稱：")
        if not ok or not name.strip():
            return
        color, ok2 = QInputDialog.getText(
            self, "標籤顏色", "顏色（hex，如 #89b4fa）：", text="#89b4fa"
        )
        if not ok2:
            return
        create_tag(self._conn, name.strip(),
                   color.strip() or "#89b4fa", parent_id)
        self._load()

    def _add_child_tag(self) -> None:
        item = self._tree.currentItem()
        parent_id = item.data(0, Qt.UserRole) if item else None
        self._add_tag(parent_id)

    def _delete_tag(self) -> None:
        item = self._tree.currentItem()
        if not item:
            return
        tag_id = item.data(0, Qt.UserRole)
        reply = QMessageBox.question(
            self, "確認", f"刪除標籤「{item.text(0)}」及其所有子標籤？"
        )
        if reply == QMessageBox.Yes:
            delete_tag(self._conn, tag_id)
            self._load()
