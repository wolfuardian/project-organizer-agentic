"""Shim — 轉發至新路徑，保持舊 import 不壞。

CRUD 函式轉發至 infrastructure/repositories/rule_repo.py。
比對邏輯轉發至 domain/services/classification.py。
"""

import sqlite3

from domain.models import ClassifyRule  # noqa: F401
from domain.services.classification import _matches, apply_rules  # noqa: F401
from infrastructure.repositories.rule_repo import SqliteRuleRepository


def init_rules_table(conn: sqlite3.Connection) -> None:
    SqliteRuleRepository(conn).init_table()

def list_rules(conn: sqlite3.Connection) -> list[ClassifyRule]:
    return SqliteRuleRepository(conn).list_rules()

def add_rule(conn: sqlite3.Connection, name: str, pattern: str,
             pattern_type: str = "glob", match_target: str = "name",
             category: str = "other", priority: int = 100) -> int:
    return SqliteRuleRepository(conn).add_rule(
        name, pattern, pattern_type, match_target, category, priority)

def update_rule(conn: sqlite3.Connection, rule_id: int, **kwargs) -> None:
    SqliteRuleRepository(conn).update_rule(rule_id, **kwargs)

def delete_rule(conn: sqlite3.Connection, rule_id: int) -> None:
    SqliteRuleRepository(conn).delete_rule(rule_id)
