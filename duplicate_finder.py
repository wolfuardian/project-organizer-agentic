"""重複檔案偵測 — 先以 (大小, 檔名) 快篩，再以 MD5 確認."""

import hashlib
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


CHUNK = 65536  # 64 KB


@dataclass
class DuplicateGroup:
    file_hash: str
    file_size: int
    files: list[dict] = field(default_factory=list)
    # files 的每筆 dict：{node_id, project_id, project_name, rel_path, abs_path}


def _md5(path: Path) -> Optional[str]:
    """計算檔案 MD5；無法讀取時回傳 None."""
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(CHUNK):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def find_duplicates(
    conn: sqlite3.Connection,
    project_ids: Optional[list[int]] = None,
) -> list[DuplicateGroup]:
    """
    在指定專案（或全部專案）中偵測重複檔案。

    回傳包含重複群組的清單，每群組至少有 2 個檔案。
    """
    # 取得所有檔案節點及其專案根路徑
    if project_ids:
        placeholders = ",".join("?" * len(project_ids))
        rows = conn.execute(
            f"""
            SELECT n.id, n.project_id, n.rel_path, n.file_size, n.name,
                   p.root_path, p.name AS project_name
            FROM nodes n
            JOIN projects p ON p.id = n.project_id
            WHERE n.node_type = 'file'
              AND n.project_id IN ({placeholders})
              AND n.file_size IS NOT NULL
            ORDER BY n.file_size, n.name
            """,
            project_ids,
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT n.id, n.project_id, n.rel_path, n.file_size, n.name,
                   p.root_path, p.name AS project_name
            FROM nodes n
            JOIN projects p ON p.id = n.project_id
            WHERE n.node_type = 'file'
              AND n.file_size IS NOT NULL
            ORDER BY n.file_size, n.name
            """
        ).fetchall()

    # 按 (file_size, name) 分群，快速排除不可能重複的檔案
    from collections import defaultdict
    size_groups: dict[tuple, list] = defaultdict(list)
    for row in rows:
        key = (row["file_size"], row["name"])
        size_groups[key].append(row)

    # 只對 size+name 相同的群做雜湊比對
    hash_groups: dict[str, list] = defaultdict(list)
    for candidates in size_groups.values():
        if len(candidates) < 2:
            continue
        for row in candidates:
            abs_path = Path(row["root_path"]) / row["rel_path"]
            file_hash = _md5(abs_path)
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
