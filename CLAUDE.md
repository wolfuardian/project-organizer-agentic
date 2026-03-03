# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 執行方式

```bash
# 安裝依賴（Python 3.11+，需要 PySide6）
pip install PySide6

# 執行應用程式
python main.py
```

目前無 `requirements.txt`，唯一外部依賴為 **PySide6**。

## 架構概覽

DDD（Domain-Driven Design）分層架構，以 PySide6（Qt 6）建構，資料持久化至 SQLite。

### 目錄結構（DDD 四層）

```
main.py                          → Composition Root（組裝所有層）

domain/                          → 領域層：純 Python，零外部依賴
├── models.py                    → 領域實體（dataclass）
├── enums.py                     → 列舉與常數
├── protocols.py                 → Repository Protocol 介面（typing.Protocol）
└── services/                    → 純業務邏輯（無 DB、無 UI）
    ├── classification.py        → classify_file + apply_rules 邏輯
    ├── fuzzy_match.py           → fuzzy_score / fuzzy_filter
    ├── file_operations.py       → move / delete / copy / merge / undo
    ├── batch_rename.py          → preview + execute rename
    └── git_info.py              → get_git_info

infrastructure/                  → 基礎設施層：SQLite 實作
├── database.py                  → get_connection, init_db, DDL, migration
└── repositories/                → Repository 實作（每個回傳 domain/models）
    ├── project_repo.py          → projects + project_roots CRUD
    ├── node_repo.py             → nodes CRUD + abs_path + search + filter
    ├── tag_repo.py              → tags + node_tags CRUD
    ├── todo_repo.py             → todos CRUD + timeline
    ├── relation_repo.py         → project_relations CRUD
    ├── template_repo.py         → templates + template_entries CRUD
    ├── tool_repo.py             → external_tools CRUD
    ├── rule_repo.py             → classify_rules CRUD
    ├── session_repo.py          → operation_sessions + file_operations CRUD
    └── settings_repo.py         → settings key-value store

application/                     → 應用層：Use Case 協調器
├── project_service.py           → 專案 CRUD + 掃描 + 進度 + Git 狀態
├── organization_service.py      → 分類規則 + 重複偵測 + 批次重命名
├── session_service.py           → 工作階段管理
├── tag_service.py               → 標籤管理
├── task_service.py              → TODO + 關聯 + 時間軸
├── template_service.py          → 模板 CRUD / scaffold / extract / export / import
├── search_service.py            → 搜尋 + 過濾 + 模糊跳轉
├── report_service.py            → Markdown / HTML 報告匯出
└── settings_service.py          → 工具設定 + 備份還原 + 主題讀寫

presentation/                    → 展示層：PySide6 UI
├── main_window.py               → MainWindow 骨架
├── tree_model.py                → ProjectTreeModel + TreeNode
├── themes.py                    → 主題定義 + Qt stylesheet
├── widgets/                     → 嵌入式元件
│   ├── todo_panel.py            → TodoPanel
│   ├── metadata_panel.py        → MetadataPanel
│   └── timeline_widget.py       → TimelineWidget
└── dialogs/                     → 所有對話框
    ├── project_dialogs.py       → ProjectRootsDialog
    ├── organization_dialogs.py  → RulesDialog, DuplicateDialog, BatchRenameDialog
    ├── tag_dialogs.py           → TagManagerDialog
    ├── template_dialogs.py      → TemplateManager/Edit/Picker, ExtractTemplate
    ├── search_dialogs.py        → SearchDialog, FilterDialog, QuickJumpDialog
    ├── relation_dialogs.py      → ProjectRelationsDialog, TimelineDialog
    ├── session_dialogs.py       → OperationHistoryDialog
    └── settings_dialogs.py      → ToolsDialog, BackupDialog, ThemeDialog, ReportDialog

tests/
└── test_use_cases.py            → 8 個 use case 驗證
```

### Shim 過渡層

根目錄保留 shim 檔案（如 `database.py`、`scanner.py` 等），轉發至新路徑，確保舊 import 不壞。

初始化流程：`main.py`（Composition Root）→ `get_connection()` + `init_db()` → `MainWindow.__init__()` → `_load_project_list()` → `_build_ui()`

## 資料庫

SQLite 存於 `~/.project-organizer/data.db`，啟用 WAL 模式與外鍵約束。

主要資料表：
- **projects**：id, name, root_path, description, status, progress, created_at, updated_at
- **nodes**：id, project_id, parent_id, name, rel_path, node_type（file / folder / virtual）, sort_order, pinned, note, root_id, role
- **project_roots**：id, project_id, root_path, role, label, sort_order, added_at（Phase 8）
- **tags / node_tags**：多層級標籤與節點的多對多關聯
- **todos**：專案 TODO 任務清單（Phase 4）
- **project_relations**：專案間依賴 / 相關 / 參考關聯（Phase 5）
- **templates / template_entries**：專案模板定義與目錄結構（Phase 3）
- **external_tools**：外部工具設定（Phase 7）
- **operation_sessions**：工作階段（Phase 8）
- **file_operations**：檔案操作記錄（Phase 8）

## 關鍵設計決策

- **虛擬資料夾**：node_type = `"virtual"`，無對應的 rel_path，僅存在於資料庫邏輯結構中
- **拖放排序**：透過 `move_node()` 更新 parent_id 與 sort_order，不修改實際檔案系統
- **主題**：`presentation/themes.py` 定義 4 種主題色彩，以 Qt stylesheet 套用全域樣式
- **掃描忽略清單**：定義於 `domain/enums.py` 的 `IGNORE_DIRS` / `IGNORE_FILES` 常數
- **DDD 分層**：domain 層使用 `typing.Protocol` 定義 Repository 介面，infrastructure 層實作；兩層透過結構型子型別解耦
- **Shim 過渡**：根目錄保留 shim 檔案轉發至新路徑，確保向後相容
- **多根目錄**：一個專案可有多個 `project_roots`，每個 root 有角色（proj/source/assets/docs/output/misc）
- **路徑解析**：統一透過 `get_node_abs_path()` 解析，支援 root_id 和 fallback
- **檔案操作引擎**：所有操作支援 dry_run 預覽 + undo；刪除移至 `~/.project-organizer/trash/`
- **工作階段**：`SessionManager` 管理操作生命週期，finalize 確認、cancel 全部復原

<!-- sync:features-start (由 /project-info sync 自動產生，勿手動編輯) -->
## 功能開發狀態

> 本段落由 `/project-info sync` 從 git 歷史自動產生。
> commit 慣例：`feat(phaseN): 功能描述` — sync 時會解析此格式。

### Phase 1：核心基礎 ✅
- 專案新增 / 刪除 / 掃描目錄結構
- 虛擬資料夾、拖放排序、釘選
- Catppuccin Mocha 深色主題

### Phase 2：萬用整理器 ✅
- 資料夾掃描與自動分類（classifier.py）
- 規則引擎 — 使用者自訂分類規則 glob/regex（rule_engine.py）
- 重複檔案偵測與清理（duplicate_finder.py）
- 批次重新命名（batch_rename.py）

### Phase 3：專案模板系統 ✅
- 內建模板（Python/Web/Rust/Unity/Node.js/空白）
- 模板 CRUD、scaffold、匯出/匯入 JSON
- 自訂模板管理 UI（TemplateManagerDialog）
- 從現有專案反推模板（ExtractTemplateDialog）

### Phase 4：專案狀態追蹤 ✅
- 專案進度（未開始/進行中/暫停/完成）+ 徽章顯示
- TODO 任務清單（TodoPanel，嵌入左側欄）
- 時間軸視圖（TimelineDialog，含 TODO 完成率）
- Git 狀態整合（branch / dirty / ahead-behind → status bar）

### Phase 5：標籤與 Metadata 管理 ✅
- 多層級標籤系統（TagManagerDialog）+ 右鍵指派
- MetadataPanel（F3 開關，右側面板顯示/編輯備註）
- 專案關聯管理（ProjectRelationsDialog）

### Phase 6：搜尋與過濾 ✅
- 全域搜尋（Ctrl+F，搜尋檔名/備註/標籤）
- 進階過濾（Ctrl+Shift+F，類別/標籤/大小/日期組合條件）
- 模糊跳轉（Ctrl+P，fuzzy matching + 方向鍵導航）

### Phase 7：進階功能 ✅
- 多視窗（Ctrl+Shift+W）
- 外部工具整合（VSCode / Terminal，右鍵「以…開啟」子選單）
- 匯出報告（Markdown / HTML）
- 備份與還原（BackupDialog）
- 外觀主題自訂（4 種主題 + Ranger 風格檔案樹著色）

### Phase 8：多根目錄 + 檔案操作引擎 + 工作階段 ✅
- 多根目錄資料模型（project_roots，角色分類，自動遷移）
- 多根樹顯示（>1 root 時頂層以角色分組）
- ProjectRootsDialog（新增 / 移除 / 改角色 + 自動掃描）
- 檔案操作引擎（move / delete / copy / merge + dry_run + undo）
- 應用程式回收桶（~/.project-organizer/trash/）
- 工作階段管理（開始 / 復原 / 確認完成 / 取消）
- 操作歷史面板（OperationHistoryDialog）
- 右鍵檔案操作（session active 時：移動 / 刪除 / 複製 / 合併）
- 狀態列工作階段指示器

### 程式碼 TODO
- `main_window.py:1542` — 進度條（節點右側）
- `main_window.py:1581` — 面板（嵌入左側欄）
<!-- sync:features-end -->
