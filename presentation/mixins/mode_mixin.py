"""模式切換 mixin — read / virtual / realtime 模式管理。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QAbstractItemView, QMessageBox

from domain.enums import (
    MODE_READ, MODE_VIRTUAL, MODE_REALTIME, MODE_LABELS,
)

if TYPE_CHECKING:
    from presentation.main_window import MainWindow


class ModeMixin:
    """模式切換 + 模式相關 UI 狀態更新。"""

    def _set_mode(self, mode: str) -> None:
        """切換操作模式。"""
        # 離開虛擬模式時，若有未套用變更，詢問使用者
        if self._controller.mode == MODE_VIRTUAL and mode != MODE_VIRTUAL:
            if self._controller.virtual_active and self._controller.pending_commands():
                reply = QMessageBox.question(
                    self, "虛擬模式",
                    "目前有未套用的虛擬變更，要放棄嗎？",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    for k, btn in self._mode_buttons.items():
                        btn.setChecked(k == self._controller.mode)
                    return
            self._controller.discard()
            self._clear_virtual_overlay()

        self._controller.set_mode(mode)
        for k, btn in self._mode_buttons.items():
            btn.setChecked(k == mode)
        self._apply_mode()
        self.statusBar().showMessage(f"模式：{MODE_LABELS[mode]}")

    def _apply_mode(self) -> None:
        """根據當前模式啟用/停用 UI 元件。"""
        is_read = self._controller.mode == MODE_READ
        is_virtual = self._controller.mode == MODE_VIRTUAL

        if is_read:
            self._tree_view.setDragEnabled(False)
            self._tree_view.setAcceptDrops(False)
            self._tree_view.setDragDropMode(QAbstractItemView.NoDragDrop)
        else:
            self._tree_view.setDragEnabled(True)
            self._tree_view.setAcceptDrops(True)
            self._tree_view.setDragDropMode(QAbstractItemView.InternalMove)

        # 虛擬模式：開始 VirtualService + 設定 drop 攔截
        if is_virtual and self._tree_model:
            if not self._controller.virtual_active:
                snapshot = getattr(self, "_last_snapshot", None) or self._build_flat_lists()[1]
                self._controller.begin_virtual(snapshot)
            self._tree_model.set_on_drop(self._on_virtual_drop)
        elif self._tree_model:
            self._tree_model.set_on_drop(
                self._on_live_drop if self._controller.mode == MODE_REALTIME else None
            )

        self._virtual_bar.setVisible(is_virtual)
        self._update_virtual_status()

        # 非即時模式時關閉第二面板
        if self._controller.mode != MODE_REALTIME and self._panel_b.isVisible():
            self._panel_b.setVisible(False)
            self._act_panel_b.setChecked(False)
            self._splitter.update()
