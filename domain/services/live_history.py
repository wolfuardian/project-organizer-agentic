"""LiveHistory — 即時模式的操作歷史，支援 undo/redo（直接操作檔案系統）。"""

from __future__ import annotations

from pathlib import Path

from domain.models import Command, OperationRecord
from domain.services.file_operations import (
    move_file, delete_to_trash, copy_file, undo_operation,
)


class LiveHistory:
    """cursor-based undo/redo，每筆記錄為已執行的 OperationRecord。"""

    def __init__(self) -> None:
        self._records: list[tuple[Command, OperationRecord]] = []
        self._cursor: int = 0

    @property
    def can_undo(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor < len(self._records)

    def execute(self, cmd: Command) -> OperationRecord:
        """立即執行指令並記錄結果。失敗的操作不進入歷史。"""
        rec = self._run(cmd)
        if rec.success:
            # 丟棄 redo 區域
            del self._records[self._cursor:]
            self._records.append((cmd, rec))
            self._cursor += 1
        return rec

    def undo(self) -> bool:
        """復原上一筆操作。回傳是否成功。"""
        if self._cursor <= 0:
            return False
        self._cursor -= 1
        _, rec = self._records[self._cursor]
        return undo_operation(
            rec.op_type, rec.source,
            dest=rec.dest, trash_key=rec.trash_key,
        )

    def redo(self) -> OperationRecord | None:
        """重做上一筆復原的操作。回傳新的 OperationRecord。"""
        if self._cursor >= len(self._records):
            return None
        cmd, _ = self._records[self._cursor]
        rec = self._run(cmd)
        if rec.success:
            self._records[self._cursor] = (cmd, rec)
            self._cursor += 1
        return rec

    def history(self) -> list[OperationRecord]:
        """回傳所有已執行（cursor 前）的操作記錄。"""
        return [rec for _, rec in self._records[:self._cursor]]

    def clear(self) -> None:
        self._records.clear()
        self._cursor = 0

    @staticmethod
    def _run(cmd: Command) -> OperationRecord:
        """根據 Command.op 派發到對應的 file_operations 函式。"""
        if cmd.op == "move" and cmd.dest:
            return move_file(cmd.source, cmd.dest)
        elif cmd.op == "delete":
            return delete_to_trash(cmd.source)
        elif cmd.op == "copy" and cmd.dest:
            return copy_file(cmd.source, cmd.dest)
        elif cmd.op == "rename" and cmd.dest:
            return move_file(cmd.source, cmd.dest)
        elif cmd.op == "mkdir":
            try:
                Path(cmd.source).mkdir(parents=True, exist_ok=True)
                return OperationRecord(
                    op_type="mkdir", source=cmd.source, success=True,
                )
            except Exception as e:
                return OperationRecord(
                    op_type="mkdir", source=cmd.source,
                    success=False, error=str(e),
                )
        return OperationRecord(
            op_type=cmd.op, source=cmd.source,
            success=False, error=f"unsupported op: {cmd.op}",
        )
