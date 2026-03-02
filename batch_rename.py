"""批次重新命名 — 支援樣板、序號、前後綴、regex 替換."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RenamePreview:
    original: str    # 原始檔名
    new_name: str    # 預覽新檔名
    abs_path: str    # 實際路徑（執行時使用）
    conflict: bool = False  # 新名稱是否與同目錄其他檔案衝突


def _apply_template(template: str, stem: str, ext: str, index: int,
                    start: int, step: int) -> str:
    """
    樣板替換，支援以下 placeholder：
      {stem}  原始主檔名（不含副檔名）
      {ext}   副檔名（不含點，例如 txt）
      {n}     序號（從 start 開始，間距 step）
      {n:03}  零填充序號
    """
    n = start + index * step
    mapping = {
        "stem": stem,
        "ext":  ext,
        "n":    n,
    }
    try:
        return template.format_map(_FormatMap(mapping))
    except (KeyError, ValueError):
        return template


class _FormatMap(dict):
    """允許格式化字串中使用 {n:03} 等格式規格."""
    def __missing__(self, key):
        return f"{{{key}}}"


def build_previews(
    files: list[dict],          # 每筆：{abs_path, name}
    template: str = "{stem}{ext}",
    prefix: str = "",
    suffix: str = "",
    regex_find: str = "",
    regex_replace: str = "",
    start: int = 1,
    step: int = 1,
    keep_ext: bool = True,
) -> list[RenamePreview]:
    """
    依設定產生批次重新命名的預覽清單。

    執行順序：regex 替換 → 套用樣板 → 加前後綴
    """
    previews = []

    for i, f in enumerate(files):
        original = f["name"]
        p = Path(original)
        stem = p.stem
        ext = p.suffix  # 含點，例如 .txt

        # Step 1：regex 替換（套用於完整檔名）
        working = original
        if regex_find:
            try:
                working = re.sub(regex_find, regex_replace, working)
            except re.error:
                pass
        p2 = Path(working)
        stem2 = p2.stem
        ext2 = p2.suffix if not keep_ext else ext

        # Step 2：套用樣板
        new_stem = _apply_template(template, stem2, ext2.lstrip("."), i, start, step)

        # Step 3：前後綴
        new_stem = f"{prefix}{new_stem}{suffix}"

        # 組合最終檔名
        if keep_ext and ext:
            new_name = new_stem if new_stem.endswith(ext) else new_stem + ext
        else:
            new_name = new_stem

        previews.append(RenamePreview(
            original=original,
            new_name=new_name,
            abs_path=f["abs_path"],
        ))

    # 標記衝突（新名稱重複）
    seen: dict[str, int] = {}
    for p in previews:
        key = p.new_name.lower()
        seen[key] = seen.get(key, 0) + 1
    for p in previews:
        p.conflict = seen[p.new_name.lower()] > 1 or p.new_name == p.original

    return previews


def execute_renames(previews: list[RenamePreview]) -> tuple[int, list[str]]:
    """
    執行重新命名。回傳 (成功數, 錯誤訊息清單)。
    跳過 conflict=True 或 new_name == original 的項目。
    """
    success = 0
    errors = []
    for item in previews:
        if item.conflict or item.new_name == item.original:
            continue
        src = Path(item.abs_path)
        dst = src.parent / item.new_name
        try:
            src.rename(dst)
            success += 1
        except OSError as e:
            errors.append(f"{item.original} → {item.new_name}：{e}")
    return success, errors
