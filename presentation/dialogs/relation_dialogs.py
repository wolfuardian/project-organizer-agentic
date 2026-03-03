"""專案關聯 + 時間軸對話框."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QDialogButtonBox,
    QHeaderView, QAbstractItemView, QMessageBox, QScrollArea,
)

from database import (
    RELATION_LABELS, PROGRESS_LABELS,
    list_projects, list_relations, add_relation, delete_relation,
    get_timeline,
)
from presentation.widgets.timeline_widget import TimelineWidget


class ProjectRelationsDialog(QDialog):
    """新增 / 刪除專案之間的依賴、相關、參考關係。"""

    def __init__(self, conn, project_id: int, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._project_id = project_id
        row = conn.execute(
            "SELECT name FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        self._project_name = row["name"] if row else f"#{project_id}"
        self.setWindowTitle(f"專案關聯：{self._project_name}")
        self.resize(620, 400)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["來源", "關係", "目標", "備註"])
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("＋ 新增關聯")
        btn_add.clicked.connect(self._add)
        btn_del = QPushButton("－ 刪除")
        btn_del.clicked.connect(self._delete)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load(self) -> None:
        self._relations = list_relations(self._conn, self._project_id)
        self._table.setRowCount(0)
        for rel in self._relations:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(rel["source_name"]))
            self._table.setItem(r, 1, QTableWidgetItem(
                RELATION_LABELS.get(rel["relation_type"], rel["relation_type"])
            ))
            self._table.setItem(r, 2, QTableWidgetItem(rel["target_name"]))
            note_item = QTableWidgetItem(rel["note"] or "")
            note_item.setData(Qt.UserRole, rel["id"])
            self._table.setItem(r, 3, note_item)

    def _add(self) -> None:
        # 取得所有專案（排除自己）
        all_projects = [
            r for r in list_projects(self._conn)
            if r["id"] != self._project_id
        ]
        if not all_projects:
            QMessageBox.information(self, "提示", "沒有其他專案可以建立關聯。")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("新增關聯")
        form = QFormLayout(dlg)

        target_combo = QComboBox()
        for p in all_projects:
            target_combo.addItem(p["name"], p["id"])
        form.addRow("目標專案：", target_combo)

        rel_combo = QComboBox()
        for key, label in RELATION_LABELS.items():
            rel_combo.addItem(label, key)
        form.addRow("關係類型：", rel_combo)

        note_edit = QLineEdit()
        form.addRow("備註：", note_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        if dlg.exec_() == QDialog.Accepted:
            target_id = target_combo.currentData()
            rel_type  = rel_combo.currentData()
            add_relation(self._conn, self._project_id,
                         target_id, rel_type, note_edit.text().strip())
            self._load()

    def _delete(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        rel_id = self._table.item(row, 3).data(Qt.UserRole)
        if rel_id is None:
            return
        reply = QMessageBox.question(self, "確認", "刪除此關聯？")
        if reply == QMessageBox.Yes:
            delete_relation(self._conn, rel_id)
            self._load()


class TimelineDialog(QDialog):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.setWindowTitle("專案時間軸")
        self.resize(760, 460)
        rows = get_timeline(conn)
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = TimelineWidget(rows)
        scroll.setWidget(widget)
        layout.addWidget(scroll)
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
