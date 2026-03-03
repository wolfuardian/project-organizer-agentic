"""檔案操作引擎 — move / delete / copy / merge，全部可復原."""

import shutil
import uuid
from pathlib import Path
from typing import Optional

from domain.models import OperationRecord, MergeResult


TRASH_DIR = Path.home() / ".project-organizer" / "trash"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


# ── Move ─────────────────────────────────────────────────────

def move_file(source: str | Path, dest: str | Path,
              dry_run: bool = False) -> OperationRecord:
    """移動檔案或資料夾。"""
    src, dst = Path(source), Path(dest)
    rec = OperationRecord(op_type="move", source=str(src), dest=str(dst))

    if not src.exists():
        rec.success = False
        rec.error = f"來源不存在：{src}"
        return rec

    if dst.exists():
        rec.success = False
        rec.error = f"目標已存在：{dst}"
        return rec

    if dry_run:
        return rec

    try:
        _ensure_parent(dst)
        shutil.move(str(src), str(dst))
    except Exception as e:
        rec.success = False
        rec.error = str(e)
    return rec


# ── Delete (to trash) ────────────────────────────────────────

def delete_to_trash(target: str | Path,
                    dry_run: bool = False) -> OperationRecord:
    """刪除到應用程式回收桶（非系統回收桶）。"""
    tgt = Path(target)
    trash_key = uuid.uuid4().hex[:12]
    rec = OperationRecord(
        op_type="delete", source=str(tgt),
        dest=str(TRASH_DIR / trash_key), trash_key=trash_key,
    )

    if not tgt.exists():
        rec.success = False
        rec.error = f"目標不存在：{tgt}"
        return rec

    if dry_run:
        return rec

    try:
        trash_dest = TRASH_DIR / trash_key
        trash_dest.mkdir(parents=True, exist_ok=True)
        # 保留原始檔名
        shutil.move(str(tgt), str(trash_dest / tgt.name))
    except Exception as e:
        rec.success = False
        rec.error = str(e)
    return rec


# ── Copy ─────────────────────────────────────────────────────

def copy_file(source: str | Path, dest: str | Path,
              dry_run: bool = False) -> OperationRecord:
    """複製檔案或資料夾。"""
    src, dst = Path(source), Path(dest)
    rec = OperationRecord(op_type="copy", source=str(src), dest=str(dst))

    if not src.exists():
        rec.success = False
        rec.error = f"來源不存在：{src}"
        return rec

    if dst.exists():
        rec.success = False
        rec.error = f"目標已存在：{dst}"
        return rec

    if dry_run:
        return rec

    try:
        _ensure_parent(dst)
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
    except Exception as e:
        rec.success = False
        rec.error = str(e)
    return rec


# ── Merge folder ─────────────────────────────────────────────

def merge_folder(source: str | Path, dest: str | Path,
                 dry_run: bool = False) -> MergeResult:
    """合併資料夾：將 source 的內容移入 dest，衝突檔略過。"""
    src, dst = Path(source), Path(dest)
    result = MergeResult()

    if not src.is_dir():
        result.skipped.append(f"來源不是資料夾：{src}")
        return result

    dst.mkdir(parents=True, exist_ok=True)

    for item in src.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(src)
        target = dst / rel

        if target.exists():
            result.skipped.append(str(rel))
            continue

        rec = move_file(item, target, dry_run=dry_run)
        result.moved.append(rec)

    # 移完後如果 source 已空，乾掉
    if not dry_run:
        try:
            _remove_empty_dirs(src)
        except Exception:
            pass

    return result


def _remove_empty_dirs(path: Path) -> None:
    """遞迴移除空資料夾。"""
    if not path.is_dir():
        return
    for child in path.iterdir():
        if child.is_dir():
            _remove_empty_dirs(child)
    if not any(path.iterdir()):
        path.rmdir()


# ── Undo ─────────────────────────────────────────────────────

def undo_operation(rec_type: str, source: str,
                   dest: Optional[str] = None,
                   trash_key: Optional[str] = None) -> bool:
    """反向操作：move 反向、delete 從 trash 復原、copy 刪複本。"""
    try:
        if rec_type == "move" and dest:
            # 把 dest 移回 source
            d, s = Path(dest), Path(source)
            if d.exists():
                _ensure_parent(s)
                shutil.move(str(d), str(s))
                return True

        elif rec_type == "delete" and trash_key:
            # 從回收桶復原
            trash_dest = TRASH_DIR / trash_key
            src = Path(source)
            if trash_dest.exists():
                # 回收桶裡只有一個檔案/資料夾
                items = list(trash_dest.iterdir())
                if items:
                    _ensure_parent(src)
                    shutil.move(str(items[0]), str(src))
                # 清掉 trash_key 目錄
                shutil.rmtree(str(trash_dest), ignore_errors=True)
                return True

        elif rec_type == "copy" and dest:
            # 刪除複本
            d = Path(dest)
            if d.exists():
                if d.is_dir():
                    shutil.rmtree(str(d))
                else:
                    d.unlink()
                return True

    except Exception:
        return False

    return False


def clean_trash() -> int:
    """清空回收桶，回傳清除的項目數。"""
    if not TRASH_DIR.exists():
        return 0
    count = 0
    for item in TRASH_DIR.iterdir():
        if item.is_dir():
            shutil.rmtree(str(item), ignore_errors=True)
            count += 1
    return count
