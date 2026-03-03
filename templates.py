"""Shim — 轉發至新路徑，保持舊 import 不壞。"""

import sqlite3

from domain.models import ProjectTemplate, TemplateEntry  # noqa: F401
from application.template_service import (  # noqa: F401
    get_builtin_templates, BUILTIN_TEMPLATES,
    scaffold, project_to_template,
    export_template, import_template,
)
from infrastructure.repositories.template_repo import SqliteTemplateRepository


def init_templates_table(conn: sqlite3.Connection) -> None:
    SqliteTemplateRepository(conn).init_table()

def save_template(conn: sqlite3.Connection,
                  tmpl: ProjectTemplate) -> int:
    return SqliteTemplateRepository(conn).save_template(tmpl)

def list_templates(conn: sqlite3.Connection,
                   include_builtin: bool = True):
    return SqliteTemplateRepository(conn).list_templates(include_builtin)

def delete_template(conn: sqlite3.Connection,
                    template_id: int) -> None:
    SqliteTemplateRepository(conn).delete_template(template_id)
