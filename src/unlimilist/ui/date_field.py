"""An optional date input: dd/mm/yyyy text, a calendar popup and a clear button."""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QDate, QEvent, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCalendarWidget,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QToolButton,
    QWidget,
    QWidgetAction,
)

from unlimilist.ui.icons import icon

DATE_FORMAT = "%d/%m/%Y"


def format_date(value: date) -> str:
    return value.strftime(DATE_FORMAT)


class DateField(QWidget):
    dateChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("dd/mm/yyyy")
        self.line_edit.textChanged.connect(self._on_text_changed)

        self._calendar = QCalendarWidget()
        self._calendar.clicked.connect(self._on_calendar_picked)
        menu = QMenu(self)
        action = QWidgetAction(menu)
        action.setDefaultWidget(self._calendar)
        menu.addAction(action)
        menu.aboutToShow.connect(self._sync_calendar)
        self._menu = menu

        self.line_edit.setObjectName("dateText")
        self.line_edit.setFrame(False)
        self.line_edit.installEventFilter(self)

        calendar_button = QToolButton()
        calendar_button.setObjectName("dateCalendar")
        calendar_button.setIcon(icon("calendar", "#6B6F7A"))
        calendar_button.setIconSize(QSize(18, 18))
        calendar_button.setToolTip("Pick a date")
        calendar_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        calendar_button.setMenu(menu)
        calendar_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._clear_button = QToolButton()
        self._clear_button.setObjectName("dateClear")
        self._clear_button.setIcon(icon("x", "#3A3D45", 14))
        self._clear_button.setIconSize(QSize(14, 14))
        self._clear_button.setToolTip("Clear the date")
        self._clear_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._clear_button.clicked.connect(lambda: self.set_date(None))
        self._clear_button.hide()

        self._box = QFrame()
        self._box.setObjectName("dateBox")
        box_layout = QHBoxLayout(self._box)
        box_layout.setContentsMargins(10, 4, 6, 4)
        box_layout.setSpacing(6)
        box_layout.addWidget(calendar_button)
        box_layout.addWidget(self.line_edit, 1)
        box_layout.addWidget(self._clear_button)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._box)

    def eventFilter(self, watched, event):
        if watched is self.line_edit and event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self._set_box_state("focused" if event.type() == QEvent.Type.FocusIn else "")
        return super().eventFilter(watched, event)

    def _set_box_state(self, state: str) -> None:
        if not self.is_valid():
            state = "invalid"
        self._box.setProperty("state", state)
        self._box.style().unpolish(self._box)
        self._box.style().polish(self._box)

    def date(self) -> date | None:
        """The entered date, or None when empty. Raises ValueError for unreadable text."""
        text = self.line_edit.text().strip()
        if not text:
            return None
        return datetime.strptime(text, DATE_FORMAT).date()

    def set_date(self, value: date | None) -> None:
        self.line_edit.setText(format_date(value) if value else "")

    def is_valid(self) -> bool:
        try:
            self.date()
        except ValueError:
            return False
        return True

    def _on_text_changed(self) -> None:
        self._clear_button.setVisible(bool(self.line_edit.text()))
        self._set_box_state("focused" if self.line_edit.hasFocus() else "")
        self.dateChanged.emit()

    def _sync_calendar(self) -> None:
        current = self.date() if self.is_valid() else None
        current = current or date.today()
        self._calendar.setSelectedDate(QDate(current.year, current.month, current.day))

    def _on_calendar_picked(self, picked: QDate) -> None:
        self.set_date(date(picked.year(), picked.month(), picked.day()))
        self._menu.close()
