"""A Task drawn as a raised card that can be clicked or dragged."""

from PySide6.QtCore import QByteArray, QMimeData, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QLabel, QVBoxLayout

from unlimilist.domain import LaneKind, Stage, Task, Urgency
from unlimilist.ui.date_field import format_date
from unlimilist.ui.styling import URGENCY_COLOURS, text_colour

TASK_MIME_TYPE = "application/x-unlimilist-task"
_RADIUS = 8
_STRIPE = 5


def encode_drag(task: Task) -> QMimeData:
    mime = QMimeData()
    mime.setData(TASK_MIME_TYPE, QByteArray(f"{task.id}|{task.kind.value}".encode()))
    return mime


def decode_drag(mime: QMimeData) -> tuple[str, LaneKind] | None:
    if not mime.hasFormat(TASK_MIME_TYPE):
        return None
    task_id, kind = bytes(mime.data(TASK_MIME_TYPE)).decode().split("|")
    return task_id, LaneKind(kind)


class CardWidget(QFrame):
    clicked = Signal(str)

    def __init__(self, task: Task, urgency: Urgency, fill: QColor, parent=None):
        super().__init__(parent)
        self.task = task
        self._urgency = urgency
        self._fill = fill
        self._press_pos: QPoint | None = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        ink = text_colour(fill)
        muted = QColor(ink)
        muted.setAlphaF(0.78)

        self.title_label = QLabel(self._title_text())
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(f"color: {ink.name()}; font-weight: 600; background: transparent;")
        self.meta_label = QLabel(self._meta_text())
        self.meta_label.setStyleSheet(
            f"color: {muted.name(QColor.NameFormat.HexArgb)}; font-size: 11px; background: transparent;"
        )
        self.meta_label.setHidden(not self.meta_label.text())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(_STRIPE + 10, 9, 10, 9)
        layout.setSpacing(3)
        layout.addWidget(self.title_label)
        layout.addWidget(self.meta_label)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(14)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)

    def _title_text(self) -> str:
        if self.task.priority is not None:
            return f"{self.task.priority}. {self.task.title}"
        return self.task.title

    def _meta_text(self) -> str:
        parts = []
        if self.task.stage == Stage.DONE:
            parts.append(f"✓ {format_date(self.task.completed_at)}")
        elif self.task.kind == LaneKind.TIME_LIMITED:
            dates = []
            if self.task.due_date:
                dates.append(f"▶ {format_date(self.task.due_date)}")
            if self.task.deadline:
                dates.append(f"⚑ {format_date(self.task.deadline)}")
            parts.append(" → ".join(dates))
            if self._urgency == Urgency.START_PASSED:
                parts.append("· start passed")
        icons = ("📝" if self.task.details else "") + ("📎" if self.task.usable_data else "")
        if icons:
            parts.append(icons)
        return "  ".join(parts)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, _RADIUS, _RADIUS)

        # Lit from above: lighter at the top edge, darker at the bottom.
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0.0, self._fill.lighter(118))
        gradient.setColorAt(0.5, self._fill)
        gradient.setColorAt(1.0, self._fill.darker(112))
        painter.fillPath(path, gradient)
        painter.setPen(QPen(self._fill.darker(130), 1))
        painter.drawPath(path)
        highlight = QColor(255, 255, 255, 70)
        painter.setPen(QPen(highlight, 1))
        painter.drawLine(int(rect.left() + _RADIUS), int(rect.top() + 1), int(rect.right() - _RADIUS), int(rect.top() + 1))

        stripe = URGENCY_COLOURS.get(self._urgency)
        if stripe:
            painter.save()
            painter.setClipPath(path)
            painter.fillRect(QRectF(rect.left(), rect.top(), _STRIPE, rect.height()), stripe)
            painter.restore()
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_pos is None:
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < QApplication.startDragDistance():
            return
        drag = QDrag(self)
        drag.setMimeData(encode_drag(self.task))
        drag.setPixmap(self.grab())
        drag.setHotSpot(self._press_pos)
        self._press_pos = None
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.MoveAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseReleaseEvent(self, event):
        if self._press_pos is not None and event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = None
            self.clicked.emit(self.task.id)
        super().mouseReleaseEvent(event)
