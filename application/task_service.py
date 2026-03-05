"""任務服務 — Todo + Relation 薄層轉發。"""

from typing import Optional


class TaskService:
    """注入 TodoRepo, RelationRepo。"""

    def __init__(self, todo_repo, relation_repo):
        self._todos = todo_repo
        self._relations = relation_repo

    # ── Todo ──────────────────────────────────────────────

    def list_todos(self, project_id: int):
        return self._todos.list_todos(project_id)

    def add_todo(self, project_id: int, title: str,
                 priority: int = 0,
                 due_date: Optional[str] = None) -> int:
        return self._todos.add_todo(project_id, title, priority, due_date)

    def toggle_todo(self, todo_id: int) -> None:
        self._todos.toggle_todo(todo_id)

    def delete_todo(self, todo_id: int) -> None:
        self._todos.delete_todo(todo_id)

    def get_timeline(self):
        return self._todos.get_timeline()

    # ── Relation ──────────────────────────────────────────

    def list_relations(self, project_id: int):
        return self._relations.list_relations(project_id)

    def add_relation(self, source_id: int, target_id: int,
                     relation_type: str, note: str = "") -> None:
        self._relations.add_relation(source_id, target_id, relation_type, note)

    def delete_relation(self, relation_id: int) -> None:
        self._relations.delete_relation(relation_id)
