# 三層式專案管理架構 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 將兩層架構（專案清單 → 檔案樹）重構為三層（專案清單 → 資料夾面板 → 檔案樹），專案成為抽象分類，資料夾獨立管理。

**Architecture:** 新增中間面板 widget `FolderPanel`，插入 splitter 的 left 和 tree_container 之間。修改 `_on_project_selected` 改為載入資料夾清單而非直接建立 tree model。新增 `_on_folder_selected` 以選定 root_id 載入檔案樹。`create_project` 改為只需名稱，不需選資料夾。

**Tech Stack:** PySide6, SQLite, 既有 DDD 分層

---

## Task 1: 資料模型 — 允許空 root_path

**Files:**
- Modify: `infrastructure/database.py:25-28` (DDL)
- Modify: `infrastructure/repositories/project_repo.py:15-24` (create_project)
- Modify: `domain/protocols.py:24-25` (Protocol 簽名)
- Modify: `database.py:32-34` (shim)

**Step 1: 修改 DDL — projects.root_path 改為可 NULL**

在 `infrastructure/database.py` 的 `init_db()` 中，DDL 用 `CREATE TABLE IF NOT EXISTS`，已存在的表不會被修改。需要加一段 migration 來放寬約束。

但 SQLite 不支援 `ALTER TABLE ... ALTER COLUMN`。既有資料庫的 `root_path TEXT NOT NULL UNIQUE` 無法直接改。

**務實方案：** 新建專案時，`root_path` 給空字串 `""` 而非 NULL，避免破壞既有 NOT NULL + UNIQUE 約束。UNIQUE 約束在空字串上只允許一個空值 — 所以改為用專案名稱作為 root_path 的 fallback（`root_path = name`）以保持 UNIQUE。

```python
# infrastructure/repositories/project_repo.py — create_project
def create_project(self, name: str, root_path: str = "",
                   description: str = "") -> int:
    now = datetime.now().isoformat()
    # 若無 root_path，用 name 作為唯一識別
    effective_path = root_path or f"__project__{name}_{now}"
    cur = self._conn.execute(
        "INSERT INTO projects (name, root_path, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, effective_path, description, now, now),
    )
    self._conn.commit()
    return cur.lastrowid
```

**Step 2: 更新 Protocol 簽名**

```python
# domain/protocols.py
def create_project(self, name: str, root_path: str = "",
                   description: str = "") -> int: ...
```

**Step 3: 更新 shim**

```python
# database.py
def create_project(conn, name: str, root_path: str = "",
                   description: str = "") -> int:
    return SqliteProjectRepository(conn).create_project(name, root_path, description)
```

**Step 4: 驗證**

Run: `python -c "from database import create_project; print('OK')"`

**Step 5: Commit**

```
feat: create_project 允許空 root_path — 專案不再強制綁定資料夾
```

---

## Task 2: 新增 FolderPanel widget

**Files:**
- Create: `presentation/widgets/folder_panel.py`

**Step 1: 建立 FolderPanel**

```python
"""中間面板 — 專案資料夾清單 + 狀態列。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFileDialog, QInputDialog,
)

from database import (
    list_project_roots, add_project_root, set_project_progress,
)
from domain.enums import PROGRESS_STATES, PROGRESS_LABELS, PROJECT_ROOT_ROLES


class FolderPanel(QWidget):
    """中間面板：頂部狀態列 + 資料夾清單 + 底部新增按鈕。"""

    folder_selected = Signal(int)   # 發射 root_id
    scan_requested = Signal(int, int, str)  # project_id, root_id, root_path

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._project_id: int | None = None
        self._project_name: str = ""
        self._project_progress: str = "not_started"
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── 狀態列 ──
        status_row = QHBoxLayout()
        status_row.setSpacing(4)
        self._lbl_name = QLabel()
        self._lbl_name.setWordWrap(True)
        status_row.addWidget(self._lbl_name, 1)

        self._btn_progress = QPushButton()
        self._btn_progress.setToolTip("點擊切換專案進度")
        self._btn_progress.setFixedHeight(22)
        self._btn_progress.clicked.connect(self._cycle_progress)
        status_row.addWidget(self._btn_progress)
        layout.addLayout(status_row)

        # ── 資料夾清單 ──
        self._folder_list = QListWidget()
        self._folder_list.currentItemChanged.connect(self._on_folder_changed)
        layout.addWidget(self._folder_list)

        # ── 新增按鈕 ──
        btn_add = QPushButton("＋ 新增資料夾")
        btn_add.clicked.connect(self._add_folder)
        layout.addWidget(btn_add)

    def load_project(self, project_id: int, name: str, progress: str) -> None:
        """載入指定專案的資料夾清單。"""
        self._project_id = project_id
        self._project_name = name
        self._project_progress = progress
        self._lbl_name.setText(name)
        self._update_progress_btn()
        self._reload_folders()

    def _reload_folders(self) -> None:
        self._folder_list.clear()
        if not self._project_id:
            return
        roots = list_project_roots(self._conn, self._project_id)
        for r in roots:
            path = Path(r["root_path"])
            role = r["role"] or "misc"
            label = r["label"] or path.name
            display = f"{label}  [{role}]"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, r["id"])
            item.setData(Qt.UserRole + 1, r["root_path"])
            item.setToolTip(str(r["root_path"]))
            self._folder_list.addItem(item)
        # 自動選中第一個
        if self._folder_list.count() > 0:
            self._folder_list.setCurrentRow(0)

    def _on_folder_changed(self, current: QListWidgetItem,
                           previous: QListWidgetItem) -> None:
        if current:
            root_id = current.data(Qt.UserRole)
            self.folder_selected.emit(root_id)

    def _add_folder(self) -> None:
        if not self._project_id:
            return
        folder = QFileDialog.getExistingDirectory(self, "選擇資料夾")
        if not folder:
            return
        # 選擇角色
        roles = PROJECT_ROOT_ROLES
        role, ok = QInputDialog.getItem(
            self, "角色", "選擇資料夾角色：", roles, 0, False,
        )
        if not ok:
            return
        try:
            root_id = add_project_root(
                self._conn, self._project_id, folder, role,
            )
        except Exception:
            return
        self._reload_folders()
        # 選中新加入的項目（最後一個）
        self._folder_list.setCurrentRow(self._folder_list.count() - 1)
        # 請求掃描
        self.scan_requested.emit(self._project_id, root_id, folder)

    def _cycle_progress(self) -> None:
        if not self._project_id:
            return
        idx = PROGRESS_STATES.index(self._project_progress)
        next_state = PROGRESS_STATES[(idx + 1) % len(PROGRESS_STATES)]
        set_project_progress(self._conn, self._project_id, next_state)
        self._project_progress = next_state
        self._update_progress_btn()

    def _update_progress_btn(self) -> None:
        label = PROGRESS_LABELS.get(self._project_progress, self._project_progress)
        self._btn_progress.setText(label)

    def current_root_id(self) -> int | None:
        item = self._folder_list.currentItem()
        return item.data(Qt.UserRole) if item else None
```

**Step 2: 驗證 import**

Run: `python -c "from presentation.widgets.folder_panel import FolderPanel; print('OK')"`

**Step 3: Commit**

```
feat: 新增 FolderPanel 中間面板 widget — 資料夾清單 + 狀態列
```

---

## Task 3: 佈局重構 — 在 splitter 插入 FolderPanel

**Files:**
- Modify: `presentation/main_window.py` (_build_ui, splitter 設定)

**Step 1: import FolderPanel**

在 `main_window.py` 頂部 import 區加入：
```python
from presentation.widgets.folder_panel import FolderPanel
```

**Step 2: 在 `_build_ui` 中建立 FolderPanel 並插入 splitter**

在 `left` widget 建立之後、`tree_container` 建立之前，新增：
```python
self._folder_panel = FolderPanel(self._conn, parent=self)
self._folder_panel.folder_selected.connect(self._on_folder_selected)
self._folder_panel.scan_requested.connect(self._on_folder_scan_requested)
```

修改 splitter addWidget 順序：
```python
self._left_panel = left
splitter.addWidget(left)
splitter.addWidget(self._folder_panel)    # 新增：第二層
splitter.addWidget(tree_container)
splitter.addWidget(self._panel_b)
splitter.addWidget(self._meta_panel)
```

更新 stretch/collapsible/sizes：
```python
splitter.setStretchFactor(0, 0)  # left
splitter.setStretchFactor(1, 0)  # folder panel
splitter.setStretchFactor(2, 1)  # tree
splitter.setStretchFactor(3, 1)  # panel b
splitter.setStretchFactor(4, 0)  # meta
splitter.setCollapsible(0, False)
splitter.setCollapsible(1, False)
splitter.setCollapsible(2, False)
splitter.setSizes([180, 180, 1, 0, 0])
```

設定 folder_panel 寬度限制：
```python
self._folder_panel.setMinimumWidth(140)
self._folder_panel.setMaximumWidth(220)
```

注意：splitter handle 索引會偏移。原本 handle(1) 是 left↔tree，現在 handle(1) 是 left↔folder，handle(2) 是 folder↔tree。左面板的 handle 禁用需更新：
```python
splitter.handle(1).setEnabled(False)
splitter.handle(1).setFixedWidth(0)
```

**Step 3: 驗證**

Run: `python -c "from presentation.main_window import MainWindow; print('OK')"`

**Step 4: Commit**

```
feat: 佈局重構 — splitter 插入 FolderPanel 中間面板
```

---

## Task 4: 互動邏輯 — 專案選取 → 資料夾載入 → 檔案樹載入

**Files:**
- Modify: `presentation/main_window.py` (_on_project_selected, 新增 _on_folder_selected)

**Step 1: 修改 `_on_project_selected`**

不再直接建立 TreeModel，改為載入中間面板：
```python
def _on_project_selected(self, current, previous):
    if not current:
        return
    pid = current.data(Qt.UserRole)
    self._current_project_id = pid
    # 查詢專案資訊
    from database import list_projects
    row = self._conn.execute(
        "SELECT name, progress FROM projects WHERE id=?", (pid,)
    ).fetchone()
    if not row:
        return
    self._folder_panel.load_project(pid, row["name"], row["progress"] or "not_started")
```

`load_project` 最後會自動選中第一個資料夾 → 觸發 `folder_selected` signal → `_on_folder_selected`。

**Step 2: 新增 `_on_folder_selected`**

```python
def _on_folder_selected(self, root_id: int) -> None:
    """中間面板選取資料夾 → 載入該資料夾的檔案樹。"""
    if not self._current_project_id:
        return
    self._current_root_id = root_id
    self._tree_model = ProjectTreeModel(
        self._conn, self._current_project_id, root_id=root_id,
    )
    self._tree_view.setModel(self._tree_model)
    setup_tree_header(self._tree_view.header())
    self._tree_view.selectionModel().currentChanged.connect(
        self._on_tree_selection_changed
    )
    search_cache, self._last_snapshot = self._build_flat_lists()
    self._flat_search.set_flat_cache(search_cache)
    self._flat_search.deactivate()
    self._tree_view.setVisible(True)
    self._apply_mode()
```

**Step 3: 初始化 `_current_root_id`**

在 `__init__` 中加入：
```python
self._current_root_id: int | None = None
```

**Step 4: Commit**

```
feat: 互動邏輯 — 專案選取載入資料夾面板，資料夾選取載入檔案樹
```

---

## Task 5: TreeModel 支援 root_id 過濾

**Files:**
- Modify: `presentation/tree_model.py` (__init__, _build_top_level)

**Step 1: `__init__` 接收 root_id 參數**

```python
def __init__(self, conn, project_id, parent=None, root_id=None):
    super().__init__(parent)
    self._init_font_cache()
    self._icon_folder = get_category_icon("folder")
    self._icon_virtual = get_category_icon("virtual")
    self._icon_drive = get_category_icon("drive")
    self._conn = conn
    self._project_id = project_id
    self._root_id = root_id           # 新增
    self._node_repo = SqliteNodeRepository(conn)
    self._tag_repo = SqliteTagRepository(conn)
    self._multi_root = False
    self._node_map = {}
    self._path_map = {}
    self._virtual_status = {}
    self._virtual_added = []
    self._on_drop = None
    self._root = TreeNode(db_id=0, name="ROOT", rel_path="",
                          node_type="folder", pinned=False)
    self._build_top_level()
```

**Step 2: `_build_top_level` 改為按 root_id 過濾**

如果 `self._root_id` 有值，SQL 查詢加上 `AND root_id=?` 過濾，且不建立多根虛擬分組：

```python
def _build_top_level(self) -> None:
    self._node_map.clear()
    self._path_map.clear()
    self._root.children = []
    self._root.loaded = True

    if self._root_id:
        # 單根模式：只載入指定 root 的節點
        all_rows = self._conn.execute(
            "SELECT * FROM nodes WHERE project_id=? AND root_id=? "
            "ORDER BY node_type='file', pinned DESC, sort_order, name",
            (self._project_id, self._root_id),
        ).fetchall()
        self._multi_root = False
    else:
        # 舊的全量載入（向後相容）
        roots = list_project_roots(self._conn, self._project_id)
        self._multi_root = len(roots) > 1
        all_rows = self._conn.execute(
            "SELECT * FROM nodes WHERE project_id=? "
            "ORDER BY node_type='file', pinned DESC, sort_order, name",
            (self._project_id,),
        ).fetchall()

    # ... 後續組裝邏輯不變（多根分組只在 self._multi_root 時觸發）
```

**Step 3: Commit**

```
feat: ProjectTreeModel 支援 root_id 過濾 — 單根載入模式
```

---

## Task 6: 新增專案流程改為只輸入名稱

**Files:**
- Modify: `presentation/main_window.py` (_add_project)

**Step 1: 簡化 `_add_project`**

```python
def _add_project(self) -> None:
    name, ok = QInputDialog.getText(self, "新增專案", "專案名稱：")
    if not ok or not name.strip():
        return
    try:
        pid = create_project(self._conn, name.strip())
    except Exception as e:
        QMessageBox.warning(self, "錯誤", f"無法建立專案：{e}")
        return
    self._load_project_list()
    for i in range(self._project_list.count()):
        item = self._project_list.item(i)
        if item.data(Qt.UserRole) == pid:
            self._project_list.setCurrentItem(item)
            break
```

不再選資料夾、不再掃描。使用者在中間面板手動新增資料夾。

**Step 2: 更新 `_load_project_list`**

tooltip 不再顯示 root_path（可能是空的），改為顯示專案名稱或移除 tooltip：

```python
def _load_project_list(self) -> None:
    self._project_list.clear()
    for row in list_projects(self._conn):
        item = QListWidgetItem(row["name"])
        item.setData(Qt.UserRole, row["id"])
        self._project_list.addItem(item)
```

**Step 3: Commit**

```
feat: 新增專案流程簡化 — 只需輸入名稱，資料夾由中間面板管理
```

---

## Task 7: 資料夾掃描整合

**Files:**
- Modify: `presentation/main_window.py` (_on_folder_scan_requested)

**Step 1: 新增 `_on_folder_scan_requested`**

當 FolderPanel 發射 `scan_requested(pid, root_id, path)` 時，啟動背景掃描：

```python
def _on_folder_scan_requested(self, pid: int, root_id: int, path: str) -> None:
    """中間面板新增資料夾後，背景掃描該資料夾。"""
    if self._is_scanning():
        self.statusBar().showMessage("掃描進行中，請稍後再試。")
        return
    self.statusBar().showMessage(f"掃描 {path} …")
    self._refresh_timer.stop()
    from infrastructure.database import DB_PATH
    self._scan_worker = _ScanWorker(
        str(DB_PATH), pid,
        [{"id": root_id, "root_path": path}], parent=self,
    )
    self._scan_worker.progress.connect(self.statusBar().showMessage)
    self._scan_worker.finished.connect(self._on_folder_scan_finished)
    self._scan_worker.start()

def _on_folder_scan_finished(self, count: int) -> None:
    self._scan_worker = None
    if count < 0:
        self.statusBar().showMessage("掃描失敗")
        return
    self.statusBar().showMessage(f"已掃描 {count} 個項目")
    # 重新載入當前資料夾的檔案樹
    root_id = self._folder_panel.current_root_id()
    if root_id:
        self._on_folder_selected(root_id)
```

**Step 2: 更新 `_rescan_project`**

重新掃描改為只掃描當前選中的資料夾：

```python
def _rescan_project(self) -> None:
    if not self._current_project_id or not self._current_root_id:
        return
    if self._is_scanning():
        return
    item = self._folder_panel._folder_list.currentItem()
    if not item:
        return
    root_path = item.data(Qt.UserRole + 1)
    root_id = self._current_root_id
    self._on_folder_scan_requested(
        self._current_project_id, root_id, root_path,
    )
```

**Step 3: Commit**

```
feat: 資料夾掃描整合 — FolderPanel 新增資料夾後背景掃描
```

---

## Task 8: 清理與收尾

**Files:**
- Modify: `presentation/main_window.py` (移除 _on_add_scan_finished 中的舊邏輯)
- Modify: `presentation/widgets/__init__.py` (若需要 re-export)

**Step 1: 清理不再需要的程式碼**

- `_on_add_scan_finished` 可保留但簡化（只用於掃描完成通知）
- `_load_project_list` 中的 tooltip 已在 Task 6 移除

**Step 2: 移除 `_remove_project` 中清空 tree 的邏輯**

```python
def _remove_project(self) -> None:
    item = self._project_list.currentItem()
    if not item:
        return
    pid = item.data(Qt.UserRole)
    reply = QMessageBox.question(
        self, "確認", "確定要從列表移除此專案？（不會刪除實際檔案）",
    )
    if reply == QMessageBox.Yes:
        delete_project(self._conn, pid)
        self._load_project_list()
        self._tree_view.setModel(None)
        self._folder_panel._folder_list.clear()
        self._current_project_id = None
        self._current_root_id = None
```

**Step 3: 完整冒煙測試**

Run: `python main.py`
- 驗證：新增空專案 → 中間面板出現 → 新增資料夾 → 掃描 → 檔案樹載入
- 驗證：選取不同資料夾切換檔案樹
- 驗證：切換進度狀態
- 驗證：既有專案載入正常

**Step 4: Commit**

```
feat: 三層式專案管理架構完成 — 清理收尾
```
