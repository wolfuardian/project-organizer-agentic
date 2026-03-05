"""專案 CRUD + 掃描 mixin。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QModelIndex, QThread, Signal
from PySide6.QtWidgets import (
    QInputDialog, QMessageBox, QListWidgetItem, QMenu, QDialog,
)

from database import (
    create_project, list_projects, delete_project,
    list_project_roots, add_project_root,
)
from scanner import scan_directory
from presentation.tree_model import ProjectTreeModel, setup_tree_header

if TYPE_CHECKING:
    from presentation.main_window import MainWindow


class _ScanWorker(QThread):
    """背景掃描執行緒，避免阻塞 UI。"""
    finished = Signal(int)
    progress = Signal(str)

    def __init__(self, conn_path: str, project_id: int,
                 roots: list[dict], *, parent=None):
        super().__init__(parent)
        self._conn_path = conn_path
        self._project_id = project_id
        self._roots = roots

    @staticmethod
    def _format_bar(current: int, total: int) -> str:
        pct = current / total if total else 0
        filled = int(pct * 20)
        bar = "█" * filled + "░" * (20 - filled)
        return f"[{bar}] {current}/{total} ({pct:.0%})"

    def run(self) -> None:
        import sqlite3
        try:
            conn = sqlite3.connect(self._conn_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            total = 0
            for root in self._roots:
                root_id = root["id"]
                root_path = root["root_path"]
                base = total

                def _on_progress(current, item_total, _base=base):
                    msg = self._format_bar(
                        _base + current, _base + item_total,
                    )
                    self.progress.emit(f"掃描中… {msg}")

                count = scan_directory(
                    conn, self._project_id, root_path,
                    root_id=root_id,
                    progress_callback=_on_progress,
                )
                total += count
            conn.close()
            self.finished.emit(total)
        except Exception:
            self.finished.emit(-1)


class ProjectMixin:
    """專案管理相關方法 — 載入清單、新增/移除、掃描。"""

    if TYPE_CHECKING:
        # IDE 型別提示：這些屬性由 MainWindow 提供
        _conn: ...
        _project_list: ...
        _current_project_id: int | None
        _current_root_id: int | None
        _folder_panel: ...
        _tree_view: ...
        _tree_model: ...
        _flat_search: ...
        _scan_worker: ...
        _refresh_timer: ...
        _last_snapshot: list
        _controller: ...

    def _load_project_list(self) -> None:
        self._project_list.clear()
        for row in list_projects(self._conn):
            item = QListWidgetItem(row["name"])
            item.setData(Qt.UserRole, row["id"])
            self._project_list.addItem(item)

    def _add_project(self) -> None:
        name, ok = QInputDialog.getText(self, "新增專案", "專案名稱：")
        if not ok or not name.strip():
            return
        try:
            pid = create_project(self._conn, name.strip())
        except Exception as e:
            QMessageBox.warning(self, "錯誤", f"無法建立專案：{e}")
            return
        self._load_project_list()
        for i in range(self._project_list.count()):
            item = self._project_list.item(i)
            if item.data(Qt.UserRole) == pid:
                self._project_list.setCurrentItem(item)
                break

    def _on_folder_scan_requested(self, pid: int, root_id: int,
                                   path: str) -> None:
        """中間面板新增資料夾後，背景掃描該資料夾。"""
        if self._is_scanning():
            self.statusBar().showMessage("掃描進行中，請稍後再試。")
            return
        self.statusBar().showMessage(f"掃描 {path} …")
        self._refresh_timer.stop()
        from infrastructure.database import DB_PATH
        self._scan_worker = _ScanWorker(
            str(DB_PATH), pid,
            [{"id": root_id, "root_path": path}], parent=self,
        )
        self._scan_worker.progress.connect(self.statusBar().showMessage)
        self._scan_worker.finished.connect(self._on_folder_scan_finished)
        self._scan_worker.start()

    def _on_folder_scan_finished(self, count: int) -> None:
        self._scan_worker = None
        if count < 0:
            self.statusBar().showMessage("掃描失敗")
            return
        self.statusBar().showMessage(f"已掃描 {count} 個項目")
        root_id = self._folder_panel.current_root_id()
        if root_id:
            self._on_folder_selected(root_id)

    def _remove_project(self) -> None:
        item = self._project_list.currentItem()
        if not item:
            return
        pid = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "確認", "確定要從列表移除此專案？（不會刪除實際檔案）",
        )
        if reply == QMessageBox.Yes:
            delete_project(self._conn, pid)
            self._load_project_list()
            self._tree_view.setModel(None)
            self._folder_panel._list.clear()
            self._current_project_id = None
            self._current_root_id = None
            self._flat_search.deactivate()
            self._tree_view.setVisible(True)

    def _is_scanning(self) -> bool:
        return self._scan_worker is not None and self._scan_worker.isRunning()

    def _rescan_project(self) -> None:
        if not self._current_project_id or not self._current_root_id:
            return
        if self._is_scanning():
            return
        item = self._folder_panel._list.currentItem()
        if not item:
            return
        root_path = item.data(Qt.UserRole + 1)
        self.statusBar().showMessage(f"重新掃描 {root_path} …")
        self._refresh_timer.stop()
        from infrastructure.database import DB_PATH
        self._scan_worker = _ScanWorker(
            str(DB_PATH), self._current_project_id,
            [{"id": self._current_root_id, "root_path": root_path}],
            parent=self,
        )
        self._scan_worker.progress.connect(self.statusBar().showMessage)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _on_scan_finished(self, count: int) -> None:
        self._scan_worker = None
        if count < 0:
            QMessageBox.warning(self, "掃描失敗", "重新掃描時發生錯誤，已還原。")
            return
        self.statusBar().showMessage(f"已掃描 {count} 個項目")
        self._refresh_with_state()

    def _show_project_context_menu(self, pos) -> None:
        item = self._project_list.itemAt(pos)
        if not item:
            return
        pid = item.data(Qt.UserRole)
        menu = QMenu(self)
        act_roots = menu.addAction("管理根目錄…")
        act_roots.triggered.connect(
            lambda: self._open_roots_dialog(pid)
        )
        menu.addSeparator()
        act_remove = menu.addAction("移除專案")
        act_remove.triggered.connect(self._remove_project)
        menu.exec_(self._project_list.viewport().mapToGlobal(pos))

    def _open_roots_dialog(self, project_id: int) -> None:
        from presentation.dialogs.project_dialogs import ProjectRootsDialog
        dlg = ProjectRootsDialog(self._conn, project_id, self)
        if dlg.exec_() == QDialog.Accepted:
            self._rescan_project()

    def _on_project_selected(self, current: QListWidgetItem,
                              previous: QListWidgetItem) -> None:
        if not current:
            return
        pid = current.data(Qt.UserRole)
        self._current_project_id = pid
        self._current_root_id = None
        row = self._conn.execute(
            "SELECT name, progress FROM projects WHERE id=?", (pid,)
        ).fetchone()
        if not row:
            return
        self._folder_panel.load_project(
            pid, row["name"], row["progress"] or "not_started",
        )

    def _on_folder_selected(self, root_id: int) -> None:
        """中間面板選取資料夾 → 載入該資料夾的檔案樹。"""
        if not self._current_project_id:
            return
        self._current_root_id = root_id
        self._tree_model = ProjectTreeModel(
            self._conn, self._current_project_id, root_id=root_id,
        )
        self._tree_view.setModel(self._tree_model)
        setup_tree_header(self._tree_view.header())
        self._tree_view.selectionModel().currentChanged.connect(
            self._on_tree_selection_changed
        )
        search_cache, self._last_snapshot = self._build_flat_lists()
        self._flat_search.set_flat_cache(search_cache)
        self._flat_search.deactivate()
        self._tree_view.setVisible(True)
        self._apply_mode()
