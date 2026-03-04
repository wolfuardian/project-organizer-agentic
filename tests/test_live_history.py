"""Tests for LiveHistory — immediate file operations with undo/redo."""
import unittest
from unittest.mock import patch, MagicMock

from domain.models import Command, OperationRecord


class TestLiveHistory(unittest.TestCase):

    def _make(self):
        from domain.services.live_history import LiveHistory
        return LiveHistory()

    def test_empty_state(self):
        lh = self._make()
        self.assertFalse(lh.can_undo)
        self.assertFalse(lh.can_redo)
        self.assertEqual(lh.history(), [])

    @patch("domain.services.live_history.move_file")
    def test_execute_move(self, mock_move):
        mock_move.return_value = OperationRecord(
            op_type="move", source="/a.txt", dest="/b/a.txt", success=True,
        )
        lh = self._make()
        rec = lh.execute(Command(op="move", source="/a.txt", dest="/b/a.txt"))
        self.assertTrue(rec.success)
        self.assertTrue(lh.can_undo)
        mock_move.assert_called_once_with("/a.txt", "/b/a.txt")

    @patch("domain.services.live_history.delete_to_trash")
    def test_execute_delete(self, mock_del):
        mock_del.return_value = OperationRecord(
            op_type="delete", source="/a.txt", success=True, trash_key="abc",
        )
        lh = self._make()
        rec = lh.execute(Command(op="delete", source="/a.txt"))
        self.assertTrue(rec.success)
        self.assertEqual(rec.trash_key, "abc")

    @patch("domain.services.live_history.copy_file")
    def test_execute_copy(self, mock_copy):
        mock_copy.return_value = OperationRecord(
            op_type="copy", source="/a.txt", dest="/a_copy.txt", success=True,
        )
        lh = self._make()
        rec = lh.execute(Command(op="copy", source="/a.txt", dest="/a_copy.txt"))
        self.assertTrue(rec.success)

    @patch("domain.services.live_history.undo_operation")
    @patch("domain.services.live_history.move_file")
    def test_undo(self, mock_move, mock_undo):
        mock_move.return_value = OperationRecord(
            op_type="move", source="/a.txt", dest="/b/a.txt", success=True,
        )
        mock_undo.return_value = True
        lh = self._make()
        lh.execute(Command(op="move", source="/a.txt", dest="/b/a.txt"))
        result = lh.undo()
        self.assertTrue(result)
        self.assertFalse(lh.can_undo)
        self.assertTrue(lh.can_redo)
        mock_undo.assert_called_once_with("move", "/a.txt", dest="/b/a.txt", trash_key=None)

    @patch("domain.services.live_history.move_file")
    def test_redo(self, mock_move):
        rec1 = OperationRecord(op_type="move", source="/a.txt", dest="/b/a.txt", success=True)
        rec2 = OperationRecord(op_type="move", source="/a.txt", dest="/b/a.txt", success=True)
        mock_move.side_effect = [rec1, rec2]
        lh = self._make()
        lh.execute(Command(op="move", source="/a.txt", dest="/b/a.txt"))
        with patch("domain.services.live_history.undo_operation", return_value=True):
            lh.undo()
        result = lh.redo()
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertTrue(lh.can_undo)
        self.assertFalse(lh.can_redo)

    @patch("domain.services.live_history.move_file")
    def test_execute_after_undo_clears_redo(self, mock_move):
        rec = OperationRecord(op_type="move", source="/a.txt", dest="/b/a.txt", success=True)
        mock_move.return_value = rec
        lh = self._make()
        lh.execute(Command(op="move", source="/a.txt", dest="/b/a.txt"))
        with patch("domain.services.live_history.undo_operation", return_value=True):
            lh.undo()
        self.assertTrue(lh.can_redo)
        # new execute clears redo
        lh.execute(Command(op="move", source="/x.txt", dest="/y.txt"))
        self.assertFalse(lh.can_redo)

    @patch("domain.services.live_history.move_file")
    def test_failed_execution_not_in_history(self, mock_move):
        mock_move.return_value = OperationRecord(
            op_type="move", source="/a.txt", dest="/b/a.txt",
            success=False, error="permission denied",
        )
        lh = self._make()
        rec = lh.execute(Command(op="move", source="/a.txt", dest="/b/a.txt"))
        self.assertFalse(rec.success)
        self.assertFalse(lh.can_undo)

    def test_undo_on_empty_returns_false(self):
        lh = self._make()
        self.assertFalse(lh.undo())

    def test_redo_on_empty_returns_none(self):
        lh = self._make()
        self.assertIsNone(lh.redo())

    @patch("domain.services.live_history.move_file")
    def test_history_returns_records(self, mock_move):
        mock_move.return_value = OperationRecord(
            op_type="move", source="/a.txt", dest="/b/a.txt", success=True,
        )
        lh = self._make()
        lh.execute(Command(op="move", source="/a.txt", dest="/b/a.txt"))
        lh.execute(Command(op="move", source="/c.txt", dest="/d.txt"))
        self.assertEqual(len(lh.history()), 2)

    def test_clear(self):
        lh = self._make()
        lh.clear()
        self.assertFalse(lh.can_undo)
        self.assertEqual(lh.history(), [])


if __name__ == "__main__":
    unittest.main()
