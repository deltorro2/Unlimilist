"""Core domain types. See CONTEXT.md for the vocabulary."""

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


class Urgency(Enum):
    NONE = "none"
    START_PASSED = "start_passed"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"


class InvalidTask(ValueError):
    """A Task's fields break a rule, e.g. a missing Title."""


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

    @property
    def kind(self) -> LaneKind:
        if self.due_date or self.deadline:
            return LaneKind.TIME_LIMITED
        return LaneKind.SOMEDAY

    @property
    def earliest_date(self) -> date | None:
        dates = [d for d in (self.due_date, self.deadline) if d]
        return min(dates, default=None)

    def validate(self) -> None:
        if not self.title.strip():
            raise InvalidTask("Title is required.")
        if self.due_date and self.deadline and self.due_date > self.deadline:
            raise InvalidTask("Due date cannot be later than the Deadline.")
