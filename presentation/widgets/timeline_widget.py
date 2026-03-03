"""時間軸繪圖元件."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from database import PROGRESS_LABELS


_PROGRESS_COLORS = {
    "not_started": "#6c7086",
    "in_progress": "#89b4fa",
    "paused":      "#f9e2af",
    "completed":   "#a6e3a1",
}


class TimelineWidget(QWidget):
    """自繪時間軸：每個專案一條橫列，顏色代表進度。"""

    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self._rows = rows
        self.setMinimumHeight(max(120, len(rows) * 48 + 40))

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor, QFont, QPen
        from PySide6.QtCore import QRectF
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        W = self.width()
        row_h = 44
        margin_left = 160
        margin_right = 20
        track_y = 28

        if not self._rows:
            painter.drawText(20, 40, "尚無專案資料")
            return

        # 時間範圍
        from datetime import datetime
        def _dt(s: str) -> datetime:
            return datetime.fromisoformat(s[:19])

        times = [_dt(r["created_at"]) for r in self._rows]
        t_min, t_max = min(times), max(times)
        span = max((t_max - t_min).total_seconds(), 1)

        def _x(dt: datetime) -> float:
            frac = (dt - t_min).total_seconds() / span
            return margin_left + frac * (W - margin_left - margin_right)

        # 主軸線
        axis_y = track_y + len(self._rows) * row_h // 2
        painter.setPen(QPen(QColor("#45475a"), 2))
        painter.drawLine(margin_left, axis_y, W - margin_right, axis_y)

        for i, row in enumerate(self._rows):
            y = track_y + i * row_h
            cx = _x(_dt(row["created_at"]))
            progress = row["progress"] or "not_started"
            color = QColor(_PROGRESS_COLORS.get(progress, "#6c7086"))

            # 專案名稱（左側）
            painter.setPen(QColor("#cdd6f4"))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            name = row["name"]
            if len(name) > 18:
                name = name[:17] + "…"
            painter.drawText(4, y + 16, name)

            # 進度標籤
            badge = PROGRESS_LABELS.get(progress, progress)
            painter.setPen(color)
            font2 = QFont(font)
            font2.setPointSize(8)
            painter.setFont(font2)
            painter.drawText(4, y + 30, badge)

            # 節點圓圈
            painter.setBrush(color)
            painter.setPen(QPen(QColor("#1e1e2e"), 1))
            painter.drawEllipse(int(cx) - 7, y + 6, 14, 14)

            # todo 進度條（節點右側）
            total = row["todo_total"] or 0
            done  = row["todo_done"] or 0
            if total:
                bar_x = int(cx) + 10
                bar_w = min(60, W - bar_x - margin_right)
                bar_h = 6
                bar_y = y + 12
                painter.setBrush(QColor("#313244"))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 3, 3)
                fill_w = int(bar_w * done / total)
                painter.setBrush(QColor("#a6e3a1"))
                painter.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 3, 3)
                painter.setPen(QColor("#a6adc8"))
                painter.setFont(font2)
                painter.drawText(bar_x + bar_w + 4, bar_y + bar_h,
                                 f"{done}/{total}")
