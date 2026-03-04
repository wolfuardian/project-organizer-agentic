"""專案服務 — scanner 掃描邏輯 + project CRUD."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from domain.enums import IGNORE_DIRS, IGNORE_FILES
from domain.services.classification import classify_file, apply_rules


class ProjectService:
    """注入 ProjectRepo, NodeRepo, RuleRepo。"""

    def __init__(self, project_repo, node_repo, rule_repo):
        self._projects = project_repo
        self._nodes = node_repo
        self._rules = rule_repo

    # ── 掃描邏輯（搬自 scanner.py）────────────────────────

    def scan_directory(
        self,
        project_id: int,
        root: Path,
        parent_id: Optional[int] = None,
        max_depth: int = 10,
        root_id: Optional[int] = None,
        on_progress: Optional[object] = None,
    ) -> int:
        """遞迴掃描目錄，回傳新增/更新的節點數.

        先收集所有 entries 到分層列表，再按層級批次 upsert，
        整體包在一個 transaction 裡以減少 I/O 開銷。

        on_progress: 可選 callback(current, total)，寫入階段逐層呼叫。
        """
        rules = self._rules.list_rules()

        # 收集階段：純檔案系統操作，不碰 DB
        levels: list[list[dict]] = []
        parent_map: dict[str, str] = {}  # rel_path → parent_rel_path
        self._collect_entries(
            root, root, rules, max_depth, 0,
            parent_id, levels, parent_map,
        )
        if not levels:
            return 0

        total_items = sum(len(lv) for lv in levels)

        # 寫入階段：一次查 existing map，逐層批次 upsert
        existing_map = self._nodes.get_existing_node_map(
            project_id, root_id,
        )
        count = 0
        path_to_id: dict[str, int] = {}
        self._nodes.begin_transaction()
        try:
            for level_entries in levels:
                for entry in level_entries:
                    prp = parent_map.get(entry["rel_path"])
                    if prp is not None:
                        entry["parent_id"] = path_to_id.get(prp)

                id_map = self._nodes.bulk_upsert_nodes(
                    project_id, level_entries, root_id,
                    existing_map=existing_map,
                )
                path_to_id.update(id_map)
                existing_map.update(id_map)
                count += len(level_entries)
                if on_progress:
                    on_progress(count, total_items)
            self._nodes.commit_transaction()
        except Exception:
            self._nodes.rollback_transaction()
            raise
        return count

    def _collect_entries(
        self,
        directory: Path,
        project_root: Path,
        rules: list,
        max_depth: int,
        depth: int,
        parent_id: Optional[int],
        levels: list[list[dict]],
        parent_map: dict[str, str],
        parent_rel_path: Optional[str] = None,
    ) -> None:
        """遞迴收集目錄內容到分層列表（不做 DB 操作）。"""
        if depth > max_depth:
            return

        try:
            entries = sorted(directory.iterdir(),
                             key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return

        while len(levels) <= depth:
            levels.append([])

        for entry in entries:
            if entry.name in IGNORE_FILES:
                continue

            rel = str(entry.relative_to(project_root))

            if entry.is_dir():
                if entry.name in IGNORE_DIRS:
                    continue
                node_data: dict = {
                    "name": entry.name,
                    "rel_path": rel,
                    "node_type": "folder",
                    "sort_order": 0,
                }
                if depth == 0:
                    node_data["parent_id"] = parent_id
                else:
                    parent_map[rel] = parent_rel_path
                levels[depth].append(node_data)

                self._collect_entries(
                    entry, project_root, rules, max_depth,
                    depth + 1, None, levels, parent_map,
                    parent_rel_path=rel,
                )

            elif entry.is_file():
                file_size, modified_at, category = self._stat_and_classify(
                    entry, rules, rel,
                )
                node_data = {
                    "name": entry.name,
                    "rel_path": rel,
                    "node_type": "file",
                    "sort_order": 0,
                    "file_size": file_size,
                    "modified_at": modified_at,
                    "category": category,
                }
                if depth == 0:
                    node_data["parent_id"] = parent_id
                else:
                    parent_map[rel] = parent_rel_path
                levels[depth].append(node_data)

    @staticmethod
    def _stat_and_classify(
        entry: Path, rules: list, rel_path: str,
    ) -> tuple:
        """取得檔案 stat 資訊並分類，回傳 (file_size, modified_at, category)。"""
        try:
            st = entry.stat()
            file_size = st.st_size
            modified_at = datetime.fromtimestamp(st.st_mtime).isoformat()
        except OSError:
            file_size = None
            modified_at = None
        category = (apply_rules(rules, entry.name, rel_path)
                    or classify_file(entry.name))
        return file_size, modified_at, category
