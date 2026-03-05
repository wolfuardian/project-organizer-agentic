"""右鍵選單 mixin — 檔案樹右鍵選單 + 開啟檔案/資料夾。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMenu

from database import get_node_abs_path
from domain.enums import MODE_READ, MODE_VIRTUAL

if TYPE_CHECKING:
    from presentation.main_window import MainWindow


class ContextMenuMixin:
    """檔案樹右鍵選單 + 系統開啟 + 檔案管理器。"""

    def _show_context_menu(self, pos) -> None:
        idx = self._tree_view.indexAt(pos)
        node = self._node_from_index(idx)
        if node is None:
            return

        menu = QMenu(self)

        # 編輯操作（虛擬 / 即時模式）
        if self._controller.mode != MODE_READ:
            suffix = "（虛擬）" if self._controller.mode == MODE_VIRTUAL else ""
            act_del = menu.addAction(f"刪除{suffix}")
            act_del.triggered.connect(self._do_delete_selected)
            act_ren = menu.addAction(f"重命名{suffix}")
            act_ren.triggered.connect(self._do_rename_selected)
            if node.node_type in ("folder", "virtual"):
                act_mkdir = menu.addAction(f"新增資料夾{suffix}")
                act_mkdir.triggered.connect(self._do_mkdir)
            menu.addSeparator()

        if node.node_type == "file":
            act_open = menu.addAction("以系統預設開啟")
            act_open.triggered.connect(lambda: self._open_system(node))

        act_reveal = menu.addAction("在檔案管理器中顯示")
        act_reveal.triggered.connect(lambda: self._open_in_explorer(node))

        menu.exec_(self._tree_view.viewport().mapToGlobal(pos))

    def _open_system(self, node) -> None:
        full = self._resolve_node_path(node)
        if not full or not full.is_file():
            return
        import os
        os.startfile(str(full))

    def _resolve_node_path(self, node) -> Path | None:
        """統一路徑解析：優先透過 get_node_abs_path，fallback 到 projects.root_path。"""
        abs_path = get_node_abs_path(self._conn, node.db_id)
        if abs_path:
            return abs_path
        if not self._current_project_id:
            return None
        row = self._conn.execute(
            "SELECT root_path FROM projects WHERE id=?",
            (self._current_project_id,),
        ).fetchone()
        if not row:
            return None
        return Path(row["root_path"]) / node.rel_path

    def _open_in_explorer(self, node) -> None:
        full = self._resolve_node_path(node)
        if not full:
            return
        import subprocess, sys
        if sys.platform == "win32":
            if full.is_dir():
                subprocess.Popen(["explorer", str(full)])
            else:
                subprocess.Popen(["explorer", "/select,", str(full)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(full)])
        else:
            subprocess.Popen(["xdg-open", str(full.parent if full.is_file() else full)])
