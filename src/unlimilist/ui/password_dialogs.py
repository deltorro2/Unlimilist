"""The Notebook password's dialogs: typing it, creating it and changing it. Each is opened through a function,
so the caller (and its tests) only see the answer."""

from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

_SHAKE_MS = 300


def _password_field() -> QLineEdit:
    field = QLineEdit()
    field.setEchoMode(QLineEdit.EchoMode.Password)
    field.setMinimumWidth(260)
    return field


class _PasswordDialog(QDialog):
    """A message, some password fields, an error line and OK/Cancel. `accept_if` decides whether OK closes."""

    def __init__(self, title: str, message: str, labels: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("passwordDialog")
        self.message = QLabel(message)
        self.message.setWordWrap(True)
        self.fields = [_password_field() for _ in labels]
        form = QFormLayout()
        for label, field in zip(labels, self.fields):
            form.addRow(label, field)
        self.error = QLabel()
        self.error.setObjectName("passwordError")
        self.error.hide()
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self._ok)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(self.message)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addWidget(self.buttons)
        self.accept_if: Callable[[list[str]], str | None] = lambda values: None  # an error, or None to close
        self._shake: QPropertyAnimation | None = None

    def values(self) -> list[str]:
        return [field.text() for field in self.fields]

    def _ok(self) -> None:
        error = self.accept_if(self.values())
        if error is None:
            self.accept()
            return
        self.error.setText(error)
        self.error.show()
        self.fields[0].selectAll()
        self.fields[0].setFocus()
        self._shake_window()

    def _shake_window(self) -> None:
        """A quick side-to-side shake, the macOS way of saying "wrong password"."""
        start = self.pos()
        self._shake = QPropertyAnimation(self, b"pos", self)
        self._shake.setDuration(_SHAKE_MS)
        for step, dx in enumerate([0, -10, 10, -8, 8, -4, 4, 0]):
            self._shake.setKeyValueAt(step / 7, start + QPoint(dx, 0))
        self._shake.setEasingCurve(QEasingCurve.Type.Linear)
        self._shake.start()


def ask_password(
    parent: QWidget | None,
    accept: Callable[[str], bool],
    title: str = "Secured Note",
    message: str = "Type the Notebook password to open Secured Notes.",
) -> str | None:
    """The password once `accept` takes it, or None if cancelled. A wrong one shakes the dialog."""
    dialog = _PasswordDialog(title, message, ["Password:"], parent)
    dialog.accept_if = lambda values: None if accept(values[0]) else "Wrong password. Try again."
    return dialog.values()[0] if dialog.exec() == QDialog.DialogCode.Accepted else None


def _new_password_error(new: str, repeat: str) -> str | None:
    if not new:
        return "The password can't be empty."
    if new != repeat:
        return "The two passwords don't match."
    return None


def create_password(parent: QWidget | None) -> str | None:
    """A new Notebook password, typed twice, or None if cancelled."""
    dialog = _PasswordDialog(
        "Create the Notebook password",
        "Secured Notes are encrypted with one Notebook password. A copy is kept in your Keychain; "
        "without the password, Secured Notes can't be read.",
        ["Password:", "Repeat:"],
        parent,
    )
    dialog.accept_if = lambda values: _new_password_error(*values)
    return dialog.values()[0] if dialog.exec() == QDialog.DialogCode.Accepted else None


def change_password(parent: QWidget | None, is_current: Callable[[str], bool]) -> tuple[str, str] | None:
    """(old, new) once the old password is right and the new one is typed twice, or None if cancelled."""
    dialog = _PasswordDialog(
        "Change the Notebook password",
        "Every Secured Note is encrypted again with the new password.",
        ["Current password:", "New password:", "Repeat:"],
        parent,
    )

    def error(values: list[str]) -> str | None:
        old, new, repeat = values
        if not is_current(old):
            return "The current password is wrong."
        return _new_password_error(new, repeat)

    dialog.accept_if = error
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    old, new, _ = dialog.values()
    return old, new
