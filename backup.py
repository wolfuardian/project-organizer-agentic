"""備份與同步設定工具 — 複製 SQLite 資料庫檔案到指定目錄."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

# 資料庫預設路徑（與 database.py 保持一致）
_DB_PATH = Path.home() / ".project-organizer" / "data.db"


# ── 備份 ──────────────────────────────────────────────────────────


def create_backup(dest_dir: Path, db_path: Path = _DB_PATH) -> Path:
    """
    將 data.db 複製到 dest_dir，
    檔名格式：data_YYYYMMDD_HHMMSS.db
    回傳備份檔案的完整路徑。
    """
    if not db_path.exists():
        raise FileNotFoundError(f"找不到資料庫：{db_path}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = dest_dir / f"data_{ts}.db"
    shutil.copy2(db_path, dest)
    return dest


def list_backups(dest_dir: Path) -> list[Path]:
    """列出備份目錄中的所有 .db 檔，依時間新到舊排序。"""
    if not dest_dir.exists():
        return []
    files = sorted(dest_dir.glob("data_*.db"), reverse=True)
    return list(files)


def restore_backup(backup_path: Path, db_path: Path = _DB_PATH) -> None:
    """
    將備份檔案還原到 db_path。
    還原前先建立一份「還原前備份」（data_before_restore_*.db）。
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"備份檔不存在：{backup_path}")

    # 先備份目前資料庫
    if db_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        pre = db_path.parent / f"data_before_restore_{ts}.db"
        shutil.copy2(db_path, pre)

    shutil.copy2(backup_path, db_path)


def delete_backup(backup_path: Path) -> None:
    """刪除指定備份檔。"""
    if backup_path.exists():
        backup_path.unlink()


def prune_backups(dest_dir: Path, keep: int = 10) -> list[Path]:
    """
    保留最新的 keep 份備份，刪除多餘的舊備份。
    回傳被刪除的檔案清單。
    """
    files = list_backups(dest_dir)
    to_delete = files[keep:]
    for f in to_delete:
        f.unlink(missing_ok=True)
    return to_delete


# ── 設定持久化（存在 SQLite 的 settings 表格）──────────────────────


def _ensure_settings_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS settings "
        "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    conn.commit()


def get_setting(conn: sqlite3.Connection, key: str,
                default: str = "") -> str:
    _ensure_settings_table(conn)
    row = conn.execute(
        "SELECT value FROM settings WHERE key=?", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    _ensure_settings_table(conn)
    conn.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
