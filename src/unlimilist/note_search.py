"""Notebook search: finds Notes whose Title or Body holds the search text (an Exact match) or some of its words
(a Partial match), ignoring case and matching inside words.

A word index (each word -> the Notes that have it) narrows the Notes to check; the text itself then decides.
The index of the Open Notes is kept in a file in the notes folder, so a launch only redoes the Notes that changed:

    {"version": 1, "notes": {"<note id>": {"fingerprint": "<sha1 of Title and Body>", "words": [...]}}}

A Secured Note is indexed in memory only: its Title always, its Body only while it can be read (the Notebook
password is unlocked). Nothing of a Secured Note is written to the file.
"""

import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from unlimilist.notebook import Note, Notebook

MIN_CHARS = 3  # shorter text, and shorter words in a Partial match, would match nearly everything
_WORD = re.compile(r"\w+")
_VERSION = 1


@dataclass(frozen=True)
class SearchResult:
    exact: list[str]  # ids of the Notes holding the whole text
    partial: list[str]  # ids of the other Notes holding some of its words, most words first
    whole_found: bool
    found_words: tuple[str, ...]  # the words (of a multi-word text) that some Note holds
    word_counts: dict[str, int]  # for each partial match, how many of the words it holds


NO_RESULT = SearchResult([], [], False, (), {})


def search_words(text: str) -> list[str]:
    """The words a Partial match looks for: those of three or more letters, once each. A one-word text has none."""
    parts = text.split()
    if len(parts) < 2:
        return []
    words: list[str] = []
    for part in parts:
        word = re.sub(r"^\W+|\W+$", "", part).casefold()
        if len(word) >= MIN_CHARS and word not in words:
            words.append(word)
    return words


def _fingerprint(note: Note) -> str:
    return hashlib.sha1(f"{note.title}\0{note.body}".encode("utf-8")).hexdigest()


class NoteSearch:
    def __init__(
        self,
        notebook: Notebook,
        index_path: Path | None = None,
        read_secured: Callable[[Note], str | None] = lambda note: None,
    ):
        """`read_secured` gives a Secured Note's plain Body, or None while it can't be read."""
        self._notebook = notebook
        self._path = index_path
        self._read_secured = read_secured
        self._texts: dict[str, str] = {}  # id -> case-folded "Title\0Body", what a match is checked against
        self._words: dict[str, set[str]] = {}
        self._postings: dict[str, set[str]] = {}  # word -> ids
        self._fingerprints: dict[str, str] = {}  # Open Notes only, as in the file
        self._secured_prints: dict[str, str] = {}  # Secured Notes: so an unchanged one isn't decrypted again
        self._dirty = False
        self._sync(self._load())
        notebook.subscribe(self._changed)

    def set_secured_reader(self, read_secured: Callable[[Note], str | None]) -> None:
        self._read_secured = read_secured
        self.forget_secured()

    def forget_secured(self) -> None:
        """Index the Secured Notes again, e.g. once the Notebook password is unlocked and their Bodies can be read."""
        self._secured_prints.clear()
        for note in self._notebook.notes():
            if note.secured:
                self._index(note)

    def search(self, text: str) -> SearchResult:
        query = text.strip().casefold()
        if len(query) < MIN_CHARS:
            return NO_RESULT
        order = [n.id for n in self._notebook.notes()]
        exact_ids = {i for i in self._candidates(query) if query in self._texts.get(i, "")}
        exact = [i for i in order if i in exact_ids]
        counts: dict[str, int] = {}
        found = []
        for word in search_words(text):
            holders = {i for i in self._candidates(word) if word in self._texts.get(i, "")}
            if holders:
                found.append(word)
            for note_id in holders - exact_ids:
                counts[note_id] = counts.get(note_id, 0) + 1
        partial = sorted((i for i in order if i in counts), key=lambda i: -counts[i])
        return SearchResult(exact, partial, bool(exact), tuple(found), counts)

    def flush(self) -> None:
        """Write the index file if anything changed since it was last written."""
        if not self._dirty or self._path is None:
            return
        notes = {
            note_id: {"fingerprint": fingerprint, "words": sorted(self._words[note_id])}
            for note_id, fingerprint in self._fingerprints.items()
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(self._path.name + ".tmp")
        temporary.write_text(json.dumps({"version": _VERSION, "notes": notes}, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self._path)
        self._dirty = False

    def _candidates(self, query: str) -> set[str]:
        """The Notes that may hold `query`: each of its words is inside some word they have."""
        tokens = _WORD.findall(query)
        if not tokens:
            return set(self._texts)
        found: set[str] | None = None
        for token in tokens:
            ids = set().union(*(ids for word, ids in self._postings.items() if token in word))
            found = ids if found is None else found & ids
        return found or set()

    def _load(self) -> dict[str, dict]:
        if self._path is None:
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if data.get("version") != _VERSION or not isinstance(data.get("notes"), dict):
                return {}
            return data["notes"]
        except (OSError, ValueError, AttributeError):
            return {}  # missing or broken: every Note is indexed afresh

    def _sync(self, saved: dict[str, dict]) -> None:
        for note in self._notebook.notes():
            entry = saved.get(note.id)
            if not note.secured and isinstance(entry, dict) and entry.get("fingerprint") == _fingerprint(note):
                self._set(note.id, self._text(note), set(entry.get("words") or ()))
                self._fingerprints[note.id] = entry["fingerprint"]
            else:
                self._index(note)
        if set(saved) - set(self._fingerprints):
            self._dirty = True  # entries of Notes that are gone or now Secured

    def _changed(self, note_id: str, note: Note | None) -> None:
        if note is None:
            self._drop(note_id)
            self._secured_prints.pop(note_id, None)
        elif note.secured:
            if self._secured_prints.get(note_id) != _fingerprint(note):
                self._index(note)
        elif self._fingerprints.get(note_id) != _fingerprint(note):
            self._index(note)

    def _index(self, note: Note) -> None:
        text = self._text(note)
        self._set(note.id, text, set(_WORD.findall(text)))
        if note.secured:
            self._secured_prints[note.id] = _fingerprint(note)
            if self._fingerprints.pop(note.id, None) is not None:
                self._dirty = True
        else:
            self._fingerprints[note.id] = _fingerprint(note)
            self._dirty = True

    def _text(self, note: Note) -> str:
        body = (self._read_secured(note) or "") if note.secured else note.body
        return f"{note.title}\0{body}".casefold()

    def _set(self, note_id: str, text: str, words: set[str]) -> None:
        self._drop(note_id, forget=False)
        self._texts[note_id] = text
        self._words[note_id] = words
        for word in words:
            self._postings.setdefault(word, set()).add(note_id)

    def _drop(self, note_id: str, forget: bool = True) -> None:
        for word in self._words.pop(note_id, ()):
            holders = self._postings.get(word)
            if holders is not None:
                holders.discard(note_id)
                if not holders:
                    del self._postings[word]
        self._texts.pop(note_id, None)
        if forget and self._fingerprints.pop(note_id, None) is not None:
            self._dirty = True
