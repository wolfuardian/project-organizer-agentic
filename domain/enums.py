"""列舉與常數 — 從各模組提取的共用定義。"""


# ── 專案進度 ──────────────────────────────────────────────────

PROGRESS_STATES = ["not_started", "in_progress", "paused", "completed"]

PROGRESS_LABELS = {
    "not_started": "未開始",
    "in_progress": "進行中",
    "paused":      "暫停",
    "completed":   "已完成",
}

# ── 專案關聯類型 ──────────────────────────────────────────────

RELATION_LABELS = {
    "depends_on":  "依賴",
    "related_to":  "相關",
    "references":  "參考",
}

# ── 專案根目錄角色 ────────────────────────────────────────────

PROJECT_ROOT_ROLES = ["proj", "source", "assets", "docs", "output", "misc"]

# ── 操作模式 ──────────────────────────────────────────────────

MODE_READ = "read"
MODE_VIRTUAL = "virtual"
MODE_REALTIME = "realtime"

MODE_LABELS = {
    MODE_READ:     "閱覽",
    MODE_VIRTUAL:  "虛擬",
    MODE_REALTIME: "即時",
}

MODE_TOOLTIPS = {
    MODE_READ:     "閱覽模式：唯讀瀏覽，不可拖放或修改",
    MODE_VIRTUAL:  "虛擬模式：拖放與操作只改 DB 結構，不動實際檔案",
    MODE_REALTIME: "即時模式：所有操作立即反映到檔案系統（含工作階段）",
}

MODE_COLORS = {
    MODE_READ:     "#89b4fa",
    MODE_VIRTUAL:  "#cba6f7",
    MODE_REALTIME: "#a6e3a1",
}

# ── 分類標籤 ──────────────────────────────────────────────────

CATEGORY_LABELS = {
    "image":    "圖片",
    "video":    "影片",
    "audio":    "音訊",
    "code":     "程式碼",
    "document": "文件",
    "archive":  "壓縮檔",
    "data":     "資料",
    "font":     "字型",
    "3d":       "3D",
    "other":    "其他",
}

# ── 掃描忽略清單 ──────────────────────────────────────────────

IGNORE_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", "node_modules",
    ".vs", ".idea", "Library", "Temp", "Logs", "obj", "bin",
    ".venv", "venv", "env", ".uv-venvs",
}

IGNORE_FILES = {
    ".DS_Store", "Thumbs.db", "desktop.ini",
}
