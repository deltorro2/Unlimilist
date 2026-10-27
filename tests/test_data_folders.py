"""Normal and test builds: only a packaged normal build reads your real Tasks and Notes, from the Vault."""

import importlib.util
from pathlib import Path

from unlimilist.data_folders import TEST_MARKER, folder_for_test_notes, folder_for_test_tasks, is_test_build

ROOT = Path(__file__).resolve().parent.parent


def test_running_from_source_is_a_test_run(tmp_path):
    assert is_test_build(frozen=False, package_dir=tmp_path)


def test_a_packaged_build_is_normal_unless_it_carries_the_test_marker(tmp_path):
    assert not is_test_build(frozen=True, package_dir=tmp_path)

    (tmp_path / TEST_MARKER).write_text("")

    assert is_test_build(frozen=True, package_dir=tmp_path)


def test_the_test_build_reads_the_fixed_test_folders_beside_the_settings(tmp_path):
    assert folder_for_test_tasks(tmp_path) == tmp_path / "test"
    assert folder_for_test_notes(tmp_path) == tmp_path / "test-notes"


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
