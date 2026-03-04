"""Tests for fuzzy_score_positions — fuzzy match with character indices."""
import unittest


class TestFuzzyScorePositions(unittest.TestCase):

    def _fn(self, pattern, text):
        from domain.services.fuzzy_match import fuzzy_score_positions
        return fuzzy_score_positions(pattern, text)

    def test_exact_match(self):
        score, positions = self._fn("abc", "abc")
        self.assertGreater(score, 0)
        self.assertEqual(positions, [0, 1, 2])

    def test_sparse_match(self):
        score, positions = self._fn("ac", "abc")
        self.assertGreater(score, 0)
        self.assertEqual(positions, [0, 2])

    def test_no_match(self):
        score, positions = self._fn("xyz", "abc")
        self.assertEqual(score, -1)
        self.assertEqual(positions, [])

    def test_case_insensitive(self):
        score, positions = self._fn("ABC", "abcdef")
        self.assertGreater(score, 0)
        self.assertEqual(positions, [0, 1, 2])

    def test_empty_pattern(self):
        score, positions = self._fn("", "abc")
        self.assertEqual(score, 0)
        self.assertEqual(positions, [])

    def test_boundary_match_positions(self):
        """匹配在分隔符後的字元應出現在正確位置。"""
        score, positions = self._fn("fm", "fuzzy_match.py")
        self.assertGreater(score, 0)
        self.assertIn(0, positions)  # f at 0
        self.assertIn(6, positions)  # m at 6

    def test_positions_length_equals_pattern(self):
        """positions 數量應等於 pattern 長度。"""
        score, positions = self._fn("helo", "hello_world")
        self.assertGreater(score, 0)
        self.assertEqual(len(positions), 4)

    def test_score_matches_fuzzy_score(self):
        """分數應與 fuzzy_score 一致。"""
        from domain.services.fuzzy_match import fuzzy_score
        pattern, text = "fm", "fuzzy_match.py"
        score1 = fuzzy_score(pattern, text)
        score2, _ = self._fn(pattern, text)
        self.assertEqual(score1, score2)


if __name__ == "__main__":
    unittest.main()
