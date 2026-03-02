# Project Organizer

桌面專案整理工具 — 檔案樹視覺化 + 拖拉整理，SQLite 持久化。

## 安裝

```bash
# Python 3.11+
pip install -r requirements.txt

# 或用 uv
uv pip install -r requirements.txt
```

## 啟動

```bash
python main.py
```

## v1 功能

- **專案管理**：新增 / 移除 / 切換多個專案
- **檔案樹掃描**：自動讀取目錄結構，忽略 .git / node_modules 等
- **拖拉排序**：直接在樹中拖動檔案與資料夾重新組織
- **虛擬資料夾**：建立不對應實際路徑的邏輯分組
- **右鍵選單**：在檔案管理器開啟、從樹中移除、新增虛擬資料夾
- **深色主題**：Catppuccin Mocha 風格
- **SQLite 儲存**：資料存於 `~/.project-organizer/data.db`

## 專案結構

```
project-organizer/
├── main.py              # 進入點
├── requirements.txt
├── plan-future.md       # 未來功能規劃
├── core/
│   ├── database.py      # SQLite CRUD
│   └── scanner.py       # 檔案系統掃描器
└── ui/
    ├── tree_model.py    # QAbstractItemModel + 拖拉
    └── main_window.py   # 主視窗 UI
```

## 鍵盤快捷鍵

| 快捷鍵 | 功能 |
|--------|------|
| Ctrl+N | 新增專案 |
| Ctrl+Q | 結束 |
| F5     | 重新掃描 |
