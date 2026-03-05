"""TODO Repository — Todo CRUD + 時間軸."""

import sqlite3
from datetime import datetime
from typing import Optional


class SqliteTodoRepository:

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def list_todos(self, project_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM todos WHERE project_id=? "
            "ORDER BY done, priority DESC, created_at",
            (project_id,),
        ).fetchall()

    def add_todo(self, project_id: int, title: str,
                 priority: int = 0,
                 due_date: Optional[str] = None) -> int:
        now = datetime.now().isoformat()
        cur = self._conn.execute(
            "INSERT INTO todos (project_id, title, priority, due_date, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, title, priority, due_date, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def toggle_todo(self, todo_id: int) -> None:
        self._conn.execute(
            "UPDATE todos SET done = 1 - done WHERE id=?", (todo_id,)
        )
        self._conn.commit()

    def delete_todo(self, todo_id: int) -> None:
        self._conn.execute("DELETE FROM todos WHERE id=?", (todo_id,))
        self._conn.commit()

    def get_timeline(self) -> list[sqlite3.Row]:
        return self._conn.execute("""
            SELECT
                p.id, p.name, p.root_path, p.progress,
                p.created_at, p.updated_at,
                COUNT(t.id)            AS todo_total,
                SUM(t.done)            AS todo_done
            FROM projects p
            LEFT JOIN todos t ON t.project_id = p.id
            GROUP BY p.id
            ORDER BY p.created_at ASC
        """).fetchall()
