"""How the Notebook's rows are drawn: flat raised rows, not convex like Task cards. A plain fill, a light line along
the top edge, and a darker line with a soft two-pixel shade along the bottom. The row under the mouse turns light
blue and its shade deepens."""

from PySide6.QtCore import QEvent, QModelIndex, QObject, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTableWidget

ROW_HEIGHT = 40
FILL = QColor("#FAFBFC")
TOP_EDGE = QColor("#FFFFFF")
BOTTOM_EDGE = QColor("#D9DDE5")
SHADE = [QColor("#E7EAF0"), QColor("#F0F2F6")]  # under the bottom edge, fading into the table
HOVER_FILL = QColor("#EEF4FF")
HOVER_TOP_EDGE = QColor("#F8FBFF")
HOVER_BOTTOM_EDGE = QColor("#C3D1EE")
HOVER_SHADE = [QColor("#D5DFF3"), QColor("#E4EAF6")]
_HOVER_ROW = "hoverRow"  # the table property holding the row under the mouse (-1: none)


class NoteRowDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        table = self.parent()
        hovered = index.row() == table.property(_HOVER_ROW)
        fill, top, bottom, shade = (
            (HOVER_FILL, HOVER_TOP_EDGE, HOVER_BOTTOM_EDGE, HOVER_SHADE)
            if hovered
            else (FILL, TOP_EDGE, BOTTOM_EDGE, SHADE)
        )
        rect = option.rect
        painter.save()
        painter.fillRect(rect, fill)
        highlight = index.data(Qt.ItemDataRole.BackgroundRole)  # a new Note's yellow, fading
        if highlight is not None:
            painter.fillRect(rect, highlight)
        painter.fillRect(rect.left(), rect.top(), rect.width(), 1, top)
        bottom_y = rect.bottom() - len(shade)
        painter.fillRect(rect.left(), bottom_y, rect.width(), 1, bottom)
        for step, colour in enumerate(shade, start=1):
            painter.fillRect(rect.left(), bottom_y + step, rect.width(), 1, colour)
        painter.restore()
        # The text and icon, over the row as drawn: no hover or selection background of the style's own.
        plain = QStyleOptionViewItem(option)
        plain.state &= ~(QStyle.StateFlag.State_MouseOver | QStyle.StateFlag.State_Selected)
        plain.backgroundBrush = Qt.BrushStyle.NoBrush
        self.initStyleOption(plain, index)
        plain.backgroundBrush = Qt.BrushStyle.NoBrush
        style = table.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, plain, painter, table)


class _HoverTracker(QObject):
    """Keeps the table's hoverRow up to date as the mouse moves over it and leaves it."""

    def __init__(self, table: QTableWidget):
        super().__init__(table)
        self._table = table
        table.viewport().installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.MouseMove:
            self._set(self._table.rowAt(event.position().toPoint().y()))
        elif event.type() in (QEvent.Type.Leave, QEvent.Type.Hide):
            self._set(-1)
        return False

    def _set(self, row: int) -> None:
        if self._table.property(_HOVER_ROW) != row:
            self._table.setProperty(_HOVER_ROW, row)
            self._table.viewport().update()


def style_rows(table: QTableWidget) -> None:
    """Draw `table`'s rows raised and flat, tinting the one under the mouse."""
    table.setProperty(_HOVER_ROW, -1)
    table.setMouseTracking(True)
    table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
    table.setItemDelegate(NoteRowDelegate(table))
    _HoverTracker(table)
