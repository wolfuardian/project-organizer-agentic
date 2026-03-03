"""Shim — 轉發至新路徑，保持舊 import 不壞。"""

import sqlite3
from typing import Optional

from domain.models import DuplicateGroup  # noqa: F401
from application.organization_service import OrganizationService
from infrastructure.repositories.rule_repo import SqliteRuleRepository
from infrastructure.repositories.node_repo import SqliteNodeRepository


def find_duplicates(
    conn: sqlite3.Connection,
    project_ids: Optional[list[int]] = None,
) -> list[DuplicateGroup]:
    svc = OrganizationService(
        SqliteRuleRepository(conn),
        SqliteNodeRepository(conn),
    )
    return svc.find_duplicates(conn, project_ids)
