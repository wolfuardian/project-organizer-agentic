"""專案相關對話框 — 多根目錄管理."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QDialogButtonBox,
    QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
    QFileDialog, QInputDialog, QMessageBox,
)

from database import (
    list_project_roots, add_project_root, remove_project_root,
    update_project_root, PROJECT_ROOT_ROLES,
)
from scanner import scan_directory


class ProjectRootsDialog(QDialog):
    """管理專案的多根目錄：新增 / 移除 / 改角色。"""

    def __init__(self, conn, project_id: int, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._project_id = project_id
        self.setWindowTitle("管理根目錄")
        self.resize(650, 350)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["路徑", "角色", "標籤", "新增時間"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("＋ 新增根目錄")
        btn_add.clicked.connect(self._add_root)
        btn_edit = QPushButton("編輯角色")
        btn_edit.clicked.connect(self._edit_root)
        btn_del = QPushButton("－ 移除")
        btn_del.clicked.connect(self._remove_root)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_edit)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load(self) -> None:
        self._roots = list_project_roots(self._conn, self._project_id)
        self._table.setRowCount(0)
        invalid_color = QColor("#f38ba8")
        for r in self._roots:
            row = self._table.rowCount()
            self._table.insertRow(row)
            valid = Path(r["root_path"]).is_dir()
            path_text = r["root_path"] if valid else f"⚠ {r['root_path']}"
            items = [
                QTableWidgetItem(path_text),
                QTableWidgetItem(r["role"]),
                QTableWidgetItem(r["label"] or ""),
                QTableWidgetItem(
                    r["added_at"][:16].replace("T", " ") if r["added_at"] else ""),
            ]
            for col, item in enumerate(items):
                if not valid:
                    item.setForeground(invalid_color)
                    if col == 0:
                        item.setToolTip("路徑不存在")
                self._table.setItem(row, col, item)

    def _add_root(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "選擇根目錄")
        if not folder:
            return
        role, ok = QInputDialog.getItem(
            self, "選擇角色", "角色：", PROJECT_ROOT_ROLES, 1, False,
        )
        if not ok:
            return
        label, ok2 = QInputDialog.getText(
            self, "標籤", "可選標籤（留空使用角色名稱）：",
        )
        try:
            root_id = add_project_root(
                self._conn, self._project_id, folder, role,
                label.strip() if ok2 else "",
            )
            # 自動掃描新根目錄
            path = Path(folder)
            if path.exists():
                scan_directory(self._conn, self._project_id, path,
                               root_id=root_id)
                self._conn.commit()
        except Exception as e:
            QMessageBox.warning(self, "錯誤", str(e))
            return
        self._load()

    def _edit_root(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._roots):
            return
        r = self._roots[row]
        role, ok = QInputDialog.getItem(
            self, "修改角色", "角色：", PROJECT_ROOT_ROLES,
            PROJECT_ROOT_ROLES.index(r["role"]) if r["role"] in PROJECT_ROOT_ROLES else 0,
            False,
        )
        if not ok:
            return
        label, ok2 = QInputDialog.getText(
            self, "標籤", "標籤：", text=r["label"] or "",
        )
        if not ok2:
            return
        update_project_root(self._conn, r["id"], role, label.strip())
        self._load()

    def _remove_root(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._roots):
            return
        r = self._roots[row]
        if len(self._roots) <= 1:
            QMessageBox.warning(self, "錯誤", "專案至少需保留一個根目錄。")
            return
        reply = QMessageBox.question(
            self, "確認",
            f"移除根目錄「{r['root_path']}」？\n"
            "（會同時移除該根下的所有節點記錄，不影響實際檔案）",
        )
        if reply == QMessageBox.Yes:
            remove_project_root(self._conn, r["id"])
            self._load()
