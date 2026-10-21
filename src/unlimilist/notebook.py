"""The Notebook: owns every Note and the rules for Titles, Daily notes, Tags and Secured Notes."""

import re
import secrets
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Protocol

from unlimilist.secure import decrypt, encrypt

TITLE_LIMIT = 80
_DAILY_TAG = "daily"
_TAG_NAME = re.compile(r"[^\W\d_][\w-]*")  # the Tag rule: a letter, then letters, digits, - or _


class NoteType(Enum):
    OPEN = "open"
    SECURED = "secured"


@dataclass(frozen=True)
class Note:
    id: str
    title: str
    body: str  # as kept: Markdown for an Open Note, the encrypted block for a Secured one
    note_type: NoteType
    tags: tuple[str, ...]
    created_at: datetime
    opened_at: datetime | None = None

    @property
    def secured(self) -> bool:
        return self.note_type == NoteType.SECURED

    @property
    def size(self) -> int:
        """The kept Body's size in bytes."""
        return len(self.body.encode("utf-8"))

    @property
    def last_activity(self) -> datetime:
        return self.opened_at or self.created_at

    def matches_tag_filter(self, tag_filter: Iterable[str]) -> bool:
        keys = {key.casefold() for key in tag_filter}
        return not keys or any(name.casefold() in keys for name in self.tags)


def is_tag_name(name: str) -> bool:
    return _TAG_NAME.fullmatch(name) is not None


def title_from_text(text: str, limit: int = TITLE_LIMIT) -> str:
    """The first line of `text`, cut at a whole word to at most `limit` characters, with … if cut."""
    line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if len(line) <= limit:
        return line
    room = line[: limit - 1]
    space = room.rfind(" ")
    return (room[:space] if space > 0 else room).rstrip() + "…"


def daily_title(day: datetime) -> str:
    return f"Daily note {day.day} {day:%b %Y}"


class NoteStore(Protocol):
    """Where the Notebook keeps its Notes between runs."""

    def load_all(self) -> list[Note]: ...

    def save(self, note: Note) -> None: ...

    def delete(self, note: Note) -> None: ...


class InMemoryNoteStore:
    def __init__(self, notes: Iterable[Note] = ()):
        self._notes = {n.id: n for n in notes}

    def load_all(self) -> list[Note]:
        return list(self._notes.values())

    def save(self, note: Note) -> None:
        self._notes[note.id] = note

    def delete(self, note: Note) -> None:
        self._notes.pop(note.id, None)


class Notebook:
    def __init__(self, store: NoteStore | None = None, clock: Callable[[], datetime] = datetime.now):
        self._store = store or InMemoryNoteStore()
        self._clock = clock
        self._notes: dict[str, Note] = {n.id: n for n in self._store.load_all()}
        self._listeners: list[Callable[[str, Note | None], None]] = []

    def subscribe(self, listener: Callable[[str, Note | None], None]) -> None:
        """Call `listener(note_id, note)` after every change; `note` is None once the Note is deleted."""
        self._listeners.append(listener)

    def notes(self) -> list[Note]:
        """Every Note, the most recently opened or created first."""
        return sorted(self._notes.values(), key=lambda n: (n.last_activity, n.created_at, n.id), reverse=True)

    def note(self, note_id: str) -> Note:
        return self._notes[note_id]

    def has_note(self, note_id: str) -> bool:
        return note_id in self._notes

    def create(
        self,
        title: str,
        body: str,
        tags: Iterable[str] = (),
        note_type: NoteType = NoteType.OPEN,
        password: str | None = None,
        opened: bool = False,
    ) -> Note | None:
        """A new Note, or None if it has neither Title nor Body. `opened` when it is being shown as it is made."""
        if not title.strip() and not body.strip():
            return None
        now = self._clock()
        title, tags = self._finish(title, body, tags)
        note = Note(
            id=f"{now:%Y-%m-%d}-{secrets.token_hex(3)}",
            title=title,
            body=self._seal(body, note_type, password),
            note_type=note_type,
            tags=tags,
            created_at=now,
            opened_at=now if opened else None,
        )
        return self._put(note)

    def quick_add(self, text: str) -> Note | None:
        """The whole text is the Body; its first line, shortened, is the Title."""
        if not text.strip():
            return None
        return self.create(title_from_text(text), text.strip())

    def save(
        self,
        note_id: str,
        title: str,
        body: str,
        tags: Iterable[str],
        note_type: NoteType,
        password: str | None = None,
    ) -> Note:
        """Save a Note's edits. `body` is the plain Body; a Secured Note is encrypted with `password`."""
        title, tags = self._finish(title, body, tags)
        note = replace(
            self._notes[note_id],
            title=title,
            body=self._seal(body, note_type, password),
            note_type=note_type,
            tags=tags,
        )
        return self._put(note)

    def read_body(self, note_id: str, password: str | None = None) -> str:
        """The plain Body. A Secured Note needs the password and raises WrongPassword without the right one."""
        note = self._notes[note_id]
        if not note.secured:
            return note.body
        return decrypt(note.body, password or "")

    def mark_opened(self, note_id: str) -> Note:
        return self._put(replace(self._notes[note_id], opened_at=self._clock()))

    def delete(self, note_id: str) -> None:
        note = self._notes.pop(note_id)
        self._store.delete(note)
        for listener in self._listeners:
            listener(note_id, None)

    def change_password(self, old: str, new: str) -> None:
        """Re-encrypt every Secured Note with the new password. Every one is read first, so if any doesn't open
        with `old` (WrongPassword) nothing has changed."""
        bodies = {n.id: decrypt(n.body, old) for n in self._notes.values() if n.secured}
        for note_id, body in bodies.items():
            self._put(replace(self._notes[note_id], body=encrypt(body, new)))

    def tags(self) -> list[tuple[str, int]]:
        """Every Tag on a Note, A to Z, with how many Notes have it. A Tag is spelled as first used."""
        counted: dict[str, list] = {}
        for note in sorted(self._notes.values(), key=lambda n: (n.created_at, n.id)):
            for name in note.tags:
                entry = counted.setdefault(name.casefold(), [name, 0])
                entry[1] += 1
        return sorted(((name, count) for name, count in counted.values()), key=lambda item: item[0].casefold())

    def _finish(self, title: str, body: str, tags: Iterable[str]) -> tuple[str, tuple[str, ...]]:
        """Check the Tags, drop repeats, and make a Note with a Body but no Title a Daily note."""
        kept: dict[str, str] = {}
        for name in tags:
            if not is_tag_name(name):
                raise ValueError(f"not a Tag: {name!r}")
            kept.setdefault(name.casefold(), name)
        title = title.strip()
        if not title:
            title = daily_title(self._clock())
            kept.setdefault(_DAILY_TAG, _DAILY_TAG)
        return title, tuple(kept.values())

    @staticmethod
    def _seal(body: str, note_type: NoteType, password: str | None) -> str:
        if note_type == NoteType.OPEN:
            return body
        if not password:
            raise ValueError("a Secured Note needs the Notebook password")
        return encrypt(body, password)

    def _put(self, note: Note) -> Note:
        self._notes[note.id] = note
        self._store.save(note)
        for listener in self._listeners:
            listener(note.id, note)
        return note
