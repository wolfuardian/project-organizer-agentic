"""Metadata 面板 — 主視窗右側."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout,
    QPushButton, QLabel, QTextEdit, QFrame,
)

from database import get_node, get_node_tags, update_node_note


class MetadataPanel(QWidget):
    """顯示選取節點的詳細 metadata，允許編輯備註。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._node_id: int | None = None
        self.setMinimumWidth(200)
        self.setMaximumWidth(280)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        layout.addWidget(QLabel("Metadata"))
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        form = QFormLayout()
        self._lbl_name  = QLabel("—")
        self._lbl_type  = QLabel("—")
        self._lbl_size  = QLabel("—")
        self._lbl_mtime = QLabel("—")
        self._lbl_cat   = QLabel("—")
        self._lbl_tags  = QLabel("—")
        self._lbl_tags.setWordWrap(True)
        for label, widget in [
            ("名稱",   self._lbl_name),
            ("類型",   self._lbl_type),
            ("大小",   self._lbl_size),
            ("修改時間", self._lbl_mtime),
            ("分類",   self._lbl_cat),
            ("標籤",   self._lbl_tags),
        ]:
            form.addRow(label + "：", widget)
        layout.addLayout(form)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        layout.addWidget(sep2)
        layout.addWidget(QLabel("備註："))
        self._note_edit = QTextEdit()
        self._note_edit.setPlaceholderText("輸入備註…")
        self._note_edit.setMaximumHeight(100)
        layout.addWidget(self._note_edit)

        btn_save = QPushButton("儲存備註")
        btn_save.clicked.connect(self._save_note)
        layout.addWidget(btn_save)
        layout.addStretch()

    def load_node(self, node_id: int,
                  project_id: int | None = None) -> None:
        self._node_id = node_id
        row = get_node(self._conn, node_id)
        if not row:
            return

        self._lbl_name.setText(row["name"])
        self._lbl_type.setText(row["node_type"])

        size = row["file_size"]
        if size is not None:
            if size >= 1_048_576:
                self._lbl_size.setText(f"{size/1_048_576:.1f} MB")
            elif size >= 1024:
                self._lbl_size.setText(f"{size/1024:.1f} KB")
            else:
                self._lbl_size.setText(f"{size} B")
        else:
            self._lbl_size.setText("—")

        mtime = row["modified_at"] or "—"
        self._lbl_mtime.setText(mtime[:16].replace("T", " ") if mtime != "—" else "—")
        self._lbl_cat.setText(row["category"] or "—")

        tags = get_node_tags(self._conn, node_id)
        self._lbl_tags.setText(", ".join(t["name"] for t in tags) or "—")

        self._note_edit.blockSignals(True)
        self._note_edit.setPlainText(row["note"] or "")
        self._note_edit.blockSignals(False)

    def _save_note(self) -> None:
        if self._node_id is None:
            return
        update_node_note(self._conn, self._node_id,
                         self._note_edit.toPlainText())
