"""The Board: owns every Task and the rules for where each one sits."""

import secrets
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Protocol

from unlimilist.domain import DeleteRefused, LaneKind, Stage, Task, UnfinishedSubtasks, Urgency

_KEEP = object()


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
        priority: int | None = None,
    ) -> Task:
        """Change a Task's fields; arguments left out keep their current value.

        Adding a date converts a Someday Task to Time-limited (dropping its Priority);
        clearing both dates converts it back, at `priority` or the bottom of its Lane.
        """
        old = self._tasks[task_id]
        changes = dict(
            title=title, details=details, usable_data=usable_data, due_date=due_date, deadline=deadline
        )
        new = replace(old, **{k: v for k, v in changes.items() if v is not _KEEP})
        new.validate()
        if new.kind == LaneKind.TIME_LIMITED:
            new = replace(new, priority=None)
        self._put(new)
        if new.stage != Stage.DONE:
            if new.kind == LaneKind.SOMEDAY and (old.kind != new.kind or priority is not None):
                self._rank(task_id, priority)
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
        if stage == Stage.DONE:
            completed_at = task.completed_at if task.stage == Stage.DONE else self._clock()
            self._put(replace(task, stage=stage, priority=None, completed_at=completed_at))
        else:
            self._put(replace(task, stage=stage, completed_at=None))
            if task.kind == LaneKind.SOMEDAY:
                self._rank(task_id, priority)
        self._renumber(*source)
        return self._tasks[task_id]

    def delete_task(self, task_id: str) -> None:
        if self._tasks[task_id].stage == Stage.IN_PROCESS:
            raise DeleteRefused("Move the Task out of In Process to delete it")
        task = self._tasks.pop(task_id)
        self._store.delete(task_id)
        self._renumber(task.stage, task.kind)

    def task(self, task_id: str) -> Task:
        return self._tasks[task_id]

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

    def lane(self, stage: Stage, kind: LaneKind | None = None) -> list[Task]:
        if stage == Stage.DONE:
            done = [t for t in self._tasks.values() if t.stage == Stage.DONE]
            return sorted(done, key=lambda t: t.completed_at, reverse=True)
        tasks = [t for t in self._tasks.values() if t.stage == stage and t.kind == kind]
        if kind == LaneKind.SOMEDAY:
            return sorted(tasks, key=lambda t: (t.priority is None, t.priority or 0, t.created_at, t.id))
        return sorted(tasks, key=lambda t: (t.earliest_date, t.created_at))

    def column(self, stage: Stage) -> list[Task]:
        """A Stage as the Board shows it: the first Time-limited Task, the top five Someday Tasks,
        then the remaining Time-limited Tasks, then the remaining Someday Tasks."""
        if stage == Stage.DONE:
            return self.lane(Stage.DONE)
        someday = self.lane(stage, LaneKind.SOMEDAY)
        time_limited = self.lane(stage, LaneKind.TIME_LIMITED)
        return time_limited[:1] + someday[:5] + time_limited[1:] + someday[5:]

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
        if self._tasks.get(task.id) != task:
            self._tasks[task.id] = task
            self._store.save(task)
