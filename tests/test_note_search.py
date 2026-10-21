"""Notebook search: Exact and Partial matches over Titles and Bodies, backed by an index file of the Open Notes."""

import json

import pytest

from unlimilist.note_search import NoteSearch
from unlimilist.notebook import Notebook, NoteType


@pytest.fixture
def notebook():
    notebook = Notebook()
    notebook.create("Trip to Lisbon", "Alfama and tram 28.\nBook the hotel early.")
    notebook.create("Groceries", "milk, bread, Lisbon sardines")
    notebook.create("Banking", "Call the bank about the card")
    return notebook


def ids(notebook, *titles):
    by_title = {n.title: n.id for n in notebook.notes()}
    return [by_title[t] for t in titles]


def test_the_whole_text_is_found_in_titles_and_bodies_ignoring_case_and_inside_words(notebook):
    search = NoteSearch(notebook)

    assert set(search.search("LISBON").exact) == set(ids(notebook, "Trip to Lisbon", "Groceries"))
    assert search.search("bank").exact == ids(notebook, "Banking")  # inside "Banking" and "bank"
    assert search.search("tram 28").exact == ids(notebook, "Trip to Lisbon")
    assert search.search("bank").partial == []


def test_a_multi_word_text_not_found_whole_finds_notes_with_some_of_its_words_most_words_first(notebook):
    search = NoteSearch(notebook)

    result = search.search("lisbon hotel tram nowhere")

    assert result.exact == []
    assert result.partial == ids(notebook, "Trip to Lisbon", "Groceries")  # 3 words, then 1
    assert result.found_words == ("lisbon", "hotel", "tram")


def test_partial_matches_leave_out_the_exact_ones(notebook):
    notebook.create("Lisbon hotel list", "")
    search = NoteSearch(notebook)

    result = search.search("lisbon hotel")

    assert result.exact == ids(notebook, "Lisbon hotel list")
    assert set(result.partial) == set(ids(notebook, "Trip to Lisbon", "Groceries"))
    assert result.whole_found


def test_short_words_do_not_count_for_partial_matches(notebook):
    result = NoteSearch(notebook).search("to xyzzy")

    assert result.exact == [] and result.partial == []
    assert result.found_words == ()


def test_a_one_word_search_has_no_partial_matches(notebook):
    assert NoteSearch(notebook).search("lisbonx").partial == []


def test_colouring_needs_three_characters(notebook):
    search = NoteSearch(notebook)

    assert not search.search("li").whole_found
    assert search.search("lis").whole_found


def test_the_search_follows_saves_and_deletes(notebook):
    search = NoteSearch(notebook)
    groceries = ids(notebook, "Groceries")[0]

    notebook.save(groceries, "Groceries", "eggs", (), NoteType.OPEN)
    assert search.search("sardines").exact == []
    notebook.delete(groceries)
    assert search.search("eggs").exact == []
    added = notebook.quick_add("Porto weekend")
    assert search.search("porto").exact == [added.id]


def test_a_secured_body_is_searched_only_when_it_can_be_read(notebook):
    bank = notebook.create("Safe", "PIN 1234 for the vault", note_type=NoteType.SECURED, password="pw")
    readable = {}
    search = NoteSearch(notebook, read_secured=lambda note: readable.get(note.id))

    assert search.search("vault").exact == []
    assert search.search("safe").exact == [bank.id]  # the Title is always searched
    readable[bank.id] = notebook.read_body(bank.id, "pw")
    search.forget_secured()
    assert search.search("vault").exact == [bank.id]


# The index file


def test_the_index_file_holds_the_open_notes_and_never_secured_text(tmp_path, notebook):
    notebook.create("Safe", "PIN 1234 vault", note_type=NoteType.SECURED, password="pw")
    path = tmp_path / ".search-index.json"

    NoteSearch(notebook, index_path=path, read_secured=lambda note: "PIN 1234 vault").flush()

    data = json.loads(path.read_text())
    assert set(data["notes"]) == {n.id for n in notebook.notes() if not n.secured}
    assert "vault" not in path.read_text() and "1234" not in path.read_text()


def test_entries_for_notes_that_are_gone_are_dropped(tmp_path, notebook):
    path = tmp_path / ".search-index.json"
    NoteSearch(notebook, index_path=path).flush()
    data = json.loads(path.read_text())
    data["notes"]["gone"] = {"fingerprint": "x", "words": ["ghost"]}
    path.write_text(json.dumps(data))

    search = NoteSearch(notebook, index_path=path)
    search.flush()

    assert search.search("ghost").exact == []
    assert "gone" not in json.loads(path.read_text())["notes"]


def test_a_changed_note_is_indexed_again_at_launch(tmp_path, notebook):
    path = tmp_path / ".search-index.json"
    NoteSearch(notebook, index_path=path).flush()
    groceries = ids(notebook, "Groceries")[0]
    notebook.save(groceries, "Groceries", "eggs and cheese", (), NoteType.OPEN)  # no search attached

    search = NoteSearch(notebook, index_path=path)

    assert search.search("cheese").exact == [groceries]


def test_a_broken_index_file_is_rebuilt(tmp_path, notebook):
    path = tmp_path / ".search-index.json"
    path.write_text("not json")

    search = NoteSearch(notebook, index_path=path)
    search.flush()

    assert search.search("sardines").exact == ids(notebook, "Groceries")
    assert json.loads(path.read_text())["version"] == 1


def test_flush_writes_only_when_something_changed(tmp_path, notebook):
    path = tmp_path / ".search-index.json"
    search = NoteSearch(notebook, index_path=path)
    search.flush()
    path.unlink()

    search.flush()
    assert not path.exists()
    notebook.quick_add("new words")
    search.flush()
    assert path.exists()
