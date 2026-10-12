# One Markdown file per Task

Each Task is stored as its own human-readable Markdown file. Metadata goes in front matter, and Details and Usable data go in the body as Markdown. The files live in a fixed app-data folder; a database was not used. This keeps the user's data plain, inspectable and editable outside the app. Because of that, the app re-reads the folder on start and must tolerate hand edits: it skips malformed files with a warning and renumbers Priorities that are duplicated or have gaps.

## Consequences

- Reordering a Lane rewrites the file of every Task whose Priority changed.
- External edits made while the app is running are not seen until the next start, and the app may overwrite them.
