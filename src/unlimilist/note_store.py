"""Keeps each Note as one Markdown file, named after its id:

    ---
    id: 2026-10-21-a1b2c3
    title: Trip to Lisbon
    type: open
    tags:
    - travel
    created_at: 2026-10-21 14:05:00
    opened_at: null
    ---
    <the Body: Markdown, or a Secured Note's encrypted block>
"""

import os
from datetime import date, datetime
from pathlib import Path

import yaml

from unlimilist.notebook import Note, NoteType

_DELETED = "-deleted"  # a deleted Open Note's file ends in .md-deleted, which load_all's *.md never matches


class MarkdownNoteStore:
    def __init__(self, folder: Path):
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.warnings: list[str] = []

    def load_all(self) -> list[Note]:
        self.warnings = []
        notes = []
        for path in sorted(self.folder.glob("*.md")):
            try:
                notes.append(_parse(path.read_text(encoding="utf-8"), path.stem))
            except Exception as error:  # a hand-edited file may be broken in any way
                self.warnings.append(f"Skipped {path.name}: {error}")
        return notes

    def save(self, note: Note) -> None:
        path = self._path(note.id)
        temporary = path.with_suffix(".md.tmp")
        temporary.write_text(_render(note), encoding="utf-8")
        os.replace(temporary, path)

    def delete(self, note: Note) -> None:
        """An Open Note's file is kept, renamed to end in -deleted, so it can be recovered by hand. A Secured
        Note's file is removed outright."""
        path = self._path(note.id)
        if not path.exists():
            return
        if note.secured:
            path.unlink()
            return
        target = path.with_name(f"{path.name}{_DELETED}")
        number = 2
        while target.exists():
            target = path.with_name(f"{path.name}{_DELETED}-{number}")
            number += 1
        os.replace(path, target)

    def _path(self, note_id: str) -> Path:
        return self.folder / f"{note_id}.md"


def _render(note: Note) -> str:
    meta = {
        "id": note.id,
        "title": note.title,
        "type": note.note_type.value,
        "tags": list(note.tags),
        "created_at": note.created_at,
        "opened_at": note.opened_at,
    }
    front_matter = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)
    return f"---\n{front_matter}---\n{note.body}\n"


def _parse(text: str, fallback_id: str) -> Note:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing front matter")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    meta = yaml.safe_load("\n".join(lines[1:end])) or {}
    body = "\n".join(lines[end + 1 :])
    if body.endswith("\n"):
        body = body[:-1]  # the newline the file ends with
    tags = meta.get("tags") or []
    if not isinstance(tags, list):
        raise ValueError("tags is not a list")
    return Note(
        id=str(meta.get("id") or fallback_id),
        title=str(meta.get("title") or ""),
        body=body,
        note_type=NoteType(meta.get("type") or NoteType.OPEN.value),
        tags=tuple(str(tag) for tag in tags),
        created_at=_as_datetime(meta.get("created_at")) or datetime.now(),
        opened_at=_as_datetime(meta.get("opened_at")),
    )


def _as_datetime(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return datetime.fromisoformat(str(value))
