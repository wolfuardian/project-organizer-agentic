"""分類規則 Repository — Rule CRUD."""

import sqlite3

from domain.models import ClassifyRule


class SqliteRuleRepository:

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def init_table(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS classify_rules (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                pattern      TEXT NOT NULL,
                pattern_type TEXT NOT NULL DEFAULT 'glob'
                             CHECK(pattern_type IN ('glob','regex')),
                match_target TEXT NOT NULL DEFAULT 'name'
                             CHECK(match_target IN ('name','path')),
                category     TEXT NOT NULL,
                priority     INTEGER DEFAULT 100,
                enabled      INTEGER DEFAULT 1
            )
        """)
        self._conn.commit()

    def list_rules(self) -> list[ClassifyRule]:
        rows = self._conn.execute(
            "SELECT * FROM classify_rules ORDER BY priority, id"
        ).fetchall()
        return [ClassifyRule(**dict(r)) for r in rows]

    def add_rule(self, name: str, pattern: str,
                 pattern_type: str = "glob", match_target: str = "name",
                 category: str = "other", priority: int = 100) -> int:
        cur = self._conn.execute(
            "INSERT INTO classify_rules "
            "(name, pattern, pattern_type, match_target, category, priority) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, pattern, pattern_type, match_target, category, priority),
        )
        self._conn.commit()
        return cur.lastrowid

    def update_rule(self, rule_id: int, **kwargs) -> None:
        allowed = {"name", "pattern", "pattern_type", "match_target",
                   "category", "priority", "enabled"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k}=?" for k in fields)
        self._conn.execute(
            f"UPDATE classify_rules SET {set_clause} WHERE id=?",
            (*fields.values(), rule_id),
        )
        self._conn.commit()

    def delete_rule(self, rule_id: int) -> None:
        self._conn.execute(
            "DELETE FROM classify_rules WHERE id=?", (rule_id,))
        self._conn.commit()
