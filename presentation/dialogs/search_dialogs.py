"""搜尋與過濾對話框 — 全域搜尋、進階過濾、模糊跳轉."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox,
    QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QDialogButtonBox,
    QHeaderView, QAbstractItemView,
)

from database import search_nodes, filter_nodes, all_tags_flat
from fuzzy import fuzzy_filter


_ALL_CATEGORIES = [
    "image", "video", "audio", "code", "document",
    "archive", "data", "font", "3d", "other",
]


class QuickJumpDialog(QDialog):
    """Ctrl+P 風格模糊搜尋：即時輸入即時過濾，Enter 開啟，方向鍵導航。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._all_items: list[dict] = []
        self.setWindowTitle("快速跳轉")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.resize(600, 380)
        self._build_ui()
        self._load_all()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._input = QLineEdit()
        self._input.setPlaceholderText("輸入檔名進行模糊搜尋…")
        self._input.textChanged.connect(self._on_input)
        self._input.installEventFilter(self)
        layout.addWidget(self._input)

        self._list = QListWidget()
        self._list.itemActivated.connect(self._open_item)
        layout.addWidget(self._list)

        self._lbl = QLabel("輸入關鍵字開始搜尋")
        self._lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._lbl)

    def _load_all(self) -> None:
        """一次性載入所有節點供模糊比對（排除資料夾）。"""
        rows = self._conn.execute("""
            SELECT n.id, n.name, n.rel_path, n.node_type,
                   p.name AS project_name, p.root_path
            FROM nodes n
            JOIN projects p ON p.id = n.project_id
            WHERE n.node_type = 'file'
            ORDER BY n.name
        """).fetchall()
        self._all_items = [dict(r) for r in rows]

    def _on_input(self, text: str) -> None:
        self._list.clear()
        if not text:
            self._lbl.setText("輸入關鍵字開始搜尋")
            return
        results = fuzzy_filter(text, self._all_items, key="name", limit=50)
        for item_data in results:
            display = f"{item_data['name']}  —  {item_data['project_name']}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, item_data)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)
        self._lbl.setText(f"{len(results)} 筆")

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent
        if obj is self._input and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Down:
                row = self._list.currentRow()
                self._list.setCurrentRow(min(row + 1, self._list.count() - 1))
                return True
            if key == Qt.Key_Up:
                row = self._list.currentRow()
                self._list.setCurrentRow(max(row - 1, 0))
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                item = self._list.currentItem()
                if item:
                    self._open_item(item)
                return True
            if key == Qt.Key_Escape:
                self.reject()
                return True
        return super().eventFilter(obj, event)

    def _open_item(self, item: QListWidgetItem) -> None:
        import subprocess, sys
        data = item.data(Qt.UserRole)
        if not data:
            return
        p = Path(data["root_path"]) / data["rel_path"]
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(p)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p.parent)])
        self.accept()


class SearchDialog(QDialog):
    """跨專案搜尋檔名、備註、標籤，雙擊結果可在檔案管理器中開啟。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("全域搜尋")
        self.resize(720, 460)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("搜尋檔名、備註、標籤…")
        self._input.textChanged.connect(self._search)
        top.addWidget(self._input)
        self._lbl_count = QLabel("0 筆")
        top.addWidget(self._lbl_count)
        layout.addLayout(top)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["檔名", "分類", "專案", "相對路徑"])
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.doubleClicked.connect(self._open_item)
        layout.addWidget(self._table)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._input.setFocus()

    def _search(self, query: str) -> None:
        self._table.setRowCount(0)
        if len(query) < 2:
            self._lbl_count.setText("0 筆")
            return
        rows = search_nodes(self._conn, query)
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(row["name"]))
            self._table.setItem(r, 1, QTableWidgetItem(row["category"] or "—"))
            self._table.setItem(r, 2, QTableWidgetItem(row["project_name"]))
            path_item = QTableWidgetItem(row["rel_path"])
            path_item.setData(Qt.UserRole, {
                "abs_path": str(Path(row["root_path"]) / row["rel_path"]),
                "node_type": row["node_type"],
            })
            self._table.setItem(r, 3, path_item)
        self._lbl_count.setText(f"{len(rows)} 筆")

    def _open_item(self, index) -> None:
        import subprocess, sys
        item = self._table.item(index.row(), 3)
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        p = Path(data["abs_path"])
        if sys.platform == "win32":
            if p.is_dir():
                subprocess.Popen(["explorer", str(p)])
            else:
                subprocess.Popen(["explorer", "/select,", str(p)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p.parent if p.is_file() else p)])


class FilterDialog(QDialog):
    """組合條件過濾節點：類別、標籤、大小範圍、修改日期。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("進階過濾器")
        self.resize(800, 520)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── 條件區 ──────────────────────────────────────
        cond = QHBoxLayout()

        # 類別 (多選)
        cat_box = QVBoxLayout()
        cat_box.addWidget(QLabel("檔案類別："))
        self._cat_checks: dict[str, QCheckBox] = {}
        for cat in _ALL_CATEGORIES:
            cb = QCheckBox(cat)
            self._cat_checks[cat] = cb
            cat_box.addWidget(cb)
        cat_box.addStretch()
        cond.addLayout(cat_box)

        # 標籤 (多選)
        tag_box = QVBoxLayout()
        tag_box.addWidget(QLabel("標籤（AND）："))
        self._tag_list = QListWidget()
        self._tag_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self._tag_list.setMaximumHeight(200)
        for tag in all_tags_flat(self._conn):
            item = QListWidgetItem(tag["name"])
            item.setData(Qt.UserRole, tag["id"])
            self._tag_list.addItem(item)
        tag_box.addWidget(self._tag_list)
        tag_box.addStretch()
        cond.addLayout(tag_box)

        # 大小 + 日期
        right_box = QVBoxLayout()
        right_box.addWidget(QLabel("大小範圍（KB，留空不限）："))
        size_row = QHBoxLayout()
        self._min_size = QLineEdit(); self._min_size.setPlaceholderText("最小")
        self._max_size = QLineEdit(); self._max_size.setPlaceholderText("最大")
        size_row.addWidget(self._min_size)
        size_row.addWidget(QLabel("~"))
        size_row.addWidget(self._max_size)
        right_box.addLayout(size_row)

        right_box.addWidget(QLabel("修改日期（YYYY-MM-DD，留空不限）："))
        date_row = QHBoxLayout()
        self._date_after  = QLineEdit(); self._date_after.setPlaceholderText("起始")
        self._date_before = QLineEdit(); self._date_before.setPlaceholderText("結束")
        date_row.addWidget(self._date_after)
        date_row.addWidget(QLabel("~"))
        date_row.addWidget(self._date_before)
        right_box.addLayout(date_row)
        right_box.addStretch()
        cond.addLayout(right_box)

        layout.addLayout(cond)

        btn_row = QHBoxLayout()
        btn_run = QPushButton("執行過濾")
        btn_run.clicked.connect(self._run)
        btn_clear = QPushButton("清除條件")
        btn_clear.clicked.connect(self._clear)
        self._lbl_count = QLabel("0 筆")
        btn_row.addWidget(btn_run)
        btn_row.addWidget(btn_clear)
        btn_row.addWidget(self._lbl_count)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── 結果表格 ─────────────────────────────────────
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["檔名", "類別", "大小", "修改時間", "專案 / 路徑"]
        )
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.doubleClicked.connect(self._open_item)
        layout.addWidget(self._table)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _run(self) -> None:
        cats = [c for c, cb in self._cat_checks.items() if cb.isChecked()]
        tag_ids = [
            item.data(Qt.UserRole)
            for item in self._tag_list.selectedItems()
        ]

        def _kb(text: str) -> Optional[int]:
            t = text.strip()
            return int(float(t) * 1024) if t else None

        def _date(text: str) -> Optional[str]:
            t = text.strip()
            return t if t else None

        rows = filter_nodes(
            self._conn,
            categories=cats or None,
            tag_ids=tag_ids or None,
            min_size=_kb(self._min_size.text()),
            max_size=_kb(self._max_size.text()),
            modified_after=_date(self._date_after.text()),
            modified_before=_date(self._date_before.text()),
        )
        self._table.setRowCount(0)
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(row["name"]))
            self._table.setItem(r, 1, QTableWidgetItem(row["category"] or "—"))
            sz = row["file_size"]
            size_str = (f"{sz/1024:.1f} KB" if sz else "—")
            self._table.setItem(r, 2, QTableWidgetItem(size_str))
            mtime = (row["modified_at"] or "—")[:16].replace("T", " ")
            self._table.setItem(r, 3, QTableWidgetItem(mtime))
            loc = f"{row['project_name']} / {row['rel_path']}"
            loc_item = QTableWidgetItem(loc)
            loc_item.setData(Qt.UserRole, {
                "abs_path": str(Path(row["root_path"]) / row["rel_path"]),
                "node_type": row["node_type"],
            })
            self._table.setItem(r, 4, loc_item)
        self._lbl_count.setText(f"{len(rows)} 筆")

    def _clear(self) -> None:
        for cb in self._cat_checks.values():
            cb.setChecked(False)
        self._tag_list.clearSelection()
        for w in (self._min_size, self._max_size,
                  self._date_after, self._date_before):
            w.clear()

    def _open_item(self, index) -> None:
        import subprocess, sys
        item = self._table.item(index.row(), 4)
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        p = Path(data["abs_path"])
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(p)]
                             if p.is_file() else ["explorer", str(p)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p.parent if p.is_file() else p)])
