"""Shim — 轉發至新路徑，保持舊 import 不壞。"""

import sqlite3
from pathlib import Path

from application.settings_service import SettingsService
from infrastructure.repositories.tool_repo import SqliteToolRepository
from infrastructure.repositories.settings_repo import SqliteSettingsRepository

# ── 靜態方法（不需 conn）────────────────────────────────────

create_backup = SettingsService.create_backup
list_backups = SettingsService.list_backups
restore_backup = SettingsService.restore_backup
delete_backup = SettingsService.delete_backup
prune_backups = SettingsService.prune_backups


# ── 需要 conn 的設定函式 ─────────────────────────────────────

def get_setting(conn: sqlite3.Connection, key: str,
                default: str = "") -> str:
    return SqliteSettingsRepository(conn).get_setting(key, default)


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    SqliteSettingsRepository(conn).set_setting(key, value)
