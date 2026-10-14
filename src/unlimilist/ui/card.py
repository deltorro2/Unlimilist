"""A Task drawn as a raised, square-cornered card that can be clicked or dragged."""

from typing import NamedTuple

from PySide6.QtCore import QByteArray, QMimeData, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDrag,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QTextLayout,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from unlimilist.domain import LaneKind, Stage, Task, Urgency
from unlimilist.ui.date_field import format_date
from unlimilist.ui.icons import ACTIVITY_LABELS, activity_pixmap
from unlimilist.ui.styling import LATE, LATE_BORDER, TAG_BACKGROUND, TAG_INK, URGENCY_COLOURS, text_colour

TASK_MIME_TYPE = "application/x-unlimilist-task"
_STRIPE = 5
_MAX_LINES = 4
_MAX_CHIP_CHARS = 12
_CHIP_GAP = 6
_STATUS_SIZE = 12
_BADGE_SIZE = 14
_BADGE_GAP = 6
_LATE_BORDER_WIDTH = 2


class Dragged(NamedTuple):
    """What a Column needs to know about a Task being dragged over it."""

    task_id: str
    kind: LaneKind
    unfinished_subtasks: int


def encode_drag(task: Task) -> QMimeData:
    mime = QMimeData()
    payload = f"{task.id}|{task.kind.value}|{task.unfinished_subtasks}"
    mime.setData(TASK_MIME_TYPE, QByteArray(payload.encode()))
    return mime


def decode_drag(mime: QMimeData) -> Dragged | None:
    if not mime.hasFormat(TASK_MIME_TYPE):
        return None
    task_id, kind, unfinished = bytes(mime.data(TASK_MIME_TYPE)).decode().split("|")
    return Dragged(task_id, LaneKind(kind), int(unfinished))


def tag_chip_text(task: Task) -> str:
    """"#first" or "#first +N", at most 12 characters: a longer Tag is cut with "…" and keeps its "+N".
    Empty when the Task has no Tags."""
    if not task.tags:
        return ""
    more = f" +{len(task.tags) - 1}" if len(task.tags) > 1 else ""
    name = f"#{task.tags[0]}"
    room = _MAX_CHIP_CHARS - len(more)
    if len(name) > room:
        name = name[: room - 1] + "…"
    return name + more


def status_fill(task: Task) -> str:
    """The card's status circle: full once Done, two thirds with Subtasks, otherwise empty."""
    if task.stage == Stage.DONE:
        return "full"
    return "two_thirds" if task.has_subtasks else "empty"


def status_pixmap(fill: str, colour: QColor, size: int = _STATUS_SIZE) -> QPixmap:
    scale = 2  # crisp on Retina
    image = QPixmap(size * scale, size * scale)
    image.setDevicePixelRatio(scale)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    circle = QRectF(1, 1, size - 2, size - 2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(colour)
    if fill == "full":
        painter.drawEllipse(circle)
    elif fill == "two_thirds":
        painter.drawPie(circle, 90 * 16, -240 * 16)  # from 12 o'clock, clockwise
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(colour, 1.5))
    painter.drawEllipse(circle)
    painter.end()
    return image


def wrap_lines(text: str, font: QFont, width: int, max_lines: int, first_width: int | None = None) -> list[str]:
    """`text` word-wrapped to `width`, at most `max_lines` lines, the last one elided with '…' if cut.

    `first_width`, if given, is the width of the first line only.
    """
    if not text or width <= 0 or max_lines <= 0:
        return []
    widths = [first_width if first_width is not None else width] + [width] * (max_lines - 1)
    metrics = QFontMetrics(font)
    layout = QTextLayout(text, font)
    layout.beginLayout()
    spans = []
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(max(widths[min(len(spans), max_lines - 1)], 1))
        spans.append((line.textStart(), line.textLength()))
    layout.endLayout()
    lines = [text[start : start + length].rstrip() for start, length in spans[:max_lines]]
    if len(spans) > max_lines:
        rest = text[spans[max_lines - 1][0] :]
        lines[-1] = metrics.elidedText(rest, Qt.TextElideMode.ElideRight, widths[max_lines - 1])
    return lines


class CardWidget(QFrame):
    clicked = Signal(str)

    def __init__(self, task: Task, urgency: Urgency, fill: QColor, parent=None):
        super().__init__(parent)
        self.task = task
        self._urgency = urgency
        self._fill = fill
        self._press_pos: QPoint | None = None
        self._done = task.stage == Stage.DONE
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        ink = text_colour(fill)
        muted = QColor(ink)
        muted.setAlphaF(0.8)

        # Blue, lightened on dark cards so it stays visible.
        blue = QColor("#A9C8FF") if ink.lightness() > 128 else QColor("#1F5FD6")
        self.status_icon = QLabel()
        self.status_icon.setProperty("fill", status_fill(task))
        self.status_icon.setPixmap(status_pixmap(status_fill(task), blue))
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon.setStyleSheet("background: transparent;")
        self.status_icon.setToolTip(
            {"full": "Done", "two_thirds": "Has Subtasks", "empty": "No Subtasks"}[status_fill(task)]
        )

        self.title_label = QLabel()
        title_font = self.title_label.font()
        title_font.setBold(True)
        title_font.setStrikeOut(self._done)
        self.title_label.setFont(title_font)
        # As tall as one title line, so the circle sits centred on the first line.
        title_line = QFontMetrics(title_font).height()
        self.status_icon.setFixedSize(_STATUS_SIZE, title_line)

        # The Activity badge sits in the left margin, level with the first title line. Done cards leave it out.
        self.activity_badge = QLabel()
        self.activity_badge.setProperty("activity", task.activity.value)
        self.activity_badge.setPixmap(activity_pixmap(task.activity, _BADGE_SIZE))
        self.activity_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activity_badge.setFixedSize(_BADGE_SIZE, title_line)
        self.activity_badge.setStyleSheet("background: transparent;")
        self.activity_badge.setToolTip(ACTIVITY_LABELS[task.activity])
        self.activity_badge.setHidden(self._done)
        self.title_label.setStyleSheet(f"color: {ink.name()}; background: transparent;")

        # The first Tag in the top-right corner, with "+N" for the rest. It floats over the first title line
        # instead of taking a column, so only that line makes room for it.
        self._title_line = title_line
        self.tag_chip = QLabel(tag_chip_text(task), self)
        self.tag_chip.setObjectName("tagChip")
        self.tag_chip.setToolTip(" ".join(f"#{name}" for name in task.tags))
        self.tag_chip.setStyleSheet(
            f"background: {TAG_BACKGROUND.name()}; color: {TAG_INK.name()}; border: 1px solid rgba(0, 0, 0, 0.12);"
            " border-radius: 7px; padding: 0px 6px; font-size: 11px; font-weight: 600;"
        )
        self.tag_chip.adjustSize()
        self.tag_chip.setHidden(not task.tags)

        self.meta_label = QLabel(self._meta_text())
        meta_font = self.meta_label.font()
        meta_font.setPointSizeF(meta_font.pointSizeF() - 2)
        self.meta_label.setFont(meta_font)
        self.meta_label.setStyleSheet(f"color: {muted.name(QColor.NameFormat.HexArgb)}; background: transparent;")
        self.meta_label.setHidden(not self.meta_label.text())

        # Text is wrapped and cut to the card's width, so the labels must not dictate a width.
        for label in (self.title_label, self.meta_label):
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            label.setMinimumWidth(1)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)
        top.addWidget(self.status_icon, 0, Qt.AlignmentFlag.AlignTop)
        top.addSpacing(2)
        top.addWidget(self.title_label, 1)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(2)
        content.addLayout(top)
        content.addWidget(self.meta_label)

        layout = QHBoxLayout(self)
        vertical = 7 if self._done else 9
        layout.setContentsMargins(_STRIPE + (10 if self._done else 3), vertical, 10, vertical)
        layout.setSpacing(_BADGE_GAP)
        layout.addWidget(self.activity_badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(content, 1)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 85))
        self.setGraphicsEffect(shadow)
        self._fit_text()

    def fill(self) -> str:
        """The card's base colour, as #rrggbb."""
        return self._fill.name()

    def _meta_text(self) -> str:
        if self._done:
            return f"✓ {format_date(self.task.completed_at)}"
        if self.task.kind != LaneKind.TIME_LIMITED:
            return ""
        dates = []
        if self.task.due_date:
            dates.append(f"▶ {format_date(self.task.due_date)}")
        if self.task.deadline:
            dates.append(f"⚑ {format_date(self.task.deadline)}")
        text = " → ".join(dates)
        if self._urgency == Urgency.START_PASSED:
            text += "  · start passed"
        return text

    def _title_text(self) -> str:
        if self.task.priority is not None:
            return f"{self.task.priority}. {self.task.title}"
        return self.task.title

    def _fit_text(self) -> None:
        """The title wraps over every line the card has (4, less one for a dates line; Done cards keep one),
        its first line making room for the Tag chip."""
        margins = self.layout().contentsMargins()
        badge = 0 if self._done else _BADGE_SIZE + _BADGE_GAP
        content_width = max(self.width() - margins.left() - margins.right() - badge, 40)
        width = content_width - (_STATUS_SIZE + 6)
        chip = 0 if self.tag_chip.isHidden() else self.tag_chip.width() + _CHIP_GAP
        max_lines = 1 if self._done else _MAX_LINES - (0 if self.meta_label.isHidden() else 1)

        title_lines = wrap_lines(self._title_text(), self.title_label.font(), width, max_lines, width - chip)
        self.title_label.setText("\n".join(title_lines))
        self.tag_chip.move(
            self.width() - margins.right() - self.tag_chip.width(),
            margins.top() + (self._title_line - self.tag_chip.height()) // 2,
        )
        self.tag_chip.raise_()
        self.updateGeometry()  # the line count, and so the height, may have changed

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_text()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        # Lit from above: lighter at the top edge, darker at the bottom.
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0.0, self._fill.lighter(116))
        gradient.setColorAt(0.5, self._fill)
        gradient.setColorAt(1.0, self._fill.darker(112))
        painter.fillRect(rect, gradient)
        painter.setPen(QPen(self._fill.darker(130), 1))
        painter.drawRect(rect)
        painter.setPen(QPen(QColor(255, 255, 255, 70), 1))
        painter.drawLine(int(rect.left() + 1), int(rect.top() + 1), int(rect.right() - 1), int(rect.top() + 1))

        stripe = URGENCY_COLOURS.get(self._urgency)
        if stripe:
            painter.fillRect(QRectF(rect.left(), rect.top(), _STRIPE, rect.height()), stripe)
        if self._urgency in LATE:
            inset = _LATE_BORDER_WIDTH / 2
            painter.setPen(QPen(LATE_BORDER, _LATE_BORDER_WIDTH))
            painter.drawRect(QRectF(self.rect()).adjusted(inset, inset, -inset, -inset))
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
