"""檔案樹模型 — QAbstractItemModel backed by SQLite, 支援拖拉排序."""

from __future__ import annotations

import json
import sqlite3
from typing import Optional

from PySide6.QtCore import (
    QAbstractItemModel, QModelIndex, Qt, QMimeData, QByteArray,
)
from PySide6.QtGui import QIcon, QColor, QFont
from PySide6.QtWidgets import QStyle, QApplication

from domain.services.classification import category_label
from database import get_children, move_node, get_node_tags, list_project_roots


class TreeNode:
    """記憶體中的樹節點快取."""

    __slots__ = ("db_id", "name", "rel_path", "node_type", "pinned",
                 "parent", "children", "row", "loaded",
                 "file_size", "modified_at", "category",
                 "root_id", "is_root_group")

    def __init__(self, db_id: int, name: str, rel_path: str,
                 node_type: str, pinned: bool,
                 parent: Optional[TreeNode] = None, row: int = 0,
                 file_size: Optional[int] = None,
                 modified_at: Optional[str] = None,
                 category: Optional[str] = None,
                 root_id: Optional[int] = None,
                 is_root_group: bool = False):
        self.db_id = db_id
        self.name = name
        self.rel_path = rel_path
        self.node_type = node_type
        self.pinned = pinned
        self.parent = parent
        self.row = row
        self.children: list[TreeNode] = []
        self.loaded = False
        self.file_size = file_size
        self.modified_at = modified_at
        self.category = category
        self.root_id = root_id
        self.is_root_group = is_root_group


MIME_TYPE = "application/x-project-organizer-node"

# Ranger 風格：檔案類別 → 顏色（在深色背景上均清晰可辨）
_CAT_COLORS: dict[str, str] = {
    "image":    "#d787ff",   # 紫
    "video":    "#ff875f",   # 橘紅
    "audio":    "#ffaf00",   # 琥珀
    "code":     "#87ff87",   # 萊姆綠
    "document": "#ffffaf",   # 奶黃
    "archive":  "#ff8700",   # 橘
    "data":     "#afd7ff",   # 天藍
    "font":     "#d7afd7",   # 紫丁香
    "3d":       "#afffaf",   # 薄荷
}


_ROLE_ICONS: dict[str, str] = {
    "proj":   "📁",
    "source": "📂",
    "assets": "🎨",
    "docs":   "📝",
    "output": "📦",
    "misc":   "📎",
}


class ProjectTreeModel(QAbstractItemModel):
    """可拖拉的專案檔案樹模型."""

    def __init__(self, conn: sqlite3.Connection, project_id: int, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._project_id = project_id
        self._multi_root = False
        self._root = TreeNode(db_id=0, name="ROOT", rel_path="",
                              node_type="folder", pinned=False)
        self._build_top_level()

    def _build_top_level(self) -> None:
        """建構頂層：多根分組或單根直顯。"""
        roots = list_project_roots(self._conn, self._project_id)
        self._multi_root = len(roots) > 1
        if self._multi_root:
            self._root.children = []
            for i, r in enumerate(roots):
                role_icon = _ROLE_ICONS.get(r["role"], "📁")
                label = r["label"] or r["role"]
                group = TreeNode(
                    db_id=r["id"],
                    name=f"{role_icon} {label}  ({r['root_path']})",
                    rel_path="",
                    node_type="folder",
                    pinned=False,
                    parent=self._root,
                    row=i,
                    root_id=r["id"],
                    is_root_group=True,
                )
                self._root.children.append(group)
            self._root.loaded = True
        else:
            self._load_children(self._root, parent_id=None)

    # ── 資料載入 ─────────────────────────────────────────

    def _load_children(self, parent_node: TreeNode,
                       parent_id: Optional[int]) -> None:
        if parent_node.is_root_group:
            # 多根分組節點：載入該 root 下的頂層節點
            rows = self._conn.execute(
                "SELECT * FROM nodes WHERE project_id=? AND root_id=? "
                "AND parent_id IS NULL "
                "ORDER BY node_type='file', pinned DESC, sort_order, name",
                (self._project_id, parent_node.db_id),
            ).fetchall()
        else:
            rows = get_children(self._conn, self._project_id, parent_id)
        parent_node.children = []
        for i, row in enumerate(rows):
            child = TreeNode(
                db_id=row["id"],
                name=row["name"],
                rel_path=row["rel_path"],
                node_type=row["node_type"],
                pinned=bool(row["pinned"]),
                parent=parent_node,
                row=i,
                file_size=row["file_size"],
                modified_at=row["modified_at"],
                category=row["category"],
                root_id=row["root_id"] if "root_id" in row.keys() else None,
            )
            parent_node.children.append(child)
        parent_node.loaded = True

    def _ensure_loaded(self, node: TreeNode) -> None:
        if not node.loaded and node.node_type in ("folder", "virtual"):
            self._load_children(node, node.db_id)

    def refresh(self) -> None:
        self.beginResetModel()
        self._build_top_level()
        self.endResetModel()

    # ── QAbstractItemModel 必要實作 ──────────────────────

    def index(self, row: int, column: int,
              parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent_node = parent.internalPointer() if parent.isValid() else self._root
        self._ensure_loaded(parent_node)
        if row < len(parent_node.children):
            return self.createIndex(row, column, parent_node.children[row])
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        node: TreeNode = index.internalPointer()
        parent_node = node.parent
        if parent_node is None or parent_node is self._root:
            return QModelIndex()
        return self.createIndex(parent_node.row, 0, parent_node)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        node = parent.internalPointer() if parent.isValid() else self._root
        self._ensure_loaded(node)
        return len(node.children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        node: TreeNode = index.internalPointer()

        if role == Qt.DisplayRole:
            prefix = "📌 " if node.pinned else ""
            return f"{prefix}{node.name}"

        if role == Qt.DecorationRole:
            if node.is_root_group:
                return QApplication.style().standardIcon(QStyle.SP_DriveHDIcon)
            style = QApplication.style()
            if node.node_type == "folder":
                return style.standardIcon(QStyle.SP_DirIcon)
            elif node.node_type == "virtual":
                return style.standardIcon(QStyle.SP_DirLinkIcon)
            else:
                return style.standardIcon(QStyle.SP_FileIcon)

        if role == Qt.ToolTipRole:
            parts = [node.rel_path]
            if node.category:
                parts.append(category_label(node.category))
            if node.file_size is not None:
                if node.file_size >= 1_048_576:
                    parts.append(f"{node.file_size / 1_048_576:.1f} MB")
                elif node.file_size >= 1024:
                    parts.append(f"{node.file_size / 1024:.1f} KB")
                else:
                    parts.append(f"{node.file_size} B")
            if node.modified_at:
                parts.append(node.modified_at[:16].replace("T", " "))
            tags = get_node_tags(self._conn, node.db_id)
            if tags:
                parts.append("🏷 " + ", ".join(t["name"] for t in tags))
            return "  |  ".join(parts)

        if role == Qt.ForegroundRole:
            if node.node_type in ("folder", "virtual"):
                color = QColor("#5fd7ff")          # 資料夾：青藍
            else:
                hex_c = _CAT_COLORS.get(node.category or "", "#c8c8c8")
                color = QColor(hex_c)
            if node.name.startswith("."):
                color = color.darker(170)           # 隱藏檔自動暗化
            return color

        if role == Qt.FontRole:
            font = QFont()
            if node.node_type in ("folder", "virtual"):
                font.setBold(True)
            if node.name.startswith("."):
                font.setItalic(True)
            return font

        return None

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        node = parent.internalPointer() if parent.isValid() else self._root
        if node.node_type == "file":
            return False
        if node.loaded:
            return len(node.children) > 0
        return True  # 尚未載入，先回報有子項

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        default = super().flags(index)
        if index.isValid():
            return default | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        return default | Qt.ItemIsDropEnabled

    # ── 拖拉支援 ─────────────────────────────────────────

    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.MoveAction

    def mimeTypes(self) -> list[str]:
        return [MIME_TYPE]

    def mimeData(self, indexes: list[QModelIndex]) -> QMimeData:
        data = QMimeData()
        ids = [idx.internalPointer().db_id for idx in indexes if idx.isValid()]
        data.setData(MIME_TYPE, QByteArray(json.dumps(ids).encode()))
        return data

    def _is_ancestor_or_self(self, node_id: int,
                              target_id: Optional[int]) -> bool:
        """回傳 True 若 target_id 是 node_id 本身或其後代（防止循環拖放）."""
        current = target_id
        while current is not None:
            if current == node_id:
                return True
            row = self._conn.execute(
                "SELECT parent_id FROM nodes WHERE id=?", (current,)
            ).fetchone()
            if row is None:
                break
            current = row["parent_id"]
        return False

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction,
                     row: int, column: int,
                     parent: QModelIndex) -> bool:
        if action != Qt.MoveAction:
            return False
        if not data.hasFormat(MIME_TYPE):
            return False

        raw = bytes(data.data(MIME_TYPE)).decode()
        node_ids: list[int] = json.loads(raw)

        target_node = parent.internalPointer() if parent.isValid() else self._root
        new_parent_id = target_node.db_id if target_node is not self._root else None

        # 不允許把資料夾拖進自己或自己的後代
        for nid in node_ids:
            if self._is_ancestor_or_self(nid, new_parent_id):
                return False

        for i, nid in enumerate(node_ids):
            sort = row + i if row >= 0 else len(target_node.children) + i
            move_node(self._conn, nid, new_parent_id, sort)

        self.refresh()
        return True
