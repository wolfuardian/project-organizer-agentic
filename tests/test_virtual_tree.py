"""Tests for VirtualTree — applies commands to a flat snapshot."""
import unittest


def _snapshot():
    """建立一個簡單的 flat snapshot 供測試用。"""
    return [
        {"path": "/proj/a.txt", "node_type": "file"},
        {"path": "/proj/b.txt", "node_type": "file"},
        {"path": "/proj/sub", "node_type": "folder"},
        {"path": "/proj/sub/c.txt", "node_type": "file"},
    ]


class TestVirtualTree(unittest.TestCase):

    def _make(self, snapshot, commands):
        from domain.services.virtual_tree import VirtualTree, VNodeStatus
        return VirtualTree(snapshot, commands), VNodeStatus

    def test_no_commands_all_unchanged(self):
        from domain.models import Command
        vt, S = self._make(_snapshot(), [])
        result = vt.resolve()
        self.assertEqual(len(result), 4)
        self.assertTrue(all(n["status"] == S.UNCHANGED for n in result))

    def test_delete_marks_node(self):
        from domain.models import Command
        vt, S = self._make(_snapshot(), [
            Command(op="delete", source="/proj/a.txt"),
        ])
        result = vt.resolve()
        deleted = [n for n in result if n["status"] == S.DELETED]
        self.assertEqual(len(deleted), 1)
        self.assertEqual(deleted[0]["path"], "/proj/a.txt")

    def test_move_marks_source_and_adds_dest(self):
        from domain.models import Command
        vt, S = self._make(_snapshot(), [
            Command(op="move", source="/proj/a.txt", dest="/proj/sub/a.txt"),
        ])
        result = vt.resolve()
        moved = [n for n in result if n["status"] == S.MOVED]
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0]["path"], "/proj/a.txt")
        added = [n for n in result if n["status"] == S.ADDED]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["path"], "/proj/sub/a.txt")

    def test_rename_marks_source_and_adds_dest(self):
        from domain.models import Command
        vt, S = self._make(_snapshot(), [
            Command(op="rename", source="/proj/b.txt", dest="/proj/bb.txt"),
        ])
        result = vt.resolve()
        renamed = [n for n in result if n["status"] == S.RENAMED]
        self.assertEqual(len(renamed), 1)
        self.assertEqual(renamed[0]["path"], "/proj/b.txt")
        added = [n for n in result if n["status"] == S.ADDED]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["path"], "/proj/bb.txt")

    def test_mkdir_adds_new_dir(self):
        from domain.models import Command
        vt, S = self._make(_snapshot(), [
            Command(op="mkdir", source="/proj/newdir"),
        ])
        result = vt.resolve()
        added = [n for n in result if n["status"] == S.ADDED]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["path"], "/proj/newdir")
        self.assertEqual(added[0]["node_type"], "folder")

    def test_copy_keeps_source_adds_dest(self):
        from domain.models import Command
        vt, S = self._make(_snapshot(), [
            Command(op="copy", source="/proj/a.txt", dest="/proj/a_copy.txt"),
        ])
        result = vt.resolve()
        # source 不變
        orig = [n for n in result if n["path"] == "/proj/a.txt"]
        self.assertEqual(orig[0]["status"], S.UNCHANGED)
        # dest 新增
        added = [n for n in result if n["status"] == S.ADDED]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["path"], "/proj/a_copy.txt")

    def test_multiple_commands_compose(self):
        from domain.models import Command
        vt, S = self._make(_snapshot(), [
            Command(op="delete", source="/proj/a.txt"),
            Command(op="rename", source="/proj/b.txt", dest="/proj/bb.txt"),
        ])
        result = vt.resolve()
        paths_status = {n["path"]: n["status"] for n in result}
        self.assertEqual(paths_status["/proj/a.txt"], S.DELETED)
        self.assertEqual(paths_status["/proj/b.txt"], S.RENAMED)
        self.assertEqual(paths_status["/proj/bb.txt"], S.ADDED)


if __name__ == "__main__":
    unittest.main()
