"""規則引擎 — 使用者自訂的檔案分類規則（glob / regex）."""

import fnmatch
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ClassifyRule:
    id: int
    name: str           # 規則名稱（顯示用）
    pattern: str        # glob 或 regex 模式
    pattern_type: str   # 'glob' | 'regex'
    match_target: str   # 'name' | 'path'（匹配檔名 or 相對路徑）
    category: str       # 套用的分類
    priority: int       # 數字越小優先度越高
    enabled: int        # 1=啟用, 0=停用


# ── 資料庫 DDL ────────────────────────────────────────────────

def init_rules_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS classify_rules (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            pattern      TEXT NOT NULL,
            pattern_type TEXT NOT NULL DEFAULT 'glob'
                         CHECK(pattern_type IN ('glob','regex')),
            match_target TEXT NOT NULL DEFAULT 'name'
                         CHECK(match_target IN ('name','path')),
            category     TEXT NOT NULL,
            priority     INTEGER DEFAULT 100,
            enabled      INTEGER DEFAULT 1
        )
    """)
    conn.commit()


# ── CRUD ─────────────────────────────────────────────────────

def list_rules(conn: sqlite3.Connection) -> list[ClassifyRule]:
    rows = conn.execute(
        "SELECT * FROM classify_rules ORDER BY priority, id"
    ).fetchall()
    return [ClassifyRule(**dict(r)) for r in rows]


def add_rule(conn: sqlite3.Connection, name: str, pattern: str,
             pattern_type: str = "glob", match_target: str = "name",
             category: str = "other", priority: int = 100) -> int:
    cur = conn.execute(
        "INSERT INTO classify_rules "
        "(name, pattern, pattern_type, match_target, category, priority) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, pattern, pattern_type, match_target, category, priority),
    )
    conn.commit()
    return cur.lastrowid


def update_rule(conn: sqlite3.Connection, rule_id: int, **kwargs) -> None:
    allowed = {"name", "pattern", "pattern_type", "match_target",
               "category", "priority", "enabled"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k}=?" for k in fields)
    conn.execute(
        f"UPDATE classify_rules SET {set_clause} WHERE id=?",
        (*fields.values(), rule_id),
    )
    conn.commit()


def delete_rule(conn: sqlite3.Connection, rule_id: int) -> None:
    conn.execute("DELETE FROM classify_rules WHERE id=?", (rule_id,))
    conn.commit()


# ── 比對邏輯 ─────────────────────────────────────────────────

def _matches(rule: ClassifyRule, filename: str, rel_path: str) -> bool:
    target = filename if rule.match_target == "name" else rel_path
    if rule.pattern_type == "glob":
        return fnmatch.fnmatch(target, rule.pattern)
    else:
        try:
            return bool(re.search(rule.pattern, target))
        except re.error:
            return False


def apply_rules(rules: list[ClassifyRule], filename: str,
                rel_path: str) -> Optional[str]:
    """依優先度比對規則，回傳第一個符合的分類；無符合則回傳 None."""
    for rule in rules:
        if rule.enabled and _matches(rule, filename, rel_path):
            return rule.category
    return None
