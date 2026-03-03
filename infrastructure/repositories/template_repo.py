"""模板 Repository — Template CRUD."""

import sqlite3
from datetime import datetime

from domain.models import ProjectTemplate, TemplateEntry


class SqliteTemplateRepository:

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def init_table(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS templates (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                description TEXT DEFAULT '',
                category    TEXT DEFAULT 'general',
                is_builtin  INTEGER DEFAULT 0,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS template_entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL
                            REFERENCES templates(id) ON DELETE CASCADE,
                path        TEXT NOT NULL,
                is_dir      INTEGER DEFAULT 0,
                content     TEXT DEFAULT ''
            );
        """)
        self._conn.commit()

    def save_template(self, tmpl: ProjectTemplate) -> int:
        now = datetime.now().isoformat()
        cur = self._conn.execute(
            "INSERT INTO templates (name, description, category, is_builtin, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (tmpl.name, tmpl.description, tmpl.category,
             1 if tmpl.is_builtin else 0, now),
        )
        tid = cur.lastrowid
        for e in tmpl.entries:
            self._conn.execute(
                "INSERT INTO template_entries (template_id, path, is_dir, content) "
                "VALUES (?, ?, ?, ?)",
                (tid, e.path, 1 if e.is_dir else 0, e.content),
            )
        self._conn.commit()
        tmpl.id = tid
        tmpl.created_at = now
        return tid

    def list_templates(self,
                       include_builtin: bool = True) -> list[ProjectTemplate]:
        where = "" if include_builtin else "WHERE is_builtin=0"
        rows = self._conn.execute(
            f"SELECT * FROM templates {where} ORDER BY category, name"
        ).fetchall()
        result = []
        for row in rows:
            entries = self._conn.execute(
                "SELECT * FROM template_entries WHERE template_id=? ORDER BY path",
                (row["id"],),
            ).fetchall()
            result.append(ProjectTemplate(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                category=row["category"],
                is_builtin=bool(row["is_builtin"]),
                created_at=row["created_at"],
                entries=[
                    TemplateEntry(path=e["path"],
                                  is_dir=bool(e["is_dir"]),
                                  content=e["content"])
                    for e in entries
                ],
            ))
        return result

    def delete_template(self, template_id: int) -> None:
        self._conn.execute(
            "DELETE FROM templates WHERE id=? AND is_builtin=0",
            (template_id,))
        self._conn.commit()
