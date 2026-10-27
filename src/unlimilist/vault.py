"""The Vault: the folder that holds the Tasks and Notes (see docs/adr/0007-the-vault-location-is-kept-per-mac.md).
Any folder can be one; Tasks are kept in its tasks folder and Notes in its notes folder."""

from pathlib import Path

from unlimilist.note_store import MarkdownNoteStore
from unlimilist.notebook import Note
from unlimilist.secure import WrongPassword, decrypt

DEFAULT_NAME = "UnlimiList Vault"


def tasks_folder(vault: Path) -> Path:
    return vault / "tasks"


def notes_folder(vault: Path) -> Path:
    return vault / "notes"


def has_data(folder: Path) -> bool:
    """Whether `folder` already holds Tasks or Notes, i.e. a tasks or notes folder."""
    return tasks_folder(folder).is_dir() or notes_folder(folder).is_dir()


def new_vault_folder(location: Path, name: str) -> Path:
    """Where a new Vault called `name` goes in `location`. Raises ValueError if `name` isn't a plain folder name."""
    name = name.strip()
    if not name or "/" in name or name in (".", ".."):
        raise ValueError("Give the Vault a name, without a /.")
    return location / name


def has_secured_notes(vault: Path) -> bool:
    return _a_secured_note(vault) is not None


def password_opens(vault: Path, password: str) -> bool:
    """Whether `password` opens the Vault's Secured Notes; any password does when it has none."""
    secured = _a_secured_note(vault)
    if secured is None:
        return True
    try:
        decrypt(secured.body, password)
    except WrongPassword:
        return False
    return True


def _a_secured_note(vault: Path) -> Note | None:
    if not notes_folder(vault).is_dir():
        return None
    return next((note for note in MarkdownNoteStore(notes_folder(vault)).load_all() if note.secured), None)
