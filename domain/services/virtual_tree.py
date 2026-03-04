"""VirtualTree — 將 Command 套用到 flat snapshot，產生帶狀態的節點清單。"""

from __future__ import annotations

from enum import Enum, auto

from domain.models import Command


class VNodeStatus(Enum):
    UNCHANGED = auto()
    MOVED = auto()
    DELETED = auto()
    ADDED = auto()
    RENAMED = auto()


class VirtualTree:
    """純函式式：給定 snapshot + commands，resolve() 回傳標注過的節點清單。"""

    def __init__(self, snapshot: list[dict], commands: list[Command]) -> None:
        self._snapshot = snapshot
        self._commands = commands

    def resolve(self) -> list[dict]:
        # 複製 snapshot，標記為 UNCHANGED
        nodes = [
            {**n, "status": VNodeStatus.UNCHANGED}
            for n in self._snapshot
        ]
        # 建立 path → index 對應（用於快速查找）
        path_idx: dict[str, int] = {n["path"]: i for i, n in enumerate(nodes)}

        for cmd in self._commands:
            if cmd.op == "delete":
                if cmd.source in path_idx:
                    nodes[path_idx[cmd.source]]["status"] = VNodeStatus.DELETED

            elif cmd.op == "move":
                if cmd.source in path_idx:
                    nodes[path_idx[cmd.source]]["status"] = VNodeStatus.MOVED
                if cmd.dest:
                    src = nodes[path_idx[cmd.source]] if cmd.source in path_idx else {}
                    new_node = {
                        "path": cmd.dest,
                        "node_type": src.get("node_type", "file"),
                        "status": VNodeStatus.ADDED,
                    }
                    path_idx[cmd.dest] = len(nodes)
                    nodes.append(new_node)

            elif cmd.op == "rename":
                if cmd.source in path_idx:
                    nodes[path_idx[cmd.source]]["status"] = VNodeStatus.RENAMED
                if cmd.dest:
                    src = nodes[path_idx[cmd.source]] if cmd.source in path_idx else {}
                    new_node = {
                        "path": cmd.dest,
                        "node_type": src.get("node_type", "file"),
                        "status": VNodeStatus.ADDED,
                    }
                    path_idx[cmd.dest] = len(nodes)
                    nodes.append(new_node)

            elif cmd.op == "copy":
                # source 保持不變，dest 新增
                if cmd.dest:
                    src = nodes[path_idx[cmd.source]] if cmd.source in path_idx else {}
                    new_node = {
                        "path": cmd.dest,
                        "node_type": src.get("node_type", "file"),
                        "status": VNodeStatus.ADDED,
                    }
                    path_idx[cmd.dest] = len(nodes)
                    nodes.append(new_node)

            elif cmd.op == "mkdir":
                new_node = {
                    "path": cmd.source,
                    "node_type": "folder",
                    "status": VNodeStatus.ADDED,
                }
                path_idx[cmd.source] = len(nodes)
                nodes.append(new_node)

        return nodes
