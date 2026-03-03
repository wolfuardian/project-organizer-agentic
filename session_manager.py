"""Shim — 轉發至新路徑，保持舊 import 不壞。"""

import sqlite3
from typing import Optional

from infrastructure.repositories.session_repo import SqliteSessionRepository
from application.session_service import SessionService


class SessionManager:
    """保持原始介面 SessionManager(conn, project_id)。"""

    def __init__(self, conn: sqlite3.Connection, project_id: int):
        repo = SqliteSessionRepository(conn)
        self._svc = SessionService(repo)
        self._svc.bind_project(project_id)

    @property
    def active(self) -> bool:
        return self._svc.active

    @property
    def session_id(self) -> Optional[int]:
        return self._svc.session_id

    def start(self, description: str = "") -> int:
        return self._svc.start(description)

    def resume(self, session_id: int) -> None:
        self._svc.resume(session_id)

    def execute_move(self, source, dest, node_id=None, dry_run=False):
        return self._svc.execute_move(source, dest, node_id, dry_run)

    def execute_delete(self, target, node_id=None, dry_run=False):
        return self._svc.execute_delete(target, node_id, dry_run)

    def execute_copy(self, source, dest, node_id=None, dry_run=False):
        return self._svc.execute_copy(source, dest, node_id, dry_run)

    def execute_merge(self, source, dest, dry_run=False):
        return self._svc.execute_merge(source, dest, dry_run)

    def undo_last(self) -> bool:
        return self._svc.undo_last()

    def undo_to(self, operation_id: int) -> int:
        return self._svc.undo_to(operation_id)

    def get_history(self) -> list:
        return self._svc.get_history()

    def operation_count(self) -> int:
        return self._svc.operation_count()

    def finalize(self, do_clean_trash: bool = False) -> None:
        self._svc.finalize(do_clean_trash)

    def cancel(self) -> int:
        return self._svc.cancel()
