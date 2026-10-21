# Unlimilist

A personal desktop task manager that shows Tasks on a Kanban Board, separating open-ended work from work bound to dates.

## Language

**Task**:
A single piece of work the user wants to track. On the Board it is drawn as a card, but "card" refers only to its visual.
_Avoid_: Todo, card, item

**Board**:
The Kanban view of Tasks, arranged into Stages and Lanes.
_Avoid_: Kanban, view, Dashboard

**Card font size**:
How large the text on the Board's cards is drawn: one of five sizes, from 1 (smallest) to 5 (largest), where 2 is the standard size. It can make cards taller but never wider. It is chosen in Settings, on the Board view tab, and kept between launches.
_Avoid_: Zoom, dashboard font, text scale

**Stage**:
One of Inbox, In Process or Done, i.e. where a Task is in its life. The Board draws each Stage as a Column.
_Avoid_: Stack, status

**Lane**:
A subdivision of a Stage that holds either Someday Tasks or Time-limited Tasks. On the Board, a Stage's two Lanes are shown interleaved in one Column rather than side by side.
_Avoid_: Substack, swimlane, section

**Column**:
How the Board shows one Stage: its Lanes interleaved, with Someday Tasks aligned left and Time-limited Tasks aligned right. The order starts with the first Time-limited Task, then the top five Someday Tasks, then up to three more Time-limited Tasks that are under a month away. Every other Time-limited Task sits among the remaining Someday Tasks, after one Someday Task plus one more for each whole month until its earlier date. Time-limited Tasks keep their date order, and any that go past the last Someday Task come at the end.
_Avoid_: Merged lane, stack

**Inbox / In Process / Done**:
The three Stages. Inbox and In Process each have a Someday Lane and a Time-limited Lane. Done is a single list that holds both kinds of Task. A Task in In Process cannot be deleted; it has to leave In Process first.

**Folded Done**:
Done shown only as a narrow strip at the right of the Board, with its title and switch, so Inbox and In Process get its room. Tasks can still be dropped on the strip to complete them. Every launch starts with Done unfolded.
_Avoid_: Hidden, closed, collapsed

**Deleted Task**:
A Task the user deleted from Inbox or Done. It leaves the Board for good, but its file is kept under a name ending in `-deleted`, so it can be recovered by hand. A Task in In Process cannot be deleted.
_Avoid_: Removed, archived, trashed

**Duplicate**:
A copy of an Inbox Task, made from its context menu. Its Title is the original's with "[Duplication] " in front. It copies the Details (and so the Tags), Usable data, Activity and dates, but every Subtask starts unfinished. A Someday duplicate is ranked right below the original.
_Avoid_: Clone, copy

**Priority**:
A Someday Task's rank within its Lane: 1 is the top, and ranks run 1..N with no gaps or ties. A Someday Task always has a Priority. A new Task, or one that has just become Someday, starts at the bottom. Asking for a rank past the bottom (999 by convention) means the bottom.
_Avoid_: Order, position, importance

**Title**:
The short required name of a Task.

**Details**:
Optional formatted text that describes what the Task is.
_Avoid_: Description, notes

**Activity**:
The kind of work a Task represents: General Task, Ask, Phone call, Meeting, Develop or Milestone. Ask means getting an answer or information from someone, such as a question to a colleague, a client or support. Every Task has exactly one, and a new Task starts as General Task. It describes the work only and does not affect where the Task sits on the Board.
_Avoid_: Type, category, kind

**Subtask**:
A checkbox item in a Task's Details, either finished (checked) or unfinished. Subtasks normally form one list at the start of the Details, before any other text, and a new Subtask goes at the end of that list. A checkbox found further down still counts as a Subtask. A Task with unfinished Subtasks cannot enter Done, but once in Done its Subtasks can be edited freely.
_Avoid_: Checklist item, todo, child task

**Tag**:
A one-word label: letters, digits, - and _, starting with a letter. Tags ignore case, so #Work and #work are the same Tag, whether on a Task or a Note. A Task's Tags are written in its Details as #word. The # has to start a word, and a # inside code or a link doesn't count. A Task has every Tag that appears in its Details, and its first Tag is the first one written. A Note's Tags are kept in its own Tag area, never in its Body. The sidebar lists every Tag in both views, each counted for the view on screen.
_Avoid_: Label, hashtag, category

**Tag filter**:
The set of Tags selected in the sidebar, shared by the Board and the Notebook. When it isn't empty, each view shows only the Tasks or Notes that have at least one selected Tag. Switching views keeps it. It is cleared by Clear, by creating a Task or a Note, and when the app starts. A Tag that no Task or Note has any more drops out of it.
_Avoid_: Tag search, tag query

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

**Notebook**:
The second view of the app, next to the Board (the sidebar names them Tasks and Notebook): a table of all Notes, most recently opened or created first. Choosing a Note opens it in place of the table.
_Avoid_: Notes view, library, Dashboard

**Note**:
A piece of Markdown text the user keeps for reference. It has a Title, a Body, Tags, a Created date, a Last opened date and a Type. A Note is not a Task: it never appears on the Board and is not linked to any Task.
_Avoid_: Document, memo, page

**Show Note**:
How the Notebook shows one Note, in place of its table: in View mode the Body is rendered, and in Edit mode the Title, Type, Tags and the Body's Markdown can be changed. A new Note opens in Edit mode and an existing one in View mode. Edits are saved on leaving Edit mode, on leaving the Note, and every five minutes while editing. Showing a Note sets its Last opened date.
_Avoid_: Note dialog, note editor, preview

**Daily note**:
A Note saved with a Body but no Title. It is titled "Daily note" plus the day it was created, and gets the Tag #daily.
_Avoid_: Journal, untitled note

**Imported Note**:
A Note made from an outside file (Markdown, text, CSV, Word or PDF) whose content was converted to Markdown. It is titled after the file name and starts Open, with no Tags. The original file is not kept, and its images are not brought in.
_Avoid_: Attachment, upload

**Deleted Note**:
A Note the user deleted. It leaves the Notebook for good. An Open Note's file is kept under a name ending in `-deleted`, so it can be recovered by hand. A Secured Note can be deleted only with the Notebook password, and its file is removed outright.
_Avoid_: Archived, trashed

**Type**:
Whether a Note is Open or Secured. It can be changed only while editing the Note.
_Avoid_: Kind, format, category

**Secured Note**:
A Note whose Body is encrypted and can be read only with the Notebook password. Its Title, Tags, dates and Type stay readable.
_Avoid_: Private, locked, hidden

**Notebook password**:
The one password that opens every Secured Note. It is asked for the first time a Secured Note is opened and is then remembered until the app quits. Every password typed is checked against the copy kept in the macOS Keychain, never in the app's own files.
_Avoid_: Note password, PIN
