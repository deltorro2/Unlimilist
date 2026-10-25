"""Core domain types. See CONTEXT.md for the vocabulary."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class Stage(Enum):
    INBOX = "inbox"
    IN_PROCESS = "in_process"
    DONE = "done"


class LaneKind(Enum):
    SOMEDAY = "someday"
    TIME_LIMITED = "time_limited"


class Activity(Enum):
    """The kind of work a Task represents. The value names its icon and is what the Task file stores."""

    GENERAL_TASK = "general-task"
    ASK = "ask"
    PHONE_CALL = "phone-call"
    MEETING = "meeting"
    DEVELOP_CODE = "develop-code"
    MILESTONE = "milestone"


class Urgency(Enum):
    NONE = "none"
    START_PASSED = "start_passed"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"


@dataclass(frozen=True)
class StaleLimits:
    """How many days a Someday Task may wait in each Stage before it is Stale, before one more per Priority rank."""

    inbox: int = 10
    in_process: int = 4

    def days(self, stage: Stage) -> int | None:
        return {Stage.INBOX: self.inbox, Stage.IN_PROCESS: self.in_process}.get(stage)


@dataclass(frozen=True)
class Stale:
    """Why a Task is Stale: whole days it has waited, and how many its Stage and Priority allow."""

    waited: int
    allowed: int


class InvalidTask(ValueError):
    """A Task's fields break a rule, e.g. a missing Title."""


class DeleteRefused(ValueError):
    """A Task in In Process cannot be deleted; it has to leave In Process first."""


class DuplicateRefused(ValueError):
    """Only an Inbox Task can be duplicated."""


class UnfinishedSubtasks(ValueError):
    """A Task cannot enter Done while some of its Subtasks are unfinished."""

    def __init__(self, count: int):
        self.count = count
        noun = "subtask" if count == 1 else "subtasks"
        super().__init__(f"You still have {count} unfinished {noun}")


# A Markdown task-list item, e.g. "- [ ] Test" or "1. [x] Build".
_SUBTASK = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[([ xX])\]", re.MULTILINE)

_TICKED_SUBTASK = re.compile(r"^(\s*(?:[-*+]|\d+[.)])\s+\[)[xX](\])", re.MULTILINE)


def untick_subtasks(details: str) -> str:
    """`details` with every Subtask unfinished."""
    return _TICKED_SUBTASK.sub(r"\1 \2", details)


# Code and links never hold Tags: fenced blocks, `code spans`, [text](url) and <autolinks>.
_NOT_TAG_TEXT = re.compile(r"```.*?```|`[^`\n]*`|!?\[[^\]\n]*\]\([^)\n]*\)|<[^>\s]+>", re.DOTALL)
# A Tag: # at the start of a word (line start, a space or an opening bracket), then a letter,
# then letters, digits, - or _. Qt writes a # that starts a line as \#, so that counts too.
TAG = re.compile(r"(?<![^\s(\[{])\\?#([^\W\d_][\w-]*)")


def find_tags(text: str) -> tuple[str, ...]:
    """The Tags in `text`, each once, in the order first written and with that first spelling."""
    found: dict[str, str] = {}
    for match in TAG.finditer(_NOT_TAG_TEXT.sub(" ", text)):
        name = match.group(1).rstrip("-")
        found.setdefault(name.casefold(), name)
    return tuple(found.values())


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    stage: Stage
    created_at: datetime
    details: str = ""
    usable_data: str = ""
    due_date: date | None = None
    deadline: date | None = None
    priority: int | None = None
    completed_at: datetime | None = None
    activity: Activity = Activity.GENERAL_TASK
    waiting_since: datetime | None = None  # when it last entered its Stage or was given a new Priority

    @property
    def kind(self) -> LaneKind:
        if self.due_date or self.deadline:
            return LaneKind.TIME_LIMITED
        return LaneKind.SOMEDAY

    @property
    def earliest_date(self) -> date | None:
        dates = [d for d in (self.due_date, self.deadline) if d]
        return min(dates, default=None)

    @property
    def tags(self) -> tuple[str, ...]:
        return find_tags(self.details)

    def matches_tag_filter(self, tag_filter: Iterable[str]) -> bool:
        """Whether the Task shows under a Tag filter: it has any selected Tag, or nothing is selected."""
        keys = {key.casefold() for key in tag_filter}
        return not keys or any(name.casefold() in keys for name in self.tags)

    @property
    def has_subtasks(self) -> bool:
        return _SUBTASK.search(self.details) is not None

    @property
    def unfinished_subtasks(self) -> int:
        return sum(1 for mark in _SUBTASK.findall(self.details) if mark == " ")

    def validate(self) -> None:
        if not self.title.strip():
            raise InvalidTask("Title is required.")
        if self.due_date and self.deadline and self.due_date > self.deadline:
            raise InvalidTask("Due date cannot be later than the Deadline.")
