"""模板系統對話框 — 反推、管理、編輯、選擇模板."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QSpinBox,
    QListWidget, QListWidgetItem, QTextEdit,
    QDialogButtonBox, QFileDialog, QMessageBox,
)

from templates import (
    get_builtin_templates, list_templates, save_template,
    delete_template, scaffold, export_template, import_template,
    project_to_template,
)


class ExtractTemplateDialog(QDialog):
    """選擇目錄，反推成模板後存入 DB 或匯出 JSON。"""

    def __init__(self, conn, default_dir: str = "", parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("從現有專案建立模板")
        self.resize(560, 360)
        self._build_ui(default_dir)

    def _build_ui(self, default_dir: str) -> None:
        layout = QFormLayout(self)

        row_dir = QHBoxLayout()
        self._dir_edit = QLineEdit(default_dir)
        btn_browse = QPushButton("…")
        btn_browse.setMaximumWidth(32)
        btn_browse.clicked.connect(self._browse)
        row_dir.addWidget(self._dir_edit)
        row_dir.addWidget(btn_browse)
        layout.addRow("來源目錄：", row_dir)

        self._name = QLineEdit()
        if default_dir:
            self._name.setText(Path(default_dir).name)
        layout.addRow("模板名稱：", self._name)

        self._desc = QLineEdit()
        layout.addRow("說明：", self._desc)

        self._cat = QComboBox()
        self._cat.addItems(["general", "python", "web", "rust", "unity",
                             "nodejs", "other"])
        layout.addRow("類別：", self._cat)

        self._depth = QSpinBox()
        self._depth.setRange(1, 8)
        self._depth.setValue(4)
        layout.addRow("最大深度：", self._depth)

        btns = QDialogButtonBox()
        btn_save = btns.addButton("儲存為自訂模板", QDialogButtonBox.AcceptRole)
        btn_export = btns.addButton("匯出 JSON", QDialogButtonBox.ActionRole)
        btn_cancel = btns.addButton(QDialogButtonBox.Cancel)
        btn_save.clicked.connect(self._save_to_db)
        btn_export.clicked.connect(self._export_json)
        btn_cancel.clicked.connect(self.reject)
        layout.addRow(btns)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "選擇來源目錄")
        if d:
            self._dir_edit.setText(d)
            if not self._name.text():
                self._name.setText(Path(d).name)

    def _extract(self):
        src = self._dir_edit.text().strip()
        name = self._name.text().strip()
        if not src or not name:
            QMessageBox.warning(self, "缺少資料", "請填寫來源目錄與模板名稱。")
            return None
        root = Path(src)
        if not root.is_dir():
            QMessageBox.warning(self, "錯誤", f"目錄不存在：{src}")
            return None
        return project_to_template(
            root=root, name=name,
            description=self._desc.text().strip(),
            category=self._cat.currentText(),
            max_depth=self._depth.value(),
        )

    def _save_to_db(self) -> None:
        tmpl = self._extract()
        if tmpl is None:
            return
        save_template(self._conn, tmpl)
        QMessageBox.information(
            self, "完成", f"已儲存模板「{tmpl.name}」（{len(tmpl.entries)} 個項目）"
        )
        self.accept()

    def _export_json(self) -> None:
        tmpl = self._extract()
        if tmpl is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "匯出模板", f"{tmpl.name}.json", "JSON (*.json)"
        )
        if path:
            Path(path).write_text(export_template(tmpl), encoding="utf-8")
            QMessageBox.information(self, "完成", f"已匯出至 {path}")


class TemplateManagerDialog(QDialog):
    """管理使用者自訂模板：新增、匯出、匯入、刪除。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("管理自訂模板")
        self.resize(680, 420)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        for label, slot in [
            ("＋ 新增", self._new_template),
            ("匯出 JSON", self._export),
            ("匯入 JSON", self._import),
            ("－ 刪除", self._delete),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(120)
        layout.addWidget(self._preview)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load(self) -> None:
        self._templates = list_templates(self._conn, include_builtin=False)
        self._list.clear()
        for t in self._templates:
            self._list.addItem(f"[{t.category}] {t.name}")

    def _on_select(self, row: int) -> None:
        if row < 0 or row >= len(self._templates):
            self._preview.clear()
            return
        t = self._templates[row]
        lines = [f"{t.name}  ({t.category})", t.description, ""]
        for e in t.entries:
            lines.append(("[dir] " if e.is_dir else "") + e.path)
        self._preview.setPlainText("\n".join(lines))

    def _new_template(self) -> None:
        dlg = TemplateEditDialog(self._conn, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._load()

    def _export(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        tmpl = self._templates[row]
        path, _ = QFileDialog.getSaveFileName(
            self, "匯出模板", f"{tmpl.name}.json", "JSON (*.json)"
        )
        if path:
            Path(path).write_text(export_template(tmpl), encoding="utf-8")
            QMessageBox.information(self, "完成", f"已匯出至 {path}")

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "匯入模板", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            json_str = Path(path).read_text(encoding="utf-8")
            tmpl = import_template(json_str)
        except Exception as e:
            QMessageBox.warning(self, "匯入失敗", str(e))
            return
        save_template(self._conn, tmpl)
        self._load()
        QMessageBox.information(self, "完成", f"已匯入模板「{tmpl.name}」")

    def _delete(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        tmpl = self._templates[row]
        reply = QMessageBox.question(self, "確認", f"刪除模板「{tmpl.name}」？")
        if reply == QMessageBox.Yes:
            delete_template(self._conn, tmpl.id)
            self._load()


class TemplateEditDialog(QDialog):
    """新增自訂模板對話框（手動輸入路徑清單）。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("新增自訂模板")
        self.resize(560, 440)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)

        self._name = QLineEdit()
        layout.addRow("名稱：", self._name)

        self._desc = QLineEdit()
        layout.addRow("說明：", self._desc)

        self._cat = QComboBox()
        self._cat.addItems(["general", "python", "web", "rust", "unity",
                             "nodejs", "other"])
        layout.addRow("類別：", self._cat)

        self._entries = QTextEdit()
        self._entries.setPlaceholderText(
            "每行一個路徑，目錄結尾加 /\n"
            "例：\n"
            "src/\n"
            "src/main.py\n"
            "README.md"
        )
        layout.addRow("目錄/檔案清單：", self._entries)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _save(self) -> None:
        from templates import ProjectTemplate, TemplateEntry
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "缺少資料", "名稱不可空白。")
            return
        entries = []
        for line in self._entries.toPlainText().splitlines():
            line = line.strip()
            if not line:
                continue
            is_dir = line.endswith("/")
            path = line.rstrip("/")
            entries.append(TemplateEntry(path=path, is_dir=is_dir))
        tmpl = ProjectTemplate(
            name=name,
            description=self._desc.text().strip(),
            category=self._cat.currentText(),
            entries=entries,
        )
        save_template(self._conn, tmpl)
        self.accept()


class TemplatePickerDialog(QDialog):
    """從模板清單選擇，指定目標目錄，scaffold 並建立專案。"""

    def __init__(self, templates, conn, parent=None):
        super().__init__(parent)
        self._templates = templates
        self._conn = conn
        self.created_project_id: int | None = None
        self.setWindowTitle("從模板新增專案")
        self.resize(680, 440)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        # 左：模板清單
        left = QVBoxLayout()
        left.addWidget(QLabel("選擇模板："))
        self._list = QListWidget()
        for tmpl in self._templates:
            tag = "[builtin]" if tmpl.is_builtin else "[custom]"
            item = QListWidgetItem(f"{tag} {tmpl.name}")
            item.setToolTip(tmpl.description)
            self._list.addItem(item)
        self._list.currentRowChanged.connect(self._on_select)
        left.addWidget(self._list)
        layout.addLayout(left, 1)

        # 右：詳情 + 設定
        right = QVBoxLayout()
        self._lbl_desc = QLabel("（選擇模板以查看說明）")
        self._lbl_desc.setWordWrap(True)
        right.addWidget(self._lbl_desc)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(160)
        right.addWidget(self._preview)

        form = QFormLayout()
        self._name_edit = QLineEdit()
        form.addRow("專案名稱：", self._name_edit)
        row_dir = QHBoxLayout()
        self._dir_edit = QLineEdit()
        btn_browse = QPushButton("…")
        btn_browse.setMaximumWidth(32)
        btn_browse.clicked.connect(self._browse_dir)
        row_dir.addWidget(self._dir_edit)
        row_dir.addWidget(btn_browse)
        form.addRow("目標目錄：", row_dir)
        right.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("建立專案")
        btns.accepted.connect(self._create)
        btns.rejected.connect(self.reject)
        right.addWidget(btns)

        layout.addLayout(right, 2)

        if self._templates:
            self._list.setCurrentRow(0)

    def _on_select(self, row: int) -> None:
        if row < 0 or row >= len(self._templates):
            return
        tmpl = self._templates[row]
        self._lbl_desc.setText(f"[{tmpl.category}]  {tmpl.description}")
        lines = []
        for e in tmpl.entries:
            prefix = "[dir] " if e.is_dir else ""
            lines.append(f"{prefix}{e.path}")
        self._preview.setPlainText("\n".join(lines))

    def _browse_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "選擇父目錄")
        if d:
            self._dir_edit.setText(d)

    def _create(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "請選擇一個模板。")
            return
        tmpl = self._templates[row]
        name = self._name_edit.text().strip() or tmpl.name
        parent_dir = self._dir_edit.text().strip()
        if not parent_dir:
            QMessageBox.warning(self, "提示", "請指定目標目錄。")
            return
        target = Path(parent_dir) / name
        if target.exists():
            reply = QMessageBox.question(
                self, "目錄已存在",
                f"目錄 {target} 已存在，仍要繼續嗎？（不會刪除現有檔案）",
            )
            if reply != QMessageBox.Yes:
                return

        created, errors = scaffold(tmpl, target)
        if errors:
            QMessageBox.warning(self, "建立警告",
                                f"部分項目建立失敗：\n" + "\n".join(errors[:5]))

        from database import create_project
        from scanner import scan_directory
        try:
            pid = create_project(self._conn, name, str(target))
        except Exception as e:
            QMessageBox.warning(self, "錯誤", f"無法建立專案記錄：{e}")
            return

        count = scan_directory(self._conn, pid, target)
        self._conn.commit()
        self.created_project_id = pid
        QMessageBox.information(
            self, "完成",
            f"已建立專案「{name}」\n目錄：{target}\n建立 {created} 個項目，掃描 {count} 個節點。",
        )
        self.accept()
