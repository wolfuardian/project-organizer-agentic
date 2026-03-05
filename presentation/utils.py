"""Presentation 層共用工具函式。"""

from __future__ import annotations

from pathlib import Path


def format_file_size(size: int | None) -> str:
    """將位元組數格式化為人類可讀的大小字串。"""
    if size is None:
        return ""
    if size < 1024:
        return f"{size} B"
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
    return ""


def reveal_in_explorer(path: Path) -> None:
    """在系統檔案管理器中顯示指定路徑。"""
    import subprocess, sys

    if sys.platform == "win32":
        if path.is_dir():
            subprocess.Popen(["explorer", str(path)])
        else:
            subprocess.Popen(["explorer", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        target = str(path.parent if path.is_file() else path)
        subprocess.Popen(["xdg-open", target])
