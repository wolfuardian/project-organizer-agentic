"""設定相關對話框 — 外部工具、備份、匯出報告."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QDialogButtonBox,
    QHeaderView, QAbstractItemView, QFileDialog, QMessageBox,
)

from database import list_all_tools, add_tool, update_tool, delete_tool
from report_exporter import export_markdown, export_html, save_report
from backup import (
    create_backup, list_backups, restore_backup, delete_backup,
    get_setting, set_setting,
)


class BackupDialog(QDialog):
    """建立備份、列出備份清單、還原或刪除備份。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("備份與還原")
        self.resize(600, 400)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # 備份目錄
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("備份目錄："))
        self._dir_edit = QLineEdit()
        default_dir = get_setting(self._conn, "backup_dir",
                                  str(Path.home() / ".project-organizer" / "backups"))
        self._dir_edit.setText(default_dir)
        btn_dir = QPushButton("瀏覽…")
        btn_dir.clicked.connect(self._browse_dir)
        dir_row.addWidget(self._dir_edit)
        dir_row.addWidget(btn_dir)
        layout.addLayout(dir_row)

        # 備份清單
        self._list = QTableWidget(0, 2)
        self._list.setHorizontalHeaderLabels(["檔案名稱", "大小"])
        self._list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._list.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        for label, slot in [
            ("＋ 立即備份",   self._do_backup),
            ("↩ 還原選取",   self._restore),
            ("－ 刪除選取",   self._delete),
        ]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "選擇備份目錄",
                                             self._dir_edit.text())
        if d:
            self._dir_edit.setText(d)
            set_setting(self._conn, "backup_dir", d)

    def _backup_dir(self) -> Path:
        return Path(self._dir_edit.text())

    def _load(self) -> None:
        self._backups = list_backups(self._backup_dir())
        self._list.setRowCount(0)
        for f in self._backups:
            r = self._list.rowCount()
            self._list.insertRow(r)
            self._list.setItem(r, 0, QTableWidgetItem(f.name))
            size_kb = f.stat().st_size / 1024
            self._list.setItem(r, 1, QTableWidgetItem(f"{size_kb:.1f} KB"))

    def _do_backup(self) -> None:
        try:
            dest = create_backup(self._backup_dir())
            QMessageBox.information(self, "備份完成", f"已備份至：\n{dest}")
            self._load()
        except Exception as e:
            QMessageBox.critical(self, "備份失敗", str(e))

    def _restore(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        f = self._backups[row]
        if QMessageBox.question(
            self, "確認還原",
            f"還原「{f.name}」？\n目前資料庫將先自動備份。"
        ) != QMessageBox.Yes:
            return
        try:
            restore_backup(f)
            QMessageBox.information(self, "完成", "還原成功，請重新啟動應用程式。")
        except Exception as e:
            QMessageBox.critical(self, "還原失敗", str(e))

    def _delete(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        f = self._backups[row]
        if QMessageBox.question(self, "確認刪除",
                                f"刪除備份「{f.name}」？") == QMessageBox.Yes:
            delete_backup(f)
            self._load()


class ExportReportDialog(QDialog):
    """選擇格式與儲存路徑，匯出 Markdown 或 HTML 報告。"""

    def __init__(self, conn, project_id: int, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._project_id = project_id
        self.setWindowTitle("匯出專案報告")
        self.resize(480, 200)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._fmt = QComboBox()
        self._fmt.addItems(["Markdown (.md)", "HTML (.html)"])
        form.addRow("格式：", self._fmt)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("選擇儲存路徑…")
        btn_browse = QPushButton("瀏覽…")
        btn_browse.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit)
        path_row.addWidget(btn_browse)
        form.addRow("儲存路徑：", path_row)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._export)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse(self) -> None:
        is_html = self._fmt.currentIndex() == 1
        suffix = "HTML 檔案 (*.html)" if is_html else "Markdown 檔案 (*.md)"
        path, _ = QFileDialog.getSaveFileName(self, "儲存報告", "", suffix)
        if path:
            self._path_edit.setText(path)

    def _export(self) -> None:
        path_str = self._path_edit.text().strip()
        if not path_str:
            QMessageBox.warning(self, "缺少資訊", "請指定儲存路徑。")
            return
        path = Path(path_str)
        is_html = self._fmt.currentIndex() == 1
        content = (export_html if is_html else export_markdown)(
            self._conn, self._project_id
        )
        save_report(content, path)
        QMessageBox.information(self, "完成", f"報告已儲存至：\n{path}")
        self.accept()


class ExternalToolsDialog(QDialog):
    """新增 / 編輯 / 刪除外部工具（VSCode、Terminal、Unity Hub 等）。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("外部工具設定")
        self.resize(640, 360)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["名稱", "執行檔", "參數樣板", "啟用"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        for label, slot in [
            ("＋ 新增", self._add),
            ("編輯",  self._edit),
            ("－ 刪除", self._delete),
        ]:
            b = QPushButton(label); b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addWidget(QLabel(
            "參數樣板中可使用：{path}（完整路徑）、{dir}（所在目錄）"
        ))

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load(self) -> None:
        self._tools = list_all_tools(self._conn)
        self._table.setRowCount(0)
        for tool in self._tools:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(tool["name"]))
            self._table.setItem(r, 1, QTableWidgetItem(tool["exe_path"]))
            self._table.setItem(r, 2, QTableWidgetItem(tool["args_tmpl"] or ""))
            en = QTableWidgetItem("Y" if tool["enabled"] else "N")
            en.setData(Qt.UserRole, tool["id"])
            self._table.setItem(r, 3, en)

    def _add(self) -> None:
        dlg = ToolEditDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            add_tool(self._conn, **dlg.result)
            self._load()

    def _edit(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        tool = self._tools[row]
        dlg = ToolEditDialog(
            initial={k: tool[k] for k in ("name", "exe_path", "args_tmpl")},
            parent=self,
        )
        if dlg.exec_() == QDialog.Accepted:
            update_tool(self._conn, tool["id"], **dlg.result,
                        enabled=tool["enabled"])
            self._load()

    def _delete(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        tool = self._tools[row]
        if QMessageBox.question(self, "確認",
                                f"刪除工具「{tool['name']}」？") == QMessageBox.Yes:
            delete_tool(self._conn, tool["id"])
            self._load()


class ToolEditDialog(QDialog):
    def __init__(self, initial: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("工具設定")
        self.result: dict = {}
        self._build_ui(initial or {})

    def _build_ui(self, initial: dict) -> None:
        form = QFormLayout(self)
        self._name = QLineEdit(initial.get("name", ""))
        self._exe  = QLineEdit(initial.get("exe_path", ""))
        self._args = QLineEdit(initial.get("args_tmpl", "{path}"))
        form.addRow("名稱：",     self._name)
        form.addRow("執行檔：",   self._exe)
        form.addRow("參數樣板：", self._args)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _save(self) -> None:
        if not self._name.text().strip() or not self._exe.text().strip():
            QMessageBox.warning(self, "缺少資料", "名稱與執行檔不可空白。")
            return
        self.result = {
            "name":      self._name.text().strip(),
            "exe_path":  self._exe.text().strip(),
            "args_tmpl": self._args.text().strip() or "{path}",
        }
        self.accept()
