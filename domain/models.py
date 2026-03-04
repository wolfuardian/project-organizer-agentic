"""領域實體 — 所有核心資料結構統一為 dataclass。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Project:
    id: int
    name: str
    root_path: str
    description: str = ""
    status: str = "active"
    progress: str = "not_started"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ProjectRoot:
    id: int
    project_id: int
    root_path: str
    role: str = "source"
    label: str = ""
    sort_order: int = 0
    added_at: str = ""


@dataclass
class Node:
    id: int
    project_id: int
    parent_id: Optional[int]
    name: str
    rel_path: str
    node_type: str          # file / folder / virtual
    sort_order: int = 0
    pinned: bool = False
    note: str = ""
    file_size: Optional[int] = None
    modified_at: Optional[str] = None
    category: Optional[str] = None
    root_id: Optional[int] = None
    role: Optional[str] = None


@dataclass
class Tag:
    id: int
    name: str
    color: str = "#888888"
    parent_id: Optional[int] = None


@dataclass
class Todo:
    id: int
    project_id: int
    title: str
    done: bool = False
    priority: int = 0
    due_date: Optional[str] = None
    created_at: str = ""


@dataclass
class ProjectRelation:
    id: int
    source_id: int
    target_id: int
    relation_type: str = "related_to"
    note: str = ""
    source_name: str = ""
    target_name: str = ""


@dataclass
class ExternalTool:
    id: int
    name: str
    exe_path: str
    args_tmpl: str = "{path}"
    icon: str = ""
    enabled: bool = True


@dataclass
class ClassifyRule:
    id: int
    name: str
    pattern: str
    pattern_type: str       # glob / regex
    match_target: str       # name / path
    category: str
    priority: int = 100
    enabled: bool = True


@dataclass
class OperationSession:
    id: int
    project_id: int
    status: str = "active"  # active / finalized / cancelled
    started_at: str = ""
    ended_at: Optional[str] = None
    description: str = ""


@dataclass
class FileOperation:
    id: int
    session_id: int
    op_type: str            # move / delete / copy / merge / rename
    source_path: str
    dest_path: Optional[str] = None
    node_id: Optional[int] = None
    status: str = "pending"  # pending / executed / undone / failed
    error_msg: Optional[str] = None
    executed_at: Optional[str] = None
    sort_order: int = 0


@dataclass
class OperationRecord:
    """檔案操作引擎的執行結果。"""
    op_type: str            # move / delete / copy / merge / rename
    source: str
    dest: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    trash_key: Optional[str] = None


@dataclass
class MergeResult:
    """資料夾合併結果。"""
    moved: list[OperationRecord] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


@dataclass
class ProjectTemplate:
    name: str
    description: str
    category: str
    entries: list[TemplateEntry] = field(default_factory=list)
    id: int = 0
    is_builtin: bool = False
    created_at: str = ""


@dataclass
class TemplateEntry:
    path: str
    is_dir: bool = False
    content: str = ""


@dataclass
class TimelineEntry:
    """時間軸查詢結果。"""
    id: int
    name: str
    root_path: str
    progress: str
    created_at: str
    updated_at: str
    todo_total: int = 0
    todo_done: int = 0


@dataclass
class DuplicateGroup:
    """重複檔案群組。"""
    file_hash: str
    file_size: int
    files: list[dict] = field(default_factory=list)


@dataclass
class RenamePreview:
    """批次重新命名的預覽結果。"""
    original: str
    new_name: str
    abs_path: str
    conflict: bool = False


@dataclass
class GitInfo:
    """Git 狀態資訊。"""
    branch: str
    dirty: bool
    ahead: int
    behind: int
    untracked: int
    has_remote: bool


@dataclass
class Command:
    """虛擬模式指令 — 描述使用者意圖，不含執行細節。"""
    op: str              # "move" | "delete" | "copy" | "rename" | "mkdir"
    source: str
    dest: Optional[str] = None
    timestamp: float = field(default_factory=lambda: __import__("time").time())
