"""Where Tasks are read from. Only a packaged normal build reads your real Tasks; a test build (made with
`build_app.sh --test`) and running from source read the test folder, so manual testing never touches them."""

from pathlib import Path

TEST_MARKER = "TEST_BUILD"  # a file the test build carries inside the unlimilist package


def is_test_build(frozen: bool, package_dir: Path) -> bool:
    """Running from source, or a packaged build that carries the test marker."""
    return not frozen or (package_dir / TEST_MARKER).exists()


def tasks_folder(app_data: Path, test: bool) -> Path:
    return app_data / ("test" if test else "tasks")
