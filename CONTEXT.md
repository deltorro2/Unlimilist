# Unlimilist

A personal desktop task manager that shows Tasks on a Kanban Board, separating open-ended work from work bound to dates.

## Language

**Task**:
A single piece of work the user wants to track. On the Board it is drawn as a card, but "card" refers only to its visual.
_Avoid_: Todo, card, item

**Board**:
The Kanban view of Tasks, arranged into Stages and Lanes.
_Avoid_: Kanban, view

**Stage**:
One of Inbox, In Process or Done, i.e. where a Task is in its life. The Board draws each Stage as a Column.
_Avoid_: Stack, status

**Lane**:
A subdivision of a Stage that holds either Someday Tasks or Time-limited Tasks. On the Board, a Stage's two Lanes are shown interleaved in one Column rather than side by side.
_Avoid_: Substack, swimlane, section

**Column**:
How the Board shows one Stage: its Lanes interleaved, with Someday Tasks aligned left and Time-limited Tasks aligned right. The order is the first Time-limited Task, then the top five Someday Tasks, then the remaining Time-limited Tasks, then the remaining Someday Tasks.
_Avoid_: Merged lane, stack

**Inbox / In Process / Done**:
The three Stages. Inbox and In Process each have a Someday Lane and a Time-limited Lane. Done is a single list that holds both kinds of Task. A Task in In Process cannot be deleted; it has to leave In Process first.

**Priority**:
A Someday Task's rank within its Lane: 1 is the top, and ranks run 1..N with no gaps or ties. A Someday Task always has a Priority. A new Task, or one that has just become Someday, starts at the bottom. Asking for a rank past the bottom (999 by convention) means the bottom.
_Avoid_: Order, position, importance

**Title**:
The short required name of a Task.

**Details**:
Optional formatted text that describes what the Task is.
_Avoid_: Description, notes

**Activity**:
The kind of work a Task represents: General Task, Phone call, Meeting, Develop code or Milestone. Every Task has exactly one, and a new Task starts as General Task. It describes the work only and does not affect where the Task sits on the Board.
_Avoid_: Type, category, kind

**Subtask**:
A checkbox item in a Task's Details, either finished (checked) or unfinished. Subtasks normally form one list at the start of the Details, before any other text, and a new Subtask goes at the end of that list. A checkbox found further down still counts as a Subtask. A Task with unfinished Subtasks cannot enter Done, but once in Done its Subtasks can be edited freely.
_Avoid_: Checklist item, todo, child task

**Usable data**:
Optional formatted text holding material that helps with doing the Task, such as links, snippets or reference info.
_Avoid_: Reference, attachments, resources

**Due date**:
The date work on a Task should start. It is optional and cannot be later than the Deadline.
_Avoid_: Start date, scheduled date

**Deadline**:
The date a Task must be finished by. It is optional.
_Avoid_: End date, due

**Someday Task**:
A Task with neither a Due date nor a Deadline.

**Time-limited Task**:
A Task with a Due date, a Deadline, or both. Within its Lane it is ordered by its earlier date, never by Priority.

**Conversion**:
A change from Someday Task to Time-limited Task or back, caused by adding or clearing both dates. A Task that becomes Time-limited loses its Priority.

**Overdue**:
A Task that is not Done and whose Deadline day has passed.

**Start passed**:
A Task still in Inbox whose Due date has passed: it should have been started already. Like an Overdue Task, it is flagged as late, which outranks Due soon.

**Due soon**:
A Task that is not Done and whose Deadline is today or tomorrow, and that is neither Overdue nor Start passed.

**Completed on**:
The date a Task entered Done. Done is ordered by it, most recent first.
