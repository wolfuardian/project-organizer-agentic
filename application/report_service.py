"""報告服務 — Markdown / HTML 匯出。搬自 report_exporter.py。"""

from __future__ import annotations

import html
import sqlite3
from datetime import datetime
from pathlib import Path

from domain.enums import PROGRESS_LABELS
from domain.services.classification import category_label


class ReportService:
    """注入 ProjectRepo, NodeRepo, TagRepo, TodoRepo。"""

    def __init__(self, project_repo, node_repo, tag_repo, todo_repo):
        self._projects = project_repo
        self._nodes = node_repo
        self._tags = tag_repo
        self._todos = todo_repo

    def _fetch_project(self, conn: sqlite3.Connection,
                       project_id: int) -> dict:
        row = conn.execute(
            "SELECT * FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        return dict(row) if row else {}

    def _collect_nodes(self, conn: sqlite3.Connection,
                       project_id: int,
                       parent_id=None, depth: int = 0) -> list[dict]:
        rows = self._nodes.get_children(project_id, parent_id)
        result = []
        for row in rows:
            d = dict(row)
            d["depth"] = depth
            tags = self._tags.get_node_tags(row["id"])
            d["tags"] = [t["name"] for t in tags]
            result.append(d)
            if row["node_type"] in ("folder", "virtual"):
                result.extend(
                    self._collect_nodes(conn, project_id, row["id"], depth + 1))
        return result

    def export_markdown(self, conn: sqlite3.Connection,
                        project_id: int) -> str:
        proj = self._fetch_project(conn, project_id)
        if not proj:
            return "# 找不到專案\n"

        lines: list[str] = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        progress = PROGRESS_LABELS.get(
            proj.get("progress", "active"), "進行中")

        lines.append(f"# {proj['name']}")
        lines.append("")
        if proj.get("description"):
            lines.append(f"> {proj['description']}")
            lines.append("")
        lines.append(f"- **狀態**：{progress}")
        lines.append(f"- **根目錄**：`{proj.get('root_path', '')}`")
        lines.append(f"- **建立時間**：{proj.get('created_at', '')[:16].replace('T', ' ')}")
        lines.append(f"- **匯出時間**：{now}")
        lines.append("")

        todos = conn.execute(
            "SELECT * FROM todos WHERE project_id=? ORDER BY sort_order, id",
            (project_id,)
        ).fetchall()
        if todos:
            lines.append("## 待辦事項")
            lines.append("")
            for t in todos:
                check = "x" if t["done"] else " "
                lines.append(f"- [{check}] {t['content']}")
            lines.append("")

        nodes = self._collect_nodes(conn, project_id)
        if nodes:
            lines.append("## 檔案結構")
            lines.append("")
            lines.append("```")
            for n in nodes:
                indent = "  " * n["depth"]
                icon = "📁" if n["node_type"] in ("folder", "virtual") else "📄"
                pin = "📌 " if n["pinned"] else ""
                tag_str = (f"  [{', '.join(n['tags'])}]"
                           if n["tags"] else "")
                lines.append(
                    f"{indent}{icon} {pin}{n['name']}{tag_str}")
            lines.append("```")
            lines.append("")

        file_nodes = [n for n in nodes if n["node_type"] == "file"]
        if file_nodes:
            lines.append("## 統計")
            lines.append("")
            lines.append(f"- 檔案總數：{len(file_nodes)}")
            cats: dict[str, int] = {}
            for n in file_nodes:
                c = n.get("category") or "other"
                cats[c] = cats.get(c, 0) + 1
            for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
                lines.append(f"  - {category_label(cat)}：{count}")
            lines.append("")

        return "\n".join(lines)

    def export_html(self, conn: sqlite3.Connection,
                    project_id: int) -> str:
        proj = self._fetch_project(conn, project_id)
        if not proj:
            return "<p>找不到專案</p>"

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        progress = PROGRESS_LABELS.get(
            proj.get("progress", "active"), "進行中")
        title = html.escape(proj["name"])

        nodes = self._collect_nodes(conn, project_id)
        file_nodes = [n for n in nodes if n["node_type"] == "file"]

        def h(s: str) -> str:
            return html.escape(str(s))

        cats: dict[str, int] = {}
        for n in file_nodes:
            c = n.get("category") or "other"
            cats[c] = cats.get(c, 0) + 1
        stats_rows = "".join(
            f"<tr><td>{h(category_label(c))}</td><td>{cnt}</td></tr>"
            for c, cnt in sorted(cats.items(), key=lambda x: -x[1])
        )

        todos = conn.execute(
            "SELECT * FROM todos WHERE project_id=? ORDER BY sort_order, id",
            (project_id,)
        ).fetchall()
        todo_html = ""
        if todos:
            items = "".join(
                f'<li class="{"done" if t["done"] else ""}">'
                f'{"✔" if t["done"] else "○"} {h(t["content"])}</li>'
                for t in todos
            )
            todo_html = f"<h2>待辦事項</h2><ul class='todos'>{items}</ul>"

        tree_items = ""
        for n in nodes:
            indent = n["depth"] * 20
            icon = "📁" if n["node_type"] in ("folder", "virtual") else "📄"
            pin = "📌 " if n["pinned"] else ""
            tags = " ".join(
                f'<span class="tag">{h(t)}</span>' for t in n["tags"])
            tree_items += (
                f'<div class="node" style="margin-left:{indent}px">'
                f'{icon} {pin}{h(n["name"])} {tags}</div>\n'
            )

        return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>{title} — 專案報告</title>
<style>
  body {{ font-family: sans-serif; max-width: 900px; margin: 2em auto;
         color: #cdd6f4; background: #1e1e2e; }}
  h1   {{ color: #cba6f7; }}
  h2   {{ color: #89b4fa; border-bottom: 1px solid #45475a; padding-bottom: .3em; }}
  table{{ border-collapse: collapse; width: 100%; }}
  td,th{{ border: 1px solid #45475a; padding: .4em .8em; }}
  th   {{ background: #313244; }}
  .node{{ padding: 2px 0; font-family: monospace; }}
  .tag {{ background: #45475a; border-radius: 4px; padding: 1px 5px;
          font-size: .85em; margin-left: 4px; }}
  .todos li      {{ list-style: none; padding: 2px 0; }}
  .todos li.done {{ opacity: .6; text-decoration: line-through; }}
  .meta td        {{ border: none; padding: 2px 8px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<table class="meta">
  <tr><td>狀態</td><td>{h(progress)}</td></tr>
  <tr><td>根目錄</td><td><code>{h(proj.get('root_path',''))}</code></td></tr>
  <tr><td>建立時間</td><td>{h(proj.get('created_at','')[:16].replace('T',' '))}</td></tr>
  <tr><td>匯出時間</td><td>{h(now)}</td></tr>
</table>
{f'<p>{h(proj["description"])}</p>' if proj.get("description") else ""}

{todo_html}

<h2>檔案結構</h2>
<div class="tree">{tree_items}</div>

<h2>統計</h2>
<p>檔案總數：{len(file_nodes)}</p>
<table>
  <tr><th>分類</th><th>數量</th></tr>
  {stats_rows}
</table>

</body>
</html>
"""

    @staticmethod
    def save_report(content: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
