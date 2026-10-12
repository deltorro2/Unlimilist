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
One of Inbox, In Process or Done, i.e. where a Task is in its life.
_Avoid_: Column, stack, status

**Lane**:
A subdivision of a Stage that holds either Someday Tasks or Time-limited Tasks.
_Avoid_: Substack, swimlane, section

**Inbox / In Process / Done**:
The three Stages. Inbox and In Process each have a Someday Lane and a Time-limited Lane. Done is a single list that holds both kinds of Task.

**Priority**:
A Someday Task's rank within its Lane: 1 is the top, and ranks run 1..N with no gaps or ties. A Someday Task always has a Priority. A new Task, or one that has just become Someday, starts at the bottom.
_Avoid_: Order, position, importance

**Title**:
The short required name of a Task.

**Details**:
Optional formatted text that describes what the Task is.
_Avoid_: Description, notes

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

**Due soon**:
A Task that is not Done and whose Deadline is today or tomorrow.

**Completed on**:
The date a Task entered Done. Done is ordered by it, most recent first.
