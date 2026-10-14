# Deleting renames the Task file instead of erasing it

Deleting a Task, whether from Delete Task mode, its context menu or the Task dialog, renames its file from `<id>.md` to `<id>.md-deleted`. The app never erases a file. The app reads only `*.md` files (ADR 0001), so a Deleted Task never comes back on its own, yet a Task deleted by mistake can be recovered by renaming its file back. Deleting several Tasks at once made a mistake more costly, and there is no undo.

## Considered Options

- **Erase the file** (as before): simple, but a mistaken delete is lost for good.
- **A trash folder inside the data folder**: tidier, but the file moves away from where the user looks for it.

## Consequences

- Deleted files pile up in the data folder; nothing removes them yet.
- If `<id>.md-deleted` already exists, the newer file gets a number: `<id>.md-deleted-2`, `-3`, …
