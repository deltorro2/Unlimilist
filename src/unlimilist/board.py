"""The Board: owns every Task and the rules for where each one sits."""

import secrets
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Protocol

from unlimilist.domain import (
    Activity,
    DeleteRefused,
    DuplicateRefused,
    LaneKind,
    Stage,
    Stale,
    StaleLimits,
    Task,
    UnfinishedSubtasks,
    Urgency,
    untick_subtasks,
)

_KEEP = object()
_DUPLICATE_PREFIX = "[Duplication] "
_TOP_SOMEDAY = 5  # Someday Tasks shown right after the first Time-limited Task
_NEAR_COUNT = 3  # Time-limited Tasks under a month away that may follow them


class TaskStore(Protocol):
    """Where the Board keeps its Tasks between runs."""

    def load_all(self) -> list[Task]: ...

    def save(self, task: Task) -> None: ...

    def delete(self, task_id: str) -> None: ...


class InMemoryStore:
    def __init__(self, tasks: Iterable[Task] = ()):
        self._tasks = {t.id: t for t in tasks}

    def load_all(self) -> list[Task]:
        return list(self._tasks.values())

    def save(self, task: Task) -> None:
        self._tasks[task.id] = task

    def delete(self, task_id: str) -> None:
        self._tasks.pop(task_id, None)


class Board:
    def __init__(self, store: TaskStore | None = None, clock: Callable[[], datetime] = datetime.now):
        self._store = store or InMemoryStore()
        self._clock = clock
        self._tasks: dict[str, Task] = {t.id: t for t in self._store.load_all()}
        # Tag key (case-folded) -> ids of the Tasks that have it; built once here, then kept up to date.
        self._tag_index: dict[str, set[str]] = {}
        for task in self._tasks.values():
            self._index_tags(task)
        self._start_waiting()
        for stage in (Stage.INBOX, Stage.IN_PROCESS):
            self._renumber(stage, LaneKind.SOMEDAY)

    def add_task(
        self,
        title: str,
        *,
        details: str = "",
        usable_data: str = "",
        due_date: date | None = None,
        deadline: date | None = None,
        priority: int | None = None,
        activity: Activity = Activity.GENERAL_TASK,
    ) -> Task:
        created_at = self._clock()
        task = Task(
            id=f"{created_at:%Y-%m-%d}-{secrets.token_hex(3)}",
            title=title,
            stage=Stage.INBOX,
            created_at=created_at,
            details=details,
            usable_data=usable_data,
            due_date=due_date,
            deadline=deadline,
            activity=activity,
            waiting_since=created_at,
        )
        task.validate()
        self._put(task)
        if task.kind == LaneKind.SOMEDAY:
            self._rank(task.id, priority)
        return self._tasks[task.id]

    def edit_task(
        self,
        task_id: str,
        *,
        title=_KEEP,
        details=_KEEP,
        usable_data=_KEEP,
        due_date=_KEEP,
        deadline=_KEEP,
        activity=_KEEP,
        priority: int | None = None,
    ) -> Task:
        """Change a Task's fields; arguments left out keep their current value.

        Adding a date converts a Someday Task to Time-limited (dropping its Priority);
        clearing both dates converts it back, at `priority` or the bottom of its Lane.
        """
        old = self._tasks[task_id]
        changes = dict(
            title=title,
            details=details,
            usable_data=usable_data,
            due_date=due_date,
            deadline=deadline,
            activity=activity,
        )
        new = replace(old, **{k: v for k, v in changes.items() if v is not _KEEP})
        new.validate()
        if new.kind == LaneKind.TIME_LIMITED:
            new = replace(new, priority=None)
        self._put(new)
        if new.stage != Stage.DONE:
            if new.kind == LaneKind.SOMEDAY and (old.kind != new.kind or priority is not None):
                self._rank(task_id, priority)
                if old.kind == LaneKind.SOMEDAY:
                    self._restart_if_reranked(old)
            self._renumber(old.stage, old.kind)
        return self._tasks[task_id]

    def move_task(self, task_id: str, stage: Stage, *, priority: int | None = None) -> Task:
        """Move a Task to `stage`, into the Lane its dates imply.

        `priority` is the drop rank in a Someday Lane (bottom if None); it is ignored elsewhere.
        Raises UnfinishedSubtasks if the Task would enter Done with Subtasks left to do.
        """
        task = self._tasks[task_id]
        if stage == Stage.DONE and task.stage != Stage.DONE and task.unfinished_subtasks:
            raise UnfinishedSubtasks(task.unfinished_subtasks)
        source = (task.stage, task.kind)
        waiting_since = task.waiting_since if stage == task.stage else self._clock()
        if stage == Stage.DONE:
            completed_at = task.completed_at if task.stage == Stage.DONE else self._clock()
            self._put(replace(task, stage=stage, priority=None, completed_at=completed_at, waiting_since=waiting_since))
        else:
            self._put(replace(task, stage=stage, completed_at=None, waiting_since=waiting_since))
            if task.kind == LaneKind.SOMEDAY:
                self._rank(task_id, priority)
                if stage == task.stage:
                    self._restart_if_reranked(task)
        self._renumber(*source)
        return self._tasks[task_id]

    def duplicate_task(self, task_id: str) -> Task:
        """A copy of an Inbox Task titled "[Duplication] <title>", with every Subtask unfinished. A Someday copy is
        ranked right below the original; a Time-limited one sorts by its (same) dates."""
        original = self._tasks[task_id]
        if original.stage != Stage.INBOX:
            raise DuplicateRefused("Only an Inbox Task can be duplicated")
        return self.add_task(
            f"{_DUPLICATE_PREFIX}{original.title}",
            details=untick_subtasks(original.details),
            usable_data=original.usable_data,
            due_date=original.due_date,
            deadline=original.deadline,
            priority=original.priority + 1 if original.priority is not None else None,
            activity=original.activity,
        )

    def delete_tasks(self, task_ids: Iterable[str]) -> None:
        """Delete several Tasks at once; if any is in In Process, none is deleted."""
        task_ids = list(task_ids)
        for task_id in task_ids:
            self._check_deletable(task_id)
        for task_id in task_ids:
            self.delete_task(task_id)

    def delete_task(self, task_id: str) -> None:
        self._check_deletable(task_id)
        task = self._tasks.pop(task_id)
        self._unindex_tags(task)
        self._store.delete(task_id)
        self._renumber(task.stage, task.kind)

    def _check_deletable(self, task_id: str) -> None:
        if self._tasks[task_id].stage == Stage.IN_PROCESS:
            raise DeleteRefused("Move the Task out of In Process to delete it")

    def task(self, task_id: str) -> Task:
        return self._tasks[task_id]

    def has_task(self, task_id: str) -> bool:
        return task_id in self._tasks

    def urgency(self, task_id: str) -> Urgency:
        task = self._tasks[task_id]
        today = self._clock().date()
        if task.stage == Stage.DONE:
            return Urgency.NONE
        if task.deadline and task.deadline < today:
            return Urgency.OVERDUE
        if task.stage == Stage.INBOX and task.due_date and task.due_date < today:
            return Urgency.START_PASSED  # late, so it outranks Due soon
        if task.deadline and task.deadline <= today + timedelta(days=1):
            return Urgency.DUE_SOON
        return Urgency.NONE

    def stale(self, task_id: str, limits: StaleLimits) -> Stale | None:
        """Whether a Someday Task in Inbox or In Process has waited longer than its Stage allows, plus a day per
        Priority rank. Days are whole calendar days after the day of its Waiting since."""
        task = self._tasks[task_id]
        days = limits.days(task.stage)
        if days is None or task.kind != LaneKind.SOMEDAY or task.waiting_since is None:
            return None
        waited = (self._clock().date() - task.waiting_since.date()).days
        allowed = days + (task.priority or 0)
        return Stale(waited, allowed) if waited > allowed else None

    def tags(self) -> list[tuple[str, int]]:
        """Every Tag on the Board, A to Z, with how many Tasks have it. A Tag is spelled as first used."""
        listed = []
        for key, task_ids in self._tag_index.items():
            first = min((self._tasks[i] for i in task_ids), key=lambda t: (t.created_at, t.id))
            spelling = next(name for name in first.tags if name.casefold() == key)
            listed.append((spelling, len(task_ids)))
        return sorted(listed, key=lambda item: item[0].casefold())

    def suggest_tags(self, typed: str, limit: int = 8) -> list[str]:
        """Tags for what was typed after #: those starting with it first, then those containing its
        letters in order (fuzzy); within each group the most used first, then A to Z."""
        return rank_tags(typed, self.tags(), limit)

    def lane(self, stage: Stage, kind: LaneKind | None = None) -> list[Task]:
        if stage == Stage.DONE:
            done = [t for t in self._tasks.values() if t.stage == Stage.DONE]
            return sorted(done, key=lambda t: t.completed_at, reverse=True)
        tasks = [t for t in self._tasks.values() if t.stage == stage and t.kind == kind]
        if kind == LaneKind.SOMEDAY:
            return sorted(tasks, key=lambda t: (t.priority is None, t.priority or 0, t.created_at, t.id))
        return sorted(tasks, key=lambda t: (t.earliest_date, t.created_at))

    def column(self, stage: Stage) -> list[Task]:
        """A Stage as the Board shows it (see Column in CONTEXT.md):

        the first Time-limited Task, the top five Someday Tasks, then up to three more Time-limited Tasks that
        are under a month away. Every other Time-limited Task sits among the remaining Someday Tasks, after one
        of them plus one more per whole month until its earlier date; any pushed past the last come at the end.
        """
        if stage == Stage.DONE:
            return self.lane(Stage.DONE)
        someday = self.lane(stage, LaneKind.SOMEDAY)
        time_limited = self.lane(stage, LaneKind.TIME_LIMITED)
        today = self._clock().date()

        first, rest = time_limited[:1], time_limited[1:]
        three = []
        while rest and len(three) < _NEAR_COUNT and _whole_months(today, rest[0].earliest_date) == 0:
            three.append(rest.pop(0))

        # After how many of the remaining Someday Tasks each other Time-limited Task goes. The shift grows with
        # the date, so the date order is kept.
        remaining = someday[_TOP_SOMEDAY:]
        placed: list[Task] = []
        for index, task in enumerate(remaining + [None]):
            placed += [t for t in rest if 1 + _whole_months(today, t.earliest_date) == index]
            if task is not None:
                placed.append(task)
        placed += [t for t in rest if 1 + _whole_months(today, t.earliest_date) > len(remaining)]
        return first + someday[:_TOP_SOMEDAY] + three + placed

    def _start_waiting(self) -> None:
        """Tasks kept before Waiting since existed: every Task is made in Inbox, so an Inbox Task has waited since
        it was made; when an In Process Task got there is unknown, so it starts now. Done needs none."""
        for task in list(self._tasks.values()):
            if task.waiting_since is None and task.stage != Stage.DONE:
                start = task.created_at if task.stage == Stage.INBOX else self._clock()
                self._put(replace(task, waiting_since=start))

    def _restart_if_reranked(self, before: Task) -> None:
        """Giving a Task a new Priority restarts its clock; Tasks shifted around it keep theirs."""
        task = self._tasks[before.id]
        if task.priority != before.priority:
            self._put(replace(task, waiting_since=self._clock()))

    def _rank(self, task_id: str, priority: int | None) -> None:
        """Put a Someday Task at `priority` in its Lane (bottom if None) and renumber the Lane 1..N."""
        task = self._tasks[task_id]
        others = [t for t in self.lane(task.stage, LaneKind.SOMEDAY) if t.id != task_id]
        index = len(others) if priority is None else max(0, min(priority - 1, len(others)))
        others.insert(index, task)
        for rank, t in enumerate(others, start=1):
            self._put(replace(t, priority=rank))

    def _renumber(self, stage: Stage, kind: LaneKind) -> None:
        if stage == Stage.DONE or kind != LaneKind.SOMEDAY:
            return
        for rank, t in enumerate(self.lane(stage, kind), start=1):
            self._put(replace(t, priority=rank))

    def _put(self, task: Task) -> None:
        old = self._tasks.get(task.id)
        if old != task:
            if old is not None:
                self._unindex_tags(old)
            self._tasks[task.id] = task
            self._index_tags(task)
            self._store.save(task)

    def _index_tags(self, task: Task) -> None:
        for name in task.tags:
            self._tag_index.setdefault(name.casefold(), set()).add(task.id)

    def _unindex_tags(self, task: Task) -> None:
        for name in task.tags:
            key = name.casefold()
            self._tag_index[key].discard(task.id)
            if not self._tag_index[key]:
                del self._tag_index[key]


def rank_tags(typed: str, tags: Iterable[tuple[str, int]], limit: int = 8) -> list[str]:
    """The Tags in `tags` (name, count) that fit what was typed: those starting with it first, then those
    containing its letters in order (fuzzy); within each group the most used first, then A to Z."""
    query = typed.casefold()
    prefix, fuzzy = [], []
    for name, count in sorted(tags, key=lambda item: item[0].casefold()):
        if name.casefold().startswith(query):
            prefix.append((name, count))
        elif _contains_in_order(name.casefold(), query):
            fuzzy.append((name, count))
    ranked = [name for group in (prefix, fuzzy) for name, _ in sorted(group, key=lambda item: -item[1])]
    return ranked[:limit]


def _contains_in_order(text: str, letters: str) -> bool:
    remaining = iter(text)
    return all(letter in remaining for letter in letters)


def _whole_months(today: date, day: date) -> int:
    """Whole calendar months from `today` to `day`, rounded down; 0 for today or a past day."""
    months = (day.year - today.year) * 12 + day.month - today.month - (1 if day.day < today.day else 0)
    return max(0, months)
