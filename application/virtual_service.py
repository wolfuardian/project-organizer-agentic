"""VirtualService — 虛擬模式協調器，管理 CommandQueue + VirtualTree。"""

from __future__ import annotations

from typing import Callable

from domain.models import Command
from domain.services.command_queue import CommandQueue
from domain.services.virtual_tree import VirtualTree


class VirtualService:
    """虛擬模式的 application-layer 服務。

    生命週期：begin() → push/undo/redo → apply() 或 discard()
    """

    def __init__(self) -> None:
        self._queue = CommandQueue()
        self._snapshot: list[dict] = []
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    @property
    def can_undo(self) -> bool:
        return self._queue.can_undo

    @property
    def can_redo(self) -> bool:
        return self._queue.can_redo

    def begin(self, snapshot: list[dict]) -> None:
        """開始虛擬模式，傳入目前的 flat snapshot。"""
        self._snapshot = snapshot
        self._queue.clear()
        self._active = True

    def push(self, cmd: Command) -> None:
        self._queue.push(cmd)

    def undo(self) -> Command | None:
        return self._queue.undo()

    def redo(self) -> Command | None:
        return self._queue.redo()

    def pending_commands(self) -> list[Command]:
        return self._queue.pending()

    def resolve_tree(self) -> list[dict]:
        """回傳套用所有 pending commands 後的虛擬樹。"""
        vt = VirtualTree(self._snapshot, self._queue.pending())
        return vt.resolve()

    def apply(self, executor: Callable[[Command], bool]) -> bool:
        """套用所有 pending commands，依序呼叫 executor。

        executor 接收 Command，回傳 True 表示成功。
        全部完成後結束虛擬模式。
        """
        for cmd in self._queue.pending():
            executor(cmd)
        self._queue.clear()
        self._active = False
        return True

    def discard(self) -> None:
        """放棄所有變更，結束虛擬模式。"""
        self._queue.clear()
        self._active = False
