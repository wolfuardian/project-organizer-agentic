"""檔案樹模型 — QAbstractItemModel backed by SQLite, 支援拖拉排序."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Callable, Optional

from PySide6.QtCore import (
    QAbstractItemModel, QModelIndex, Qt, QMimeData, QByteArray,
)
from PySide6.QtGui import QIcon, QColor, QFont

from domain.services.classification import category_label
from domain.services.virtual_tree import VNodeStatus
from presentation.file_icons import get_category_icon
from database import (
    get_children, move_node, get_node_tags, list_project_roots,
    get_tags_for_nodes,
)
from infrastructure.repositories.node_repo import SqliteNodeRepository
from infrastructure.repositories.tag_repo import SqliteTagRepository


# ── 欄位格式化 ────────────────────────────────────────────

def format_file_size(size: int | None) -> str:
    """將位元組數格式化為人類可讀的大小字串。"""
    if size is None:
        return ""
    if size < 1024:
        return f"{size} B"
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
    return ""


def format_relative_time(iso_str: str | None) -> str:
    """將 ISO 時間字串格式化為相對時間（繁體中文）。"""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return ""
    delta = datetime.now() - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "剛剛"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} 分鐘前"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} 小時前"
    days = delta.days
    if days == 1:
        return "昨天"
    if days < 7:
        return f"{days} 天前"
    weeks = days // 7
    if weeks < 4:
        return f"{weeks} 週前"
    months = days // 30
    if months < 12:
        return f"{months} 個月前"
    years = days // 365
    return f"{years} 年前"


class TreeNode:
    """記憶體中的樹節點快取."""

    __slots__ = ("db_id", "name", "rel_path", "node_type", "pinned",
                 "parent", "children", "row", "loaded",
                 "file_size", "modified_at", "category",
                 "root_id", "is_root_group", "_tags_cache",
                 "_time_display")

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
        self._tags_cache: Optional[list] = None
        self._time_display: str = ""


def setup_tree_header(header) -> None:
    """設定三欄 QHeaderView 的 resize 模式（名稱 stretch、大小/時間 fit）。"""
    from PySide6.QtWidgets import QHeaderView
    header.setStretchLastSection(False)
    header.setSectionResizeMode(0, QHeaderView.Stretch)
    header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeToContents)


MIME_TYPE = "application/x-project-organizer-node"


# 虛擬模式狀態 → 前景色
_VSTATUS_COLORS: dict[VNodeStatus, str] = {
    VNodeStatus.MOVED:   "#89b4fa",   # blue
    VNodeStatus.DELETED: "#f38ba8",   # red
    VNodeStatus.ADDED:   "#a6e3a1",   # green
    VNodeStatus.RENAMED: "#f9e2af",   # yellow
}


_ROLE_LABELS: dict[str, str] = {
    "proj":   "proj",
    "source": "source",
    "assets": "assets",
    "docs":   "docs",
    "output": "output",
    "misc":   "misc",
}


class ProjectTreeModel(QAbstractItemModel):
    """可拖拉的專案檔案樹模型."""

    # ── 預建快取常量（所有實例共用，避免 data() 每次 paint 分配物件）──
    _font_normal: QFont | None = None
    _font_bold: QFont | None = None
    _font_italic: QFont | None = None
    _font_bold_italic: QFont | None = None
    _color_cache: dict[str, QColor] = {}

    @classmethod
    def _init_font_cache(cls) -> None:
        if cls._font_normal is not None:
            return
        cls._font_normal = QFont()
        cls._font_bold = QFont()
        cls._font_bold.setBold(True)
        cls._font_italic = QFont()
        cls._font_italic.setItalic(True)
        cls._font_bold_italic = QFont()
        cls._font_bold_italic.setBold(True)
        cls._font_bold_italic.setItalic(True)

    @classmethod
    def _cached_color(cls, hex_color: str) -> QColor:
        c = cls._color_cache.get(hex_color)
        if c is None:
            c = QColor(hex_color)
            cls._color_cache[hex_color] = c
        return c

    # ── QIcon 快取（instance-level，避免 standardIcon 每次 paint 呼叫，
    #    且主題切換時會建新 model 自動刷新）──

    def __init__(self, conn: sqlite3.Connection, project_id: int, parent=None, root_id: int | None = None):
        super().__init__(parent)
        self._init_font_cache()
        self._icon_folder = get_category_icon("folder")
        self._icon_virtual = get_category_icon("virtual")
        self._icon_drive = get_category_icon("drive")
        self._conn = conn
        self._project_id = project_id
        self._root_id = root_id
        self._node_repo = SqliteNodeRepository(conn)
        self._tag_repo = SqliteTagRepository(conn)
        self._multi_root = False
        self._node_map: dict[int, TreeNode] = {}  # db_id → TreeNode 快速查找
        self._path_map: dict[str, TreeNode] = {}  # rel_path → TreeNode 快速查找
        self._virtual_status: dict[str, VNodeStatus] = {}  # rel_path → status
        self._virtual_added: list[str] = []  # 虛擬模式注入節點的路徑（按深度序）
        self._on_drop: Callable | None = None  # 虛擬模式 drop 攔截回呼
        self._root = TreeNode(db_id=0, name="ROOT", rel_path="",
                              node_type="folder", pinned=False)
        self._build_top_level()

    def set_virtual_status(self, mapping: dict[str, VNodeStatus]) -> None:
        """設定虛擬模式狀態疊加（用於著色）。只通知有變更的節點。"""
        old = self._virtual_status
        self._virtual_status = mapping
        # 找出有變化的 rel_path
        changed_paths = set()
        for path in set(old) | set(mapping):
            if old.get(path) != mapping.get(path):
                changed_paths.add(path)
        if not changed_paths:
            return
        # 精確通知有變更的節點（透過 _path_map O(1) 查找）
        cols = self.columnCount() - 1
        for path in changed_paths:
            node = self._path_map.get(path)
            if node:
                idx = self.createIndex(node.row, 0, node)
                idx_end = self.createIndex(node.row, cols, node)
                self.dataChanged.emit(idx, idx_end)

    # ── 虛擬模式樹結構更新 ─────────────────────────────────

    def apply_virtual_tree(self, resolved: list[dict]) -> None:
        """套用虛擬樹：注入 ADDED 節點 + 更新狀態著色。"""
        self._clear_virtual_nodes()

        status_map: dict[str, VNodeStatus] = {}
        added: list[dict] = []
        for n in resolved:
            st = n["status"]
            if st != VNodeStatus.UNCHANGED:
                status_map[n["path"]] = st
            if st == VNodeStatus.ADDED and n.get("path"):
                added.append(n)

        # 按深度排序，確保父節點先建立
        added.sort(key=lambda n: n["path"].count("/") + n["path"].count("\\"))

        for n in added:
            path = n["path"]
            if path in self._path_map:
                continue
            sep = max(path.rfind("/"), path.rfind("\\"))
            if sep >= 0:
                parent_path, name = path[:sep], path[sep + 1:]
            else:
                parent_path, name = "", path
            parent_node = (self._path_map.get(parent_path, self._root)
                           if parent_path else self._root)
            parent_idx = (self.createIndex(parent_node.row, 0, parent_node)
                          if parent_node is not self._root else QModelIndex())
            row = len(parent_node.children)

            self.beginInsertRows(parent_idx, row, row)
            vnode = TreeNode(
                db_id=0, name=name, rel_path=path,
                node_type=n.get("node_type", "folder"),
                pinned=False, parent=parent_node, row=row,
            )
            vnode.loaded = True
            vnode._tags_cache = []
            vnode._time_display = ""
            parent_node.children.append(vnode)
            self._path_map[path] = vnode
            self._virtual_added.append(path)
            self.endInsertRows()

        self.set_virtual_status(status_map)

    def clear_virtual_tree(self) -> None:
        """清除虛擬節點和狀態著色。"""
        self._clear_virtual_nodes()
        self.set_virtual_status({})

    def _clear_virtual_nodes(self) -> None:
        """移除先前注入的虛擬 ADDED 節點（深層先移除）。"""
        for path in reversed(self._virtual_added):
            node = self._path_map.get(path)
            if not node or not node.parent:
                continue
            parent = node.parent
            parent_idx = (self.createIndex(parent.row, 0, parent)
                          if parent is not self._root else QModelIndex())
            row = node.row
            self.beginRemoveRows(parent_idx, row, row)
            parent.children.pop(row)
            for i in range(row, len(parent.children)):
                parent.children[i].row = i
            del self._path_map[path]
            self.endRemoveRows()
        self._virtual_added.clear()

    def set_on_drop(self, callback: Callable | None) -> None:
        """設定 drop 攔截回呼。若設定，dropMimeData 改為呼叫此回呼。"""
        self._on_drop = callback

    def _build_top_level(self) -> None:
        """一次性全量載入：單一 SQL 查詢取得所有節點，在記憶體中組裝樹。"""
        self._node_map.clear()
        self._path_map.clear()
        self._root.children = []
        self._root.loaded = True

        if self._root_id:
            # Single-root mode: only load nodes for this root
            all_rows = self._conn.execute(
                "SELECT * FROM nodes WHERE project_id=? AND root_id=? "
                "ORDER BY node_type='file', pinned DESC, sort_order, name",
                (self._project_id, self._root_id),
            ).fetchall()
            self._multi_root = False
        else:
            # Legacy full-load mode
            roots = list_project_roots(self._conn, self._project_id)
            self._multi_root = len(roots) > 1
            all_rows = self._conn.execute(
                "SELECT * FROM nodes WHERE project_id=? "
                "ORDER BY node_type='file', pinned DESC, sort_order, name",
                (self._project_id,),
            ).fetchall()

        # 建立 db_id → TreeNode 映射（先建所有節點，再建父子關係）
        id_to_node: dict[int, TreeNode] = {}
        for row in all_rows:
            # 預計算相對時間字串，避免 data() 每次呼叫 datetime.now()
            mod_str = row["modified_at"]
            node = TreeNode(
                db_id=row["id"],
                name=row["name"],
                rel_path=row["rel_path"],
                node_type=row["node_type"],
                pinned=bool(row["pinned"]),
                file_size=row["file_size"],
                modified_at=mod_str,
                category=row["category"],
                root_id=row["root_id"] if "root_id" in row.keys() else None,
            )
            # 預計算相對時間快取
            node._time_display = format_relative_time(mod_str)
            id_to_node[node.db_id] = node
            self._node_map[node.db_id] = node
            if node.rel_path:
                self._path_map[node.rel_path] = node

        # 多根分組：建立虛擬根群組節點
        # 使用負數 db_id 避免與 nodes.id 衝突（兩者各有獨立 AUTOINCREMENT）
        root_groups: dict[int, TreeNode] = {}  # project_roots.id → group node
        if self._multi_root:
            for i, r in enumerate(roots):
                label = r["label"] or _ROLE_LABELS.get(r["role"], r["role"])
                group = TreeNode(
                    db_id=-r["id"],
                    name=f"[{label}]  {r['root_path']}",
                    rel_path="",
                    node_type="folder",
                    pinned=False,
                    parent=self._root,
                    row=i,
                    root_id=r["id"],
                    is_root_group=True,
                )
                group.loaded = True
                self._root.children.append(group)
                self._node_map[-r["id"]] = group
                root_groups[r["id"]] = group

        # 組裝父子關係
        orphans: list[TreeNode] = []  # parent_id=NULL 的頂層節點
        for row in all_rows:
            node = id_to_node[row["id"]]
            parent_id = row["parent_id"]
            if parent_id is not None and parent_id in id_to_node:
                node.parent = id_to_node[parent_id]
            elif self._multi_root and node.root_id and node.root_id in root_groups:
                node.parent = root_groups[node.root_id]
            else:
                orphans.append(node)

        # 將子節點加入父節點的 children 列表
        for node in id_to_node.values():
            if node.parent is not None:
                node.parent.children.append(node)

        # 頂層孤兒（parent_id=NULL 且無法匹配 root_group）：掛到根
        for node in orphans:
            node.parent = self._root
            self._root.children.append(node)

        # 設定所有節點的 row 索引和 loaded 狀態
        self._finalize_children(self._root)

        # 批次載入所有標籤（單一查詢）
        all_ids = list(id_to_node.keys())
        if all_ids:
            tags_map = self._tag_repo.get_tags_for_nodes(all_ids)
            for nid, node in id_to_node.items():
                node._tags_cache = tags_map.get(nid, [])

    def _finalize_children(self, node: TreeNode) -> None:
        """遞迴設定子節點的 row 索引和 loaded 狀態。"""
        for i, child in enumerate(node.children):
            child.row = i
            child.loaded = True
            if child.children:
                self._finalize_children(child)

    def refresh(self) -> None:
        self.beginResetModel()
        self._virtual_added.clear()
        self._virtual_status.clear()
        self._build_top_level()
        self.endResetModel()

    # ── QAbstractItemModel 必要實作 ──────────────────────

    def index(self, row: int, column: int,
              parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent_node = parent.internalPointer() if parent.isValid() else self._root
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
        return len(node.children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 3

    def headerData(self, section: int, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return ("名稱", "大小", "修改時間")[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        node: TreeNode = index.internalPointer()
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                prefix = "[pin] " if node.pinned else ""
                return f"{prefix}{node.name}"
            if col == 1:
                if node.node_type == "file" and node.file_size is not None:
                    return format_file_size(node.file_size)
                return ""
            if col == 2:
                return node._time_display

        if role == Qt.TextAlignmentRole:
            if col in (1, 2):
                return int(Qt.AlignRight | Qt.AlignVCenter)

        # 以下 role 僅適用 column 0
        if col != 0:
            return None

        if role == Qt.DecorationRole:
            if node.is_root_group:
                return self._icon_drive
            if node.node_type == "folder":
                return self._icon_folder
            if node.node_type == "virtual":
                return self._icon_virtual
            return get_category_icon(node.category or "other")

        if role == Qt.ToolTipRole:
            parts = [node.rel_path]
            if node.category:
                parts.append(category_label(node.category))
            return "  |  ".join(parts)

        if role == Qt.ForegroundRole:
            # 虛擬模式狀態覆蓋
            vstatus = self._virtual_status.get(node.rel_path)
            if vstatus and vstatus in _VSTATUS_COLORS:
                return self._cached_color(_VSTATUS_COLORS[vstatus])
            if node.node_type in ("folder", "virtual"):
                hex_c = "#5fd7ff"
            else:
                hex_c = "#c8c8c8"  # 檔案統一淺灰（類型已由圖示區分）
            if node.name.startswith("."):
                dark_key = hex_c + "_dark"
                c = self._color_cache.get(dark_key)
                if c is None:
                    c = QColor(hex_c).darker(170)
                    self._color_cache[dark_key] = c
                return c
            return self._cached_color(hex_c)

        if role == Qt.FontRole:
            is_folder = node.node_type in ("folder", "virtual")
            is_hidden = node.name.startswith(".")
            if is_folder and is_hidden:
                return self._font_bold_italic
            if is_folder:
                return self._font_bold
            if is_hidden:
                return self._font_italic
            return self._font_normal

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
        """回傳 True 若 target_id 是 node_id 本身或其後代（防止循環拖放）。
        優先使用記憶體中的 parent 指標向上走，避免 N+1 SQL 查詢。"""
        if target_id is None:
            return False
        # 先嘗試用記憶體中的 _node_map 走 parent chain
        target_node = self._node_map.get(target_id)
        if target_node is not None:
            current = target_node
            while current is not None and current is not self._root:
                if current.db_id == node_id:
                    return True
                current = current.parent
            return False
        # fallback：從 DB 查（通常不會走到這裡）
        current_id = target_id
        while current_id is not None:
            if current_id == node_id:
                return True
            row = self._conn.execute(
                "SELECT parent_id FROM nodes WHERE id=?", (current_id,)
            ).fetchone()
            if row is None:
                break
            current_id = row["parent_id"]
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

        # 虛擬模式：委派給回呼
        if self._on_drop:
            sources = [self._node_map.get(nid) for nid in node_ids]
            self._on_drop(
                [s for s in sources if s is not None],
                target_node,
            )
            return True

        for i, nid in enumerate(node_ids):
            sort = row + i if row >= 0 else len(target_node.children) + i
            self._conn.execute(
                "UPDATE nodes SET parent_id=?, sort_order=? WHERE id=?",
                (new_parent_id, sort, nid),
            )
        self._conn.commit()
        self.refresh()
        return True
