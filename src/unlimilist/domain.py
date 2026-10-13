"""Core domain types. See CONTEXT.md for the vocabulary."""

import re
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
    PHONE_CALL = "phone-call"
    MEETING = "meeting"
    DEVELOP_CODE = "develop-code"
    MILESTONE = "milestone"


class Urgency(Enum):
    NONE = "none"
    START_PASSED = "start_passed"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"


class InvalidTask(ValueError):
    """A Task's fields break a rule, e.g. a missing Title."""


class DeleteRefused(ValueError):
    """A Task in In Process cannot be deleted; it has to leave In Process first."""


class UnfinishedSubtasks(ValueError):
    """A Task cannot enter Done while some of its Subtasks are unfinished."""

    def __init__(self, count: int):
        self.count = count
        noun = "subtask" if count == 1 else "subtasks"
        super().__init__(f"You still have {count} unfinished {noun}")


# A Markdown task-list item, e.g. "- [ ] Test" or "1. [x] Build".
_SUBTASK = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[([ xX])\]", re.MULTILINE)


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
