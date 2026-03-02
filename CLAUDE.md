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

單一視窗桌面應用程式，以 PySide6（Qt 6）建構，資料持久化至 SQLite。

```
main.py          → 進入點：初始化 QApplication、套用 Catppuccin Mocha 深色主題
main_window.py   → MainWindow：主 UI、專案清單、快捷鍵（Ctrl+N、Ctrl+Q、F5）
tree_model.py    → ProjectTreeModel / TreeNode：QAbstractItemModel 實作，支援拖放排序
database.py      → SQLite CRUD：init_db()、create_project()、upsert_node()、move_node()
scanner.py       → 遞迴掃描目錄，忽略 .git、node_modules、__pycache__ 等雜訊目錄
```

初始化流程：`main.py` → `MainWindow.__init__()` → `init_db()` → `_load_project_list()` → `_build_ui()`

## 資料庫

SQLite 存於 `~/.project-organizer/data.db`，啟用 WAL 模式與外鍵約束。

主要資料表：
- **projects**：id, name, root_path, description, status, created_at, updated_at
- **nodes**：id, project_id, parent_id, name, rel_path, node_type（file / folder / virtual）, sort_order, pinned, note
- **tags / node_tags**：標籤與節點的多對多關聯（為 Phase 5 預留）

## 關鍵設計決策

- **虛擬資料夾**：node_type = `"virtual"`，無對應的 rel_path，僅存在於資料庫邏輯結構中
- **拖放排序**：透過 `move_node()` 更新 parent_id 與 sort_order，不修改實際檔案系統
- **主題**：Catppuccin Mocha 色彩硬編碼於 `main.py`，並以 Qt stylesheet 套用全域樣式
- **掃描忽略清單**：定義於 `scanner.py` 頂端的 `IGNORE_DIRS` / `IGNORE_FILES` 常數
