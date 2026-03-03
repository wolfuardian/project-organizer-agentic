"""搜尋服務 — 搜尋 + 過濾 + 模糊跳轉。"""

from typing import Optional

from domain.services.fuzzy_match import fuzzy_filter


class SearchService:
    """注入 NodeRepo。"""

    def __init__(self, node_repo):
        self._nodes = node_repo

    def search_nodes(self, query: str,
                     project_ids: Optional[list[int]] = None,
                     limit: int = 200):
        return self._nodes.search_nodes(query, project_ids, limit)

    def filter_nodes(self, **kwargs):
        return self._nodes.filter_nodes(**kwargs)

    @staticmethod
    def fuzzy_filter(pattern: str, items: list[dict],
                     key: str = "name", limit: int = 50) -> list[dict]:
        return fuzzy_filter(pattern, items, key, limit)
