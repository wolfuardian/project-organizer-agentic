# 三層式專案管理架構設計

> 日期：2026-03-05

## 概述

將現有的兩層架構（專案清單 → 檔案樹）重構為三層：

- **第一層**：專案清單（左側面板） — 專案是抽象分類，不再綁定單一資料夾
- **第二層**：專案資料夾清單（中間面板） — 手動新增的資料夾，顯示名稱 + 角色標籤
- **第三層**：檔案樹（右側面板） — 顯示選中資料夾的檔案內容

## 佈局

```
┌──────────┐┌──────────────┐┌─────────────────────────┐
│ 專案清單  ││ 中間面板      ││ 檔案樹                   │
│ (QList)  ││              ││ (QTreeView)              │
│          ││ [狀態列]      ││                          │
│ Project A││ ── ── ── ──  ││                          │
│ Project B││ 📁 src [source]│                          │
│ Project C││ 📁 docs [docs] │                          │
│          ││              ││                          │
│ [＋ 新增] ││ [＋ 新增資料夾]││                          │
└──────────┘└──────────────┘└─────────────────────────┘
```

## 資料模型變更

### projects 表

- `root_path`：不再是必填。新建專案時只需名稱。
- 既有的 `status`（active/archived/paused）和 `progress`（not_started/in_progress/paused/completed）欄位沿用，無需新增欄位。

### project_roots 表

- 成為核心資料來源。專案的所有資料夾都透過此表管理。
- 既有 schema 不變：`id, project_id, root_path, role, label, sort_order, added_at`。

### nodes 表

- 無變更。每個 node 已有 `root_id` FK 指向 `project_roots`。

## 中間面板設計

### 頂部狀態列

- 顯示專案名稱 + progress 狀態
- 可點擊循環切換 progress（not_started → in_progress → paused → completed）

### 資料夾清單

- QListWidget，每項顯示資料夾短名稱 + 角色標籤（如 `[source]`）
- Tooltip 顯示完整路徑
- 選取資料夾 → 檔案樹載入該資料夾的節點

### 底部按鈕

- 「＋」按鈕：彈出資料夾選擇器，選完直接加入 + 背景掃描

## 互動流程

### 新增專案

1. 點「＋ 新增」→ 輸入名稱 → 建立空專案
2. 在中間面板點「＋」新增資料夾

### 選取專案

1. 左側選取專案 → 中間面板載入該專案的 project_roots
2. 自動選中第一個資料夾
3. 檔案樹載入該資料夾的節點

### 選取資料夾

1. 中間面板選取不同資料夾 → 檔案樹切換為該資料夾的節點
2. 使用 `get_children_by_root(root_id)` 查詢

## 檔案樹載入邏輯

- `ProjectTreeModel` 建構時接收 `root_id` 參數
- 只查詢該 root 下的 nodes（非全部 roots）
- 不再需要多根目錄的虛擬分組節點

## 向後相容

- `_migrate_project_roots` 每次啟動自動執行，確保既有專案都有 project_roots 記錄
- 舊專案的 `root_path` 保留，作為 fallback
- 舊專案打開後，中間面板顯示其已有的 roots

## 影響範圍

### 需修改的檔案

- `presentation/main_window.py` — 佈局重構、互動邏輯
- `presentation/tree_model.py` — 接收 root_id 參數、單根載入
- `infrastructure/repositories/project_repo.py` — create_project 允許空 root_path
- `infrastructure/database.py` — DDL 放寬 root_path NOT NULL 約束
- `domain/protocols.py` — 更新 create_project 簽名
- `application/project_service.py` — 適配新流程

### 需新增的檔案

- `presentation/widgets/folder_panel.py` — 中間面板 widget

### 可移除的邏輯

- `ProjectTreeModel._build_top_level` 中的多根虛擬分組邏輯
- `ProjectRootsDialog`（功能由中間面板取代）
