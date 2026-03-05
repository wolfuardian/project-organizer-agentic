"""Shim — 轉發至 infrastructure 層，保持舊 import 不壞。"""

# ── DDL / connection / migration ──────────────────────────────
from infrastructure.database import (  # noqa: F401
    DB_PATH, get_connection, init_db, _migrate_project_roots,
)

# ── 常數（從 domain.enums 轉發）──────────────────────────────
from domain.enums import (  # noqa: F401
    PROGRESS_STATES, PROGRESS_LABELS,
    RELATION_LABELS, PROJECT_ROOT_ROLES,
)

# ── Repository 轉發函式 ──────────────────────────────────────
# 每個函式保持原始簽名 f(conn, ...) 以相容既有呼叫者。

import sqlite3
from pathlib import Path
from typing import Optional

from infrastructure.repositories.project_repo import SqliteProjectRepository
from infrastructure.repositories.node_repo import SqliteNodeRepository
from infrastructure.repositories.tag_repo import SqliteTagRepository
from infrastructure.repositories.todo_repo import SqliteTodoRepository
from infrastructure.repositories.relation_repo import SqliteRelationRepository
from infrastructure.repositories.tool_repo import SqliteToolRepository
from infrastructure.repositories.session_repo import SqliteSessionRepository


# ── Project ───────────────────────────────────────────────────

def create_project(conn: sqlite3.Connection, name: str, root_path: str = "",
                   description: str = "") -> int:
    return SqliteProjectRepository(conn).create_project(name, root_path, description)

def list_projects(conn: sqlite3.Connection) -> list:
    return SqliteProjectRepository(conn).list_projects()

def delete_project(conn: sqlite3.Connection, project_id: int) -> None:
    SqliteProjectRepository(conn).delete_project(project_id)

def set_project_progress(conn: sqlite3.Connection,
                         project_id: int, progress: str) -> None:
    SqliteProjectRepository(conn).set_project_progress(project_id, progress)

def add_project_root(conn: sqlite3.Connection, project_id: int,
                     root_path: str, role: str = "source",
                     label: str = "") -> int:
    return SqliteProjectRepository(conn).add_project_root(
        project_id, root_path, role, label)

def list_project_roots(conn: sqlite3.Connection,
                       project_id: int) -> list:
    return SqliteProjectRepository(conn).list_project_roots(project_id)

def update_project_root(conn: sqlite3.Connection, root_id: int,
                        role: str, label: str) -> None:
    SqliteProjectRepository(conn).update_project_root(root_id, role, label)

def remove_project_root(conn: sqlite3.Connection, root_id: int) -> None:
    SqliteProjectRepository(conn).remove_project_root(root_id)


# ── Node ──────────────────────────────────────────────────────

def upsert_node(conn: sqlite3.Connection, project_id: int,
                parent_id: Optional[int], name: str, rel_path: str,
                node_type: str, sort_order: int = 0,
                file_size: Optional[int] = None,
                modified_at: Optional[str] = None,
                category: Optional[str] = None,
                root_id: Optional[int] = None) -> int:
    return SqliteNodeRepository(conn).upsert_node(
        project_id, parent_id, name, rel_path, node_type,
        sort_order, file_size, modified_at, category, root_id)

def get_children(conn: sqlite3.Connection, project_id: int,
                 parent_id: Optional[int]) -> list:
    return SqliteNodeRepository(conn).get_children(project_id, parent_id)

def move_node(conn: sqlite3.Connection, node_id: int,
              new_parent_id: Optional[int], new_sort: int = 0) -> None:
    SqliteNodeRepository(conn).move_node(node_id, new_parent_id, new_sort)

def delete_node(conn: sqlite3.Connection, node_id: int) -> None:
    SqliteNodeRepository(conn).delete_node(node_id)

def get_node(conn: sqlite3.Connection, node_id: int):
    return SqliteNodeRepository(conn).get_node(node_id)

def update_node_note(conn: sqlite3.Connection,
                     node_id: int, note: str) -> None:
    SqliteNodeRepository(conn).update_node_note(node_id, note)

def get_node_abs_path(conn: sqlite3.Connection,
                      node_id: int) -> Optional[Path]:
    return SqliteNodeRepository(conn).get_node_abs_path(node_id)

def get_root_for_node(conn: sqlite3.Connection,
                      node_id: int):
    return SqliteNodeRepository(conn).get_root_for_node(node_id)

def search_nodes(conn: sqlite3.Connection, query: str,
                 project_ids: Optional[list[int]] = None,
                 limit: int = 200) -> list:
    return SqliteNodeRepository(conn).search_nodes(query, project_ids, limit)

def filter_nodes(conn: sqlite3.Connection,
                 project_ids=None, categories=None, tag_ids=None,
                 min_size=None, max_size=None,
                 modified_after=None, modified_before=None,
                 node_types=None, limit: int = 500) -> list:
    return SqliteNodeRepository(conn).filter_nodes(
        project_ids, categories, tag_ids, min_size, max_size,
        modified_after, modified_before, node_types, limit)


# ── Tag ───────────────────────────────────────────────────────

def list_tags(conn: sqlite3.Connection,
              parent_id: Optional[int] = None) -> list:
    return SqliteTagRepository(conn).list_tags(parent_id)

def all_tags_flat(conn: sqlite3.Connection) -> list:
    return SqliteTagRepository(conn).all_tags_flat()

def create_tag(conn: sqlite3.Connection, name: str,
               color: str = "#89b4fa",
               parent_id: Optional[int] = None) -> int:
    return SqliteTagRepository(conn).create_tag(name, color, parent_id)

def update_tag(conn: sqlite3.Connection, tag_id: int,
               name: str, color: str) -> None:
    SqliteTagRepository(conn).update_tag(tag_id, name, color)

def delete_tag(conn: sqlite3.Connection, tag_id: int) -> None:
    SqliteTagRepository(conn).delete_tag(tag_id)

def get_node_tags(conn: sqlite3.Connection, node_id: int) -> list:
    return SqliteTagRepository(conn).get_node_tags(node_id)

def get_tags_for_nodes(conn: sqlite3.Connection,
                       node_ids: list[int]) -> dict[int, list]:
    return SqliteTagRepository(conn).get_tags_for_nodes(node_ids)

def add_node_tag(conn: sqlite3.Connection, node_id: int, tag_id: int) -> None:
    SqliteTagRepository(conn).add_node_tag(node_id, tag_id)

def remove_node_tag(conn: sqlite3.Connection,
                    node_id: int, tag_id: int) -> None:
    SqliteTagRepository(conn).remove_node_tag(node_id, tag_id)


# ── Todo ──────────────────────────────────────────────────────

def list_todos(conn: sqlite3.Connection, project_id: int) -> list:
    return SqliteTodoRepository(conn).list_todos(project_id)

def add_todo(conn: sqlite3.Connection, project_id: int,
             title: str, priority: int = 0,
             due_date: Optional[str] = None) -> int:
    return SqliteTodoRepository(conn).add_todo(
        project_id, title, priority, due_date)

def toggle_todo(conn: sqlite3.Connection, todo_id: int) -> None:
    SqliteTodoRepository(conn).toggle_todo(todo_id)

def delete_todo(conn: sqlite3.Connection, todo_id: int) -> None:
    SqliteTodoRepository(conn).delete_todo(todo_id)

def get_timeline(conn: sqlite3.Connection) -> list:
    return SqliteTodoRepository(conn).get_timeline()


# ── Relation ──────────────────────────────────────────────────

def list_relations(conn: sqlite3.Connection, project_id: int) -> list:
    return SqliteRelationRepository(conn).list_relations(project_id)

def add_relation(conn: sqlite3.Connection, source_id: int,
                 target_id: int, relation_type: str,
                 note: str = "") -> None:
    SqliteRelationRepository(conn).add_relation(
        source_id, target_id, relation_type, note)

def delete_relation(conn: sqlite3.Connection, relation_id: int) -> None:
    SqliteRelationRepository(conn).delete_relation(relation_id)


# ── Tool ──────────────────────────────────────────────────────

def list_tools(conn: sqlite3.Connection) -> list:
    return SqliteToolRepository(conn).list_tools()

def list_all_tools(conn: sqlite3.Connection) -> list:
    return SqliteToolRepository(conn).list_all_tools()

def add_tool(conn: sqlite3.Connection, name: str, exe_path: str,
             args_tmpl: str = "{path}", icon: str = "") -> int:
    return SqliteToolRepository(conn).add_tool(name, exe_path, args_tmpl, icon)

def update_tool(conn: sqlite3.Connection, tool_id: int,
                name: str, exe_path: str,
                args_tmpl: str, enabled: int) -> None:
    SqliteToolRepository(conn).update_tool(tool_id, name, exe_path, args_tmpl, enabled)

def delete_tool(conn: sqlite3.Connection, tool_id: int) -> None:
    SqliteToolRepository(conn).delete_tool(tool_id)

def seed_default_tools(conn: sqlite3.Connection) -> None:
    SqliteToolRepository(conn).seed_default_tools()


# ── Session ───────────────────────────────────────────────────

def create_session(conn: sqlite3.Connection, project_id: int,
                   description: str = "") -> int:
    return SqliteSessionRepository(conn).create_session(project_id, description)

def get_active_session(conn: sqlite3.Connection,
                       project_id: int):
    return SqliteSessionRepository(conn).get_active_session(project_id)

def finalize_session(conn: sqlite3.Connection, session_id: int) -> None:
    SqliteSessionRepository(conn).finalize_session(session_id)

def cancel_session(conn: sqlite3.Connection, session_id: int) -> None:
    SqliteSessionRepository(conn).cancel_session(session_id)

def add_file_operation(conn: sqlite3.Connection, session_id: int,
                       op_type: str, source_path: str,
                       dest_path: Optional[str] = None,
                       node_id: Optional[int] = None) -> int:
    return SqliteSessionRepository(conn).add_file_operation(
        session_id, op_type, source_path, dest_path, node_id)

def update_file_operation_status(conn: sqlite3.Connection,
                                 op_id: int, status: str,
                                 error_msg: Optional[str] = None) -> None:
    SqliteSessionRepository(conn).update_file_operation_status(
        op_id, status, error_msg)

def list_file_operations(conn: sqlite3.Connection,
                         session_id: int) -> list:
    return SqliteSessionRepository(conn).list_file_operations(session_id)
