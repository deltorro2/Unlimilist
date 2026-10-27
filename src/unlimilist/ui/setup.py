"""Setup, shown when the app starts with no Vault chosen: a welcome, then opening an existing Vault or creating a
new one, then the Notebook password if this Mac has none yet. Also finds the Vault at every start (open_vault)
and lets Settings choose another (pick_vault). Nothing here ever moves or copies files.

The folder chooser and the questions are module functions, so tests can answer them."""

import os
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from unlimilist.notebook_password import NotebookPassword
from unlimilist.settings import SettingsStore
from unlimilist.ui.icons import app_icon
from unlimilist.vault import DEFAULT_NAME, has_data, has_secured_notes, new_vault_folder, password_opens

_PAGES = ("welcome", "vault", "password")
_ICON_SIZE = 96
_KEEP_CURRENT = "Your current Vault stays where it is; nothing is moved or copied."


def choose_folder(parent: QWidget | None, title: str, start: Path) -> Path | None:
    folder = QFileDialog.getExistingDirectory(parent, title, str(start))
    return Path(folder) if folder else None


def confirm_empty(parent: QWidget | None, folder: Path, switching: bool = False) -> bool:
    """Whether to use a folder without Tasks or Notes as a new, empty Vault (False: choose another)."""
    box = QMessageBox(parent)
    box.setWindowTitle("No Tasks or Notes here")
    box.setText(f"“{folder.name}” has no Tasks or Notes yet. Use it as a new, empty Vault?")
    if switching:
        box.setInformativeText(_KEEP_CURRENT)
    use = box.addButton("Use it", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Choose another…", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is use


def confirm_switch(parent: QWidget | None, folder: Path) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle("Switch Vault")
    box.setText(f"Switch to the Vault in “{folder}”?")
    box.setInformativeText(_KEEP_CURRENT)
    switch = box.addButton("Switch", QMessageBox.ButtonRole.AcceptRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.exec()
    return box.clickedButton() is switch


def vault_missing(parent: QWidget | None, folder: Path) -> str:
    """"retry", "choose" or "quit", for a saved Vault that isn't there."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Vault not found")
    box.setText("Your UnlimiList Vault can't be found.")
    box.setInformativeText(
        f"It should be at “{folder}”. If it's on a drive, plug it in; if a service like Dropbox syncs it, let the "
        "sync finish. Then try again, or choose another folder."
    )
    retry = box.addButton("Try again", QMessageBox.ButtonRole.AcceptRole)
    choose = box.addButton("Choose…", QMessageBox.ButtonRole.ActionRole)
    box.addButton("Quit", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return {retry: "retry", choose: "choose"}.get(box.clickedButton(), "quit")


def pick_vault(parent: QWidget | None, start: Path, switching: bool = False) -> Path | None:
    """Browse for a Vault. A folder without Tasks or Notes is used only once confirmed; when `switching` from
    another Vault, one with them is confirmed too. None if cancelled."""
    while True:
        folder = choose_folder(parent, "Choose your UnlimiList Vault", start)
        if folder is None:
            return None
        if not has_data(folder):
            if confirm_empty(parent, folder, switching):
                return folder
            start = folder
            continue
        return folder if not switching or confirm_switch(parent, folder) else None


def open_vault(store: SettingsStore, password: NotebookPassword, parent: QWidget | None = None) -> Path | None:
    """The Vault to open at start: the saved one, or the one chosen in Setup when none is saved yet; a missing one
    can be waited for or replaced. A new choice is saved. None means quit."""
    settings = store.load()
    if settings.vault is None:
        setup = SetupDialog(password, parent)
        if setup.exec() != QDialog.DialogCode.Accepted:
            return None
        vault = setup.vault()
    else:
        vault = Path(settings.vault)
        while not vault.is_dir():  # never made here: a late sync would then find two Vaults
            answer = vault_missing(parent, vault)
            if answer == "quit":
                return None
            if answer == "choose":
                start = vault.parent if vault.parent.is_dir() else Path.home()
                vault = pick_vault(parent, start) or vault
    if str(vault) != settings.vault:
        store.save(replace(settings, vault=str(vault)))
    return vault


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("settingsHint")
    label.setWordWrap(True)
    return label


def _password_field() -> QLineEdit:
    field = QLineEdit()
    field.setEchoMode(QLineEdit.EchoMode.Password)
    return field


class SetupDialog(QDialog):
    """Closing it before the end means there is no Vault, so the app quits."""

    def __init__(self, password: NotebookPassword, parent=None, home: Path | None = None):
        super().__init__(parent)
        self.setWindowTitle("Set up UnlimiList")
        self.setObjectName("setupDialog")
        self.setMinimumWidth(560)
        self._password = password
        self._home = home or Path.home()
        self._vault: Path | None = None

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_welcome())
        self.pages.addWidget(self._build_vault())
        self.pages.addWidget(self._build_password())

        self.error = QLabel()
        self.error.setObjectName("passwordError")
        self.error.setWordWrap(True)
        self.error.hide()

        self.back_button = QPushButton("Back")
        self.back_button.setAutoDefault(False)
        self.back_button.clicked.connect(self._back)
        self.skip_button = QPushButton("Skip")
        self.skip_button.setAutoDefault(False)
        self.skip_button.clicked.connect(lambda: self._finish(None))
        self.continue_button = QPushButton("Continue")
        self.continue_button.setDefault(True)
        self.continue_button.clicked.connect(self._continue)
        buttons = QHBoxLayout()
        buttons.addWidget(self.back_button)
        buttons.addStretch(1)
        buttons.addWidget(self.skip_button)
        buttons.addWidget(self.continue_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 18)
        layout.setSpacing(12)
        layout.addWidget(self.pages, 1)
        layout.addWidget(self.error)
        layout.addLayout(buttons)
        self._show("welcome")

    # Pages

    def _build_welcome(self) -> QWidget:
        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(_ICON_SIZE, _ICON_SIZE))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel("Welcome to UnlimiList")
        self.title.setObjectName("setupTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        line = _hint("Tasks and Notes in one place, kept as plain Markdown files in a folder you choose.")
        line.setAlignment(Qt.AlignmentFlag.AlignCenter)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        layout.addWidget(icon)
        layout.addWidget(self.title)
        layout.addWidget(line)
        layout.addStretch(1)
        return page

    def _build_vault(self) -> QWidget:
        question = QLabel("Do you already have an UnlimiList Vault?")
        question.setObjectName("settingsHeading")
        about = _hint("Your Vault is the folder that keeps all your Tasks and Notes.")
        self.sync_hint = _hint(
            "Tip: put it in a folder that Dropbox, Google Drive or a similar service keeps in sync, and your "
            "other Macs can use the same Vault."
        )

        self.have_vault = QRadioButton("Yes, open my Vault")
        self.new_vault = QRadioButton("No, create a new Vault")
        choice = QButtonGroup(self)
        choice.addButton(self.have_vault)
        choice.addButton(self.new_vault)
        choice.buttonClicked.connect(lambda _: self._show_vault_fields())

        self.vault_field = QLineEdit()
        self.vault_field.setReadOnly(True)
        self.vault_field.setPlaceholderText("Choose the folder of your Vault")
        self.browse_vault_button = QPushButton("Browse…")
        self.browse_vault_button.setAutoDefault(False)
        self.browse_vault_button.clicked.connect(self._browse_vault)
        self._existing = QWidget()
        existing = QHBoxLayout(self._existing)
        existing.setContentsMargins(24, 0, 0, 0)
        existing.addWidget(self.vault_field, 1)
        existing.addWidget(self.browse_vault_button)

        self.location_field = QLineEdit(str(self._home / "Documents"))
        self.location_field.textChanged.connect(lambda _: self._show_vault_fields())
        self.browse_location_button = QPushButton("Browse…")
        self.browse_location_button.setAutoDefault(False)
        self.browse_location_button.clicked.connect(self._browse_location)
        self.name_field = QLineEdit(DEFAULT_NAME)
        self.name_field.textChanged.connect(lambda _: self._show_vault_fields())
        location = QHBoxLayout()
        location.addWidget(self.location_field, 1)
        location.addWidget(self.browse_location_button)
        self._new = QWidget()
        new = QFormLayout(self._new)
        new.setContentsMargins(24, 0, 0, 0)
        new.addRow("Location:", location)
        new.addRow("Name:", self.name_field)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        layout.addWidget(question)
        layout.addWidget(about)
        layout.addWidget(self.sync_hint)
        layout.addSpacing(4)
        layout.addWidget(self.have_vault)
        layout.addWidget(self._existing)
        layout.addWidget(self.new_vault)
        layout.addWidget(self._new)
        layout.addStretch(1)
        return page

    def _build_password(self) -> QWidget:
        heading = QLabel("Notebook password")
        heading.setObjectName("settingsHeading")
        self.password_message = _hint("")
        self.password_field = _password_field()
        self.repeat_field = _password_field()
        form = QFormLayout()
        form.addRow("Password:", self.password_field)
        form.addRow("Repeat:", self.repeat_field)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        layout.addWidget(heading)
        layout.addWidget(self.password_message)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    # Moving through

    def page(self) -> str:
        return _PAGES[self.pages.currentIndex()]

    def vault(self) -> Path | None:
        """The Vault chosen, once Setup has finished."""
        return self._vault

    def _show(self, page: str) -> None:
        self.pages.setCurrentIndex(_PAGES.index(page))
        self.error.hide()
        self.back_button.setHidden(page == "welcome")
        self.skip_button.setVisible(page == "password")
        last = page == "password" or (page == "vault" and self._password.exists())
        self.continue_button.setText("Finish" if last else "Continue")
        if page == "vault":
            self._show_vault_fields()
        else:
            self.continue_button.setEnabled(True)

    def _show_vault_fields(self) -> None:
        self._existing.setEnabled(self.have_vault.isChecked())
        self._new.setEnabled(self.new_vault.isChecked())
        if self.have_vault.isChecked():
            ready = bool(self.vault_field.text())
        else:
            ready = self.new_vault.isChecked() and bool(self.location_field.text() and self.name_field.text())
        self.continue_button.setEnabled(ready)

    def _back(self) -> None:
        self._show(_PAGES[self.pages.currentIndex() - 1])

    def _continue(self) -> None:
        page = self.page()
        if page == "welcome":
            self._show("vault")
        elif page == "vault":
            vault = self._chosen_vault()
            if vault is None:
                return
            self._vault = vault
            if self._password.exists():
                self._finish(None)
            else:
                self._show_password_page()
        else:
            self._finish_with_password()

    def _browse_vault(self) -> None:
        folder = pick_vault(self, Path(self.vault_field.text() or self._home))
        if folder is not None:
            self.vault_field.setText(str(folder))
            self._show_vault_fields()

    def _browse_location(self) -> None:
        folder = choose_folder(self, "Where to create your Vault", Path(self.location_field.text() or self._home))
        if folder is not None:
            self.location_field.setText(str(folder))

    def _chosen_vault(self) -> Path | None:
        """The Vault the page points at, or None after showing why it can't be used."""
        if self.have_vault.isChecked():
            return Path(self.vault_field.text())
        try:
            folder = new_vault_folder(Path(self.location_field.text()), self.name_field.text())
        except ValueError as problem:
            return self._refuse(str(problem))
        if not folder.parent.is_dir():
            return self._refuse("That location doesn't exist. Choose a folder with Browse….")
        return folder

    def _show_password_page(self) -> None:
        if has_secured_notes(self._vault):
            text = (
                "This Vault has Secured Notes. Type the Notebook password they were made with; it is then kept in "
                "this Mac's Keychain."
            )
        else:
            text = (
                "Secured Notes are encrypted with one Notebook password, kept in this Mac's Keychain. Every Vault "
                "you open on this Mac uses it. You can skip this: it is then created with your first Secured Note."
            )
        self.password_message.setText(text)
        self._show("password")
        self.password_field.setFocus()

    def _finish_with_password(self) -> None:
        typed, repeat = self.password_field.text(), self.repeat_field.text()
        if not typed:
            self._refuse("The password can't be empty. To set it later, choose Skip.")
        elif typed != repeat:
            self._refuse("The two passwords don't match.")
        elif not password_opens(self._vault, typed):
            self._refuse("This password doesn't open the Vault's Secured Notes.")
        else:
            self._finish(typed)

    def _finish(self, password: str | None) -> None:
        try:
            self._vault.mkdir(parents=True, exist_ok=True)
        except OSError as problem:
            self._refuse(f"The Vault can't be created there: {problem.strerror or problem}.")
            return
        if not os.access(self._vault, os.W_OK):
            self._refuse("You can't save files in that folder. Choose another.")
            return
        if password is not None:
            self._password.create(password)
        self.accept()

    def _refuse(self, text: str) -> None:
        self.error.setText(text)
        self.error.show()
        return None
