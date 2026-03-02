"""檔案系統掃描器 — 將實際目錄結構同步到資料庫."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from classifier import classify_file
from database import upsert_node

# 預設忽略的目錄 / 檔案 patterns
IGNORE_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", "node_modules",
    ".vs", ".idea", "Library", "Temp", "Logs", "obj", "bin",
    ".venv", "venv", "env", ".uv-venvs",
}

IGNORE_FILES = {
    ".DS_Store", "Thumbs.db", "desktop.ini",
}


def scan_directory(
    conn: sqlite3.Connection,
    project_id: int,
    root: Path,
    parent_id: Optional[int] = None,
    max_depth: int = 10,
    _depth: int = 0,
    _project_root: Optional[Path] = None,
) -> int:
    """遞迴掃描目錄，回傳新增/更新的節點數."""
    if _depth > max_depth:
        return 0

    if _project_root is None:
        _project_root = root

    count = 0
    try:
        entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return 0

    for entry in entries:
        if entry.name in IGNORE_FILES:
            continue

        rel = str(entry.relative_to(_project_root))

        if entry.is_dir():
            if entry.name in IGNORE_DIRS:
                continue
            node_id = upsert_node(
                conn, project_id, parent_id,
                entry.name, rel, "folder",
            )
            count += 1
            count += scan_directory(
                conn, project_id, entry, node_id,
                max_depth, _depth + 1, _project_root,
            )
        elif entry.is_file():
            try:
                st = entry.stat()
                file_size = st.st_size
                modified_at = datetime.fromtimestamp(st.st_mtime).isoformat()
            except OSError:
                file_size = None
                modified_at = None
            upsert_node(
                conn, project_id, parent_id,
                entry.name, rel, "file",
                file_size=file_size,
                modified_at=modified_at,
                category=classify_file(entry.name),
            )
            count += 1

    return count
