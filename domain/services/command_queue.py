"""CommandQueue — 虛擬模式的指令佇列，支援 undo/redo。"""

from __future__ import annotations

from domain.models import Command


class CommandQueue:
    """cursor-based undo/redo 指令佇列。

    _commands[:_cursor] 為 pending（已確認的指令），
    _commands[_cursor:] 為 redo 區域（可重做的指令）。
    """

    def __init__(self) -> None:
        self._commands: list[Command] = []
        self._cursor: int = 0

    def push(self, cmd: Command) -> None:
        # 丟棄 redo 區域
        del self._commands[self._cursor:]
        self._commands.append(cmd)
        self._cursor += 1

    def undo(self) -> Command | None:
        if self._cursor <= 0:
            return None
        self._cursor -= 1
        return self._commands[self._cursor]

    def redo(self) -> Command | None:
        if self._cursor >= len(self._commands):
            return None
        cmd = self._commands[self._cursor]
        self._cursor += 1
        return cmd

    def pending(self) -> list[Command]:
        return list(self._commands[:self._cursor])

    def clear(self) -> None:
        self._commands.clear()
        self._cursor = 0

    @property
    def can_undo(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor < len(self._commands)
