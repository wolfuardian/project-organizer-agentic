"""整理服務 — 規則 CRUD + 重複偵測 + 批次重新命名."""

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Optional

from domain.models import DuplicateGroup, RenamePreview
from domain.services.batch_rename import build_previews, execute_renames


CHUNK = 65536  # 64 KB


class OrganizationService:
    """注入 RuleRepo, NodeRepo。"""

    def __init__(self, rule_repo, node_repo):
        self._rules = rule_repo
        self._nodes = node_repo

    # ── 重複檔案偵測（搬自 duplicate_finder.py）──────────

    @staticmethod
    def _md5(path: Path) -> Optional[str]:
        h = hashlib.md5()
        try:
            with open(path, "rb") as f:
                while chunk := f.read(CHUNK):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    def find_duplicates(
        self,
        conn,
        project_ids: Optional[list[int]] = None,
    ) -> list[DuplicateGroup]:
        rows = self._nodes.get_file_nodes_for_duplicates(project_ids)

        size_groups: dict[tuple, list] = defaultdict(list)
        for row in rows:
            key = (row["file_size"], row["name"])
            size_groups[key].append(row)

        hash_groups: dict[str, list] = defaultdict(list)
        for candidates in size_groups.values():
            if len(candidates) < 2:
                continue
            for row in candidates:
                abs_path = Path(row["root_path"]) / row["rel_path"]
                file_hash = self._md5(abs_path)
                if file_hash is None:
                    continue
                hash_groups[file_hash].append({
                    "node_id":      row["id"],
                    "project_id":   row["project_id"],
                    "project_name": row["project_name"],
                    "rel_path":     row["rel_path"],
                    "abs_path":     str(abs_path),
                    "file_size":    row["file_size"],
                })

        result = []
        for file_hash, files in hash_groups.items():
            if len(files) >= 2:
                result.append(DuplicateGroup(
                    file_hash=file_hash,
                    file_size=files[0]["file_size"],
                    files=files,
                ))

        result.sort(key=lambda g: g.file_size, reverse=True)
        return result

    # ── 批次重新命名轉發 ─────────────────────────────────

    @staticmethod
    def build_previews(files, **kwargs) -> list[RenamePreview]:
        return build_previews(files, **kwargs)

    @staticmethod
    def execute_renames(previews) -> tuple[int, list[str]]:
        return execute_renames(previews)
