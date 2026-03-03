"""節點 Repository — Node CRUD + 路徑解析 + 搜尋 + 過濾."""

import sqlite3
from pathlib import Path
from typing import Optional


class SqliteNodeRepository:

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def upsert_node(self, project_id: int,
                    parent_id: Optional[int], name: str, rel_path: str,
                    node_type: str, sort_order: int = 0,
                    file_size: Optional[int] = None,
                    modified_at: Optional[str] = None,
                    category: Optional[str] = None,
                    root_id: Optional[int] = None) -> int:
        row = self._conn.execute(
            "SELECT id FROM nodes WHERE project_id=? AND rel_path=? AND "
            "COALESCE(root_id,0)=COALESCE(?,0)",
            (project_id, rel_path, root_id),
        ).fetchone()
        if row:
            self._conn.execute(
                "UPDATE nodes SET file_size=?, modified_at=?, category=?, root_id=? "
                "WHERE id=?",
                (file_size, modified_at, category, root_id, row["id"]),
            )
            return row["id"]
        cur = self._conn.execute(
            "INSERT INTO nodes "
            "(project_id, parent_id, name, rel_path, node_type, sort_order,"
            " file_size, modified_at, category, root_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, parent_id, name, rel_path, node_type, sort_order,
             file_size, modified_at, category, root_id),
        )
        return cur.lastrowid

    def get_node(self, node_id: int) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM nodes WHERE id=?", (node_id,)
        ).fetchone()

    def get_children(self, project_id: int,
                     parent_id: Optional[int]) -> list[sqlite3.Row]:
        if parent_id is None:
            return self._conn.execute(
                "SELECT * FROM nodes WHERE project_id=? AND parent_id IS NULL "
                "ORDER BY node_type='file', pinned DESC, sort_order, name",
                (project_id,),
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM nodes WHERE project_id=? AND parent_id=? "
            "ORDER BY node_type='file', pinned DESC, sort_order, name",
            (project_id, parent_id),
        ).fetchall()

    def get_children_by_root(self, project_id: int,
                             root_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM nodes WHERE project_id=? AND root_id=? "
            "AND parent_id IS NULL "
            "ORDER BY node_type='file', pinned DESC, sort_order, name",
            (project_id, root_id),
        ).fetchall()

    def move_node(self, node_id: int,
                  new_parent_id: Optional[int],
                  new_sort: int = 0) -> None:
        self._conn.execute(
            "UPDATE nodes SET parent_id=?, sort_order=? WHERE id=?",
            (new_parent_id, new_sort, node_id),
        )
        self._conn.commit()

    def delete_node(self, node_id: int) -> None:
        self._conn.execute("DELETE FROM nodes WHERE id=?", (node_id,))
        self._conn.commit()

    def delete_nodes_by_project(self, project_id: int) -> None:
        self._conn.execute(
            "DELETE FROM nodes WHERE project_id=?", (project_id,))
        self._conn.commit()

    def update_node_note(self, node_id: int, note: str) -> None:
        self._conn.execute(
            "UPDATE nodes SET note=? WHERE id=?", (note, node_id))
        self._conn.commit()

    def get_node_abs_path(self, node_id: int) -> Optional[Path]:
        """透過 root_id 解析節點的絕對路徑。虛擬節點回傳 None。"""
        row = self._conn.execute("""
            SELECT n.rel_path, n.node_type, n.root_id,
                   pr.root_path AS pr_root,
                   p.root_path  AS p_root
            FROM nodes n
            JOIN projects p ON p.id = n.project_id
            LEFT JOIN project_roots pr ON pr.id = n.root_id
            WHERE n.id=?
        """, (node_id,)).fetchone()
        if not row or row["node_type"] == "virtual":
            return None
        base = row["pr_root"] if row["pr_root"] else row["p_root"]
        if not base:
            return None
        return Path(base) / row["rel_path"]

    def get_root_for_node(self, node_id: int) -> Optional[sqlite3.Row]:
        """取得節點所屬的 project_root 記錄。"""
        return self._conn.execute("""
            SELECT pr.* FROM project_roots pr
            JOIN nodes n ON n.root_id = pr.id
            WHERE n.id=?
        """, (node_id,)).fetchone()

    def get_parent_id(self, node_id: int) -> Optional[int]:
        row = self._conn.execute(
            "SELECT parent_id FROM nodes WHERE id=?", (node_id,)
        ).fetchone()
        return row["parent_id"] if row else None

    def search_nodes(self, query: str,
                     project_ids: Optional[list[int]] = None,
                     limit: int = 200) -> list[sqlite3.Row]:
        q = f"%{query}%"
        base = """
            SELECT DISTINCT
                n.id, n.name, n.rel_path, n.node_type,
                n.file_size, n.category, n.note,
                p.id   AS project_id,
                p.name AS project_name,
                p.root_path
            FROM nodes n
            JOIN projects p ON p.id = n.project_id
            LEFT JOIN node_tags nt ON nt.node_id = n.id
            LEFT JOIN tags      t  ON t.id = nt.tag_id
            WHERE (
                n.name LIKE ?
                OR n.note LIKE ?
                OR t.name LIKE ?
            )
        """
        params: list = [q, q, q]

        if project_ids:
            placeholders = ",".join("?" * len(project_ids))
            base += f" AND n.project_id IN ({placeholders})"
            params.extend(project_ids)

        base += " ORDER BY n.name LIMIT ?"
        params.append(limit)
        return self._conn.execute(base, params).fetchall()

    def filter_nodes(
        self,
        project_ids: Optional[list[int]] = None,
        categories: Optional[list[str]] = None,
        tag_ids: Optional[list[int]] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        modified_after: Optional[str] = None,
        modified_before: Optional[str] = None,
        node_types: Optional[list[str]] = None,
        limit: int = 500,
    ) -> list[sqlite3.Row]:
        clauses: list[str] = []
        params: list = []

        if project_ids:
            placeholders = ",".join("?" * len(project_ids))
            clauses.append(f"n.project_id IN ({placeholders})")
            params.extend(project_ids)

        if node_types:
            placeholders = ",".join("?" * len(node_types))
            clauses.append(f"n.node_type IN ({placeholders})")
            params.extend(node_types)

        if categories:
            placeholders = ",".join("?" * len(categories))
            clauses.append(f"n.category IN ({placeholders})")
            params.extend(categories)

        if min_size is not None:
            clauses.append("n.file_size >= ?")
            params.append(min_size)

        if max_size is not None:
            clauses.append("n.file_size <= ?")
            params.append(max_size)

        if modified_after:
            clauses.append("n.modified_at >= ?")
            params.append(modified_after)

        if modified_before:
            clauses.append("n.modified_at <= ?")
            params.append(modified_before)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        tag_clauses = ""
        if tag_ids:
            for tid in tag_ids:
                tag_clauses += (
                    f" AND EXISTS (SELECT 1 FROM node_tags nt"
                    f" WHERE nt.node_id=n.id AND nt.tag_id={int(tid)})"
                )

        sql = f"""
            SELECT DISTINCT
                n.id, n.name, n.rel_path, n.node_type,
                n.file_size, n.category, n.modified_at, n.note,
                p.id   AS project_id,
                p.name AS project_name,
                p.root_path
            FROM nodes n
            JOIN projects p ON p.id = n.project_id
            {where}
            {tag_clauses}
            ORDER BY n.name
            LIMIT ?
        """
        params.append(limit)
        return self._conn.execute(sql, params).fetchall()

    def get_file_nodes_for_duplicates(
        self,
        project_ids: Optional[list[int]] = None,
    ) -> list[sqlite3.Row]:
        base_sql = """
            SELECT n.id, n.project_id, n.rel_path, n.file_size, n.name,
                   COALESCE(pr.root_path, p.root_path) AS root_path,
                   p.name AS project_name
            FROM nodes n
            JOIN projects p ON p.id = n.project_id
            LEFT JOIN project_roots pr ON pr.id = n.root_id
            WHERE n.node_type = 'file'
              AND n.file_size IS NOT NULL
        """
        if project_ids:
            placeholders = ",".join("?" * len(project_ids))
            return self._conn.execute(
                f"{base_sql} AND n.project_id IN ({placeholders}) "
                "ORDER BY n.file_size, n.name",
                project_ids,
            ).fetchall()
        return self._conn.execute(
            f"{base_sql} ORDER BY n.file_size, n.name"
        ).fetchall()
