# Simplify TODO — 全專案程式碼精簡清單

> 產生日期：2026-03-05
> 來源：5 個平行 code-simplifier agent 全面審查
> 總計：69 項（去重後）

---

## 優先級說明

- **P0 — BUG/破損**：會導致執行時錯誤或邏輯錯誤
- **P1 — 高影響**：跨檔案重複、違反架構規範、大量死碼
- **P2 — 中影響**：單檔內的簡化、命名改善、不一致修正
- **P3 — 低影響**：風格微調、文件更新

---

## P0 — BUG / 破損

### ~~[B01] presentation/main_window.py:576–590 — _rescan_project 重複連接 signal~~ ✅ 已在 mixin refactor 中修好
- `_rescan_project()` 呼叫 `_on_folder_scan_requested()` 後又再次連接 `progress`/`finished` signal 並 `start()`
- 結果：掃描 worker 被啟動兩次、signal 重複觸發

### ~~[B02] main.py:21–22 — 資料庫雙重初始化~~ ✅
- `main()` 呼叫 `get_connection()` + `init_db()` 產生 `conn`，但從未傳給 `MainWindow`
- `MainWindow.__init__` 又獨立呼叫一次 `get_connection()` + `init_db()`
- 結果：初始化兩次、`conn` 變數浪費

### ~~[B03] presentation/main_window.py:567,581 — 存取 FolderPanel 不存在的私有屬性~~ ✅
- `main_window.py` 存取 `FolderPanel._folder_list`，但實際屬性名為 `_list`
- 結果：可能 AttributeError

---

## P1 — 高影響（架構 / 跨檔案）

### 跨層：sqlite3.Row 回傳違反 DDD 規範

> CLAUDE.md 明訂：「Repository 方法回傳 domain/models.py 的 dataclass，不回傳 sqlite3.Row」

| # | 檔案 | 說明 |
|---|---|---|
| A01 | infrastructure/repositories/project_repo.py | list_projects, get_project, list_project_roots 回傳 Row |
| A02 | infrastructure/repositories/node_repo.py | get_node, get_children, search_nodes, filter_nodes 等回傳 Row |
| A03 | infrastructure/repositories/tag_repo.py | 回傳 Row |
| A04 | infrastructure/repositories/todo_repo.py | 回傳 Row |
| A05 | infrastructure/repositories/relation_repo.py | 回傳 Row |
| A06 | infrastructure/repositories/tool_repo.py | 回傳 Row |
| A07 | infrastructure/repositories/session_repo.py | 回傳 Row |

### 跨層：重複邏輯待抽取

| # | 位置 | 說明 |
|---|---|---|
| D01 | presentation/ 4 處 | `format_file_size()` 重複實作於 tree_model.py:28, organization_dialogs.py:265, metadata_panel.py:74, search_dialogs.py:322 |
| D02 | presentation/ 5 處 | 「在檔案總管中開啟」邏輯重複於 main_window.py:1093, organization_dialogs.py:245, search_dialogs.py:108/179/343 |
| D03 | application/session_service.py:52–93 | execute_move/delete/copy 三個方法完全相同的 pattern，應抽取 `_execute_op` |
| D04 | application/mode_controller.py:30–73 | execute/undo/redo/can_undo/can_redo 五個方法重複 if/elif 分派，應改用 dispatch dict |
| D05 | domain/services/file_operations.py:20–109 | move_file/copy_file 共用驗證邏輯重複，應抽取 `_validate_source_dest` |
| D06 | infrastructure/repositories/session_repo.py:34–49 | finalize_session/cancel_session 幾乎相同，應合併為 `_close_session` |
| D07 | infrastructure/repositories/tool_repo.py:12–19 | list_tools/list_all_tools 僅差 WHERE 條件，應合併加 `enabled_only` 參數 |
| D08 | infrastructure/repositories/node_repo.py:20–77 | upsert_node 和 get_existing_node_map 重複 root_id IS NULL 分支邏輯 |

### 根目錄 database.py shim — 大量死碼

| # | 說明 |
|---|---|
| S01 | database.py 共 246 行，約 12 個 wrapper 從未被 import：delete_node, get_root_for_node, update_tag, add_node_tag, remove_node_tag, list_tools, seed_default_tools, create_session, finalize_session, cancel_session, add_file_operation, update_file_operation_status |
| S02 | PROGRESS_STATES, DB_PATH 從未從此 shim 被 import |

### 死碼：整個檔案 / 類別未使用

| # | 位置 | 說明 |
|---|---|---|
| X01 | presentation/widgets/dual_panel.py:84 | `DualPanelWidget` 類別從未被 import 或實例化 |
| X02 | themes.py (root shim) | 整個檔案從未被任何模組 import（main.py 直接用 presentation.themes） |
| X03 | domain/services/git_info.py:71 | `format_git_badge` 從未在檔案外被呼叫 |
| X04 | infrastructure/repositories/todo_repo.py:55 | `list_todos_raw` 定義了但整條鏈（protocol → service → repo）都未被呼叫 |
| X05 | domain/protocols.py:163 | `list_todos_raw` Protocol 宣告可一併移除 |
| X06 | presentation/themes.py:9 | `_PALETTE` dict 定義了但從未被參照（stylesheet 直接寫死 hex） |

---

## P2 — 中影響（單檔簡化）

### application/

| # | 位置 | 類型 | 說明 |
|---|---|---|---|
| AP01 | report_service.py:6 | STYLE | import sqlite3 違反 DDD 分層規則（application 層不應直接依賴 sqlite3） |
| AP02 | report_service.py:23–28 | OVERCOMPLX | `_fetch_project` 用 raw SQL 而非注入的 repository |
| AP03 | report_service.py:68–71,137–140 | OVERCOMPLX | export_markdown/html 用 raw SQL 查 todos 而非 repository |
| AP04 | report_service.py:46–47,111–112 | DUPLICATE | export_markdown/html 的 data fetching 前置邏輯重複 |
| AP05 | report_service.py:101–131 | DUPLICATE | category 計數邏輯在兩個 export 方法中重複 |
| AP06 | organization_service.py:37 | DEAD_CODE | `find_duplicates` 的 `conn` 參數從未使用 |
| AP07 | template_service.py:260–293 | OVERCOMPLX | class method 全是單行委派給同檔的 module-level function |
| AP08 | tag_service.py:6–35 | OVERCOMPLX | 整個 class 是純 pass-through proxy，無任何業務邏輯 |
| AP09 | task_service.py:6–45 | OVERCOMPLX | 同上，純 pass-through |
| AP10 | search_service.py:8–25 | OVERCOMPLX | 同上，純 pass-through |
| AP11 | virtual_service.py:58–65 | CLEANUP | `apply` 忽略 executor 回傳值，docstring 與行為不符 |

### domain/

| # | 位置 | 類型 | 說明 |
|---|---|---|---|
| DM01 | models.py:164 | DEAD_CODE | `TimelineEntry` dataclass 從未被實例化 |
| DM02 | enums.py:29–30 | STYLE | MODE_READ/VIRTUAL/REALTIME 用 plain string 而非 Enum，與檔名 enums.py 不一致 |
| DM03 | services/classification.py:53 | STYLE | 不必要的 lazy import（無循環依賴風險） |
| DM04 | services/batch_rename.py:95 | OVERCOMPLX | conflict boolean 混淆「名稱碰撞」與「無變更」兩種語意 |
| DM05 | services/batch_rename.py:75 | NAMING | 變數 `f` 與 f-string 視覺混淆，應改名 |
| DM06 | services/git_info.py:40 | NAMING | 變數 `l`（小寫 L）易與數字 1 混淆，應改名為 `line` |
| DM07 | services/live_history.py:69–93 | OVERCOMPLX | if/elif chain 應改用 dispatch dict |
| DM08 | services/live_history.py:77–78 | DUPLICATE | rename 與 move 處理邏輯完全相同，可合併 |
| DM09 | services/virtual_tree.py:44 | OVERCOMPLX | 空 dict fallback 靜默吞掉 missing source |
| DM10 | services/file_operations.py:139 | STYLE | 註解用語風格不一致（「乾掉」vs 其他正式中文） |

### infrastructure/

| # | 位置 | 類型 | 說明 |
|---|---|---|---|
| IF01 | database.py:24–196 | OVERCOMPLX | init_db 用 6 個分散的 executescript，可合併 |
| IF02 | database.py:68–78,150–158 | STYLE | ALTER TABLE migration 用 bare `except Exception: pass`，應限縮為 `sqlite3.OperationalError` |
| IF03 | database.py:68–78,150–158 | DUPLICATE | ALTER TABLE + try/except 重複 pattern，應抽取 `_safe_add_column` helper |
| IF04 | database.py:123–132 | OVERCOMPLX | init_db 內 inline import 3 個 repo 做 seed，耦合隱蔽 |
| IF05 | node_repo.py:309–315 | STYLE | filter_nodes 的 tag 過濾用 f-string 而非參數化查詢 |
| IF06 | tag_repo.py:53 | CLEANUP | `get_tags_for_nodes` 實作存在但 Protocol 無對應宣告 |
| IF07 | tag_repo.py:69–73 | STYLE | 手動 dict 建構應改用 `dict.setdefault` |
| IF08 | settings_repo.py:12–16 | STYLE | settings table DDL 在 constructor 中，與其他 table 在 init_db 不一致 |

### presentation/

| # | 位置 | 類型 | 說明 |
|---|---|---|---|
| PR01 | dialogs/organization_dialogs.py:13 | UNUSED_IMPORT | `PROGRESS_LABELS` imported 但未使用 |
| PR02 | main_window.py:165 | STYLE | `QSizePolicy` inline import 應移至頂層 |
| PR03 | main_window.py:164,950 | STYLE | `get_category_icon` 多處 inline import，應移至頂層 |
| PR04 | tree_model.py:8 | STYLE | 混用 `Optional[X]` 和 `X | None` 語法 |
| PR05 | tree_model.py:130 | CLEANUP | `_ROLE_LABELS` 每個 key == value，dict 無意義 |
| PR06 | widgets/todo_panel.py:60 | CLEANUP | `QColor` 在 loop 內 import |
| PR07 | dialogs/search_dialogs.py:87 | CLEANUP | `QEvent` inline import |
| PR08 | widgets/timeline_widget.py:26,42 | CLEANUP | `QPainter`/`QColor`/`QFont`/`QPen`/`datetime` 在 paintEvent 內 import（影響效能） |
| PR09 | 多處（7 個） | STYLE | `exec_()` 應改為 `exec()`（PySide6 中 `_` 後綴已 deprecated） |
| PR10 | widgets/__init__.py | CLEANUP | 未 export 較新的 widgets（DiffPanel, FlatSearchWidget 等） |
| PR11 | themes.py:183,188 | OVERCOMPLX | build_stylesheet/apply_theme 接受但忽略 theme_name 參數，API 誤導 |

### 根目錄 shim/

| # | 位置 | 類型 | 說明 |
|---|---|---|---|
| SH01 | backup.py:16 | DEAD_CODE | `prune_backups` 從未被 import |
| SH02 | backup.py:3–4 | UNUSED_IMPORT | `Path` imported 但未使用 |
| SH03 | session_manager.py:1–60 | OVERCOMPLX | 60 行純 pass-through class，每個方法都是 1:1 委派 |
| SH04 | report_exporter.py:29 | STYLE | `save_report` 參數缺少 type annotation |
| SH05 | main.py:28 | STYLE | import MainWindow 走 shim，但 STYLESHEET 直接走 presentation.themes，不一致 |

---

## P3 — 低影響（文件更新）

| # | 說明 |
|---|---|
| DOC01 | CLAUDE.md shim 檔案清單過時：列了 classifier.py, git_utils.py, tree_model.py, test_use_cases.py 但這些已不存在 |

---

## 統計

| 層級 | 項目數 |
|---|---|
| P0 BUG | 3 |
| P1 架構/跨檔 | 22 |
| P2 單檔簡化 | 43 |
| P3 文件 | 1 |
| **合計** | **69** |

| 類型 | 項目數 |
|---|---|
| DEAD_CODE | 16 |
| DUPLICATE | 13 |
| OVERCOMPLX | 13 |
| STYLE | 15 |
| CLEANUP | 8 |
| UNUSED_IMPORT | 3 |
| BUG | 3 |
