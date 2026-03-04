"""Tests for VirtualService — coordinates CommandQueue + VirtualTree."""
import unittest
from unittest.mock import MagicMock, patch


def _snapshot():
    return [
        {"path": "/proj/a.txt", "node_type": "file"},
        {"path": "/proj/b.txt", "node_type": "file"},
        {"path": "/proj/sub", "node_type": "folder"},
    ]


class TestVirtualService(unittest.TestCase):

    def _make(self, snapshot=None):
        from application.virtual_service import VirtualService
        svc = VirtualService()
        svc.begin(snapshot or _snapshot())
        return svc

    def test_begin_sets_active(self):
        svc = self._make()
        self.assertTrue(svc.active)

    def test_push_and_pending(self):
        from domain.models import Command
        svc = self._make()
        svc.push(Command(op="delete", source="/proj/a.txt"))
        self.assertEqual(len(svc.pending_commands()), 1)

    def test_undo_redo(self):
        from domain.models import Command
        svc = self._make()
        svc.push(Command(op="delete", source="/proj/a.txt"))
        svc.push(Command(op="delete", source="/proj/b.txt"))
        svc.undo()
        self.assertEqual(len(svc.pending_commands()), 1)
        svc.redo()
        self.assertEqual(len(svc.pending_commands()), 2)

    def test_resolve_tree_reflects_commands(self):
        from domain.models import Command
        from domain.services.virtual_tree import VNodeStatus
        svc = self._make()
        svc.push(Command(op="delete", source="/proj/a.txt"))
        result = svc.resolve_tree()
        deleted = [n for n in result if n["status"] == VNodeStatus.DELETED]
        self.assertEqual(len(deleted), 1)

    def test_discard_clears_everything(self):
        from domain.models import Command
        svc = self._make()
        svc.push(Command(op="delete", source="/proj/a.txt"))
        svc.discard()
        self.assertFalse(svc.active)
        self.assertEqual(svc.pending_commands(), [])

    def test_apply_calls_executor(self):
        from domain.models import Command
        svc = self._make()
        svc.push(Command(op="delete", source="/proj/a.txt"))
        svc.push(Command(op="move", source="/proj/b.txt", dest="/proj/sub/b.txt"))

        results = []
        def fake_executor(cmd):
            results.append(cmd.op)
            return True

        ok = svc.apply(fake_executor)
        self.assertTrue(ok)
        self.assertEqual(results, ["delete", "move"])
        self.assertFalse(svc.active)

    def test_apply_empty_returns_true(self):
        svc = self._make()
        ok = svc.apply(lambda cmd: True)
        self.assertTrue(ok)
        self.assertFalse(svc.active)

    def test_not_active_before_begin(self):
        from application.virtual_service import VirtualService
        svc = VirtualService()
        self.assertFalse(svc.active)

    def test_can_undo_can_redo(self):
        from domain.models import Command
        svc = self._make()
        self.assertFalse(svc.can_undo)
        self.assertFalse(svc.can_redo)
        svc.push(Command(op="delete", source="/proj/a.txt"))
        self.assertTrue(svc.can_undo)
        svc.undo()
        self.assertTrue(svc.can_redo)


if __name__ == "__main__":
    unittest.main()
