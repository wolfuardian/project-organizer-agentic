"""SQLite 資料庫層 — 專案與節點的持久化儲存."""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional


DB_PATH = Path.home() / ".project-organizer" / "data.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            root_path   TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            status      TEXT DEFAULT 'active'
                        CHECK(status IN ('active','archived','paused')),
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS nodes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            parent_id   INTEGER REFERENCES nodes(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            rel_path    TEXT NOT NULL,
            node_type   TEXT NOT NULL CHECK(node_type IN ('file','folder','virtual')),
            sort_order  INTEGER DEFAULT 0,
            pinned      INTEGER DEFAULT 0,
            note        TEXT DEFAULT '',
            file_size   INTEGER DEFAULT NULL,
            modified_at TEXT DEFAULT NULL,
            category    TEXT DEFAULT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_nodes_project ON nodes(project_id);
        CREATE INDEX IF NOT EXISTS idx_nodes_parent  ON nodes(parent_id);

        CREATE TABLE IF NOT EXISTS tags (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name  TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT '#888888'
        );

        CREATE TABLE IF NOT EXISTS node_tags (
            node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
            tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
            PRIMARY KEY (node_id, tag_id)
        );
    """)
    # Migration：為舊資料庫補上新欄位
    for col_def in [
        "ALTER TABLE nodes ADD COLUMN file_size   INTEGER DEFAULT NULL",
        "ALTER TABLE nodes ADD COLUMN modified_at TEXT    DEFAULT NULL",
        "ALTER TABLE nodes ADD COLUMN category    TEXT    DEFAULT NULL",
    ]:
        try:
            conn.execute(col_def)
        except Exception:
            pass  # 欄位已存在

    conn.commit()


# ── Project CRUD ──────────────────────────────────────────────

def create_project(conn: sqlite3.Connection, name: str, root_path: str,
                   description: str = "") -> int:
    now = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO projects (name, root_path, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, root_path, description, now, now),
    )
    conn.commit()
    return cur.lastrowid


def list_projects(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM projects ORDER BY updated_at DESC"
    ).fetchall()


def delete_project(conn: sqlite3.Connection, project_id: int) -> None:
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()


# ── Node CRUD ─────────────────────────────────────────────────

def upsert_node(conn: sqlite3.Connection, project_id: int,
                parent_id: Optional[int], name: str, rel_path: str,
                node_type: str, sort_order: int = 0,
                file_size: Optional[int] = None,
                modified_at: Optional[str] = None,
                category: Optional[str] = None) -> int:
    row = conn.execute(
        "SELECT id FROM nodes WHERE project_id=? AND rel_path=?",
        (project_id, rel_path),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE nodes SET file_size=?, modified_at=?, category=? WHERE id=?",
            (file_size, modified_at, category, row["id"]),
        )
        return row["id"]
    cur = conn.execute(
        "INSERT INTO nodes "
        "(project_id, parent_id, name, rel_path, node_type, sort_order,"
        " file_size, modified_at, category) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (project_id, parent_id, name, rel_path, node_type, sort_order,
         file_size, modified_at, category),
    )
    return cur.lastrowid


def get_children(conn: sqlite3.Connection, project_id: int,
                 parent_id: Optional[int]) -> list[sqlite3.Row]:
    if parent_id is None:
        return conn.execute(
            "SELECT * FROM nodes WHERE project_id=? AND parent_id IS NULL "
            "ORDER BY node_type='file', pinned DESC, sort_order, name",
            (project_id,),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM nodes WHERE project_id=? AND parent_id=? "
        "ORDER BY node_type='file', pinned DESC, sort_order, name",
        (project_id, parent_id),
    ).fetchall()


def move_node(conn: sqlite3.Connection, node_id: int,
              new_parent_id: Optional[int], new_sort: int = 0) -> None:
    conn.execute(
        "UPDATE nodes SET parent_id=?, sort_order=? WHERE id=?",
        (new_parent_id, new_sort, node_id),
    )
    conn.commit()


def delete_node(conn: sqlite3.Connection, node_id: int) -> None:
    conn.execute("DELETE FROM nodes WHERE id=?", (node_id,))
    conn.commit()
