"""專案 Repository — Project + ProjectRoot CRUD."""

import sqlite3
from datetime import datetime
from typing import Optional


class SqliteProjectRepository:

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # ── Project CRUD ──────────────────────────────────────

    def create_project(self, name: str, root_path: str,
                       description: str = "") -> int:
        now = datetime.now().isoformat()
        cur = self._conn.execute(
            "INSERT INTO projects (name, root_path, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, root_path, description, now, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_projects(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC"
        ).fetchall()

    def get_project(self, project_id: int) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM projects WHERE id=?", (project_id,)
        ).fetchone()

    def delete_project(self, project_id: int) -> None:
        self._conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        self._conn.commit()

    def set_project_progress(self, project_id: int,
                             progress: str) -> None:
        now = datetime.now().isoformat()
        self._conn.execute(
            "UPDATE projects SET progress=?, updated_at=? WHERE id=?",
            (progress, now, project_id),
        )
        self._conn.commit()

    # ── Project Roots ─────────────────────────────────────

    def add_project_root(self, project_id: int, root_path: str,
                         role: str = "source", label: str = "") -> int:
        now = datetime.now().isoformat()
        cur = self._conn.execute(
            "INSERT INTO project_roots "
            "(project_id, root_path, role, label, sort_order, added_at) "
            "VALUES (?, ?, ?, ?, "
            "(SELECT COALESCE(MAX(sort_order),0)+1 FROM project_roots "
            " WHERE project_id=?), ?)",
            (project_id, root_path, role, label, project_id, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_project_roots(self, project_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM project_roots WHERE project_id=? ORDER BY sort_order",
            (project_id,),
        ).fetchall()

    def update_project_root(self, root_id: int,
                            role: str, label: str) -> None:
        self._conn.execute(
            "UPDATE project_roots SET role=?, label=? WHERE id=?",
            (role, label, root_id),
        )
        self._conn.commit()

    def remove_project_root(self, root_id: int) -> None:
        self._conn.execute("DELETE FROM project_roots WHERE id=?", (root_id,))
        self._conn.commit()
