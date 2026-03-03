"""標籤服務 — 薄層轉發。"""

from typing import Optional


class TagService:
    """注入 TagRepo。"""

    def __init__(self, tag_repo):
        self._tags = tag_repo

    def list_tags(self, parent_id: Optional[int] = None):
        return self._tags.list_tags(parent_id)

    def all_tags_flat(self):
        return self._tags.all_tags_flat()

    def create_tag(self, name: str, color: str = "#89b4fa",
                   parent_id: Optional[int] = None) -> int:
        return self._tags.create_tag(name, color, parent_id)

    def update_tag(self, tag_id: int, name: str, color: str) -> None:
        self._tags.update_tag(tag_id, name, color)

    def delete_tag(self, tag_id: int) -> None:
        self._tags.delete_tag(tag_id)

    def get_node_tags(self, node_id: int):
        return self._tags.get_node_tags(node_id)

    def add_node_tag(self, node_id: int, tag_id: int) -> None:
        self._tags.add_node_tag(node_id, tag_id)

    def remove_node_tag(self, node_id: int, tag_id: int) -> None:
        self._tags.remove_node_tag(node_id, tag_id)
