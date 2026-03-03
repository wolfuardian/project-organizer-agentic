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
        _depth: int = 0,
        _project_root: Optional[Path] = None,
        _rules: Optional[list] = None,
        root_id: Optional[int] = None,
    ) -> int:
        """遞迴掃描目錄，回傳新增/更新的節點數.

        最佳化：先收集所有 entries，再按層級批次 upsert，
        整體包在一個 transaction 裡以減少 I/O 開銷。
        """
        # 只有最外層呼叫做初始化 + transaction 包裹
        is_top_level = (_depth == 0)

        if _project_root is None:
            _project_root = root

        if _rules is None:
            _rules = self._rules.list_rules()

        if is_top_level:
            # 頂層：收集全部 entries，按層級批次寫入
            levels: list[list[dict]] = []
            self._collect_entries(
                root, _project_root, _rules, max_depth, 0,
                parent_id, levels, root_id,
            )
            if not levels:
                return 0

            count = 0
            path_to_id: dict[str, int] = {}
            conn = self._nodes._conn
            conn.execute("BEGIN")
            try:
                for level_entries in levels:
                    # 將 parent_rel_path 解析為實際的 parent_id
                    for entry in level_entries:
                        prp = entry.pop("_parent_rel_path", None)
                        if prp is not None:
                            entry["parent_id"] = path_to_id.get(prp)
                        # else: parent_id 已設定（根層級）

                    id_map = self._nodes.bulk_upsert_nodes(
                        project_id, level_entries, root_id,
                    )
                    path_to_id.update(id_map)
                    count += len(level_entries)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            return count
        else:
            # 遞迴呼叫（相容舊的呼叫慣例，不應實際走到這裡）
            return self._scan_directory_legacy(
                project_id, root, parent_id, max_depth,
                _depth, _project_root, _rules, root_id,
            )

    def _collect_entries(
        self,
        directory: Path,
        project_root: Path,
        rules: list,
        max_depth: int,
        depth: int,
        parent_id: Optional[int],
        levels: list[list[dict]],
        root_id: Optional[int],
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

        # 確保此層級的 list 存在
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
                    node_data["_parent_rel_path"] = parent_rel_path
                levels[depth].append(node_data)

                # 遞迴進入子目錄
                self._collect_entries(
                    entry, project_root, rules, max_depth,
                    depth + 1, None, levels, root_id,
                    parent_rel_path=rel,
                )

            elif entry.is_file():
                try:
                    st = entry.stat()
                    file_size = st.st_size
                    modified_at = datetime.fromtimestamp(
                        st.st_mtime).isoformat()
                except OSError:
                    file_size = None
                    modified_at = None
                category = (apply_rules(rules, entry.name, rel)
                            or classify_file(entry.name))
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
                    node_data["_parent_rel_path"] = parent_rel_path
                levels[depth].append(node_data)

    def _scan_directory_legacy(
        self,
        project_id: int,
        root: Path,
        parent_id: Optional[int],
        max_depth: int,
        _depth: int,
        _project_root: Path,
        _rules: list,
        root_id: Optional[int],
    ) -> int:
        """舊版逐筆 upsert 邏輯，作為非頂層遞迴呼叫的 fallback。"""
        if _depth > max_depth:
            return 0

        count = 0
        try:
            entries = sorted(root.iterdir(),
                             key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return 0

        for entry in entries:
            if entry.name in IGNORE_FILES:
                continue

            rel = str(entry.relative_to(_project_root))

            if entry.is_dir():
                if entry.name in IGNORE_DIRS:
                    continue
                node_id = self._nodes.upsert_node(
                    project_id, parent_id,
                    entry.name, rel, "folder",
                    root_id=root_id,
                )
                count += 1
                count += self._scan_directory_legacy(
                    project_id, entry, node_id,
                    max_depth, _depth + 1, _project_root, _rules,
                    root_id,
                )
            elif entry.is_file():
                try:
                    st = entry.stat()
                    file_size = st.st_size
                    modified_at = datetime.fromtimestamp(
                        st.st_mtime).isoformat()
                except OSError:
                    file_size = None
                    modified_at = None
                category = (apply_rules(_rules, entry.name, rel)
                            or classify_file(entry.name))
                self._nodes.upsert_node(
                    project_id, parent_id,
                    entry.name, rel, "file",
                    file_size=file_size,
                    modified_at=modified_at,
                    category=category,
                    root_id=root_id,
                )
                count += 1

        return count
