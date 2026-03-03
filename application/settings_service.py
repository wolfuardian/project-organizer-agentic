"""設定服務 — 工具 CRUD + backup 邏輯。搬自 backup.py。"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

_DB_PATH = Path.home() / ".project-organizer" / "data.db"


class SettingsService:
    """注入 ToolRepo, SettingsRepo。"""

    def __init__(self, tool_repo, settings_repo):
        self._tools = tool_repo
        self._settings = settings_repo

    # ── Settings ──────────────────────────────────────────

    def get_setting(self, key: str, default: str = "") -> str:
        return self._settings.get_setting(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings.set_setting(key, value)

    # ── Backup（搬自 backup.py）──────────────────────────

    @staticmethod
    def create_backup(dest_dir: Path,
                      db_path: Path = _DB_PATH) -> Path:
        if not db_path.exists():
            raise FileNotFoundError(f"找不到資料庫：{db_path}")
        dest_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = dest_dir / f"data_{ts}.db"
        shutil.copy2(db_path, dest)
        return dest

    @staticmethod
    def list_backups(dest_dir: Path) -> list[Path]:
        if not dest_dir.exists():
            return []
        return sorted(dest_dir.glob("data_*.db"), reverse=True)

    @staticmethod
    def restore_backup(backup_path: Path,
                       db_path: Path = _DB_PATH) -> None:
        if not backup_path.exists():
            raise FileNotFoundError(f"備份檔不存在：{backup_path}")
        if db_path.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            pre = db_path.parent / f"data_before_restore_{ts}.db"
            shutil.copy2(db_path, pre)
        shutil.copy2(backup_path, db_path)

    @staticmethod
    def delete_backup(backup_path: Path) -> None:
        if backup_path.exists():
            backup_path.unlink()

    @staticmethod
    def prune_backups(dest_dir: Path, keep: int = 10) -> list[Path]:
        files = SettingsService.list_backups(dest_dir)
        to_delete = files[keep:]
        for f in to_delete:
            f.unlink(missing_ok=True)
        return to_delete
