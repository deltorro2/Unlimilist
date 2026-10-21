"""Normal and test builds: only a packaged normal build reads your real Tasks and Notes."""

import importlib.util
from pathlib import Path

from unlimilist.data_folders import TEST_MARKER, is_test_build, notes_folder, tasks_folder

ROOT = Path(__file__).resolve().parent.parent


def test_running_from_source_is_a_test_run(tmp_path):
    assert is_test_build(frozen=False, package_dir=tmp_path)


def test_a_packaged_build_is_normal_unless_it_carries_the_test_marker(tmp_path):
    assert not is_test_build(frozen=True, package_dir=tmp_path)

    (tmp_path / TEST_MARKER).write_text("")

    assert is_test_build(frozen=True, package_dir=tmp_path)


def test_the_normal_build_reads_tasks_and_the_test_build_reads_test(tmp_path):
    assert tasks_folder(tmp_path, test=False) == tmp_path / "tasks"
    assert tasks_folder(tmp_path, test=True) == tmp_path / "test"


def test_the_normal_build_keeps_notes_in_notes_and_the_test_build_in_test_notes(tmp_path):
    assert notes_folder(tmp_path, test=False) == tmp_path / "notes"
    assert notes_folder(tmp_path, test=True) == tmp_path / "test-notes"


def test_the_test_tasks_script_writes_to_the_test_folder_by_default():
    spec = importlib.util.spec_from_file_location("make_test_tasks", ROOT / "scripts" / "make_test_tasks.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    assert script.default_folder().parts[-2:] == ("Unlimilist", "test")


def test_the_test_notes_script_writes_to_the_test_notes_folder_by_default():
    spec = importlib.util.spec_from_file_location("make_test_notes", ROOT / "scripts" / "make_test_notes.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    assert script.default_folder().parts[-2:] == ("Unlimilist", "test-notes")
