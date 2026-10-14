"""The app's name in the toolbar: "UnlimiList" in bold, its L inside a thin red ring, then the version in red."""

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


class AppTitle(QWidget):
    def __init__(self, name: str, version: str, ringed_letter: str = "L", parent=None):
        super().__init__(parent)
        self._name = name
        self._version = version
        index = name.index(ringed_letter)
        self._before, self._letter, self._after = name[:index], name[index], name[index + 1 :]
        self.setAccessibleName(f"{name} {version}")
        self.setToolTip(f"{name} {version}")

        self._name_font = QFont(self.font())
        self._name_font.setPixelSize(_NAME_PIXELS)
        self._name_font.setWeight(QFont.Weight.ExtraBold)
        self._version_font = QFont(self._name_font)
        self._version_font.setPixelSize(_VERSION_PIXELS)
        self._version_font.setWeight(QFont.Weight.Bold)
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
        x += version_width + _MARGIN
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
        painter.end()


def _ink(font: QFont, text: str) -> QRectF:
    """The exact bounds of `text`'s outline when drawn at the origin (y is negative above the baseline)."""
    if not text:
        return QRectF()
    path = QPainterPath()
    path.addText(0, 0, font, text)
    return path.boundingRect()
