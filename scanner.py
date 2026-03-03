"""Shim — 轉發至新路徑，保持舊 import 不壞。"""

import sqlite3
from pathlib import Path
from typing import Optional

from domain.enums import IGNORE_DIRS, IGNORE_FILES  # noqa: F401
from infrastructure.repositories.project_repo import SqliteProjectRepository
from infrastructure.repositories.node_repo import SqliteNodeRepository
from infrastructure.repositories.rule_repo import SqliteRuleRepository
from application.project_service import ProjectService


def scan_directory(
    conn: sqlite3.Connection,
    project_id: int,
    root: Path,
    parent_id: Optional[int] = None,
    max_depth: int = 10,
    _depth: int = 0,
    _project_root: Optional[Path] = None,
    _rules: Optional[list] = None,
    root_id: Optional[int] = None,
) -> int:
    svc = ProjectService(
        SqliteProjectRepository(conn),
        SqliteNodeRepository(conn),
        SqliteRuleRepository(conn),
    )
    return svc.scan_directory(
        project_id, root, parent_id, max_depth,
        _depth, _project_root, _rules, root_id,
    )
