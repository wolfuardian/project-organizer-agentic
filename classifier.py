"""檔案分類器 — 依副檔名判斷檔案類別."""

from pathlib import Path

# 副檔名 → 類別對照表
_EXT_MAP: dict[str, str] = {}

_CATEGORIES: dict[str, set[str]] = {
    "image":    {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
                 ".svg", ".ico", ".tiff", ".tif", ".raw", ".heic"},
    "video":    {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv",
                 ".webm", ".m4v", ".mpg", ".mpeg"},
    "audio":    {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a",
                 ".wma", ".opus", ".mid", ".midi"},
    "code":     {".py", ".js", ".ts", ".jsx", ".tsx", ".java",
                 ".c", ".cpp", ".cc", ".h", ".hpp", ".cs", ".go",
                 ".rs", ".rb", ".php", ".swift", ".kt", ".html",
                 ".css", ".scss", ".sass", ".vue", ".dart", ".lua",
                 ".sh", ".bat", ".ps1", ".r", ".m", ".mm"},
    "document": {".pdf", ".doc", ".docx", ".xls", ".xlsx",
                 ".ppt", ".pptx", ".txt", ".md", ".rst", ".odt",
                 ".rtf", ".pages", ".numbers", ".key", ".epub"},
    "archive":  {".zip", ".tar", ".gz", ".rar", ".7z",
                 ".bz2", ".xz", ".tgz", ".tar.gz"},
    "data":     {".json", ".xml", ".csv", ".yaml", ".yml",
                 ".toml", ".ini", ".cfg", ".conf", ".sql",
                 ".db", ".sqlite", ".env"},
    "font":     {".ttf", ".otf", ".woff", ".woff2", ".eot"},
    "3d":       {".fbx", ".obj", ".blend", ".dae", ".stl",
                 ".3ds", ".gltf", ".glb"},
}

# 建立反向查詢字典
for _cat, _exts in _CATEGORIES.items():
    for _ext in _exts:
        _EXT_MAP[_ext] = _cat


def classify_file(filename: str) -> str:
    """依副檔名回傳分類名稱；無法辨識則回傳 'other'."""
    ext = Path(filename).suffix.lower()
    return _EXT_MAP.get(ext, "other")


def category_label(category: str) -> str:
    """回傳分類的顯示標籤（含 emoji）."""
    labels = {
        "image":    "🖼 圖片",
        "video":    "🎬 影片",
        "audio":    "🎵 音訊",
        "code":     "💻 程式碼",
        "document": "📄 文件",
        "archive":  "📦 壓縮檔",
        "data":     "🗃 資料",
        "font":     "🔤 字型",
        "3d":       "🧊 3D",
        "other":    "📎 其他",
    }
    return labels.get(category, category)
