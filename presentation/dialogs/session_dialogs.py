"""工作階段操作歷史對話框."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QDialogButtonBox,
    QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox,
)


_OP_TYPE_LABELS = {
    "move":   "📦 移動",
    "delete": "🗑 刪除",
    "copy":   "📋 複製",
    "merge":  "🔀 合併",
    "rename": "✏ 重新命名",
}

_STATUS_LABELS = {
    "pending":  "⏳ 待執行",
    "executed": "✅ 已執行",
    "undone":   "↩ 已復原",
    "failed":   "❌ 失敗",
}


class OperationHistoryDialog(QDialog):
    """顯示工作階段的操作歷史，支援復原。"""

    def __init__(self, session_mgr, parent=None):
        super().__init__(parent)
        self._session = session_mgr
        self.setWindowTitle("操作歷史")
        self.resize(800, 450)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["類型", "來源", "目標", "狀態", "時間"]
        )
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_undo_last = QPushButton("↩ 復原最後一步")
        btn_undo_last.clicked.connect(self._undo_last)
        btn_undo_to = QPushButton("↩ 復原到此筆（含之後）")
        btn_undo_to.clicked.connect(self._undo_to_selected)
        btn_row.addWidget(btn_undo_last)
        btn_row.addWidget(btn_undo_to)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load(self) -> None:
        ops = self._session.get_history()
        self._ops = ops
        self._table.setRowCount(0)
        for op in ops:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(
                r, 0, QTableWidgetItem(
                    _OP_TYPE_LABELS.get(op["op_type"], op["op_type"])))
            self._table.setItem(r, 1, QTableWidgetItem(op["source_path"]))
            self._table.setItem(r, 2, QTableWidgetItem(op["dest_path"] or ""))
            self._table.setItem(
                r, 3, QTableWidgetItem(
                    _STATUS_LABELS.get(op["status"], op["status"])))
            self._table.setItem(
                r, 4, QTableWidgetItem(
                    op["executed_at"][:16].replace("T", " ")
                    if op["executed_at"] else ""))

    def _undo_last(self) -> None:
        ok = self._session.undo_last()
        if ok:
            QMessageBox.information(self, "復原", "已復原最後一步操作。")
        else:
            QMessageBox.information(self, "復原", "沒有可復原的操作。")
        self._load()

    def _undo_to_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._ops):
            return
        op = self._ops[row]
        reply = QMessageBox.question(
            self, "確認復原",
            f"復原到此筆操作（含之後的全部）？\n"
            f"這會復原此筆及之後的所有已執行操作。",
        )
        if reply != QMessageBox.Yes:
            return
        count = self._session.undo_to(op["id"])
        QMessageBox.information(self, "復原", f"已復原 {count} 筆操作。")
        self._load()
