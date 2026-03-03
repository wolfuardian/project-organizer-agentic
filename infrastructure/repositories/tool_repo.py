"""外部工具 Repository — Tool CRUD."""

import sys
import sqlite3


class SqliteToolRepository:

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def list_tools(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM external_tools WHERE enabled=1 ORDER BY name"
        ).fetchall()

    def list_all_tools(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM external_tools ORDER BY name"
        ).fetchall()

    def add_tool(self, name: str, exe_path: str,
                 args_tmpl: str = "{path}", icon: str = "") -> int:
        cur = self._conn.execute(
            "INSERT INTO external_tools (name, exe_path, args_tmpl, icon) "
            "VALUES (?, ?, ?, ?)",
            (name, exe_path, args_tmpl, icon),
        )
        self._conn.commit()
        return cur.lastrowid

    def update_tool(self, tool_id: int, name: str, exe_path: str,
                    args_tmpl: str, enabled: int) -> None:
        self._conn.execute(
            "UPDATE external_tools SET name=?, exe_path=?, args_tmpl=?, enabled=? "
            "WHERE id=?",
            (name, exe_path, args_tmpl, enabled, tool_id),
        )
        self._conn.commit()

    def delete_tool(self, tool_id: int) -> None:
        self._conn.execute(
            "DELETE FROM external_tools WHERE id=?", (tool_id,))
        self._conn.commit()

    def seed_default_tools(self) -> None:
        if self._conn.execute(
            "SELECT COUNT(*) FROM external_tools"
        ).fetchone()[0]:
            return
        defaults = [
            ("VS Code",     "code",                   "{path}"),
            ("Terminal",
             "wt" if sys.platform == "win32" else "x-terminal-emulator",
             "--startingDirectory {dir}"),
            ("Unity Hub",   "unityhub",               "{dir}"),
        ]
        for name, exe, tmpl in defaults:
            self._conn.execute(
                "INSERT INTO external_tools (name, exe_path, args_tmpl) "
                "VALUES (?,?,?)",
                (name, exe, tmpl),
            )
        self._conn.commit()
