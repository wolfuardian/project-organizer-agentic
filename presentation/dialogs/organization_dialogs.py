"""整理工具對話框 — 規則管理、重複偵測、批次重新命名."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QDialogButtonBox,
    QHeaderView, QAbstractItemView, QMessageBox,
)

from database import PROGRESS_LABELS
from rule_engine import list_rules, add_rule, update_rule, delete_rule
from duplicate_finder import find_duplicates
from batch_rename import build_previews, execute_renames


CATEGORIES = ["image", "video", "audio", "code", "document",
              "archive", "data", "font", "3d", "other"]


class RulesDialog(QDialog):
    """檢視、新增、刪除自訂分類規則."""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("自訂分類規則")
        self.resize(720, 400)
        self._build_ui()
        self._load_rules()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["名稱", "模式", "類型", "比對目標", "分類", "啟用"]
        )
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("＋ 新增規則")
        btn_add.clicked.connect(self._add_rule)
        btn_del = QPushButton("－ 刪除規則")
        btn_del.clicked.connect(self._delete_rule)
        btn_toggle = QPushButton("啟用 / 停用")
        btn_toggle.clicked.connect(self._toggle_rule)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addWidget(btn_toggle)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load_rules(self) -> None:
        self._rules = list_rules(self._conn)
        self._table.setRowCount(0)
        for rule in self._rules:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(rule.name))
            self._table.setItem(r, 1, QTableWidgetItem(rule.pattern))
            self._table.setItem(r, 2, QTableWidgetItem(rule.pattern_type))
            self._table.setItem(r, 3, QTableWidgetItem(rule.match_target))
            self._table.setItem(r, 4, QTableWidgetItem(rule.category))
            enabled_item = QTableWidgetItem("Y" if rule.enabled else "N")
            enabled_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(r, 5, enabled_item)

    def _add_rule(self) -> None:
        dlg = RuleEditDialog(self._conn, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._load_rules()

    def _delete_rule(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._rules):
            return
        rule = self._rules[row]
        reply = QMessageBox.question(self, "確認", f"刪除規則「{rule.name}」？")
        if reply == QMessageBox.Yes:
            delete_rule(self._conn, rule.id)
            self._load_rules()

    def _toggle_rule(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._rules):
            return
        rule = self._rules[row]
        update_rule(self._conn, rule.id, enabled=0 if rule.enabled else 1)
        self._load_rules()


class RuleEditDialog(QDialog):
    """新增規則對話框."""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("新增分類規則")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)

        self._name = QLineEdit()
        self._name.setPlaceholderText("例：忽略暫存檔")
        layout.addRow("名稱：", self._name)

        self._pattern = QLineEdit()
        self._pattern.setPlaceholderText("例：*.tmp  或  ^test_.*\\.py$")
        layout.addRow("模式：", self._pattern)

        self._ptype = QComboBox()
        self._ptype.addItems(["glob", "regex"])
        layout.addRow("模式類型：", self._ptype)

        self._target = QComboBox()
        self._target.addItems(["name", "path"])
        layout.addRow("比對目標：", self._target)

        self._category = QComboBox()
        self._category.addItems(CATEGORIES)
        layout.addRow("分類：", self._category)

        self._priority = QSpinBox()
        self._priority.setRange(1, 999)
        self._priority.setValue(100)
        layout.addRow("優先度（小優先）：", self._priority)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _save(self) -> None:
        name = self._name.text().strip()
        pattern = self._pattern.text().strip()
        if not name or not pattern:
            QMessageBox.warning(self, "缺少資料", "名稱與模式不可空白。")
            return
        add_rule(
            self._conn,
            name=name,
            pattern=pattern,
            pattern_type=self._ptype.currentText(),
            match_target=self._target.currentText(),
            category=self._category.currentText(),
            priority=self._priority.value(),
        )
        self.accept()


class DuplicateDialog(QDialog):
    """偵測並顯示重複檔案群組，支援在檔案管理器中開啟。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("重複檔案偵測")
        self.resize(860, 500)
        self._groups: list = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self._btn_scan = QPushButton("開始掃描（所有專案）")
        self._btn_scan.clicked.connect(self._scan)
        self._lbl_status = QLabel("尚未掃描")
        top.addWidget(self._btn_scan)
        top.addWidget(self._lbl_status)
        top.addStretch()
        layout.addLayout(top)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["檔名", "大小", "專案", "相對路徑"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_open = QPushButton("在檔案管理器中開啟")
        btn_open.clicked.connect(self._open_selected)
        btn_row.addWidget(btn_open)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _scan(self) -> None:
        self._btn_scan.setEnabled(False)
        self._lbl_status.setText("掃描中…")
        self._table.setRowCount(0)
        groups = find_duplicates(self._conn)
        self._on_scan_done(groups)

    def _on_scan_done(self, groups) -> None:
        self._groups = groups
        self._table.setRowCount(0)
        for group in groups:
            # 群組分隔行（顯示 hash 與大小）
            sep_row = self._table.rowCount()
            self._table.insertRow(sep_row)
            size_str = self._fmt_size(group.file_size)
            sep_item = QTableWidgetItem(
                f"▶ {len(group.files)} 個重複  ({size_str} each)  MD5: {group.file_hash}"
            )
            sep_item.setBackground(Qt.darkGray)
            self._table.setItem(sep_row, 0, sep_item)
            self._table.setSpan(sep_row, 0, 1, 4)

            for f in group.files:
                r = self._table.rowCount()
                self._table.insertRow(r)
                name = Path(f["rel_path"]).name
                self._table.setItem(r, 0, QTableWidgetItem(name))
                self._table.setItem(r, 1, QTableWidgetItem(self._fmt_size(f["file_size"])))
                self._table.setItem(r, 2, QTableWidgetItem(f["project_name"]))
                item_path = QTableWidgetItem(f["rel_path"])
                item_path.setData(Qt.UserRole, f["abs_path"])
                self._table.setItem(r, 3, item_path)

        total = sum(len(g.files) - 1 for g in groups)
        self._lbl_status.setText(
            f"找到 {len(groups)} 組重複，共 {total} 個多餘複本"
            if groups else "未發現重複檔案"
        )
        self._btn_scan.setEnabled(True)

    def _open_selected(self) -> None:
        import subprocess, sys
        row = self._table.currentRow()
        if row < 0:
            return
        item = self._table.item(row, 3)
        if not item:
            return
        abs_path = item.data(Qt.UserRole)
        if not abs_path:
            return
        p = Path(abs_path)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(p)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p.parent)])

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size >= 1_048_576:
            return f"{size / 1_048_576:.1f} MB"
        if size >= 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size} B"


class BatchRenameDialog(QDialog):
    """批次重新命名：樣板、前後綴、序號、regex 替換，含即時預覽。"""

    def __init__(self, files: list, conn, project_id: int, parent=None):
        super().__init__(parent)
        self._files = files
        self._conn = conn
        self._project_id = project_id
        self.setWindowTitle(f"批次重新命名（{len(files)} 個檔案）")
        self.resize(800, 540)
        self._build_ui()
        self._refresh_preview()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self._template = QLineEdit("{stem}{ext}")
        self._template.setPlaceholderText("{stem}  {ext}  {n}  {n:03}")
        self._template.textChanged.connect(self._refresh_preview)
        form.addRow("樣板：", self._template)

        self._prefix = QLineEdit()
        self._prefix.textChanged.connect(self._refresh_preview)
        form.addRow("前綴：", self._prefix)

        self._suffix = QLineEdit()
        self._suffix.textChanged.connect(self._refresh_preview)
        form.addRow("後綴：", self._suffix)

        row_n = QHBoxLayout()
        self._start = QSpinBox(); self._start.setRange(0, 9999); self._start.setValue(1)
        self._step  = QSpinBox(); self._step.setRange(1, 100);   self._step.setValue(1)
        self._start.valueChanged.connect(self._refresh_preview)
        self._step.valueChanged.connect(self._refresh_preview)
        row_n.addWidget(QLabel("起始序號："))
        row_n.addWidget(self._start)
        row_n.addWidget(QLabel("  間距："))
        row_n.addWidget(self._step)
        row_n.addStretch()
        form.addRow(row_n)

        self._regex_find = QLineEdit()
        self._regex_find.setPlaceholderText("Regex 搜尋（留空不套用）")
        self._regex_find.textChanged.connect(self._refresh_preview)
        form.addRow("Regex 搜尋：", self._regex_find)

        self._regex_replace = QLineEdit()
        self._regex_replace.textChanged.connect(self._refresh_preview)
        form.addRow("Regex 替換：", self._regex_replace)

        layout.addLayout(form)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["原始名稱", "新名稱（預覽）"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self._table)

        self._lbl_info = QLabel("")
        layout.addWidget(self._lbl_info)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("執行重新命名")
        btns.accepted.connect(self._execute)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _refresh_preview(self) -> None:
        from PySide6.QtGui import QColor
        previews = build_previews(
            self._files,
            template=self._template.text() or "{stem}{ext}",
            prefix=self._prefix.text(),
            suffix=self._suffix.text(),
            regex_find=self._regex_find.text(),
            regex_replace=self._regex_replace.text(),
            start=self._start.value(),
            step=self._step.value(),
        )
        self._previews = previews
        self._table.setRowCount(0)
        changes = 0
        for pv in previews:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(pv.original))
            new_item = QTableWidgetItem(pv.new_name)
            if pv.conflict:
                new_item.setForeground(QColor("#f38ba8"))  # 紅色警示
            elif pv.new_name != pv.original:
                new_item.setForeground(QColor("#a6e3a1"))  # 綠色
                changes += 1
            self._table.setItem(r, 1, new_item)
        conflicts = sum(1 for p in previews if p.conflict)
        self._lbl_info.setText(
            f"將重新命名 {changes} 個檔案" +
            (f"  {conflicts} 個衝突（紅色標示，將略過）" if conflicts else "")
        )

    def _execute(self) -> None:
        if not hasattr(self, "_previews"):
            return
        reply = QMessageBox.question(
            self, "確認", f"確定要重新命名這些檔案？此操作無法自動還原。"
        )
        if reply != QMessageBox.Yes:
            return
        success, errors = execute_renames(self._previews)
        # 同步更新資料庫中的節點名稱
        for pv in self._previews:
            if not pv.conflict and pv.new_name != pv.original:
                self._conn.execute(
                    "UPDATE nodes SET name=?, rel_path=REPLACE(rel_path, ?, ?) "
                    "WHERE project_id=? AND name=?",
                    (pv.new_name, pv.original, pv.new_name,
                     self._project_id, pv.original),
                )
        self._conn.commit()
        msg = f"完成：{success} 個檔案已重新命名。"
        if errors:
            msg += f"\n\n錯誤（{len(errors)} 個）：\n" + "\n".join(errors[:10])
        QMessageBox.information(self, "完成", msg)
        self.accept()
