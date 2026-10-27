"""Which build is running. Only a packaged normal build reads your real Tasks and Notes, from the Vault (see
vault.py); a test build (made with `build_app.sh --test`) and running from source read the fixed test folders,
so manual testing never touches them."""

from pathlib import Path

TEST_MARKER = "TEST_BUILD"  # a file the test build carries inside the unlimilist package


def is_test_build(frozen: bool, package_dir: Path) -> bool:
    """Running from source, or a packaged build that carries the test marker."""
    return not frozen or (package_dir / TEST_MARKER).exists()


def folder_for_test_tasks(app_data: Path) -> Path:
    return app_data / "test"


def folder_for_test_notes(app_data: Path) -> Path:
    return app_data / "test-notes"
