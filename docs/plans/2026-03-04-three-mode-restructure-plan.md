# Three-Mode Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure the project organizer from a feature-packed project management tool into a focused file organizer with Preview/Virtual/Live three-mode architecture.

**Architecture:** Incremental refactoring — strip UI bloat first, then rebuild mode system with CommandQueue (virtual) and LiveHistory (live), add dual panels, and finally flat-list search. Domain and infrastructure layers stay untouched; presentation layer is progressively replaced.

**Tech Stack:** Python 3.12+, PySide6, SQLite, unittest

**Test runner:** `python3 -m unittest discover tests -v`

**Design doc:** `docs/plans/2026-03-04-three-mode-restructure-design.md`

---

## Phase 1: Strip UI Bloat

Remove unused components, dialogs, and menu items. After this phase the app runs with a drastically simplified UI.

### Task 1.1: Remove TodoPanel from MainWindow

**Files:**
- Modify: `presentation/main_window.py:80,163-164` (remove import and instantiation)
- Modify: `presentation/main_window.py:129-240` (remove from _build_ui layout)

**Step 1: Remove TodoPanel import**

In `presentation/main_window.py`, remove the TodoPanel import (line 80) and all references. The import line is:
```python
from presentation.widgets.todo_panel import TodoPanel
```

**Step 2: Remove TodoPanel instantiation and layout placement**

In `_build_ui()`, find and remove the TodoPanel creation (~line 163-164) and its addition to the left panel layout. Search for `self._todo_panel` or `TodoPanel` in the file and remove all references.

**Step 3: Run app to verify it launches**

```
python3 main.py
```

Verify: App launches without errors, left panel shows only project list (no TODO section).

**Step 4: Commit**

```
git add presentation/main_window.py
git commit -m "refactor: remove TodoPanel from main window"
```

---

### Task 1.2: Strip Tools Menu Items

**Files:**
- Modify: `presentation/main_window.py:318-361` (Tools menu section in _build_menu_bar)

**Step 1: Identify all Tools menu items to remove**

Remove from the Tools menu:
- Classification Rules (RulesDialog)
- Duplicate Files (DuplicateDialog)
- Batch Rename (BatchRenameDialog)
- Tag Manager (TagManagerDialog)
- Manage Templates (TemplateManagerDialog)
- Extract Template (ExtractTemplateDialog)
- External Tools (ExternalToolsDialog)
- Export Report (ExportReportDialog)
- Backup & Restore (BackupDialog)

Keep:
- Theme (ThemeDialog)

**Step 2: Replace Tools menu with simplified version**

In `_build_menu_bar()`, replace the entire Tools menu section (~lines 318-361) with just the Theme item. The menu label can stay as "工具 (&T)" or rename to "設定" — keep it minimal.

**Step 3: Remove associated action handler methods**

Search `main_window.py` for methods that open the removed dialogs and remove them. These are typically named like `_open_rules_dialog`, `_open_duplicate_dialog`, etc.

**Step 4: Remove now-unused dialog imports**

Remove imports for: `RulesDialog`, `DuplicateDialog`, `BatchRenameDialog`, `TagManagerDialog`, `TemplateManagerDialog`, `TemplatePickerDialog`, `ExtractTemplateDialog`, `ExternalToolsDialog`, `ExportReportDialog`, `BackupDialog`, `ToolEditDialog`.

Keep imports for: `ThemeDialog`, `ProjectRootsDialog`, `OperationHistoryDialog` (temporarily — will be reworked later), `SearchDialog`, `FilterDialog`, `QuickJumpDialog`.

**Step 5: Run app to verify**

```
python3 main.py
```

Verify: Tools menu only shows Theme.

**Step 6: Commit**

```
git add presentation/main_window.py
git commit -m "refactor: strip Tools menu to Theme only"
```

---

### Task 1.3: Strip View Menu Items

**Files:**
- Modify: `presentation/main_window.py:394-434` (View menu in _build_menu_bar)

**Step 1: Remove these View menu items**

Remove:
- Global Search (Ctrl+F) — will be replaced by inline flat-list search
- Advanced Filter (Ctrl+Shift+F) — removing
- Quick Jump (Ctrl+P) — will be replaced by inline flat-list search
- Timeline — removing

Keep:
- Refresh (F5)
- Metadata Panel (F3)
- Collapse All
- Expand All

**Step 2: Remove associated handler methods and dialog opening code**

Remove methods that open SearchDialog, FilterDialog, QuickJumpDialog, TimelineDialog.

**Step 3: Remove dialog imports**

Remove imports for: `SearchDialog`, `FilterDialog`, `QuickJumpDialog`, `ProjectRelationsDialog`, `TimelineDialog`.

**Step 4: Run app to verify**

```
python3 main.py
```

**Step 5: Commit**

```
git add presentation/main_window.py
git commit -m "refactor: strip View menu — remove search/filter/timeline dialogs"
```

---

### Task 1.4: Strip Session Menu and Git Status

**Files:**
- Modify: `presentation/main_window.py:364-392` (Session menu)
- Modify: `presentation/main_window.py:568-579` (Git status)
- Modify: `presentation/main_window.py:712-783` (Session methods)
- Modify: `presentation/main_window.py:232-239` (Session indicator in status bar)

**Step 1: Remove the entire Session menu**

Remove the session menu block (~lines 364-392) from `_build_menu_bar()`. This includes start session, history, undo last, finalize, cancel.

**Step 2: Remove session indicator from status bar**

In `_build_ui()`, remove the session indicator label (~lines 232-239).

**Step 3: Remove session handler methods**

Remove: `_start_session()`, `_undo_last_op()`, `_finalize_session()`, `_cancel_session()`, `_open_history_dialog()`, `_update_session_ui()`, and the session file operation methods (`_session_move`, `_session_delete`, `_session_copy`, `_session_merge`, `_confirm_preview`, `_handle_op_result`).

**Step 4: Remove SessionManager import and instantiation**

Find `SessionManager` (or `session_service`) import and `self._session` creation, remove them.

**Step 5: Remove Git status code**

Find and remove Git status refresh code (~lines 568-579) and any Git-related status bar updates.

**Step 6: Run app to verify**

```
python3 main.py
```

Verify: No Session menu, no session indicator, no git status in status bar.

**Step 7: Commit**

```
git add presentation/main_window.py
git commit -m "refactor: remove Session menu, session indicator, and Git status"
```

---

### Task 1.5: Strip Project Status/Progress/Badge from Project List

**Files:**
- Modify: `presentation/main_window.py` (project list item rendering)

**Step 1: Simplify project list items**

Find where project list items are created/rendered. Currently they show name + status badge + progress. Change to show only project name and path. Remove progress/status badge rendering.

**Step 2: Remove project status context menu items**

In the project list right-click menu, remove options for: Progress, Relations. Keep only: Roots management (simplified), Remove project.

**Step 3: Run app to verify**

```
python3 main.py
```

**Step 4: Commit**

```
git add presentation/main_window.py
git commit -m "refactor: simplify project list to name + path only"
```

---

### Task 1.6: Strip Right-Click Context Menu

**Files:**
- Modify: `presentation/main_window.py:831-918` (_show_context_menu)

**Step 1: Replace context menu with minimal version**

Replace the entire `_show_context_menu()` method. For now (before mode system rework), provide a minimal menu:

```python
def _show_context_menu(self, pos):
    idx = self._tree_view.indexAt(pos)
    node = self._node_from_index(idx)
    if node is None:
        return

    menu = QMenu(self)

    if node.node_type == "file":
        act_open = menu.addAction("以系統預設開啟")
        act_open.triggered.connect(lambda: self._open_system(node))

    act_reveal = menu.addAction("在檔案管理器中顯示")
    act_reveal.triggered.connect(lambda: self._reveal_in_explorer(node))

    menu.exec(self._tree_view.viewport().mapToGlobal(pos))
```

This removes: tag submenu, session file operations, virtual folder creation, delete tree node. These will be re-added properly in Phase 3-4 via ModeController.

**Step 2: Remove now-orphaned helper methods**

Remove tag-related context menu methods, virtual folder creation methods.

**Step 3: Verify _open_system and _reveal_in_explorer still work**

If these methods don't exist, implement them simply using `os.startfile` (Windows) or `subprocess.Popen(["xdg-open", ...])` (Linux).

**Step 4: Run app to verify**

```
python3 main.py
```

Right-click on a file should only show "以系統預設開啟" and "在檔案管理器中顯示".

**Step 5: Commit**

```
git add presentation/main_window.py
git commit -m "refactor: minimal right-click context menu"
```

---

### Task 1.7: Remove File Menu bloat

**Files:**
- Modify: `presentation/main_window.py:294-316` (File menu in _build_menu_bar)

**Step 1: Simplify File menu**

Keep:
- New project path (Ctrl+N) — renamed action if needed
- Manage project roots
- Quit (Ctrl+Q)

Remove:
- Open New Window (Ctrl+Shift+W) — multi-window feature
- New from Template (Ctrl+Shift+N) — template system

**Step 2: Run and commit**

```
python3 main.py
git add presentation/main_window.py
git commit -m "refactor: simplify File menu"
```

---

### Task 1.8: Verify and clean up dead code

**Step 1: Search for remaining references to removed components**

Search `main_window.py` for any remaining references to: `todo`, `template`, `tag`, `relation`, `timeline`, `duplicate`, `batch_rename`, `rules`, `backup`, `export_report`, `external_tool`, `git_info`, `session` (old session system), `progress` (project progress), `badge`.

**Step 2: Remove any remaining dead code**

**Step 3: Run app and full test suite**

```
python3 main.py
python3 -m unittest discover tests -v
```

**Step 4: Commit**

```
git add -A
git commit -m "refactor: Phase 1 complete — dead code cleanup"
```

---

## Phase 2: Tree Columns + Project Selector Slimdown

### Task 2.1: Add file_size and modified_at formatting helpers

**Files:**
- Modify: `presentation/tree_model.py` (add helper functions)
- Create: `tests/test_tree_columns.py`

**Step 1: Write test**

Create `tests/test_tree_columns.py`:

```python
"""Tests for tree column display: size and relative time."""
import unittest
from datetime import datetime, timedelta


class TestRelativeTime(unittest.TestCase):

    def test_just_now(self):
        from presentation.tree_model import format_relative_time
        now = datetime.now().isoformat()
        self.assertEqual(format_relative_time(now), "剛剛")

    def test_minutes_ago(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(minutes=5)).isoformat()
        self.assertEqual(format_relative_time(t), "5 分鐘前")

    def test_hours_ago(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(hours=3)).isoformat()
        self.assertEqual(format_relative_time(t), "3 小時前")

    def test_yesterday(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(days=1)).isoformat()
        self.assertEqual(format_relative_time(t), "昨天")

    def test_days_ago(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(days=5)).isoformat()
        self.assertEqual(format_relative_time(t), "5 天前")

    def test_weeks_ago(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(weeks=3)).isoformat()
        self.assertEqual(format_relative_time(t), "3 週前")

    def test_months_ago(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(days=90)).isoformat()
        self.assertEqual(format_relative_time(t), "3 個月前")

    def test_year_ago(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(days=400)).isoformat()
        self.assertEqual(format_relative_time(t), "1 年前")

    def test_none_input(self):
        from presentation.tree_model import format_relative_time
        self.assertEqual(format_relative_time(None), "")


class TestFormatSize(unittest.TestCase):

    def test_bytes(self):
        from presentation.tree_model import format_file_size
        self.assertEqual(format_file_size(512), "512 B")

    def test_kilobytes(self):
        from presentation.tree_model import format_file_size
        self.assertEqual(format_file_size(4300), "4.2 KB")

    def test_megabytes(self):
        from presentation.tree_model import format_file_size
        self.assertEqual(format_file_size(356_000_000), "339.5 MB")

    def test_gigabytes(self):
        from presentation.tree_model import format_file_size
        self.assertEqual(format_file_size(2_500_000_000), "2.3 GB")

    def test_zero(self):
        from presentation.tree_model import format_file_size
        self.assertEqual(format_file_size(0), "0 B")

    def test_none(self):
        from presentation.tree_model import format_file_size
        self.assertEqual(format_file_size(None), "")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests — expect fail**

```
python3 -m unittest tests/test_tree_columns.py -v
```

Expected: ImportError — `format_relative_time` and `format_file_size` not found.

**Step 3: Implement helpers**

In `presentation/tree_model.py`, add `format_relative_time(iso_str)` and `format_file_size(size)` functions. See design doc for format specifications.

**Step 4: Run tests — expect pass**

```
python3 -m unittest tests/test_tree_columns.py -v
```

**Step 5: Commit**

```
git add presentation/tree_model.py tests/test_tree_columns.py
git commit -m "feat: format_relative_time and format_file_size helpers with tests"
```

---

### Task 2.2: TreeModel 3 columns

**Files:**
- Modify: `presentation/tree_model.py:219-283` (columnCount, data, headerData)
- Modify: `presentation/main_window.py` (enable header, set column widths)

**Step 1: Change columnCount to return 3**

**Step 2: Add headerData method returning ("名稱", "大小", "修改時間")**

**Step 3: Update data() for Qt.DisplayRole**

- Column 0: node name (existing)
- Column 1: `format_file_size(node.file_size)` — files only, empty for folders
- Column 2: `format_relative_time(node.modified_at)`

**Step 4: Add Qt.TextAlignmentRole for columns 1 and 2 (right-aligned)**

**Step 5: Only apply DecorationRole/ForegroundRole/FontRole to column 0**

**Step 6: Ensure TreeNode gets file_size and modified_at during scan**

Check if scan populates these. If not, add `os.stat()` calls during node loading.

**Step 7: Enable header in MainWindow**

Change `setHeaderHidden(True)` to `setHeaderHidden(False)`. Configure column resize modes:
- Column 0: Stretch
- Column 1: ResizeToContents
- Column 2: ResizeToContents

**Step 8: Run app to verify 3 columns display correctly**

```
python3 main.py
```

**Step 9: Commit**

```
git add presentation/tree_model.py presentation/main_window.py
git commit -m "feat: tree view 3 columns — name, size, relative time"
```

---

### Task 2.3: Slim down project selector

**Files:**
- Modify: `presentation/main_window.py:139-145` (project list in _build_ui)

**Step 1: Reduce left panel max width. Show only project name + path.**

**Step 2: Remove project list right-click items for Progress, Relations. Keep only: manage roots, remove project.**

**Step 3: Run app, commit**

```
python3 main.py
git add presentation/main_window.py
git commit -m "refactor: slim project selector — name + path only"
```

---

## Phase 3: CommandQueue + Virtual Mode

### Task 3.1: Command dataclass

**Files:**
- Modify: `domain/models.py`
- Create: `tests/test_command_queue.py`

**Step 1: Write test for Command creation**

**Step 2: Add Command dataclass to domain/models.py**

```python
@dataclass
class Command:
    """虛擬模式指令 — 描述使用者意圖，不含執行細節。"""
    op: str              # "move" | "delete" | "copy" | "rename" | "mkdir"
    source: str
    dest: str | None
    timestamp: float = field(default_factory=lambda: __import__("time").time())
```

**Step 3: Run test, commit**

---

### Task 3.2: CommandQueue

**Files:**
- Create: `domain/services/command_queue.py`
- Modify: `tests/test_command_queue.py`

**Step 1: Write comprehensive tests**

Test cases:
- Empty queue: can_undo=False, can_redo=False, pending=[]
- Push and pending
- Undo reduces pending
- Redo restores pending
- Full cycle: push 3, undo all, redo all
- Push after undo clears redo history
- Clear empties everything
- Undo/redo on empty is noop

**Step 2: Implement CommandQueue in domain/services/command_queue.py**

Pure Python, no external deps. Fields: `_commands: list[Command]`, `_cursor: int`. Methods: `push()`, `undo()`, `redo()`, `pending()`, `clear()`. Properties: `can_undo`, `can_redo`.

**Step 3: Run tests, commit**

---

### Task 3.3: VirtualTree

**Files:**
- Create: `domain/services/virtual_tree.py`
- Create: `tests/test_virtual_tree.py`

**Step 1: Write tests**

Test: no commands = all unchanged, delete marks node, move marks source+adds dest, rename marks source+adds dest, mkdir adds new dir node.

**Step 2: Implement VirtualTree**

Pure Python. Takes a flat snapshot `list[dict]` + commands, produces annotated node list with `VNodeStatus` enum (UNCHANGED/MOVED/DELETED/ADDED/RENAMED).

**Step 3: Run tests, commit**

---

### Task 3.4: VirtualService (application layer)

**Files:**
- Create: `application/virtual_service.py`
- Create: `tests/test_virtual_service.py`

Coordinates CommandQueue + VirtualTree + execution. API: `begin()`, `push()`, `undo()`, `redo()`, `resolve_tree()`, `pending_commands()`, `apply()`, `discard()`.

Write tests, implement, commit.

---

### Task 3.5: Diff Panel UI

**Files:**
- Create: `presentation/widgets/diff_panel.py`

QDialog showing pending commands as diff summary. Buttons: "確認套用" / "取消". Manual test only.

Commit.

---

### Task 3.6: Wire Virtual Mode into MainWindow

**Files:**
- Modify: `presentation/main_window.py`

Wire:
1. Mode switch to VIRTUAL -> create VirtualService with tree snapshot
2. Tree shows VirtualTree output with status coloring
3. Drag/right-click/shortcuts -> `virtual_service.push(Command(...))`
4. Ctrl+Z/Ctrl+Shift+Z -> undo/redo on virtual service
5. Status bar: "套用變更" / "放棄並退出" buttons in virtual mode
6. "套用變更" -> DiffPanel -> confirm executes, cancel stays
7. "放棄並退出" -> confirm dialog -> discard -> switch to preview

Commit.

---

## Phase 4: Live Mode + ModeController

### Task 4.1: LiveHistory

**Files:**
- Create: `domain/services/live_history.py`
- Create: `tests/test_live_history.py`

Same cursor structure as CommandQueue but entries hold OperationRecord. Undo calls file_operations.undo_operation(). Redo re-executes.

Write tests (mock file operations), implement, commit.

---

### Task 4.2: ModeController

**Files:**
- Create: `application/mode_controller.py`
- Create: `tests/test_mode_controller.py`

Unified interface: `execute(command)`, `undo()`, `redo()`. Dispatches to VirtualService or LiveHistory based on mode. Preview blocks all.

Write tests, implement, commit.

---

### Task 4.3: Wire ModeController into MainWindow

**Files:**
- Modify: `presentation/main_window.py`

Replace direct operation code with `self._controller.execute(command)`. Wire Ctrl+Z/Shift+Z, wire right-click menu through controller.

Commit.

---

### Task 4.4: Edit menu + Mode menu + keyboard shortcuts

**Files:**
- Modify: `presentation/main_window.py`

Add Edit menu (復原/重做/剪下/複製/貼上/重命名/刪除/新增資料夾).
Add Mode menu (預覽 Ctrl+1 / 虛擬 Ctrl+2 / 即時 Ctrl+3 / 套用變更 Ctrl+Enter / 放棄並退出).

Commit.

---

## Phase 5: Dual Panel

### Task 5.1: DualPanelWidget

**Files:**
- Create: `presentation/widgets/dual_panel.py`

QSplitter with two tree panels. Each has project selector (QComboBox) + QTreeView. Panel B hidden by default. F6 toggles (Live mode only). Cross-panel drag-drop creates move commands.

Commit.

---

### Task 5.2: Wire DualPanel into MainWindow

**Files:**
- Modify: `presentation/main_window.py`

Replace single tree container with DualPanelWidget. F6 only works in Live mode.

Commit.

---

## Phase 6: Flat-List Search + Match Highlighting

### Task 6.1: fuzzy_score_positions

**Files:**
- Modify: `domain/services/fuzzy_match.py`
- Create: `tests/test_fuzzy_positions.py`

**Step 1: Write tests**

Test exact match positions, sparse match, no match, case insensitive.

**Step 2: Implement fuzzy_score_positions**

Variant of fuzzy_score that also collects matched character indices. Returns `tuple[int, list[int]]`.

**Step 3: Run tests, commit**

---

### Task 6.2: FlatSearchWidget + HighlightDelegate

**Files:**
- Create: `presentation/widgets/flat_search.py`
- Create: `presentation/widgets/highlight_delegate.py`

FlatSearchWidget: QLineEdit + QListView. Uses flat cache, fuzzy_filter on keystroke. Enter emits "selected", Escape emits "cancelled".

HighlightDelegate: QStyledItemDelegate painting matched chars in distinct color.

Commit.

---

### Task 6.3: Wire FlatSearch into MainWindow

**Files:**
- Modify: `presentation/main_window.py`

Printable keystroke on tree -> hide TreeView, show FlatSearchWidget. Enter -> navigate to file in tree. Escape -> close search. Build flat cache on project load. Remove old FuzzyFilterProxyModel and eventFilter logic.

Commit.

---

### Task 6.4: Final integration test

**Step 1: Run full test suite**

```
python3 -m unittest discover tests -v
```

**Step 2: Manual testing checklist**

- [ ] Preview mode: browse, see sizes/times, cannot edit
- [ ] Virtual mode: drag move, right-click delete, rename — tree reflects changes
- [ ] Virtual Ctrl+Z/Ctrl+Shift+Z works through full history
- [ ] Virtual "套用變更" shows diff, confirm executes, cancel stays
- [ ] Virtual "放棄並退出" clears all
- [ ] Live mode: operations execute immediately
- [ ] Live Ctrl+Z undoes real file operation
- [ ] Live F6 opens dual panel, cross-project drag works
- [ ] Flat search: type to search, highlighted matches, Enter navigates, Escape closes
- [ ] F3 MetadataPanel still works
- [ ] Theme switching still works

**Step 3: Commit**

```
git add -A
git commit -m "feat: Phase 6 complete — three-mode restructure finished"
```
