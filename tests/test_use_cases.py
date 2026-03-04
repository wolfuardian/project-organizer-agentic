"""Phase 8 Use Case 驗證 — 證明多根目錄 + 檔案操作引擎 + 工作階段管理能達成整理專案的目的."""

import shutil
import sqlite3
import tempfile
from pathlib import Path

from database import (
    get_connection, init_db, create_project,
    add_project_root, list_project_roots, update_project_root,
    remove_project_root, get_node_abs_path, upsert_node,
    list_file_operations, get_active_session, PROJECT_ROOT_ROLES,
)
from scanner import scan_directory
from session_manager import SessionManager
from file_ops import (
    move_file, delete_to_trash, copy_file, merge_folder,
    undo_operation, clean_trash, TRASH_DIR,
)


# ── 測試用基礎設施 ────────────────────────────────────────

class TestEnv:
    """建立隔離的測試環境：獨立 DB + 暫存目錄。"""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="po_test_"))
        self.db_path = self.tmp / "test.db"
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        init_db(self.conn)

    def cleanup(self):
        self.conn.close()
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def make_tree(self, base_name: str, structure: dict) -> Path:
        """建立目錄樹。structure: {name: None(file) | str(content) | dict(子目錄)}"""
        base = self.tmp / base_name
        base.mkdir(parents=True, exist_ok=True)
        self._fill(base, structure)
        return base

    def _fill(self, parent: Path, structure: dict):
        for name, content in structure.items():
            p = parent / name
            if isinstance(content, dict):
                p.mkdir(exist_ok=True)
                self._fill(p, content)
            else:
                p.write_text(content or "", encoding="utf-8")


def _pass(name: str):
    print(f"  PASS:{name}")


def _section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ══════════════════════════════════════════════════════════════
# Use Case 1：一個遊戲專案散落在三個資料夾，要統一管理
# ══════════════════════════════════════════════════════════════

def test_multi_root_game_project():
    _section("UC1：多根目錄 — 遊戲專案散落三處")
    env = TestEnv()

    # 情境：程式碼在 D:\dev\mygame，美術資源在 E:\assets\mygame，文件在雲端同步資料夾
    code_dir = env.make_tree("dev_mygame", {
        "src": {"main.py": "print('game')", "engine.py": "class Engine: pass"},
        "tests": {"test_main.py": "assert True"},
    })
    assets_dir = env.make_tree("assets_mygame", {
        "sprites": {"hero.png": "PNG", "enemy.png": "PNG"},
        "audio": {"bgm.ogg": "OGG", "sfx_hit.wav": "WAV"},
    })
    docs_dir = env.make_tree("docs_mygame", {
        "GDD.md": "# Game Design Document",
        "changelog.md": "## v0.1",
    })

    # Step 1：建立專案，主根為程式碼目錄
    pid = create_project(env.conn, "MyGame", str(code_dir))
    root1 = add_project_root(env.conn, pid, str(code_dir), "proj", "程式碼")
    scan_directory(env.conn, pid, code_dir, root_id=root1)
    env.conn.commit()

    roots = list_project_roots(env.conn, pid)
    assert len(roots) == 1
    _pass("建立專案 + 主根目錄")

    # Step 2：新增第二個根（美術資源）
    root2 = add_project_root(env.conn, pid, str(assets_dir), "assets", "美術")
    scan_directory(env.conn, pid, assets_dir, root_id=root2)
    env.conn.commit()

    roots = list_project_roots(env.conn, pid)
    assert len(roots) == 2
    assert roots[1]["role"] == "assets"
    _pass("新增 assets 根目錄 + 掃描")

    # Step 3：新增第三個根（文件）
    root3 = add_project_root(env.conn, pid, str(docs_dir), "docs", "文件")
    scan_directory(env.conn, pid, docs_dir, root_id=root3)
    env.conn.commit()

    roots = list_project_roots(env.conn, pid)
    assert len(roots) == 3
    _pass("新增 docs 根目錄 + 掃描")

    # Step 4：驗證三個根下的節點都能解析絕對路徑
    # 找到 hero.png
    row = env.conn.execute(
        "SELECT id FROM nodes WHERE project_id=? AND name='hero.png'", (pid,)
    ).fetchone()
    abs_path = get_node_abs_path(env.conn, row["id"])
    assert abs_path is not None
    assert abs_path == assets_dir / "sprites" / "hero.png"
    _pass("get_node_abs_path() 跨根解析正確")

    # Step 5：修改角色 + 標籤
    update_project_root(env.conn, root2, "assets", "2D 美術")
    r = env.conn.execute(
        "SELECT label FROM project_roots WHERE id=?", (root2,)
    ).fetchone()
    assert r["label"] == "2D 美術"
    _pass("修改根目錄角色/標籤")

    # Step 6：移除一個根，節點要隨之刪除
    nodes_before = env.conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE root_id=?", (root3,)
    ).fetchone()[0]
    assert nodes_before > 0
    remove_project_root(env.conn, root3)
    nodes_after = env.conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE root_id=?", (root3,)
    ).fetchone()[0]
    assert nodes_after == 0
    roots = list_project_roots(env.conn, pid)
    assert len(roots) == 2
    _pass("移除根目錄 → 節點連動刪除")

    env.cleanup()


# ══════════════════════════════════════════════════════════════
# Use Case 2：整理下載資料夾 — 分類散亂檔案
# ══════════════════════════════════════════════════════════════

def test_organize_downloads():
    _section("UC2：工作階段 — 整理下載資料夾（移動 + 刪除 + 復原）")
    env = TestEnv()

    # 情境：下載資料夾堆了一堆東西，要整理到分類目錄
    downloads = env.make_tree("Downloads", {
        "report_final.pdf": "PDF content",
        "report_final_v2.pdf": "PDF content v2",
        "photo_001.jpg": "JPEG",
        "photo_002.jpg": "JPEG",
        "installer.exe": "MZ...",
        "notes.txt": "some notes",
        "old_backup.zip": "PK...",
    })
    organized = env.make_tree("Organized", {
        "documents": {},
        "images": {},
        "archives": {},
    })

    pid = create_project(env.conn, "整理下載", str(downloads))
    root_dl = add_project_root(env.conn, pid, str(downloads), "source", "下載區")
    root_org = add_project_root(env.conn, pid, str(organized), "output", "已整理")
    scan_directory(env.conn, pid, downloads, root_id=root_dl)
    env.conn.commit()

    # Step 1：開始工作階段
    sm = SessionManager(env.conn, pid)
    sid = sm.start("整理 2026-03 下載")
    assert sm.active
    _pass("工作階段啟動")

    # Step 2：移動 PDF 到 documents
    rec = sm.execute_move(
        str(downloads / "report_final.pdf"),
        str(organized / "documents" / "report_final.pdf"),
    )
    assert rec.success
    assert not (downloads / "report_final.pdf").exists()
    assert (organized / "documents" / "report_final.pdf").exists()
    _pass("移動 report_final.pdf → documents/")

    # Step 3：移動照片到 images
    rec = sm.execute_move(
        str(downloads / "photo_001.jpg"),
        str(organized / "images" / "photo_001.jpg"),
    )
    assert rec.success
    rec = sm.execute_move(
        str(downloads / "photo_002.jpg"),
        str(organized / "images" / "photo_002.jpg"),
    )
    assert rec.success
    _pass("移動 2 張照片 → images/")

    # Step 4：刪除不需要的安裝程式
    rec = sm.execute_delete(str(downloads / "installer.exe"))
    assert rec.success
    assert not (downloads / "installer.exe").exists()
    _pass("刪除 installer.exe → 回收桶")

    # Step 5：移動壓縮檔
    rec = sm.execute_move(
        str(downloads / "old_backup.zip"),
        str(organized / "archives" / "old_backup.zip"),
    )
    assert rec.success
    _pass("移動 old_backup.zip → archives/")

    # 驗證操作歷史
    history = sm.get_history()
    assert len(history) == 5
    executed = [op for op in history if op["status"] == "executed"]
    assert len(executed) == 5
    _pass(f"操作歷史記錄 {len(executed)} 筆")

    # Step 6：等等，搞錯了！installer.exe 其實還要用 → 復原刪除
    ok = sm.undo_last()  # 復原最後一筆（move old_backup.zip）
    assert ok
    ok = sm.undo_last()  # 復原 delete installer.exe
    assert ok
    assert (downloads / "installer.exe").exists()
    _pass("復原 2 步 → installer.exe 從回收桶恢復")

    # Step 7：重新刪除 backup，保留 installer
    rec = sm.execute_move(
        str(downloads / "old_backup.zip"),
        str(organized / "archives" / "old_backup.zip"),
    )
    assert rec.success
    _pass("重新移動 old_backup.zip（修正後的操作）")

    # Step 8：確認完成
    sm.finalize(do_clean_trash=True)
    assert not sm.active
    _pass("工作階段確認完成 + 清空回收桶")

    # 最終驗證
    assert (organized / "documents" / "report_final.pdf").exists()
    assert (organized / "images" / "photo_001.jpg").exists()
    assert (organized / "images" / "photo_002.jpg").exists()
    assert (organized / "archives" / "old_backup.zip").exists()
    assert (downloads / "installer.exe").exists()   # 保留了
    assert (downloads / "notes.txt").exists()        # 沒動
    assert (downloads / "report_final_v2.pdf").exists()  # 沒動
    _pass("最終檔案配置正確")

    env.cleanup()


# ══════════════════════════════════════════════════════════════
# Use Case 3：合併兩個版本的資源資料夾
# ══════════════════════════════════════════════════════════════

def test_merge_folders():
    _section("UC3：資料夾合併 — 兩個版本的資源合而為一")
    env = TestEnv()

    # 情境：old_assets 和 new_assets 有部分重疊，要合併到 final
    old = env.make_tree("old_assets", {
        "logo.png": "old logo",
        "banner.png": "old banner",
        "readme.txt": "old readme",
    })
    new = env.make_tree("new_assets", {
        "logo.png": "NEW logo",         # 衝突！
        "icon.png": "new icon",
        "splash.png": "new splash",
    })
    final = env.make_tree("final_assets", {})

    pid = create_project(env.conn, "資源合併", str(old))
    add_project_root(env.conn, pid, str(old), "source", "舊版")
    add_project_root(env.conn, pid, str(new), "source", "新版")

    sm = SessionManager(env.conn, pid)
    sm.start("合併資源")

    # Step 1：先把 old 合併到 final
    result = sm.execute_merge(str(old), str(final))
    moved_count = sum(1 for r in result.moved if r.success)
    assert moved_count == 3  # logo, banner, readme
    assert len(result.skipped) == 0
    _pass(f"old → final：移動 {moved_count} 個，衝突 {len(result.skipped)} 個")

    # Step 2：再把 new 合併到 final（logo.png 會衝突）
    result = sm.execute_merge(str(new), str(final))
    moved_count = sum(1 for r in result.moved if r.success)
    assert moved_count == 2  # icon, splash（logo 衝突略過）
    assert "logo.png" in result.skipped
    _pass(f"new → final：移動 {moved_count} 個，衝突 {len(result.skipped)} 個（logo.png）")

    # 驗證 final 的內容
    assert (final / "logo.png").read_text() == "old logo"  # 保留舊的
    assert (final / "banner.png").exists()
    assert (final / "readme.txt").exists()
    assert (final / "icon.png").exists()
    assert (final / "splash.png").exists()
    _pass("合併結果正確：衝突保留先到的版本")

    sm.finalize()
    env.cleanup()


# ══════════════════════════════════════════════════════════════
# Use Case 4：操作失敗不會破壞狀態
# ══════════════════════════════════════════════════════════════

def test_error_handling():
    _section("UC4：錯誤處理 — 操作失敗時安全降級")
    env = TestEnv()

    src_dir = env.make_tree("src", {"a.txt": "hello"})
    pid = create_project(env.conn, "錯誤測試", str(src_dir))
    add_project_root(env.conn, pid, str(src_dir), "proj")

    sm = SessionManager(env.conn, pid)
    sm.start("測試錯誤")

    # 移動不存在的檔案
    rec = sm.execute_move(
        str(src_dir / "nonexistent.txt"),
        str(src_dir / "dest.txt"),
    )
    assert not rec.success
    assert "不存在" in rec.error
    _pass("移動不存在的檔案 → 失敗但不崩潰")

    # 移動到已存在的目標
    (src_dir / "dest.txt").write_text("occupied")
    rec = sm.execute_move(
        str(src_dir / "a.txt"),
        str(src_dir / "dest.txt"),
    )
    assert not rec.success
    assert "已存在" in rec.error
    assert (src_dir / "a.txt").exists()  # 來源沒被動到
    _pass("目標已存在 → 來源不受影響")

    # 刪除不存在的檔案
    rec = sm.execute_delete(str(src_dir / "ghost.txt"))
    assert not rec.success
    _pass("刪除不存在的檔案 → 失敗但不崩潰")

    # 成功操作仍正常
    rec = sm.execute_move(
        str(src_dir / "a.txt"),
        str(src_dir / "moved_a.txt"),
    )
    assert rec.success
    _pass("之後的正常操作不受先前錯誤影響")

    # 歷史中失敗的記為 failed
    history = sm.get_history()
    failed = [op for op in history if op["status"] == "failed"]
    executed = [op for op in history if op["status"] == "executed"]
    assert len(failed) == 3
    assert len(executed) == 1
    _pass(f"歷史紀錄：{len(failed)} 失敗 + {len(executed)} 成功")

    sm.cancel()
    env.cleanup()


# ══════════════════════════════════════════════════════════════
# Use Case 5：取消工作階段 — 全部復原，彷彿沒做過
# ══════════════════════════════════════════════════════════════

def test_cancel_restores_everything():
    _section("UC5：取消工作階段 — 所有操作全部復原")
    env = TestEnv()

    base = env.make_tree("workspace", {
        "a.txt": "AAA",
        "b.txt": "BBB",
        "c.txt": "CCC",
        "sub": {"d.txt": "DDD"},
    })
    dest = env.make_tree("target", {})

    pid = create_project(env.conn, "復原測試", str(base))
    add_project_root(env.conn, pid, str(base), "proj")

    sm = SessionManager(env.conn, pid)
    sm.start("嘗試整理")

    # 執行一連串操作
    sm.execute_move(str(base / "a.txt"), str(dest / "a.txt"))
    sm.execute_move(str(base / "b.txt"), str(dest / "b.txt"))
    sm.execute_delete(str(base / "c.txt"))
    sm.execute_copy(str(base / "sub" / "d.txt"), str(dest / "d_copy.txt"))

    # 此時 base 裡只剩 sub/d.txt
    assert not (base / "a.txt").exists()
    assert not (base / "b.txt").exists()
    assert not (base / "c.txt").exists()
    assert (dest / "a.txt").exists()
    assert (dest / "b.txt").exists()
    assert (dest / "d_copy.txt").exists()
    _pass("4 項操作全部執行成功")

    # 取消！全部復原
    count = sm.cancel()
    assert count == 4
    _pass(f"cancel() 復原了 {count} 項操作")

    # 驗證一切回到原狀
    assert (base / "a.txt").exists()
    assert (base / "a.txt").read_text() == "AAA"
    assert (base / "b.txt").exists()
    assert (base / "b.txt").read_text() == "BBB"
    assert (base / "c.txt").exists()
    assert (base / "c.txt").read_text() == "CCC"
    assert (base / "sub" / "d.txt").exists()
    # dest 裡的複本已被清除
    assert not (dest / "a.txt").exists()
    assert not (dest / "b.txt").exists()
    assert not (dest / "d_copy.txt").exists()
    _pass("所有檔案回到原始狀態")

    assert not sm.active
    _pass("session 狀態為 cancelled")

    env.cleanup()


# ══════════════════════════════════════════════════════════════
# Use Case 6：undo_to — 復原到特定步驟
# ══════════════════════════════════════════════════════════════

def test_undo_to_specific_step():
    _section("UC6：undo_to — 保留前兩步，復原後三步")
    env = TestEnv()

    base = env.make_tree("files", {
        "1.txt": "one",
        "2.txt": "two",
        "3.txt": "three",
        "4.txt": "four",
        "5.txt": "five",
    })
    dest = env.make_tree("moved", {})

    pid = create_project(env.conn, "undo_to 測試", str(base))
    add_project_root(env.conn, pid, str(base), "proj")

    sm = SessionManager(env.conn, pid)
    sm.start("逐步復原")

    # 5 筆移動操作
    sm.execute_move(str(base / "1.txt"), str(dest / "1.txt"))  # op 1
    sm.execute_move(str(base / "2.txt"), str(dest / "2.txt"))  # op 2
    sm.execute_move(str(base / "3.txt"), str(dest / "3.txt"))  # op 3
    sm.execute_move(str(base / "4.txt"), str(dest / "4.txt"))  # op 4
    sm.execute_move(str(base / "5.txt"), str(dest / "5.txt"))  # op 5

    history = sm.get_history()
    assert len(history) == 5
    _pass("5 筆操作完成")

    # 復原到第 3 筆（含）→ 應復原 op3, op4, op5
    op3_id = history[2]["id"]
    count = sm.undo_to(op3_id)
    assert count == 3
    _pass(f"undo_to(op3) 復原了 {count} 筆")

    # 前兩筆保留（1.txt 和 2.txt 還在 dest），後三筆恢復
    assert (dest / "1.txt").exists()     # 保留
    assert (dest / "2.txt").exists()     # 保留
    assert (base / "3.txt").exists()     # 已復原
    assert (base / "4.txt").exists()     # 已復原
    assert (base / "5.txt").exists()     # 已復原
    assert not (dest / "3.txt").exists()
    assert not (dest / "4.txt").exists()
    assert not (dest / "5.txt").exists()
    _pass("前 2 筆保留，後 3 筆正確復原")

    sm.finalize()
    env.cleanup()


# ══════════════════════════════════════════════════════════════
# Use Case 7：dry_run 預覽不會動到任何檔案
# ══════════════════════════════════════════════════════════════

def test_dry_run_safety():
    _section("UC7：dry_run 預覽 — 確保只看不動")
    env = TestEnv()

    base = env.make_tree("preview_test", {
        "important.doc": "DO NOT TOUCH",
        "sub": {"data.csv": "1,2,3"},
    })

    pid = create_project(env.conn, "dry_run 測試", str(base))
    add_project_root(env.conn, pid, str(base), "proj")

    sm = SessionManager(env.conn, pid)
    sm.start("預覽測試")

    # dry_run move
    rec = sm.execute_move(
        str(base / "important.doc"), "/tmp/somewhere/important.doc",
        dry_run=True,
    )
    assert rec.success
    assert (base / "important.doc").exists()
    _pass("dry_run move：檔案未被移動")

    # dry_run delete
    rec = sm.execute_delete(str(base / "sub" / "data.csv"), dry_run=True)
    assert rec.success
    assert (base / "sub" / "data.csv").exists()
    _pass("dry_run delete：檔案未被刪除")

    # dry_run copy
    rec = sm.execute_copy(
        str(base / "important.doc"),
        str(base / "important_copy.doc"),
        dry_run=True,
    )
    assert rec.success
    assert not (base / "important_copy.doc").exists()
    _pass("dry_run copy：複本未被建立")

    # dry_run 不會留下操作歷史
    history = sm.get_history()
    assert len(history) == 0
    _pass("dry_run 不產生操作紀錄")

    sm.cancel()
    env.cleanup()


# ══════════════════════════════════════════════════════════════
# Use Case 8：DB 遷移 — 舊專案升級後一切正常
# ══════════════════════════════════════════════════════════════

def test_migration_backward_compat():
    _section("UC8：向後相容 — 舊專案（無 root_id）遷移後正常運作")
    env = TestEnv()

    base = env.make_tree("legacy", {"old.txt": "old data"})

    # 模擬舊版行為：直接寫 project 和 node，不設 root_id
    now = "2025-01-01T00:00:00"
    env.conn.execute(
        "INSERT INTO projects (name, root_path, description, created_at, updated_at) "
        "VALUES (?, ?, '', ?, ?)",
        ("舊專案", str(base), now, now),
    )
    pid = env.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    env.conn.execute(
        "INSERT INTO nodes (project_id, parent_id, name, rel_path, node_type, sort_order) "
        "VALUES (?, NULL, 'old.txt', 'old.txt', 'file', 0)",
        (pid,),
    )
    env.conn.commit()

    # 確認此時 node 沒有 root_id
    node = env.conn.execute(
        "SELECT root_id FROM nodes WHERE project_id=?", (pid,)
    ).fetchone()
    assert node["root_id"] is None
    _pass("舊節點 root_id 為 NULL（模擬舊版資料）")

    # 執行遷移（重新 init_db）
    from database import _migrate_project_roots
    _migrate_project_roots(env.conn)

    # 驗證已自動建立 project_root
    roots = list_project_roots(env.conn, pid)
    assert len(roots) == 1
    assert roots[0]["role"] == "proj"
    assert roots[0]["root_path"] == str(base)
    _pass("遷移自動建立 project_root（role=proj）")

    # 驗證 node 的 root_id 已回填
    node = env.conn.execute(
        "SELECT root_id FROM nodes WHERE project_id=?", (pid,)
    ).fetchone()
    assert node["root_id"] == roots[0]["id"]
    _pass("舊節點 root_id 已回填")

    # 路徑解析正常
    nid = env.conn.execute(
        "SELECT id FROM nodes WHERE project_id=? AND name='old.txt'", (pid,)
    ).fetchone()["id"]
    abs_path = get_node_abs_path(env.conn, nid)
    assert abs_path == base / "old.txt"
    _pass("get_node_abs_path() 在遷移後的舊節點上正確運作")

    env.cleanup()


# ══════════════════════════════════════════════════════════════
# 執行所有 Use Cases
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  Phase 8 Use Case 驗證")
    print("=" * 60)

    tests = [
        test_multi_root_game_project,
        test_organize_downloads,
        test_merge_folders,
        test_error_handling,
        test_cancel_restores_everything,
        test_undo_to_specific_step,
        test_dry_run_safety,
        test_migration_backward_compat,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"\n  FAIL:{test_fn.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"  結果：{passed} 通過 / {failed} 失敗 / 共 {passed + failed} 個情境")
    print(f"{'=' * 60}")

    exit(1 if failed else 0)
