"""資料夾面板 — 中間欄顯示專案根目錄清單。"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QFileDialog, QInputDialog,
)

from database import list_project_roots, add_project_root, set_project_progress
from domain.enums import PROGRESS_STATES, PROGRESS_LABELS, PROJECT_ROOT_ROLES


class FolderPanel(QWidget):
    """顯示當前專案的根目錄清單，支援新增資料夾與切換進度。"""

    folder_selected = Signal(int)          # root_id
    scan_requested = Signal(int, int, str)  # project_id, root_id, root_path

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._project_id: int | None = None
        self._progress: str = "not_started"
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(0)

        # ── top: project name + progress button ──
        hdr = QHBoxLayout()
        self._lbl_name = QLabel("")
        self._lbl_name.setStyleSheet("font-weight: bold;")
        hdr.addWidget(self._lbl_name, 1)

        self._btn_progress = QPushButton("")
        self._btn_progress.setMaximumWidth(72)
        self._btn_progress.setToolTip("點擊切換專案進度")
        self._btn_progress.clicked.connect(self._cycle_progress)
        hdr.addWidget(self._btn_progress)
        layout.addLayout(hdr)

        # ── middle: folder list ──
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, 1)

        # ── bottom: add folder button ──
        btn_add = QPushButton("＋  新增資料夾")
        btn_add.setFixedHeight(32)
        btn_add.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-top: 1px solid #2e2e36;
                border-radius: 0;
                color: #a0a0af;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 0.08em;
                padding: 0;
            }
            QPushButton:hover {
                color: #d4a054;
                border-top: 1px solid #d4a054;
                background-color: rgba(212, 160, 84, 0.06);
            }
            QPushButton:pressed {
                color: #e0c08a;
                background-color: rgba(212, 160, 84, 0.12);
            }
        """)
        btn_add.clicked.connect(self._add_folder)
        layout.addWidget(btn_add)

    # ── public API ───────────────────────────────────────────────

    def load_project(self, project_id: int, name: str, progress: str) -> None:
        self._project_id = project_id
        self._progress = progress or "not_started"
        self._lbl_name.setText(name)
        self._update_progress_button()
        self._refresh()

    def set_project_name(self, name: str) -> None:
        self._lbl_name.setText(name)

    def current_root_id(self) -> int | None:
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(Qt.UserRole)

    # ── internal ─────────────────────────────────────────────────

    def _update_progress_button(self) -> None:
        label = PROGRESS_LABELS.get(self._progress, self._progress)
        self._btn_progress.setText(label)

    def _refresh(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        if self._project_id is None:
            self._list.blockSignals(False)
            return
        roots = list_project_roots(self._conn, self._project_id)
        for r in roots:
            root_path = r["root_path"]
            root_id = r["id"]
            role = r["role"]
            short_name = Path(root_path).name or root_path
            text = f"{short_name}  [{role}]"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, root_id)
            item.setData(Qt.UserRole + 1, root_path)
            item.setToolTip(root_path)
            self._list.addItem(item)
        self._list.blockSignals(False)
        # auto-select first
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _on_selection_changed(self, current: QListWidgetItem | None,
                              _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        root_id = current.data(Qt.UserRole)
        if root_id is not None:
            self.folder_selected.emit(root_id)

    def _cycle_progress(self) -> None:
        if self._project_id is None:
            return
        idx = PROGRESS_STATES.index(self._progress) if self._progress in PROGRESS_STATES else 0
        next_idx = (idx + 1) % len(PROGRESS_STATES)
        self._progress = PROGRESS_STATES[next_idx]
        set_project_progress(self._conn, self._project_id, self._progress)
        self._update_progress_button()

    def _add_folder(self) -> None:
        if self._project_id is None:
            return
        folder = QFileDialog.getExistingDirectory(self, "選擇資料夾")
        if not folder:
            return
        roles = PROJECT_ROOT_ROLES
        role, ok = QInputDialog.getItem(
            self, "選擇角色", "此資料夾的角色：", roles, 0, False)
        if not ok:
            return
        root_id = add_project_root(self._conn, self._project_id, folder, role)
        self._refresh()
        self.scan_requested.emit(self._project_id, root_id, folder)
