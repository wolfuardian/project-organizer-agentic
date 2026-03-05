"""Repository Protocol 介面 — 使用 typing.Protocol 實現結構型子型別。

這是後端（infrastructure + application）與前端（presentation）之間的合約。
Domain 層不需要 import infrastructure 層。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from domain.models import (
    Project, ProjectRoot, Node, Tag, Todo,
    ProjectRelation, ExternalTool, ClassifyRule,
    OperationSession, FileOperation, TimelineEntry,
    ProjectTemplate,
)


@runtime_checkable
class ProjectRepository(Protocol):
    """專案與專案根目錄的 CRUD。"""

    def create_project(self, name: str, root_path: str = "",
                       description: str = "") -> int: ...

    def list_projects(self) -> list[Project]: ...

    def get_project(self, project_id: int) -> Optional[Project]: ...

    def delete_project(self, project_id: int) -> None: ...

    def set_project_progress(self, project_id: int,
                             progress: str) -> None: ...

    # ── Project Roots ──

    def add_project_root(self, project_id: int, root_path: str,
                         role: str = "source",
                         label: str = "") -> int: ...

    def list_project_roots(self, project_id: int) -> list[ProjectRoot]: ...

    def update_project_root(self, root_id: int,
                            role: str, label: str) -> None: ...

    def remove_project_root(self, root_id: int) -> None: ...


@runtime_checkable
class NodeRepository(Protocol):
    """節點 CRUD + 路徑解析 + 搜尋 + 過濾。"""

    def upsert_node(self, project_id: int,
                    parent_id: Optional[int], name: str, rel_path: str,
                    node_type: str, sort_order: int = 0,
                    file_size: Optional[int] = None,
                    modified_at: Optional[str] = None,
                    category: Optional[str] = None,
                    root_id: Optional[int] = None) -> int: ...

    def get_existing_node_map(self, project_id: int,
                              root_id: Optional[int] = None,
                              ) -> dict[str, int]: ...

    def bulk_upsert_nodes(self, project_id: int,
                          nodes_data: list[dict],
                          root_id: Optional[int] = None,
                          existing_map: Optional[dict[str, int]] = None,
                          ) -> dict[str, int]: ...

    # ── Transaction 輔助 ──

    def begin_transaction(self) -> None: ...
    def commit_transaction(self) -> None: ...
    def rollback_transaction(self) -> None: ...

    def get_node(self, node_id: int) -> Optional[Node]: ...

    def get_children(self, project_id: int,
                     parent_id: Optional[int]) -> list[Node]: ...

    def get_children_by_root(self, project_id: int,
                             root_id: int) -> list[Node]: ...

    def move_node(self, node_id: int,
                  new_parent_id: Optional[int],
                  new_sort: int = 0) -> None: ...

    def delete_node(self, node_id: int) -> None: ...

    def delete_nodes_by_project(self, project_id: int) -> None: ...

    def update_node_note(self, node_id: int, note: str) -> None: ...

    def get_node_abs_path(self, node_id: int) -> Optional[Path]: ...

    def get_root_for_node(self, node_id: int) -> Optional[ProjectRoot]: ...

    def get_parent_id(self, node_id: int) -> Optional[int]: ...

    def search_nodes(self, query: str,
                     project_ids: Optional[list[int]] = None,
                     limit: int = 200) -> list[Node]: ...

    def filter_nodes(
        self,
        project_ids: Optional[list[int]] = None,
        categories: Optional[list[str]] = None,
        tag_ids: Optional[list[int]] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        modified_after: Optional[str] = None,
        modified_before: Optional[str] = None,
        node_types: Optional[list[str]] = None,
        limit: int = 500,
    ) -> list[Node]: ...

    def get_file_nodes_for_duplicates(
        self,
        project_ids: Optional[list[int]] = None,
    ) -> list[dict]: ...


@runtime_checkable
class TagRepository(Protocol):
    """標籤 CRUD + node_tag 指派。"""

    def list_tags(self, parent_id: Optional[int] = None) -> list[Tag]: ...

    def all_tags_flat(self) -> list[Tag]: ...

    def create_tag(self, name: str, color: str = "#89b4fa",
                   parent_id: Optional[int] = None) -> int: ...

    def update_tag(self, tag_id: int, name: str, color: str) -> None: ...

    def delete_tag(self, tag_id: int) -> None: ...

    def get_node_tags(self, node_id: int) -> list[Tag]: ...

    def add_node_tag(self, node_id: int, tag_id: int) -> None: ...

    def remove_node_tag(self, node_id: int, tag_id: int) -> None: ...


@runtime_checkable
class TodoRepository(Protocol):
    """TODO CRUD + 時間軸。"""

    def list_todos(self, project_id: int) -> list[Todo]: ...

    def add_todo(self, project_id: int, title: str,
                 priority: int = 0,
                 due_date: Optional[str] = None) -> int: ...

    def toggle_todo(self, todo_id: int) -> None: ...

    def delete_todo(self, todo_id: int) -> None: ...

    def get_timeline(self) -> list[TimelineEntry]: ...

    def list_todos_raw(self, project_id: int) -> list[Todo]: ...


@runtime_checkable
class RelationRepository(Protocol):
    """專案關聯 CRUD。"""

    def list_relations(self, project_id: int) -> list[ProjectRelation]: ...

    def add_relation(self, source_id: int, target_id: int,
                     relation_type: str,
                     note: str = "") -> None: ...

    def delete_relation(self, relation_id: int) -> None: ...


@runtime_checkable
class TemplateRepository(Protocol):
    """模板 CRUD。"""

    def init_table(self) -> None: ...

    def save_template(self, tmpl: ProjectTemplate) -> int: ...

    def list_templates(self,
                       include_builtin: bool = True) -> list[ProjectTemplate]: ...

    def delete_template(self, template_id: int) -> None: ...


@runtime_checkable
class ToolRepository(Protocol):
    """外部工具 CRUD。"""

    def list_tools(self) -> list[ExternalTool]: ...

    def list_all_tools(self) -> list[ExternalTool]: ...

    def add_tool(self, name: str, exe_path: str,
                 args_tmpl: str = "{path}",
                 icon: str = "") -> int: ...

    def update_tool(self, tool_id: int, name: str, exe_path: str,
                    args_tmpl: str, enabled: int) -> None: ...

    def delete_tool(self, tool_id: int) -> None: ...

    def seed_default_tools(self) -> None: ...


@runtime_checkable
class RuleRepository(Protocol):
    """分類規則 CRUD。"""

    def init_table(self) -> None: ...

    def list_rules(self) -> list[ClassifyRule]: ...

    def add_rule(self, name: str, pattern: str,
                 pattern_type: str = "glob",
                 match_target: str = "name",
                 category: str = "other",
                 priority: int = 100) -> int: ...

    def update_rule(self, rule_id: int, **kwargs) -> None: ...

    def delete_rule(self, rule_id: int) -> None: ...


@runtime_checkable
class SessionRepository(Protocol):
    """工作階段 + 檔案操作 CRUD。"""

    def create_session(self, project_id: int,
                       description: str = "") -> int: ...

    def get_active_session(self,
                           project_id: int) -> Optional[OperationSession]: ...

    def finalize_session(self, session_id: int) -> None: ...

    def cancel_session(self, session_id: int) -> None: ...

    def add_file_operation(self, session_id: int, op_type: str,
                           source_path: str,
                           dest_path: Optional[str] = None,
                           node_id: Optional[int] = None) -> int: ...

    def update_file_operation_status(self, op_id: int, status: str,
                                     error_msg: Optional[str] = None) -> None: ...

    def list_file_operations(self,
                             session_id: int) -> list[FileOperation]: ...


@runtime_checkable
class SettingsRepository(Protocol):
    """設定 key-value store。"""

    def get_setting(self, key: str, default: str = "") -> str: ...

    def set_setting(self, key: str, value: str) -> None: ...
