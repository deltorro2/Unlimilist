"""Keeps each Task as one Markdown file (see docs/adr/0001-one-markdown-file-per-task.md).

File layout:

    ---
    id: 2026-10-12-a1b2c3
    stage: inbox
    activity: general-task
    priority: 1
    due_date: 2026-10-14
    deadline: null
    created_at: 2026-10-12 09:00:00
    completed_at: null
    waiting_since: 2026-10-12 09:00:00
    ---
    # Title

    ## Details

    <markdown>

    ## Usable data

    <markdown>
"""

import os
from datetime import date, datetime
from pathlib import Path

import yaml

from unlimilist.domain import Activity, Stage, Task

_DETAILS = "## Details"
_USABLE_DATA = "## Usable data"
_DELETED = "-deleted"  # a deleted Task's file ends in .md-deleted, which load_all's *.md never matches


class MarkdownTaskStore:
    def __init__(self, folder: Path):
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.warnings: list[str] = []

    def load_all(self) -> list[Task]:
        self.warnings = []
        tasks = []
        for path in sorted(self.folder.glob("*.md")):
            try:
                tasks.append(_parse(path.read_text(encoding="utf-8"), path.stem, path.name, self.warnings))
            except Exception as error:  # a hand-edited file may be broken in any way
                self.warnings.append(f"Skipped {path.name}: {error}")
        return tasks

    def save(self, task: Task) -> None:
        path = self._path(task.id)
        temporary = path.with_suffix(".md.tmp")
        temporary.write_text(_render(task), encoding="utf-8")
        os.replace(temporary, path)

    def delete(self, task_id: str) -> None:
        """Keep the file, renamed to end in -deleted, so it is never loaded again but can be recovered by hand
        (see docs/adr/0004-deleting-renames-the-task-file.md). A taken name gets a number."""
        path = self._path(task_id)
        if not path.exists():
            return
        target = path.with_name(f"{path.name}{_DELETED}")
        number = 2
        while target.exists():
            target = path.with_name(f"{path.name}{_DELETED}-{number}")
            number += 1
        os.replace(path, target)

    def _path(self, task_id: str) -> Path:
        return self.folder / f"{task_id}.md"


class _Dumper(yaml.SafeDumper):
    """Writes every value out in full: a new Task's waiting_since is its created_at, which would be an alias."""

    def ignore_aliases(self, data) -> bool:
        return True


def _render(task: Task) -> str:
    meta = {
        "id": task.id,
        "stage": task.stage.value,
        "activity": task.activity.value,
        "priority": task.priority,
        "due_date": task.due_date,
        "deadline": task.deadline,
        "created_at": task.created_at,
        "completed_at": task.completed_at,
        "waiting_since": task.waiting_since,
    }
    front_matter = yaml.dump(meta, Dumper=_Dumper, sort_keys=False, allow_unicode=True)
    return (
        f"---\n{front_matter}---\n"
        f"# {task.title}\n\n"
        f"{_DETAILS}\n\n{task.details.strip()}\n\n"
        f"{_USABLE_DATA}\n\n{task.usable_data.strip()}\n"
    )


def _parse(text: str, fallback_id: str, file_name: str, warnings: list[str]) -> Task:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing front matter")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    meta = yaml.safe_load("\n".join(lines[1:end])) or {}
    body = lines[end + 1 :]

    title_line = next((i for i, line in enumerate(body) if line.startswith("# ")), None)
    if title_line is None:
        raise ValueError("missing '# Title' line")
    details_start = _index_of(body, _DETAILS)
    usable_start = _last_index_of(body, _USABLE_DATA)

    details, usable_data = "", ""
    if details_start is not None:
        details_end = usable_start if usable_start is not None and usable_start > details_start else len(body)
        details = "\n".join(body[details_start + 1 : details_end])
    if usable_start is not None:
        usable_data = "\n".join(body[usable_start + 1 :])

    task = Task(
        id=str(meta.get("id") or fallback_id),
        title=body[title_line][2:].strip(),
        stage=Stage(meta.get("stage", Stage.INBOX.value)),
        created_at=_as_datetime(meta.get("created_at")) or datetime.now(),
        details=details.strip(),
        usable_data=usable_data.strip(),
        due_date=_as_date(meta.get("due_date")),
        deadline=_as_date(meta.get("deadline")),
        priority=meta.get("priority"),
        completed_at=_as_datetime(meta.get("completed_at")),
        activity=_as_activity(meta.get("activity"), file_name, warnings),
        waiting_since=_as_datetime(meta.get("waiting_since")),  # files from before it existed have none
    )
    if task.stage == Stage.DONE and task.completed_at is None:
        task = Task(**{**task.__dict__, "completed_at": task.created_at})
    task.validate()
    return task


def _as_activity(value, file_name: str, warnings: list[str]) -> Activity:
    """Files written before Activities existed have none: they are General Tasks."""
    if value is None or value == "":
        return Activity.GENERAL_TASK
    try:
        return Activity(str(value))
    except ValueError:
        warnings.append(f"{file_name}: unknown activity '{value}', shown as a General Task")
        return Activity.GENERAL_TASK


def _index_of(lines: list[str], heading: str) -> int | None:
    return next((i for i, line in enumerate(lines) if line.strip() == heading), None)


def _last_index_of(lines: list[str], heading: str) -> int | None:
    return next((i for i in reversed(range(len(lines))) if lines[i].strip() == heading), None)


def _as_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _as_datetime(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return datetime.fromisoformat(str(value))
