"""專案模板系統 — 資料結構、內建模板、CRUD、匯出入、反推."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── 資料結構 ─────────────────────────────────────────────────

@dataclass
class TemplateEntry:
    path: str           # 相對路徑，例如 src/main.py
    is_dir: bool = False
    content: str = ""   # 檔案初始內容（目錄忽略此欄）


@dataclass
class ProjectTemplate:
    name: str
    description: str
    category: str
    entries: list[TemplateEntry] = field(default_factory=list)
    id: int = 0             # DB id；0 代表內建（未存入 DB）
    is_builtin: bool = False
    created_at: str = ""
