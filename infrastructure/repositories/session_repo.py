"""工作階段 Repository — Session + FileOperation CRUD."""

import sqlite3
from datetime import datetime
from typing import Optional


class SqliteSessionRepository:

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create_session(self, project_id: int,
                       description: str = "") -> int:
        now = datetime.now().isoformat()
        cur = self._conn.execute(
            "INSERT INTO operation_sessions "
            "(project_id, status, started_at, description) "
            "VALUES (?, 'active', ?, ?)",
            (project_id, now, description),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_active_session(self,
                           project_id: int) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM operation_sessions "
            "WHERE project_id=? AND status='active' "
            "ORDER BY started_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()

    def finalize_session(self, session_id: int) -> None:
        now = datetime.now().isoformat()
        self._conn.execute(
            "UPDATE operation_sessions SET status='finalized', ended_at=? "
            "WHERE id=?", (now, session_id),
        )
        self._conn.commit()

    def cancel_session(self, session_id: int) -> None:
        now = datetime.now().isoformat()
        self._conn.execute(
            "UPDATE operation_sessions SET status='cancelled', ended_at=? "
            "WHERE id=?", (now, session_id),
        )
        self._conn.commit()

    def add_file_operation(self, session_id: int, op_type: str,
                           source_path: str,
                           dest_path: Optional[str] = None,
                           node_id: Optional[int] = None) -> int:
        now = datetime.now().isoformat()
        order = self._conn.execute(
            "SELECT COALESCE(MAX(sort_order),0)+1 FROM file_operations "
            "WHERE session_id=?", (session_id,),
        ).fetchone()[0]
        cur = self._conn.execute(
            "INSERT INTO file_operations "
            "(session_id, op_type, source_path, dest_path, node_id, "
            " status, executed_at, sort_order) "
            "VALUES (?, ?, ?, ?, ?, 'executed', ?, ?)",
            (session_id, op_type, source_path, dest_path, node_id, now, order),
        )
        self._conn.commit()
        return cur.lastrowid

    def update_file_operation_status(self, op_id: int, status: str,
                                     error_msg: Optional[str] = None) -> None:
        self._conn.execute(
            "UPDATE file_operations SET status=?, error_msg=? WHERE id=?",
            (status, error_msg, op_id),
        )
        self._conn.commit()

    def list_file_operations(self,
                             session_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM file_operations WHERE session_id=? "
            "ORDER BY sort_order", (session_id,),
        ).fetchall()
