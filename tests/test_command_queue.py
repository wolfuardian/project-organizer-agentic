"""Tests for Command dataclass and CommandQueue."""
import unittest


class TestCommand(unittest.TestCase):

    def test_create_command(self):
        from domain.models import Command
        cmd = Command(op="move", source="/a/b", dest="/c/d")
        self.assertEqual(cmd.op, "move")
        self.assertEqual(cmd.source, "/a/b")
        self.assertEqual(cmd.dest, "/c/d")
        self.assertIsInstance(cmd.timestamp, float)

    def test_command_no_dest(self):
        from domain.models import Command
        cmd = Command(op="delete", source="/a/b")
        self.assertIsNone(cmd.dest)


class TestCommandQueue(unittest.TestCase):

    def _make_queue(self):
        from domain.services.command_queue import CommandQueue
        return CommandQueue()

    def _make_cmd(self, op="move", source="/a", dest="/b"):
        from domain.models import Command
        return Command(op=op, source=source, dest=dest)

    def test_empty_queue(self):
        q = self._make_queue()
        self.assertFalse(q.can_undo)
        self.assertFalse(q.can_redo)
        self.assertEqual(q.pending(), [])

    def test_push_and_pending(self):
        q = self._make_queue()
        c1 = self._make_cmd(source="/1")
        c2 = self._make_cmd(source="/2")
        q.push(c1)
        q.push(c2)
        self.assertEqual(q.pending(), [c1, c2])
        self.assertTrue(q.can_undo)
        self.assertFalse(q.can_redo)

    def test_undo_reduces_pending(self):
        q = self._make_queue()
        c1 = self._make_cmd(source="/1")
        c2 = self._make_cmd(source="/2")
        q.push(c1)
        q.push(c2)
        q.undo()
        self.assertEqual(q.pending(), [c1])
        self.assertTrue(q.can_undo)
        self.assertTrue(q.can_redo)

    def test_redo_restores_pending(self):
        q = self._make_queue()
        c1 = self._make_cmd(source="/1")
        c2 = self._make_cmd(source="/2")
        q.push(c1)
        q.push(c2)
        q.undo()
        q.redo()
        self.assertEqual(q.pending(), [c1, c2])
        self.assertFalse(q.can_redo)

    def test_full_cycle(self):
        q = self._make_queue()
        cmds = [self._make_cmd(source=f"/{i}") for i in range(3)]
        for c in cmds:
            q.push(c)
        # undo all
        q.undo()
        q.undo()
        q.undo()
        self.assertEqual(q.pending(), [])
        self.assertFalse(q.can_undo)
        self.assertTrue(q.can_redo)
        # redo all
        q.redo()
        q.redo()
        q.redo()
        self.assertEqual(q.pending(), cmds)
        self.assertTrue(q.can_undo)
        self.assertFalse(q.can_redo)

    def test_push_after_undo_clears_redo(self):
        q = self._make_queue()
        c1 = self._make_cmd(source="/1")
        c2 = self._make_cmd(source="/2")
        c3 = self._make_cmd(source="/3")
        q.push(c1)
        q.push(c2)
        q.undo()  # cursor at 1, redo has c2
        q.push(c3)  # should discard c2 from redo
        self.assertEqual(q.pending(), [c1, c3])
        self.assertFalse(q.can_redo)

    def test_clear(self):
        q = self._make_queue()
        q.push(self._make_cmd())
        q.push(self._make_cmd())
        q.clear()
        self.assertEqual(q.pending(), [])
        self.assertFalse(q.can_undo)
        self.assertFalse(q.can_redo)

    def test_undo_on_empty_is_noop(self):
        q = self._make_queue()
        q.undo()  # should not raise
        self.assertEqual(q.pending(), [])

    def test_redo_on_empty_is_noop(self):
        q = self._make_queue()
        q.redo()  # should not raise
        self.assertEqual(q.pending(), [])


if __name__ == "__main__":
    unittest.main()
