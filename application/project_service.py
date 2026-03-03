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
        """遞迴掃描目錄，回傳新增/更新的節點數."""
        if _depth > max_depth:
            return 0

        if _project_root is None:
            _project_root = root

        if _rules is None:
            _rules = self._rules.list_rules()

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
                count += self.scan_directory(
                    project_id, entry, node_id,
                    max_depth, _depth + 1, _project_root, _rules,
                    root_id=root_id,
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
