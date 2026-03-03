"""專案關聯 Repository — Relation CRUD."""

import sqlite3


class SqliteRelationRepository:

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def list_relations(self, project_id: int) -> list[sqlite3.Row]:
        return self._conn.execute("""
            SELECT r.*,
                   ps.name AS source_name,
                   pt.name AS target_name
            FROM project_relations r
            JOIN projects ps ON ps.id = r.source_id
            JOIN projects pt ON pt.id = r.target_id
            WHERE r.source_id=? OR r.target_id=?
            ORDER BY r.relation_type, ps.name
        """, (project_id, project_id)).fetchall()

    def add_relation(self, source_id: int, target_id: int,
                     relation_type: str, note: str = "") -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO project_relations "
            "(source_id, target_id, relation_type, note) VALUES (?, ?, ?, ?)",
            (source_id, target_id, relation_type, note),
        )
        self._conn.commit()

    def delete_relation(self, relation_id: int) -> None:
        self._conn.execute(
            "DELETE FROM project_relations WHERE id=?", (relation_id,))
        self._conn.commit()
