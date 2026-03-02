"""專案模板系統 — 資料結構、內建模板、CRUD、匯出入、反推."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── 資料結構 ─────────────────────────────────────────────────

@dataclass
class TemplateEntry:
    path: str           # 相對路徑，例如 src/main.py
    is_dir: bool = False
    content: str = ""   # 檔案初始內容（目錄忽略此欄）


@dataclass
class ProjectTemplate:
    name: str
    description: str
    category: str
    entries: list[TemplateEntry] = field(default_factory=list)
    id: int = 0             # DB id；0 代表內建（未存入 DB）
    is_builtin: bool = False
    created_at: str = ""


# ── 內建模板 ─────────────────────────────────────────────────

def _e(path: str, content: str = "") -> TemplateEntry:
    return TemplateEntry(path=path, is_dir=False, content=content)

def _d(path: str) -> TemplateEntry:
    return TemplateEntry(path=path, is_dir=True)


BUILTIN_TEMPLATES: list[ProjectTemplate] = [

    ProjectTemplate(
        name="Python 套件",
        description="標準 Python 套件結構（src layout）",
        category="python",
        is_builtin=True,
        entries=[
            _d("src"),
            _d("src/mypackage"),
            _e("src/mypackage/__init__.py", '"""My package."""\n'),
            _e("src/mypackage/main.py",
               'def main():\n    print("Hello, world!")\n\n\nif __name__ == "__main__":\n    main()\n'),
            _d("tests"),
            _e("tests/__init__.py"),
            _e("tests/test_main.py",
               'from mypackage.main import main\n\n\ndef test_main():\n    main()\n'),
            _e("pyproject.toml",
               '[project]\nname = "mypackage"\nversion = "0.1.0"\n\n[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.backends.legacy:build"\n'),
            _e("README.md", "# My Package\n\n> TODO: 專案說明\n"),
            _e(".gitignore",
               "__pycache__/\n*.pyc\ndist/\nbuild/\n*.egg-info/\n.venv/\n"),
        ],
    ),

    ProjectTemplate(
        name="Web（HTML/CSS/JS）",
        description="靜態網站基本結構",
        category="web",
        is_builtin=True,
        entries=[
            _d("css"),
            _d("js"),
            _d("assets"),
            _e("index.html",
               '<!DOCTYPE html>\n<html lang="zh-Hant">\n<head>\n'
               '  <meta charset="UTF-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
               '  <title>My Site</title>\n  <link rel="stylesheet" href="css/style.css">\n</head>\n'
               '<body>\n  <h1>Hello, World!</h1>\n  <script src="js/main.js"></script>\n</body>\n</html>\n'),
            _e("css/style.css",
               "* { box-sizing: border-box; margin: 0; padding: 0; }\nbody { font-family: sans-serif; padding: 1rem; }\n"),
            _e("js/main.js", '"use strict";\n\nconsole.log("Hello!");\n'),
            _e("README.md", "# My Web Project\n"),
        ],
    ),

    ProjectTemplate(
        name="Rust 應用程式",
        description="Cargo 基本專案結構",
        category="rust",
        is_builtin=True,
        entries=[
            _d("src"),
            _e("src/main.rs", 'fn main() {\n    println!("Hello, world!");\n}\n'),
            _e("Cargo.toml",
               '[package]\nname = "my_app"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n'),
            _e(".gitignore", "/target\n"),
            _e("README.md", "# My Rust App\n"),
        ],
    ),

    ProjectTemplate(
        name="Unity 專案",
        description="Unity 版本控制推薦的基本結構",
        category="unity",
        is_builtin=True,
        entries=[
            _d("Assets"),
            _d("Assets/Scripts"),
            _d("Assets/Scenes"),
            _d("Assets/Prefabs"),
            _d("Assets/Materials"),
            _d("Assets/Textures"),
            _d("Assets/Audio"),
            _d("ProjectSettings"),
            _d("Packages"),
            _e(".gitignore",
               "[Ll]ibrary/\n[Tt]emp/\n[Oo]bj/\n[Bb]uild/\n[Bb]uilds/\n[Ll]ogs/\n"
               "[Uu]ser[Ss]ettings/\n*.pidb\n*.suo\n*.userprefs\n"),
            _e("README.md", "# My Unity Project\n"),
        ],
    ),

    ProjectTemplate(
        name="Node.js 應用程式",
        description="基本 Node.js / npm 專案結構",
        category="nodejs",
        is_builtin=True,
        entries=[
            _d("src"),
            _e("src/index.js", '"use strict";\n\nconsole.log("Hello!");\n'),
            _e("package.json",
               '{\n  "name": "my-app",\n  "version": "1.0.0",\n'
               '  "main": "src/index.js",\n  "scripts": {\n    "start": "node src/index.js"\n  }\n}\n'),
            _e(".gitignore", "node_modules/\ndist/\n.env\n"),
            _e("README.md", "# My Node.js App\n"),
        ],
    ),

    ProjectTemplate(
        name="空白專案",
        description="只有 README 與 .gitignore",
        category="general",
        is_builtin=True,
        entries=[
            _e("README.md", "# My Project\n"),
            _e(".gitignore", ""),
        ],
    ),
]


def get_builtin_templates() -> list[ProjectTemplate]:
    return list(BUILTIN_TEMPLATES)
