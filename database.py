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
        "ALTER TABLE nodes    ADD COLUMN file_size   INTEGER DEFAULT NULL",
        "ALTER TABLE nodes    ADD COLUMN modified_at TEXT    DEFAULT NULL",
        "ALTER TABLE nodes    ADD COLUMN category    TEXT    DEFAULT NULL",
        "ALTER TABLE projects ADD COLUMN progress    TEXT    DEFAULT 'not_started'",
        "ALTER TABLE tags     ADD COLUMN parent_id   INTEGER DEFAULT NULL",
    ]:
        try:
            conn.execute(col_def)
        except Exception:
            pass  # 欄位已存在

    conn.commit()

    # 初始化 project_relations 資料表
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS project_relations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id     INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            target_id     INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            relation_type TEXT NOT NULL DEFAULT 'related_to'
                          CHECK(relation_type IN ('depends_on','related_to','references')),
            note          TEXT DEFAULT '',
            UNIQUE(source_id, target_id, relation_type)
        );
        CREATE INDEX IF NOT EXISTS idx_relations_source ON project_relations(source_id);
        CREATE INDEX IF NOT EXISTS idx_relations_target ON project_relations(target_id);
    """)

    # 初始化 todos 資料表
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS todos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title       TEXT NOT NULL,
            done        INTEGER DEFAULT 0,
            priority    INTEGER DEFAULT 0,
            due_date    TEXT DEFAULT NULL,
            created_at  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_todos_project ON todos(project_id);
    """)

    # 初始化規則引擎資料表（避免循環 import，延遲引入）
    from rule_engine import init_rules_table
    init_rules_table(conn)

    # 初始化模板資料表
    from templates import init_templates_table
    init_templates_table(conn)


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


# 進度狀態常數與輔助
PROGRESS_STATES = ["not_started", "in_progress", "paused", "completed"]

PROGRESS_LABELS = {
    "not_started": "⬜ 未開始",
    "in_progress": "🔵 進行中",
    "paused":      "🟡 暫停",
    "completed":   "✅ 已完成",
}


def set_project_progress(conn: sqlite3.Connection,
                         project_id: int, progress: str) -> None:
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE projects SET progress=?, updated_at=? WHERE id=?",
        (progress, now, project_id),
    )
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


# ── Todo CRUD ─────────────────────────────────────────────────

def list_todos(conn: sqlite3.Connection,
               project_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM todos WHERE project_id=? "
        "ORDER BY done, priority DESC, created_at",
        (project_id,),
    ).fetchall()


def add_todo(conn: sqlite3.Connection, project_id: int,
             title: str, priority: int = 0,
             due_date: Optional[str] = None) -> int:
    now = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO todos (project_id, title, priority, due_date, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (project_id, title, priority, due_date, now),
    )
    conn.commit()
    return cur.lastrowid


def toggle_todo(conn: sqlite3.Connection, todo_id: int) -> None:
    conn.execute(
        "UPDATE todos SET done = 1 - done WHERE id=?", (todo_id,)
    )
    conn.commit()


def delete_todo(conn: sqlite3.Connection, todo_id: int) -> None:
    conn.execute("DELETE FROM todos WHERE id=?", (todo_id,))
    conn.commit()


# ── Tag CRUD ──────────────────────────────────────────────────

def list_tags(conn: sqlite3.Connection,
              parent_id: Optional[int] = None) -> list[sqlite3.Row]:
    """回傳頂層標籤（parent_id IS NULL）或指定父標籤的子標籤。"""
    if parent_id is None:
        return conn.execute(
            "SELECT * FROM tags WHERE parent_id IS NULL ORDER BY name"
        ).fetchall()
    return conn.execute(
        "SELECT * FROM tags WHERE parent_id=? ORDER BY name", (parent_id,)
    ).fetchall()


def all_tags_flat(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM tags ORDER BY name").fetchall()


def create_tag(conn: sqlite3.Connection, name: str,
               color: str = "#89b4fa",
               parent_id: Optional[int] = None) -> int:
    cur = conn.execute(
        "INSERT INTO tags (name, color, parent_id) VALUES (?, ?, ?)",
        (name, color, parent_id),
    )
    conn.commit()
    return cur.lastrowid


def update_tag(conn: sqlite3.Connection, tag_id: int,
               name: str, color: str) -> None:
    conn.execute(
        "UPDATE tags SET name=?, color=? WHERE id=?", (name, color, tag_id)
    )
    conn.commit()


def delete_tag(conn: sqlite3.Connection, tag_id: int) -> None:
    conn.execute("DELETE FROM tags WHERE id=?", (tag_id,))
    conn.commit()


def get_node_tags(conn: sqlite3.Connection,
                  node_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT t.* FROM tags t "
        "JOIN node_tags nt ON nt.tag_id = t.id "
        "WHERE nt.node_id=? ORDER BY t.name",
        (node_id,),
    ).fetchall()


def add_node_tag(conn: sqlite3.Connection,
                 node_id: int, tag_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO node_tags (node_id, tag_id) VALUES (?, ?)",
        (node_id, tag_id),
    )
    conn.commit()


def remove_node_tag(conn: sqlite3.Connection,
                    node_id: int, tag_id: int) -> None:
    conn.execute(
        "DELETE FROM node_tags WHERE node_id=? AND tag_id=?",
        (node_id, tag_id),
    )
    conn.commit()


def update_node_note(conn: sqlite3.Connection,
                     node_id: int, note: str) -> None:
    conn.execute("UPDATE nodes SET note=? WHERE id=?", (note, node_id))
    conn.commit()


def get_node(conn: sqlite3.Connection, node_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM nodes WHERE id=?", (node_id,)
    ).fetchone()


# ── Project Relations CRUD ────────────────────────────────────

RELATION_LABELS = {
    "depends_on":  "⬅ 依賴",
    "related_to":  "↔ 相關",
    "references":  "→ 參考",
}


def list_relations(conn: sqlite3.Connection,
                   project_id: int) -> list[sqlite3.Row]:
    """回傳以 project_id 為來源或目標的所有關聯，附帶對方專案名稱。"""
    return conn.execute("""
        SELECT r.*,
               ps.name AS source_name,
               pt.name AS target_name
        FROM project_relations r
        JOIN projects ps ON ps.id = r.source_id
        JOIN projects pt ON pt.id = r.target_id
        WHERE r.source_id=? OR r.target_id=?
        ORDER BY r.relation_type, ps.name
    """, (project_id, project_id)).fetchall()


def add_relation(conn: sqlite3.Connection, source_id: int,
                 target_id: int, relation_type: str,
                 note: str = "") -> None:
    conn.execute(
        "INSERT OR IGNORE INTO project_relations "
        "(source_id, target_id, relation_type, note) VALUES (?, ?, ?, ?)",
        (source_id, target_id, relation_type, note),
    )
    conn.commit()


def delete_relation(conn: sqlite3.Connection, relation_id: int) -> None:
    conn.execute("DELETE FROM project_relations WHERE id=?", (relation_id,))
    conn.commit()


# ── Search ────────────────────────────────────────────────────

def search_nodes(conn: sqlite3.Connection, query: str,
                 project_ids: Optional[list[int]] = None,
                 limit: int = 200) -> list[sqlite3.Row]:
    """
    搜尋節點：比對檔名、備註、標籤名稱（OR 關係）。
    回傳每列附帶 project_name、root_path。
    """
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
    return conn.execute(base, params).fetchall()


# ── Timeline ──────────────────────────────────────────────────

def get_timeline(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """回傳所有專案依 created_at 排序，附帶 todo 完成統計。"""
    return conn.execute("""
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
