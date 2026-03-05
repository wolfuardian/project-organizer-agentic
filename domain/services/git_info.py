"""Git 狀態工具 — 透過 subprocess 呼叫 git，取得 branch / dirty / ahead-behind."""

import subprocess
from pathlib import Path
from typing import Optional

from domain.models import GitInfo


def _run(args: list[str], cwd: Path) -> tuple[int, str]:
    """執行 git 指令，回傳 (returncode, stdout)。失敗時回傳 (-1, '')。"""
    try:
        result = subprocess.run(
            args, cwd=str(cwd),
            capture_output=True, text=True,
            timeout=5,
        )
        return result.returncode, result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return -1, ""


def get_git_info(root: Path) -> Optional[GitInfo]:
    """
    取得目錄的 Git 狀態。
    若目錄不是 git repo，或 git 指令不存在，回傳 None。
    """
    # 確認是否為 git repo
    rc, _ = _run(["git", "rev-parse", "--git-dir"], root)
    if rc != 0:
        return None

    # 分支名稱
    _, branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)
    if not branch:
        branch = "(unknown)"

    # dirty（有工作區或暫存區的變更）
    _, status_out = _run(["git", "status", "--porcelain"], root)
    lines = [l for l in status_out.splitlines() if l.strip()]
    dirty = any(not l.startswith("??") for l in lines)
    untracked = sum(1 for l in lines if l.startswith("??"))

    # ahead / behind（需要 remote tracking branch）
    has_remote = False
    ahead = behind = 0
    _, remote_branch = _run(
        ["git", "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"], root
    )
    if remote_branch and not remote_branch.startswith("fatal"):
        has_remote = True
        _, ab = _run(
            ["git", "rev-list", "--left-right", "--count",
             f"HEAD...{remote_branch}"],
            root,
        )
        if ab and "\t" in ab:
            a, b = ab.split("\t", 1)
            ahead, behind = int(a or 0), int(b or 0)

    return GitInfo(
        branch=branch,
        dirty=dirty,
        ahead=ahead,
        behind=behind,
        untracked=untracked,
        has_remote=has_remote,
    )
