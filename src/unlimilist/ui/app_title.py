"""The app's name in the toolbar: "UnlimiList" in bold, its L inside a thin red ring, then the version in red,
and in a test build an orange "TEST" tag."""

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

_INK = QColor("#1B1B1F")
_RED = QColor("#DC0405")  # the red of the logo reference
_NAME_PIXELS = 22
_VERSION_PIXELS = 16
_RING_TO_CAP = 1.75  # ring diameter, as a multiple of the capital letters' height
_RING_WIDTH_TO_DIAMETER = 0.045
_MARGIN = 2
_GAP_TO_CAP = 0.18  # clear space between the ring and the letters beside it
_MIN_GAP = 2.5
_TAG = QColor("#F57C00")  # a test build's tag: orange, so it never passes for the real app
_TAG_PIXELS = 11
_TAG_PADDING = 5


class AppTitle(QWidget):
    def __init__(self, name: str, version: str, ringed_letter: str = "L", parent=None, tag: str | None = None):
        super().__init__(parent)
        self._name = name
        self._version = version
        self._tag = tag
        index = name.index(ringed_letter)
        self._before, self._letter, self._after = name[:index], name[index], name[index + 1 :]
        label = f"{name} {version}" + (f" {tag}" if tag else "")
        self.setAccessibleName(label)
        self.setToolTip(label)

        self._name_font = QFont(self.font())
        self._name_font.setPixelSize(_NAME_PIXELS)
        self._name_font.setWeight(QFont.Weight.ExtraBold)
        self._version_font = QFont(self._name_font)
        self._version_font.setPixelSize(_VERSION_PIXELS)
        self._version_font.setWeight(QFont.Weight.Bold)
        self._tag_font = QFont(self._name_font)
        self._tag_font.setPixelSize(_TAG_PIXELS)
        self._tag_font.setWeight(QFont.Weight.Bold)
        self._layout()
        self.setFixedSize(self.sizeHint())

    def name(self) -> str:
        return self._name

    def version(self) -> str:
        return self._version

    def ring_rect(self) -> QRectF:
        return QRectF(self._ring)

    def ring_width(self) -> float:
        return self._pen_width

    def tag(self) -> str | None:
        return self._tag

    def tag_rect(self) -> QRectF:
        return QRectF(self._tag_box)

    def version_rect(self) -> QRectF:
        return QRectF(self._version_box)

    def name_rect_before_ring(self) -> QRectF:
        return QRectF(self._before_box)

    def sizeHint(self) -> QSize:
        return self._size

    def _layout(self) -> None:
        """Work out where each part goes from the letters' actual outlines, not font metrics: the ring is
        centred on its letter, and the letters on either side keep a clear gap from it."""
        version = QFontMetricsF(self._version_font)
        letter = _ink(self._name_font, self._letter)
        cap = letter.height()
        diameter = cap * _RING_TO_CAP
        self._pen_width = max(1.5, diameter * _RING_WIDTH_TO_DIAMETER)
        gap = max(_MIN_GAP, cap * _GAP_TO_CAP)
        height = diameter + 2 * _MARGIN
        centre_y = height / 2
        self._baseline = centre_y - letter.center().y()

        before = _ink(self._name_font, self._before)
        self._before_x = _MARGIN - before.left()
        self._before_box = QRectF(_MARGIN, self._baseline + before.top(), before.width(), before.height())
        ring_left = _MARGIN + before.width() + gap
        self._ring = QRectF(ring_left, centre_y - diameter / 2, diameter, diameter)
        self._letter_x = self._ring.center().x() - letter.center().x()

        after = _ink(self._name_font, self._after)
        self._after_x = self._ring.right() + gap - after.left()
        x = self._after_x + after.right() + QFontMetricsF(self._name_font).horizontalAdvance(" ") * 1.1
        self._version_x = x
        version_width = version.horizontalAdvance(self._version)
        self._version_box = QRectF(x, self._baseline - version.capHeight(), version_width, version.capHeight())
        x += version_width
        self._tag_box = QRectF()
        if self._tag:
            tag = QFontMetricsF(self._tag_font)
            width = tag.horizontalAdvance(self._tag) + 2 * _TAG_PADDING
            box_height = tag.capHeight() + 2 * _TAG_PADDING * 0.7
            x += gap * 1.5
            # Level with the version's capitals.
            middle = self._baseline - version.capHeight() / 2
            self._tag_box = QRectF(x, middle - box_height / 2, width, box_height)
            x += width
        x += _MARGIN
        self._size = QSize(int(x + 1), int(height + 1))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        painter.setFont(self._name_font)
        painter.setPen(_INK)
        painter.drawText(QPointF(self._before_x, self._baseline), self._before)
        painter.drawText(QPointF(self._letter_x, self._baseline), self._letter)
        painter.drawText(QPointF(self._after_x, self._baseline), self._after)

        painter.setPen(QPen(_RED, self._pen_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inset = self._pen_width / 2
        painter.drawEllipse(self._ring.adjusted(inset, inset, -inset, -inset))

        painter.setFont(self._version_font)
        painter.setPen(_RED)
        painter.drawText(QPointF(self._version_x, self._baseline), self._version)

        if self._tag:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_TAG)
            radius = self._tag_box.height() / 2
            painter.drawRoundedRect(self._tag_box, radius, radius)
            painter.setFont(self._tag_font)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(self._tag_box, Qt.AlignmentFlag.AlignCenter, self._tag)
        painter.end()


def _ink(font: QFont, text: str) -> QRectF:
    """The exact bounds of `text`'s outline when drawn at the origin (y is negative above the baseline)."""
    if not text:
        return QRectF()
    path = QPainterPath()
    path.addText(0, 0, font, text)
    return path.boundingRect()


class RingedLetter(QWidget):
    """One letter centred in a thin red ring: the L of the logo on its own."""

    def __init__(self, letter: str = "L", size: int = 52, parent=None):
        super().__init__(parent)
        self._letter = letter
        self._font = QFont(self.font())
        self._font.setPixelSize(round(size / _RING_TO_CAP))
        self._font.setWeight(QFont.Weight.ExtraBold)
        self._pen_width = max(1.5, size * _RING_WIDTH_TO_DIAMETER)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        inset = self._pen_width / 2
        ring = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        painter.setPen(QPen(_RED, self._pen_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ring)
        ink = _ink(self._font, self._letter)
        painter.setFont(self._font)
        painter.setPen(_INK)
        painter.drawText(QPointF(ring.center().x() - ink.center().x(), ring.center().y() - ink.center().y()), self._letter)
        painter.end()
