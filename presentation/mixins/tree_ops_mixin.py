"""樹節點操作 mixin — mkdir / delete / rename / undo / redo / refresh。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import QInputDialog, QMessageBox

from domain.enums import MODE_READ, MODE_VIRTUAL, MODE_REALTIME
from domain.models import Command

if TYPE_CHECKING:
    from presentation.main_window import MainWindow


class TreeOpsMixin:
    """樹節點 CRUD + undo/redo + refresh 相關方法。"""

    def _node_from_index(self, index):
        if not index.isValid():
            return None
        return index.internalPointer()

    def _resolve_parent_node(self, node):
        """取得適合作為 parent 的資料夾節點：若選中檔案則回傳其父資料夾。"""
        if not node:
            return None
        if node.node_type in ("folder", "virtual"):
            return node
        return node.parent if node.parent else None

    def _refresh_with_state(self) -> None:
        """refresh 樹模型並恢復展開狀態。"""
        if not self._tree_model:
            return
        expanded = set()

        def _collect_expanded(parent_idx=QModelIndex()):
            for r in range(self._tree_model.rowCount(parent_idx)):
                idx = self._tree_model.index(r, 0, parent_idx)
                if self._tree_view.isExpanded(idx):
                    node = idx.internalPointer()
                    if node and node.rel_path:
                        expanded.add(node.rel_path)
                    elif node and node.is_root_group:
                        expanded.add(f"__root_group_{node.db_id}")
                    _collect_expanded(idx)
        _collect_expanded()

        self._tree_model.refresh()

        def _restore_expanded(parent_idx=QModelIndex()):
            for r in range(self._tree_model.rowCount(parent_idx)):
                idx = self._tree_model.index(r, 0, parent_idx)
                node = idx.internalPointer()
                if not node:
                    continue
                key = node.rel_path if node.rel_path else (
                    f"__root_group_{node.db_id}" if node.is_root_group else "")
                if key and key in expanded:
                    self._tree_view.expand(idx)
                    _restore_expanded(idx)
        _restore_expanded()

        search_cache, self._last_snapshot = self._build_flat_lists()
        self._flat_search.set_flat_cache(search_cache)

    def _schedule_refresh(self) -> None:
        """節流 refresh：50ms 內的多次呼叫只觸發一次。掃描中不觸發。"""
        if self._is_scanning():
            return
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def _do_throttled_refresh(self) -> None:
        if self._tree_model:
            self._refresh_with_state()

    def _after_mutation(self) -> None:
        """undo/redo/execute 後統一重整 UI。"""
        if self._controller.mode == MODE_VIRTUAL:
            self._update_virtual_status()
        elif self._controller.mode == MODE_REALTIME and self._tree_model:
            self._schedule_refresh()

    def _do_undo(self) -> None:
        if self._controller.mode == MODE_READ:
            return
        self._controller.undo()
        self._after_mutation()

    def _do_redo(self) -> None:
        if self._controller.mode == MODE_READ:
            return
        self._controller.redo()
        self._after_mutation()

    def _do_delete_selected(self) -> None:
        """刪除選取節點（所有模式共用）；專案清單有焦點時改為移除專案。"""
        if self._project_list.hasFocus():
            self._remove_project()
            return
        if self._controller.mode == MODE_READ:
            return
        indexes = self._tree_view.selectionModel().selectedIndexes()
        seen = set()
        for idx in indexes:
            node = self._node_from_index(idx)
            if node and node.rel_path and node.rel_path not in seen:
                seen.add(node.rel_path)
                if self._controller.mode == MODE_VIRTUAL:
                    self._controller.execute(Command(op="delete", source=node.rel_path))
                elif self._controller.mode == MODE_REALTIME:
                    abs_path = self._resolve_node_path(node)
                    if abs_path:
                        rec = self._controller.execute(
                            Command(op="delete", source=str(abs_path))
                        )
                        if rec and not rec.success:
                            QMessageBox.warning(self, "刪除失敗", rec.error or "未知錯誤")
        if seen:
            if self._controller.mode == MODE_VIRTUAL:
                self._update_virtual_status()
            elif self._controller.mode == MODE_REALTIME:
                self._schedule_refresh()
            self.statusBar().showMessage(f"已刪除 {len(seen)} 個項目")

    def _do_rename_selected(self) -> None:
        """重命名選取節點（所有模式共用）。"""
        if self._controller.mode == MODE_READ:
            return
        idx = self._tree_view.currentIndex()
        node = self._node_from_index(idx)
        if not node or not node.rel_path:
            return
        new_name, ok = QInputDialog.getText(self, "重命名", "新名稱：", text=node.name)
        if not ok or not new_name.strip() or new_name.strip() == node.name:
            return
        if self._controller.mode == MODE_VIRTUAL:
            parent_path = "/".join(node.rel_path.split("/")[:-1])
            new_path = f"{parent_path}/{new_name.strip()}" if parent_path else new_name.strip()
            self._controller.execute(Command(op="rename", source=node.rel_path, dest=new_path))
            self._update_virtual_status()
        elif self._controller.mode == MODE_REALTIME:
            abs_path = self._resolve_node_path(node)
            if abs_path:
                new_dest = abs_path.parent / new_name.strip()
                rec = self._controller.execute(
                    Command(op="rename", source=str(abs_path), dest=str(new_dest))
                )
                if rec and not rec.success:
                    QMessageBox.warning(self, "重命名失敗", rec.error or "未知錯誤")
                else:
                    self._schedule_refresh()

    def _do_mkdir(self) -> None:
        """新增資料夾（所有模式共用），放入選中的資料夾內。"""
        if self._controller.mode == MODE_READ:
            return
        idx = self._tree_view.currentIndex()
        node = self._node_from_index(idx)
        parent = self._resolve_parent_node(node)
        name, ok = QInputDialog.getText(self, "新增資料夾", "資料夾名稱：")
        if not ok or not name.strip():
            return
        if self._controller.mode == MODE_VIRTUAL:
            parent_path = parent.rel_path if parent and parent.rel_path else ""
            new_path = f"{parent_path}/{name.strip()}" if parent_path else name.strip()
            self._controller.execute(Command(op="mkdir", source=new_path))
            self._update_virtual_status()
        elif self._controller.mode == MODE_REALTIME:
            parent_abs = self._resolve_node_path(parent) if parent else None
            if parent_abs and parent_abs.is_dir():
                target = parent_abs / name.strip()
            else:
                row = self._conn.execute(
                    "SELECT root_path FROM projects WHERE id=?",
                    (self._current_project_id,),
                ).fetchone()
                if not row:
                    return
                target = Path(row["root_path"]) / name.strip()
            rec = self._controller.execute(Command(op="mkdir", source=str(target)))
            if rec and not rec.success:
                QMessageBox.warning(self, "建立失敗", rec.error or "未知錯誤")
            else:
                self._schedule_refresh()
