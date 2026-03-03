"""工作階段服務 — 管理檔案操作的生命週期與復原。搬自 session_manager.py。"""

from typing import Optional

from domain.models import OperationRecord, MergeResult
from domain.services.file_operations import (
    move_file, delete_to_trash, copy_file, merge_folder,
    undo_operation, clean_trash,
)


class SessionService:
    """注入 SessionRepo。"""

    def __init__(self, session_repo):
        self._repo = session_repo
        self._session_id: Optional[int] = None
        self._project_id: Optional[int] = None

    def bind_project(self, project_id: int) -> None:
        """綁定專案，自動恢復 active session。"""
        self._project_id = project_id
        active = self._repo.get_active_session(project_id)
        if active:
            self._session_id = active["id"]

    @property
    def active(self) -> bool:
        return self._session_id is not None

    @property
    def session_id(self) -> Optional[int]:
        return self._session_id

    def start(self, description: str = "") -> int:
        if self._session_id is not None:
            raise RuntimeError("已有進行中的工作階段")
        self._session_id = self._repo.create_session(
            self._project_id, description)
        return self._session_id

    def resume(self, session_id: int) -> None:
        self._session_id = session_id

    def _require_active(self) -> int:
        if self._session_id is None:
            raise RuntimeError("沒有進行中的工作階段")
        return self._session_id

    # ── 執行操作 ──────────────────────────────────────────

    def execute_move(self, source: str, dest: str,
                     node_id: Optional[int] = None,
                     dry_run: bool = False) -> OperationRecord:
        sid = self._require_active()
        rec = move_file(source, dest, dry_run=dry_run)
        if not dry_run and rec.success:
            self._repo.add_file_operation(sid, "move", source, dest, node_id)
        elif not dry_run and not rec.success:
            op_id = self._repo.add_file_operation(
                sid, "move", source, dest, node_id)
            self._repo.update_file_operation_status(
                op_id, "failed", rec.error)
        return rec

    def execute_delete(self, target: str,
                       node_id: Optional[int] = None,
                       dry_run: bool = False) -> OperationRecord:
        sid = self._require_active()
        rec = delete_to_trash(target, dry_run=dry_run)
        if not dry_run and rec.success:
            self._repo.add_file_operation(
                sid, "delete", target, rec.dest, node_id)
        elif not dry_run and not rec.success:
            op_id = self._repo.add_file_operation(
                sid, "delete", target, None, node_id)
            self._repo.update_file_operation_status(
                op_id, "failed", rec.error)
        return rec

    def execute_copy(self, source: str, dest: str,
                     node_id: Optional[int] = None,
                     dry_run: bool = False) -> OperationRecord:
        sid = self._require_active()
        rec = copy_file(source, dest, dry_run=dry_run)
        if not dry_run and rec.success:
            self._repo.add_file_operation(sid, "copy", source, dest, node_id)
        elif not dry_run and not rec.success:
            op_id = self._repo.add_file_operation(
                sid, "copy", source, dest, node_id)
            self._repo.update_file_operation_status(
                op_id, "failed", rec.error)
        return rec

    def execute_merge(self, source: str, dest: str,
                      dry_run: bool = False) -> MergeResult:
        sid = self._require_active()
        result = merge_folder(source, dest, dry_run=dry_run)
        if not dry_run:
            for rec in result.moved:
                if rec.success:
                    self._repo.add_file_operation(
                        sid, "merge", rec.source, rec.dest)
        return result

    # ── 復原 ──────────────────────────────────────────────

    def undo_last(self) -> bool:
        sid = self._require_active()
        ops = self._repo.list_file_operations(sid)
        for op in reversed(ops):
            if op["status"] == "executed":
                return self._undo_one(op)
        return False

    def undo_to(self, operation_id: int) -> int:
        sid = self._require_active()
        ops = self._repo.list_file_operations(sid)

        target_sort = None
        for op in ops:
            if op["id"] == operation_id:
                target_sort = op["sort_order"]
                break
        if target_sort is None:
            return 0

        count = 0
        for op in reversed(ops):
            if op["status"] != "executed":
                continue
            if op["sort_order"] >= target_sort:
                if self._undo_one(op):
                    count += 1
        return count

    def _undo_one(self, op) -> bool:
        from pathlib import Path
        trash_key = None
        if op["op_type"] == "delete" and op["dest_path"]:
            trash_key = Path(op["dest_path"]).name

        ok = undo_operation(
            op["op_type"], op["source_path"],
            op["dest_path"], trash_key,
        )
        if ok:
            self._repo.update_file_operation_status(op["id"], "undone")
        return ok

    def get_history(self) -> list:
        if self._session_id is None:
            return []
        return self._repo.list_file_operations(self._session_id)

    def operation_count(self) -> int:
        if self._session_id is None:
            return 0
        return len([
            op for op in self._repo.list_file_operations(self._session_id)
            if op["status"] == "executed"
        ])

    # ── 結束 ──────────────────────────────────────────────

    def finalize(self, do_clean_trash: bool = False) -> None:
        sid = self._require_active()
        self._repo.finalize_session(sid)
        self._session_id = None
        if do_clean_trash:
            clean_trash()

    def cancel(self) -> int:
        sid = self._require_active()
        ops = self._repo.list_file_operations(sid)
        count = 0
        for op in reversed(ops):
            if op["status"] == "executed":
                if self._undo_one(op):
                    count += 1
        self._repo.cancel_session(sid)
        self._session_id = None
        return count
