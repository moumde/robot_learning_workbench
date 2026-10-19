from __future__ import annotations

from collections import deque
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class MetricPlot(QWidget):
    def __init__(self, parent=None, max_points: int = 1000):
        super().__init__(parent)
        self._points: deque[tuple[int, float]] = deque(maxlen=max_points)
        self.setMinimumHeight(220)
        self.setToolTip("训练损失曲线")

    def clear(self) -> None:
        self._points.clear()
        self.update()

    def add_point(self, step: int, value: float) -> None:
        if not math.isfinite(value):
            return
        # Replace a duplicate x coordinate instead of drawing a vertical line.
        if self._points and self._points[-1][0] == step:
            self._points[-1] = (step, value)
        else:
            self._points.append((step, value))
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        rect = QRectF(self.rect()).adjusted(12, 12, -12, -12)
        painter.fillRect(rect, palette.base())

        border_pen = QPen(palette.mid().color())
        border_pen.setWidthF(1.0)
        painter.setPen(border_pen)
        painter.drawRoundedRect(rect, 6, 6)

        if not self._points:
            painter.setPen(palette.placeholderText().color())
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "等待训练指标…")
            return

        points = list(self._points)
        steps = [p[0] for p in points]
        values = [p[1] for p in points]
        x_min, x_max = min(steps), max(steps)
        y_min, y_max = min(values), max(values)

        # Keep the single-point case visible and correctly labelled.
        draw_x_max = x_max if x_max != x_min else x_min + 1
        if y_max == y_min:
            pad = max(abs(y_min) * 0.05, 1e-6)
            y_min -= pad
            y_max += pad
        else:
            pad = (y_max - y_min) * 0.08
            y_min -= pad
            y_max += pad

        plot = rect.adjusted(48, 20, -16, -32)
        grid_pen = QPen(palette.midlight().color())
        grid_pen.setWidthF(1.0)
        painter.setPen(grid_pen)
        for i in range(5):
            y = plot.top() + plot.height() * i / 4
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        path = QPainterPath()
        for index, (step, value) in enumerate(points):
            x = plot.left() + (step - x_min) / (draw_x_max - x_min) * plot.width()
            y = plot.bottom() - (value - y_min) / (y_max - y_min) * plot.height()
            if index == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        line_pen = QPen(palette.highlight().color())
        line_pen.setWidthF(2.0)
        painter.setPen(line_pen)
        painter.drawPath(path)

        painter.setPen(palette.text().color())
        painter.drawText(
            QRectF(plot.left(), rect.top(), plot.width(), 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"损失 · 最新 {values[-1]:.6g}",
        )
        painter.drawText(
            QRectF(rect.left(), plot.top(), 42, 18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{y_max:.3g}",
        )
        painter.drawText(
            QRectF(rect.left(), plot.bottom() - 18, 42, 18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{y_min:.3g}",
        )
        if x_min == x_max:
            x_text = f"OpenPI 步 {x_min}"
        else:
            x_text = f"OpenPI 步 {x_min} → {x_max}"
        painter.drawText(
            QRectF(plot.left(), plot.bottom() + 6, plot.width(), 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            x_text,
        )
