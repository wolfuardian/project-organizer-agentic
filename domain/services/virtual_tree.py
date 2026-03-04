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

        def _add_dest(dest: str, src_node: dict) -> None:
            node = {
                "path": dest,
                "node_type": src_node.get("node_type", "file"),
                "status": VNodeStatus.ADDED,
            }
            path_idx[dest] = len(nodes)
            nodes.append(node)

        for cmd in self._commands:
            src = nodes[path_idx[cmd.source]] if cmd.source in path_idx else {}

            if cmd.op == "delete":
                if cmd.source in path_idx:
                    nodes[path_idx[cmd.source]]["status"] = VNodeStatus.DELETED

            elif cmd.op == "move":
                if cmd.source in path_idx:
                    nodes[path_idx[cmd.source]]["status"] = VNodeStatus.MOVED
                if cmd.dest:
                    _add_dest(cmd.dest, src)

            elif cmd.op == "rename":
                if cmd.source in path_idx:
                    nodes[path_idx[cmd.source]]["status"] = VNodeStatus.RENAMED
                if cmd.dest:
                    _add_dest(cmd.dest, src)

            elif cmd.op == "copy":
                if cmd.dest:
                    _add_dest(cmd.dest, src)

            elif cmd.op == "mkdir":
                _add_dest(cmd.source, {"node_type": "folder"})

        return nodes
