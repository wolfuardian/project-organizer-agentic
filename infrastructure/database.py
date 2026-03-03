"""SQLite 資料庫初始化 — DDL 與 Migration."""

import sqlite3
from pathlib import Path
from datetime import datetime


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
        CREATE INDEX IF NOT EXISTS idx_nodes_parent_composite
            ON nodes(project_id, parent_id, node_type, pinned, sort_order, name);

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

    # 初始化外部工具資料表
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS external_tools (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL,
            exe_path  TEXT NOT NULL,
            args_tmpl TEXT DEFAULT '{path}',
            icon      TEXT DEFAULT '',
            enabled   INTEGER DEFAULT 1
        );
    """)

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

    from infrastructure.repositories.tool_repo import SqliteToolRepository
    SqliteToolRepository(conn).seed_default_tools()

    # 初始化規則引擎資料表
    from infrastructure.repositories.rule_repo import SqliteRuleRepository
    SqliteRuleRepository(conn).init_table()

    # 初始化模板資料表
    from infrastructure.repositories.template_repo import SqliteTemplateRepository
    SqliteTemplateRepository(conn).init_table()

    # ── Phase 8a：多根目錄 ─────────────────────────────────
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS project_roots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            root_path   TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'source',
            label       TEXT DEFAULT '',
            sort_order  INTEGER DEFAULT 0,
            added_at    TEXT NOT NULL,
            UNIQUE(project_id, root_path)
        );
        CREATE INDEX IF NOT EXISTS idx_project_roots_project
            ON project_roots(project_id);
    """)
    # nodes 新增 root_id / role 欄位
    for col_def in [
        "ALTER TABLE nodes ADD COLUMN root_id INTEGER DEFAULT NULL "
        "REFERENCES project_roots(id) ON DELETE CASCADE",
        "ALTER TABLE nodes ADD COLUMN role TEXT DEFAULT NULL",
    ]:
        try:
            conn.execute(col_def)
        except Exception:
            pass

    # root_id 欄位就緒後才能建立包含 root_id 的索引
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_nodes_upsert "
        "ON nodes(project_id, rel_path, root_id)"
    )

    # 遷移：把每個 project 的 root_path 自動建立為 role='proj' 的 root，回填 nodes.root_id
    _migrate_project_roots(conn)

    # ── Phase 8b：操作歷史 ─────────────────────────────────
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS operation_sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            status      TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active','finalized','cancelled')),
            started_at  TEXT NOT NULL,
            ended_at    TEXT DEFAULT NULL,
            description TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS file_operations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER NOT NULL REFERENCES operation_sessions(id) ON DELETE CASCADE,
            op_type     TEXT NOT NULL CHECK(op_type IN ('move','delete','copy','merge','rename')),
            source_path TEXT NOT NULL,
            dest_path   TEXT DEFAULT NULL,
            node_id     INTEGER DEFAULT NULL,
            status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','executed','undone','failed')),
            error_msg   TEXT DEFAULT NULL,
            executed_at TEXT DEFAULT NULL,
            sort_order  INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_file_ops_session
            ON file_operations(session_id);
    """)
    conn.commit()


def _migrate_project_roots(conn: sqlite3.Connection) -> None:
    """將舊的 projects.root_path 遷移為 project_roots 記錄，並回填 nodes.root_id。"""
    projects = conn.execute(
        "SELECT id, root_path FROM projects WHERE root_path IS NOT NULL"
    ).fetchall()
    now = datetime.now().isoformat()
    for proj in projects:
        # 若已有 root 記錄則跳過
        existing = conn.execute(
            "SELECT id FROM project_roots WHERE project_id=? AND root_path=?",
            (proj["id"], proj["root_path"]),
        ).fetchone()
        if existing:
            root_id = existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO project_roots "
                "(project_id, root_path, role, label, sort_order, added_at) "
                "VALUES (?, ?, 'proj', '', 0, ?)",
                (proj["id"], proj["root_path"], now),
            )
            root_id = cur.lastrowid
        # 回填該專案下所有 root_id IS NULL 的節點
        conn.execute(
            "UPDATE nodes SET root_id=? WHERE project_id=? AND root_id IS NULL "
            "AND node_type != 'virtual'",
            (root_id, proj["id"]),
        )
    conn.commit()
