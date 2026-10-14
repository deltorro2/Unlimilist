# Tiles show the Title, not the Details

A tile on the Board shows its Activity badge, status circle, Title, Tag chip and dates, but no Details preview. The Title wraps over every line the tile has: 4, less one when there is a dates line, with "…" if it is still cut. Done tiles keep a single struck-through line. The Tag chip floats at the right end of the first Title line and takes no column of its own, so only that line makes room for it and later lines run underneath it. Its text is at most 12 characters including "+N", and a longer Tag is cut with "…" before the "+N".

## Considered Options

- **A Details preview with highlighted Tags** (built first): it repeated the Tags already in the chip, and the chip's column narrowed every Title line, so long Titles were cut early. The Details are one click away in the Task dialog.

## Consequences

- The 📎 Usable data indicator is gone too; a tile no longer shows whether a Task has Usable data.
- A Task's Subtasks and notes are visible only in the Task dialog. Progress still shows in the status circle.
