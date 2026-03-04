"""Tests for tree column display: size and relative time."""
import unittest
from datetime import datetime, timedelta


class TestRelativeTime(unittest.TestCase):

    def test_just_now(self):
        from presentation.tree_model import format_relative_time
        now = datetime.now().isoformat()
        self.assertEqual(format_relative_time(now), "剛剛")

    def test_minutes_ago(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(minutes=5)).isoformat()
        self.assertEqual(format_relative_time(t), "5 分鐘前")

    def test_hours_ago(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(hours=3)).isoformat()
        self.assertEqual(format_relative_time(t), "3 小時前")

    def test_yesterday(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(days=1)).isoformat()
        self.assertEqual(format_relative_time(t), "昨天")

    def test_days_ago(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(days=5)).isoformat()
        self.assertEqual(format_relative_time(t), "5 天前")

    def test_weeks_ago(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(weeks=3)).isoformat()
        self.assertEqual(format_relative_time(t), "3 週前")

    def test_months_ago(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(days=90)).isoformat()
        self.assertEqual(format_relative_time(t), "3 個月前")

    def test_year_ago(self):
        from presentation.tree_model import format_relative_time
        t = (datetime.now() - timedelta(days=400)).isoformat()
        self.assertEqual(format_relative_time(t), "1 年前")

    def test_none_input(self):
        from presentation.tree_model import format_relative_time
        self.assertEqual(format_relative_time(None), "")


class TestFormatSize(unittest.TestCase):

    def test_bytes(self):
        from presentation.tree_model import format_file_size
        self.assertEqual(format_file_size(512), "512 B")

    def test_kilobytes(self):
        from presentation.tree_model import format_file_size
        self.assertEqual(format_file_size(4300), "4.2 KB")

    def test_megabytes(self):
        from presentation.tree_model import format_file_size
        self.assertEqual(format_file_size(356_000_000), "339.5 MB")

    def test_gigabytes(self):
        from presentation.tree_model import format_file_size
        self.assertEqual(format_file_size(2_500_000_000), "2.3 GB")

    def test_zero(self):
        from presentation.tree_model import format_file_size
        self.assertEqual(format_file_size(0), "0 B")

    def test_none(self):
        from presentation.tree_model import format_file_size
        self.assertEqual(format_file_size(None), "")


if __name__ == "__main__":
    unittest.main()
