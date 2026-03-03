"""模板服務 — scaffold / extract / export / import。搬自 templates.py。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from domain.enums import IGNORE_DIRS
from domain.models import ProjectTemplate, TemplateEntry


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


# ── Scaffold ─────────────────────────────────────────────────

def scaffold(tmpl: ProjectTemplate, target: Path) -> tuple[int, list[str]]:
    target.mkdir(parents=True, exist_ok=True)
    created = 0
    errors: list[str] = []

    dirs  = [e for e in tmpl.entries if e.is_dir]
    files = [e for e in tmpl.entries if not e.is_dir]

    for entry in dirs + files:
        path = target / entry.path
        try:
            if entry.is_dir:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_text(entry.content, encoding="utf-8")
                    created += 1
        except OSError as e:
            errors.append(f"{entry.path}: {e}")

    return created, errors


# ── 從現有專案反推模板 ───────────────────────────────────────

_TEXT_EXTS = {
    ".py", ".js", ".ts", ".html", ".css", ".md", ".txt", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".rs", ".go", ".java",
    ".c", ".cpp", ".h", ".cs", ".sh", ".bat", ".gitignore",
}

_CONTENT_SIZE_LIMIT = 8 * 1024


def project_to_template(
    root: Path,
    name: str,
    description: str = "",
    category: str = "general",
    ignore_dirs: Optional[set[str]] = None,
    max_depth: int = 4,
) -> ProjectTemplate:
    if ignore_dirs is None:
        ignore_dirs = IGNORE_DIRS

    entries: list[TemplateEntry] = []

    def _walk(current: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            items = sorted(current.iterdir(),
                           key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return
        for item in items:
            rel = str(item.relative_to(root))
            if item.is_dir():
                if item.name in ignore_dirs:
                    continue
                entries.append(TemplateEntry(path=rel, is_dir=True))
                _walk(item, depth + 1)
            elif item.is_file():
                content = ""
                try:
                    if (item.suffix.lower() in _TEXT_EXTS
                            and item.stat().st_size <= _CONTENT_SIZE_LIMIT):
                        content = item.read_text(encoding="utf-8",
                                                 errors="replace")
                except OSError:
                    pass
                entries.append(TemplateEntry(path=rel, is_dir=False,
                                             content=content))

    _walk(root, 0)
    return ProjectTemplate(
        name=name,
        description=description,
        category=category,
        entries=entries,
    )


# ── JSON 匯出 / 匯入 ─────────────────────────────────────────

def export_template(tmpl: ProjectTemplate) -> str:
    data = {
        "name":        tmpl.name,
        "description": tmpl.description,
        "category":    tmpl.category,
        "entries": [
            {"path": e.path, "is_dir": e.is_dir, "content": e.content}
            for e in tmpl.entries
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def import_template(json_str: str) -> ProjectTemplate:
    try:
        data = json.loads(json_str)
        entries = [
            TemplateEntry(
                path=e["path"],
                is_dir=bool(e.get("is_dir", False)),
                content=e.get("content", ""),
            )
            for e in data.get("entries", [])
        ]
        return ProjectTemplate(
            name=data["name"],
            description=data.get("description", ""),
            category=data.get("category", "general"),
            entries=entries,
        )
    except (KeyError, TypeError, json.JSONDecodeError) as e:
        raise ValueError(f"無效的模板格式：{e}") from e


class TemplateService:
    """注入 TemplateRepo。"""

    def __init__(self, template_repo):
        self._repo = template_repo

    def init_table(self) -> None:
        self._repo.init_table()

    def save_template(self, tmpl: ProjectTemplate) -> int:
        return self._repo.save_template(tmpl)

    def list_templates(self, include_builtin: bool = True):
        return self._repo.list_templates(include_builtin)

    def delete_template(self, template_id: int) -> None:
        self._repo.delete_template(template_id)

    def get_builtin_templates(self) -> list[ProjectTemplate]:
        return get_builtin_templates()

    def scaffold(self, tmpl: ProjectTemplate,
                 target: Path) -> tuple[int, list[str]]:
        return scaffold(tmpl, target)

    def export_template(self, tmpl: ProjectTemplate) -> str:
        return export_template(tmpl)

    def import_template(self, json_str: str) -> ProjectTemplate:
        return import_template(json_str)

    def project_to_template(self, root: Path, name: str,
                            **kwargs) -> ProjectTemplate:
        return project_to_template(root, name, **kwargs)
