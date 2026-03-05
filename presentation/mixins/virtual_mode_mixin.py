"""虛擬模式 mixin — apply / discard / overlay / drop 攔截。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox, QDialog

from domain.enums import MODE_READ, MODE_VIRTUAL
from domain.models import Command

if TYPE_CHECKING:
    from presentation.main_window import MainWindow


class VirtualModeMixin:
    """虛擬模式指令佇列、套用/放棄、overlay 更新。"""

    def _build_flat_lists(self) -> tuple[list[dict], list[dict]]:
        """一次遍歷 tree model，同時建立搜尋快取和 snapshot。

        回傳 (search_cache, snapshot)。
        """
        search: list[dict] = []
        snapshot: list[dict] = []
        self._rel_path_to_db_id: dict[str, int] = {}
        if not self._tree_model:
            return search, snapshot
        stack = [self._tree_model._root]
        while stack:
            node = stack.pop()
            if node.db_id != 0:
                if node.rel_path:
                    search.append({"name": node.name, "rel_path": node.rel_path})
                    self._rel_path_to_db_id[node.rel_path] = node.db_id
                snapshot.append({
                    "path": node.rel_path,
                    "node_type": node.node_type,
                    "db_id": node.db_id,
                })
            if node.loaded:
                stack.extend(reversed(node.children))
        return search, snapshot

    def _on_virtual_drop(self, source_nodes, target_node) -> None:
        """虛擬模式 drop 攔截：批次 push move commands，只 resolve 一次。"""
        for src in source_nodes:
            dest = f"{target_node.rel_path}/{src.name}" if target_node.rel_path else src.name
            self._controller.execute(Command(op="move", source=src.rel_path, dest=dest))
        self._update_virtual_status()
        self.statusBar().showMessage(f"虛擬移動：{len(source_nodes)} 個項目")

    def _on_live_drop(self, source_nodes, target_node) -> None:
        """即時模式 drop 攔截：透過 controller 立即執行 move。"""
        for src in source_nodes:
            abs_src = self._resolve_node_path(src)
            abs_tgt = self._resolve_node_path(target_node)
            if abs_src and abs_tgt:
                dest = abs_tgt / src.name if abs_tgt.is_dir() else abs_tgt
                rec = self._controller.execute(
                    Command(op="move", source=str(abs_src), dest=str(dest))
                )
                if rec and not rec.success:
                    QMessageBox.warning(self, "移動失敗", rec.error or "未知錯誤")
                    return
        self._schedule_refresh()
        self.statusBar().showMessage(f"已移動 {len(source_nodes)} 個項目")

    def _update_virtual_status(self) -> None:
        """更新虛擬模式 UI：pending 計數 + 樹結構 + 著色。"""
        if not self._controller.virtual_active:
            self._lbl_pending.setText("0 項變更")
            self._clear_virtual_overlay()
            return
        cmds = self._controller.pending_commands()
        self._lbl_pending.setText(f"{len(cmds)} 項變更")
        resolved = self._controller.resolve_tree()
        if self._tree_model:
            self._tree_model.apply_virtual_tree(resolved)

    def _clear_virtual_overlay(self) -> None:
        if self._tree_model:
            self._tree_model.clear_virtual_tree()

    def _virtual_apply(self) -> None:
        """虛擬模式：開啟 DiffPanel 確認後套用所有變更。"""
        if not self._controller.virtual_active:
            return
        cmds = self._controller.pending_commands()
        if not cmds:
            QMessageBox.information(self, "虛擬模式", "沒有待套用的變更。")
            return
        from presentation.widgets.diff_panel import DiffPanel
        dlg = DiffPanel(cmds, self)
        if dlg.exec_() != QDialog.Accepted:
            return

        def executor(cmd: Command) -> bool:
            self.statusBar().showMessage(f"執行：{cmd.op} {cmd.source}")
            return True

        self._controller.apply(executor)
        self._clear_virtual_overlay()
        self._virtual_bar.setVisible(False)
        if self._tree_model:
            self._tree_model.set_on_drop(None)
        self._refresh_with_state()
        self.statusBar().showMessage("變更已套用")

    def _virtual_discard(self) -> None:
        """虛擬模式：放棄所有變更並退回預覽模式。"""
        cmds = self._controller.pending_commands()
        if self._controller.virtual_active and cmds:
            reply = QMessageBox.question(
                self, "放棄變更",
                f"確定要放棄 {len(cmds)} 項虛擬變更？",
            )
            if reply != QMessageBox.Yes:
                return
        self._controller.discard()
        self._clear_virtual_overlay()
        self._set_mode(MODE_READ)
