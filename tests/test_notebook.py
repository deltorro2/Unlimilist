"""The Notebook: Notes, their Titles, Daily notes, Tags, the default order, Secured Notes and the Note files."""

from datetime import datetime, timedelta

import pytest

from unlimilist.note_store import MarkdownNoteStore
from unlimilist.notebook import Notebook, NoteType, title_from_text
from unlimilist.secure import WrongPassword

NOW = datetime(2026, 10, 21, 14, 5)


class Clock:
    def __init__(self, now=NOW):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, minutes=1):
        self.now += timedelta(minutes=minutes)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def notebook(clock):
    return Notebook(clock=clock)


# Titles


def test_a_short_first_line_is_the_title_as_is():
    assert title_from_text("Buy milk\nand bread") == "Buy milk"


def test_a_long_title_is_cut_at_a_whole_word_to_at_most_80_characters_with_an_ellipsis():
    text = "Remember to ask the landlord about the heating, the leaking tap in the kitchen and the parking permit"

    title = title_from_text(text)

    assert len(title) <= 80
    assert title.endswith("…")
    assert text.startswith(title[:-1])
    assert text[len(title) - 1] == " "  # cut between words


def test_a_single_huge_word_is_cut_mid_word():
    title = title_from_text("x" * 200)

    assert title == "x" * 79 + "…"


# Creating Notes


def test_a_new_note_is_open_never_opened_and_keeps_its_parts(notebook):
    note = notebook.create("Lisbon", "# Day 1\nAlfama", tags=("travel", "Family"))

    assert note.title == "Lisbon"
    assert note.body == "# Day 1\nAlfama"
    assert note.tags == ("travel", "Family")
    assert note.note_type == NoteType.OPEN
    assert note.created_at == NOW
    assert note.opened_at is None
    assert notebook.note(note.id) == note


def test_a_note_with_neither_title_nor_body_is_not_kept(notebook):
    assert notebook.create("  ", "  \n") is None
    assert notebook.notes() == []


def test_a_note_with_a_body_but_no_title_becomes_a_daily_note_tagged_daily(notebook):
    note = notebook.create("", "Slept badly", tags=("health",))

    assert note.title == "Daily note 21 Oct 2026"
    assert note.tags == ("health", "daily")


def test_a_daily_note_does_not_get_daily_twice(notebook):
    assert notebook.create("", "text", tags=("Daily",)).tags == ("Daily",)


def test_quick_add_puts_the_whole_text_in_the_body_and_a_short_title(notebook):
    text = "Remember to ask the landlord about the heating, the leaking tap in the kitchen and the parking permit"

    note = notebook.quick_add(text)

    assert note.body == text
    assert note.title == title_from_text(text)
    assert note.opened_at is None


def test_quick_add_of_blank_text_makes_nothing(notebook):
    assert notebook.quick_add("   ") is None


def test_tags_must_be_one_word_starting_with_a_letter(notebook):
    with pytest.raises(ValueError):
        notebook.create("Bad", "", tags=("two words",))
    with pytest.raises(ValueError):
        notebook.create("Bad", "", tags=("1st",))


# Order


def test_notes_are_listed_by_last_opened_or_created_most_recent_first(notebook, clock):
    old = notebook.create("Old", "")
    clock.advance()
    middle = notebook.create("Middle", "")
    clock.advance()
    new = notebook.create("New", "")
    clock.advance()
    notebook.mark_opened(old.id)

    assert [n.title for n in notebook.notes()] == ["Old", "New", "Middle"]
    assert notebook.note(old.id).opened_at == clock.now
    assert middle.opened_at is None and new.opened_at is None


# Editing


def test_saving_changes_the_title_body_and_tags(notebook):
    note = notebook.create("Lisbon", "Day 1")

    saved = notebook.save(note.id, title="Porto", body="Day 2", tags=("travel",), note_type=NoteType.OPEN)

    assert (saved.title, saved.body, saved.tags) == ("Porto", "Day 2", ("travel",))
    assert saved.created_at == note.created_at


def test_clearing_the_title_of_a_saved_note_makes_it_a_daily_note(notebook):
    note = notebook.create("Lisbon", "Day 1")

    assert notebook.save(note.id, title="", body="Day 1", tags=(), note_type=NoteType.OPEN).title.startswith(
        "Daily note"
    )


# Secured Notes


def test_a_secured_note_stores_only_the_encrypted_body(notebook):
    note = notebook.create("Bank", "PIN 1234", note_type=NoteType.SECURED, password="pw")

    assert note.secured
    assert "1234" not in note.body
    assert note.title == "Bank"
    assert notebook.read_body(note.id, "pw") == "PIN 1234"
    with pytest.raises(WrongPassword):
        notebook.read_body(note.id, "nope")


def test_an_open_note_reads_without_a_password(notebook):
    note = notebook.create("Plain", "text")

    assert notebook.read_body(note.id) == "text"


def test_securing_and_unsecuring_an_existing_note(notebook):
    note = notebook.create("Bank", "PIN 1234")

    secured = notebook.save(note.id, "Bank", "PIN 1234", (), NoteType.SECURED, password="pw")
    assert "1234" not in secured.body

    opened = notebook.save(note.id, "Bank", "PIN 1234", (), NoteType.OPEN)
    assert opened.body == "PIN 1234"


def test_a_secured_note_needs_a_password_to_save(notebook):
    with pytest.raises(ValueError):
        notebook.create("Bank", "PIN", note_type=NoteType.SECURED)


def test_size_is_the_stored_body_in_bytes(notebook):
    assert notebook.create("Size", "héllo").size == 6


def test_changing_the_password_re_encrypts_every_secured_note(notebook):
    a = notebook.create("A", "alpha", note_type=NoteType.SECURED, password="old")
    b = notebook.create("B", "beta", note_type=NoteType.SECURED, password="old")
    plain = notebook.create("C", "gamma")

    notebook.change_password("old", "new")

    assert notebook.read_body(a.id, "new") == "alpha"
    assert notebook.read_body(b.id, "new") == "beta"
    assert notebook.note(plain.id).body == "gamma"
    with pytest.raises(WrongPassword):
        notebook.read_body(a.id, "old")


# Tags and the filter


def test_tags_are_counted_case_blind_and_spelled_as_first_used(notebook, clock):
    notebook.create("One", "", tags=("Travel",))
    clock.advance()
    notebook.create("Two", "", tags=("travel", "home"))

    assert notebook.tags() == [("home", 1), ("Travel", 2)]


def test_a_note_matches_the_tag_filter_if_it_has_any_selected_tag(notebook):
    note = notebook.create("One", "", tags=("Travel",))

    assert note.matches_tag_filter({"travel", "work"})
    assert not note.matches_tag_filter({"work"})
    assert note.matches_tag_filter(set())


# Deleting


def test_deleting_removes_the_note(notebook):
    note = notebook.create("Gone", "x")

    notebook.delete(note.id)

    assert not notebook.has_note(note.id)
    assert notebook.notes() == []


# Files


def test_notes_are_kept_as_markdown_files_and_load_back(tmp_path, clock):
    store = MarkdownNoteStore(tmp_path)
    notebook = Notebook(store, clock=clock)
    note = notebook.create("Trip: Lisbon & Porto", "# Day 1\n\n- Alfama", tags=("travel",))
    secured = notebook.create("Bank", "PIN 1234", note_type=NoteType.SECURED, password="pw")
    notebook.mark_opened(note.id)

    reloaded = Notebook(MarkdownNoteStore(tmp_path), clock=clock)

    assert reloaded.note(note.id) == notebook.note(note.id)
    assert reloaded.read_body(secured.id, "pw") == "PIN 1234"
    text = (tmp_path / f"{note.id}.md").read_text()
    assert text.startswith("---\n")
    assert text.rstrip().endswith("- Alfama")
    assert "1234" not in (tmp_path / f"{secured.id}.md").read_text()


def test_file_names_are_plain_ascii(tmp_path, clock):
    note = Notebook(MarkdownNoteStore(tmp_path), clock=clock).create("שלום עולם", "body")

    assert note.id.isascii()
    assert [p.name for p in tmp_path.iterdir()] == [f"{note.id}.md"]


def test_a_deleted_open_note_file_is_kept_but_a_secured_one_is_removed(tmp_path, clock):
    notebook = Notebook(MarkdownNoteStore(tmp_path), clock=clock)
    plain = notebook.create("Plain", "x")
    secured = notebook.create("Bank", "PIN", note_type=NoteType.SECURED, password="pw")

    notebook.delete(plain.id)
    notebook.delete(secured.id)

    assert sorted(p.name for p in tmp_path.iterdir()) == [f"{plain.id}.md-deleted"]
    assert Notebook(MarkdownNoteStore(tmp_path)).notes() == []


def test_a_broken_note_file_is_skipped_with_a_warning(tmp_path):
    (tmp_path / "broken.md").write_text("no front matter")
    store = MarkdownNoteStore(tmp_path)

    assert Notebook(store).notes() == []
    assert store.warnings and "broken.md" in store.warnings[0]


def test_changing_the_password_changes_nothing_if_a_note_does_not_open_with_the_old_one(notebook):
    a = notebook.create("A", "alpha", note_type=NoteType.SECURED, password="old")
    stray = notebook.create("B", "beta", note_type=NoteType.SECURED, password="other")
    before = notebook.note(a.id).body

    with pytest.raises(WrongPassword):
        notebook.change_password("old", "new")

    assert notebook.note(a.id).body == before
    assert notebook.read_body(stray.id, "other") == "beta"
