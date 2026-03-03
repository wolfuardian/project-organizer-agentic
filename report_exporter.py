"""Shim — 轉發至新路徑，保持舊 import 不壞。"""

import sqlite3

from application.report_service import ReportService
from infrastructure.repositories.project_repo import SqliteProjectRepository
from infrastructure.repositories.node_repo import SqliteNodeRepository
from infrastructure.repositories.tag_repo import SqliteTagRepository
from infrastructure.repositories.todo_repo import SqliteTodoRepository


def _make_svc(conn: sqlite3.Connection) -> ReportService:
    return ReportService(
        SqliteProjectRepository(conn),
        SqliteNodeRepository(conn),
        SqliteTagRepository(conn),
        SqliteTodoRepository(conn),
    )


def export_markdown(conn: sqlite3.Connection, project_id: int) -> str:
    return _make_svc(conn).export_markdown(conn, project_id)


def export_html(conn: sqlite3.Connection, project_id: int) -> str:
    return _make_svc(conn).export_html(conn, project_id)


def save_report(content, path) -> None:
    ReportService.save_report(content, path)
