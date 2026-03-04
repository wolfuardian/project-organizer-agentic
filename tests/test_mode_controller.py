"""Tests for ModeController — unified dispatch for all three modes."""
import unittest
from unittest.mock import patch, MagicMock

from domain.models import Command, OperationRecord
from domain.enums import MODE_READ, MODE_VIRTUAL, MODE_REALTIME


class TestModeController(unittest.TestCase):

    def _make(self, mode=MODE_VIRTUAL):
        from application.mode_controller import ModeController
        mc = ModeController()
        mc.set_mode(mode)
        return mc

    # ── Preview mode blocks everything ──────────────────

    def test_preview_blocks_execute(self):
        mc = self._make(MODE_READ)
        result = mc.execute(Command(op="delete", source="/a.txt"))
        self.assertIsNone(result)

    def test_preview_blocks_undo(self):
        mc = self._make(MODE_READ)
        self.assertIsNone(mc.undo())

    def test_preview_blocks_redo(self):
        mc = self._make(MODE_READ)
        self.assertIsNone(mc.redo())

    # ── Virtual mode dispatches to VirtualService ───────

    def test_virtual_execute_pushes_command(self):
        mc = self._make(MODE_VIRTUAL)
        mc.begin_virtual([{"path": "/a.txt", "node_type": "file"}])
        cmd = Command(op="delete", source="/a.txt")
        mc.execute(cmd)
        self.assertEqual(len(mc.pending_commands()), 1)

    def test_virtual_undo_redo(self):
        mc = self._make(MODE_VIRTUAL)
        mc.begin_virtual([{"path": "/a.txt", "node_type": "file"}])
        mc.execute(Command(op="delete", source="/a.txt"))
        mc.undo()
        self.assertEqual(len(mc.pending_commands()), 0)
        mc.redo()
        self.assertEqual(len(mc.pending_commands()), 1)

    def test_virtual_can_undo_redo(self):
        mc = self._make(MODE_VIRTUAL)
        mc.begin_virtual([])
        self.assertFalse(mc.can_undo)
        self.assertFalse(mc.can_redo)
        mc.execute(Command(op="mkdir", source="/new"))
        self.assertTrue(mc.can_undo)

    def test_virtual_resolve_tree(self):
        from domain.services.virtual_tree import VNodeStatus
        mc = self._make(MODE_VIRTUAL)
        mc.begin_virtual([{"path": "/a.txt", "node_type": "file"}])
        mc.execute(Command(op="delete", source="/a.txt"))
        tree = mc.resolve_tree()
        deleted = [n for n in tree if n["status"] == VNodeStatus.DELETED]
        self.assertEqual(len(deleted), 1)

    def test_virtual_apply(self):
        mc = self._make(MODE_VIRTUAL)
        mc.begin_virtual([{"path": "/a.txt", "node_type": "file"}])
        mc.execute(Command(op="delete", source="/a.txt"))
        results = []
        mc.apply(lambda cmd: results.append(cmd.op) or True)
        self.assertEqual(results, ["delete"])
        self.assertFalse(mc.virtual_active)

    def test_virtual_discard(self):
        mc = self._make(MODE_VIRTUAL)
        mc.begin_virtual([])
        mc.execute(Command(op="mkdir", source="/new"))
        mc.discard()
        self.assertFalse(mc.virtual_active)

    # ── Live mode dispatches to LiveHistory ─────────────

    @patch("domain.services.live_history.move_file")
    def test_live_execute(self, mock_move):
        mock_move.return_value = OperationRecord(
            op_type="move", source="/a.txt", dest="/b/a.txt", success=True,
        )
        mc = self._make(MODE_REALTIME)
        result = mc.execute(Command(op="move", source="/a.txt", dest="/b/a.txt"))
        self.assertTrue(result.success)

    @patch("domain.services.live_history.undo_operation")
    @patch("domain.services.live_history.move_file")
    def test_live_undo(self, mock_move, mock_undo):
        mock_move.return_value = OperationRecord(
            op_type="move", source="/a.txt", dest="/b/a.txt", success=True,
        )
        mock_undo.return_value = True
        mc = self._make(MODE_REALTIME)
        mc.execute(Command(op="move", source="/a.txt", dest="/b/a.txt"))
        result = mc.undo()
        self.assertTrue(result)

    @patch("domain.services.live_history.move_file")
    def test_live_can_undo(self, mock_move):
        mock_move.return_value = OperationRecord(
            op_type="move", source="/a.txt", dest="/b/a.txt", success=True,
        )
        mc = self._make(MODE_REALTIME)
        self.assertFalse(mc.can_undo)
        mc.execute(Command(op="move", source="/a.txt", dest="/b/a.txt"))
        self.assertTrue(mc.can_undo)

    # ── Mode switching ──────────────────────────────────

    def test_set_mode(self):
        mc = self._make(MODE_READ)
        self.assertEqual(mc.mode, MODE_READ)
        mc.set_mode(MODE_VIRTUAL)
        self.assertEqual(mc.mode, MODE_VIRTUAL)

    def test_mode_property(self):
        mc = self._make(MODE_REALTIME)
        self.assertEqual(mc.mode, MODE_REALTIME)


if __name__ == "__main__":
    unittest.main()
