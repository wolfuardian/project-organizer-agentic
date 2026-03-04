"""ModeController — 統一指令派發介面，依模式分派至 VirtualService 或 LiveHistory。"""

from __future__ import annotations

from typing import Any, Callable

from domain.enums import MODE_READ, MODE_VIRTUAL, MODE_REALTIME
from domain.models import Command, OperationRecord
from application.virtual_service import VirtualService
from domain.services.live_history import LiveHistory


class ModeController:
    """統一介面：execute / undo / redo，依目前模式決定行為。"""

    def __init__(self) -> None:
        self._mode: str = MODE_READ
        self._virtual = VirtualService()
        self._live = LiveHistory()

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    # ── 通用操作 ──────────────────────────────────────────

    def execute(self, cmd: Command) -> Any:
        """執行指令。Preview 回傳 None；Virtual push；Live 立即執行。"""
        if self._mode == MODE_READ:
            return None
        if self._mode == MODE_VIRTUAL:
            self._virtual.push(cmd)
            return cmd
        if self._mode == MODE_REALTIME:
            return self._live.execute(cmd)
        return None

    def undo(self) -> Any:
        if self._mode == MODE_READ:
            return None
        if self._mode == MODE_VIRTUAL:
            return self._virtual.undo()
        if self._mode == MODE_REALTIME:
            return self._live.undo()
        return None

    def redo(self) -> Any:
        if self._mode == MODE_READ:
            return None
        if self._mode == MODE_VIRTUAL:
            return self._virtual.redo()
        if self._mode == MODE_REALTIME:
            return self._live.redo()
        return None

    @property
    def can_undo(self) -> bool:
        if self._mode == MODE_VIRTUAL:
            return self._virtual.can_undo
        if self._mode == MODE_REALTIME:
            return self._live.can_undo
        return False

    @property
    def can_redo(self) -> bool:
        if self._mode == MODE_VIRTUAL:
            return self._virtual.can_redo
        if self._mode == MODE_REALTIME:
            return self._live.can_redo
        return False

    # ── Virtual 專屬 ─────────────────────────────────────

    @property
    def virtual_active(self) -> bool:
        return self._virtual.active

    def begin_virtual(self, snapshot: list[dict]) -> None:
        self._virtual.begin(snapshot)

    def pending_commands(self) -> list[Command]:
        return self._virtual.pending_commands()

    def resolve_tree(self) -> list[dict]:
        return self._virtual.resolve_tree()

    def apply(self, executor: Callable[[Command], bool]) -> bool:
        return self._virtual.apply(executor)

    def discard(self) -> None:
        self._virtual.discard()

    # ── Live 專屬 ────────────────────────────────────────

    def live_history(self) -> list[OperationRecord]:
        return self._live.history()

    def clear_live(self) -> None:
        self._live.clear()
