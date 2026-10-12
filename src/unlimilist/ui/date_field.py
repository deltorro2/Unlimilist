"""An optional date input: dd/mm/yyyy text, a calendar popup and a clear button."""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCalendarWidget,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QToolButton,
    QWidget,
    QWidgetAction,
)

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

        calendar_button = QToolButton()
        calendar_button.setText("📅")
        calendar_button.setToolTip("Pick a date")
        calendar_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        calendar_button.setMenu(menu)

        clear_button = QToolButton()
        clear_button.setText("✕")
        clear_button.setToolTip("Clear the date")
        clear_button.clicked.connect(lambda: self.set_date(None))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.line_edit, 1)
        layout.addWidget(calendar_button)
        layout.addWidget(clear_button)

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
        self.line_edit.setStyleSheet("" if self.is_valid() else "border: 1px solid #E53935;")
        self.dateChanged.emit()

    def _sync_calendar(self) -> None:
        current = self.date() if self.is_valid() else None
        current = current or date.today()
        self._calendar.setSelectedDate(QDate(current.year, current.month, current.day))

    def _on_calendar_picked(self, picked: QDate) -> None:
        self.set_date(date(picked.year(), picked.month(), picked.day()))
        self._menu.close()
