"""DiffPanel — 顯示虛擬模式 pending commands 的差異摘要對話框。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem,
    QPushButton,
)
from PySide6.QtGui import QColor

from domain.models import Command


# ── op 顯示對應 ──────────────────────────────────────────
_OP_LABELS = {
    "move": "移動",
    "delete": "刪除",
    "copy": "複製",
    "rename": "重命名",
    "mkdir": "新增資料夾",
}

_OP_COLORS = {
    "move": QColor("#89b4fa"),     # blue
    "delete": QColor("#f38ba8"),   # red
    "copy": QColor("#a6e3a1"),     # green
    "rename": QColor("#f9e2af"),   # yellow
    "mkdir": QColor("#cba6f7"),    # mauve
}


class DiffPanel(QDialog):
    """顯示 pending commands 清單，讓使用者確認或取消套用。"""

    def __init__(self, commands: list[Command], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("確認變更")
        self.setMinimumSize(480, 320)
        self._commands = commands
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"共 {len(self._commands)} 項變更："))

        self._list = QListWidget()
        for cmd in self._commands:
            label = _OP_LABELS.get(cmd.op, cmd.op)
            if cmd.dest:
                text = f"[{label}] {cmd.source} → {cmd.dest}"
            else:
                text = f"[{label}] {cmd.source}"
            item = QListWidgetItem(text)
            color = _OP_COLORS.get(cmd.op)
            if color:
                item.setForeground(color)
            self._list.addItem(item)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_apply = QPushButton("確認套用")
        btn_apply.setDefault(True)
        btn_apply.clicked.connect(self.accept)
        btn_row.addWidget(btn_apply)

        layout.addLayout(btn_row)
