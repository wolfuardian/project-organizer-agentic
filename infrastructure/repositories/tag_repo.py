"""標籤 Repository — Tag CRUD + node_tag 指派."""

import sqlite3
from typing import Optional


class SqliteTagRepository:

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def list_tags(self, parent_id: Optional[int] = None) -> list[sqlite3.Row]:
        if parent_id is None:
            return self._conn.execute(
                "SELECT * FROM tags WHERE parent_id IS NULL ORDER BY name"
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM tags WHERE parent_id=? ORDER BY name", (parent_id,)
        ).fetchall()

    def all_tags_flat(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM tags ORDER BY name").fetchall()

    def create_tag(self, name: str, color: str = "#89b4fa",
                   parent_id: Optional[int] = None) -> int:
        cur = self._conn.execute(
            "INSERT INTO tags (name, color, parent_id) VALUES (?, ?, ?)",
            (name, color, parent_id),
        )
        self._conn.commit()
        return cur.lastrowid

    def update_tag(self, tag_id: int, name: str, color: str) -> None:
        self._conn.execute(
            "UPDATE tags SET name=?, color=? WHERE id=?",
            (name, color, tag_id),
        )
        self._conn.commit()

    def delete_tag(self, tag_id: int) -> None:
        self._conn.execute("DELETE FROM tags WHERE id=?", (tag_id,))
        self._conn.commit()

    def get_node_tags(self, node_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT t.* FROM tags t "
            "JOIN node_tags nt ON nt.tag_id = t.id "
            "WHERE nt.node_id=? ORDER BY t.name",
            (node_id,),
        ).fetchall()

    def add_node_tag(self, node_id: int, tag_id: int) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO node_tags (node_id, tag_id) VALUES (?, ?)",
            (node_id, tag_id),
        )
        self._conn.commit()

    def remove_node_tag(self, node_id: int, tag_id: int) -> None:
        self._conn.execute(
            "DELETE FROM node_tags WHERE node_id=? AND tag_id=?",
            (node_id, tag_id),
        )
        self._conn.commit()
