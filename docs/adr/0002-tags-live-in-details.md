# Tags live in the Details text

A Task's Tags are not stored as a field. They are whatever `#word` Tags appear in its Details, so you add or remove a Tag simply by editing the text, and a Task file needs no new front-matter key. The issue that asked for Tags required that they be added only through the Details. Keeping them in the text also means older Task files already carry their Tags, and hand-edited files stay the single source of truth (see ADR 0001). The Board builds an index of Tags and the Tasks that have them when it loads, and updates it on every change, so the sidebar and the Tag filter never re-scan the files.

## Considered Options

- **A `tags:` list in the front matter**: easier to query, but Tags could disagree with the text, and the editor would need a separate Tag field.
- **Multi-word Tags (`#my tag`)**: free text has no clear end for them, so a Tag is one word: letters, digits, `-` and `_`, starting with a letter.

## Consequences

- Parsing has to skip what only looks like a Tag. A `#` counts only at the start of a word and never inside code or a link, so `issue#12`, `page#section` and `` `#define` `` are not Tags.
- Qt's Markdown writer saves a `#` that starts a line as `\#`, so the parser also accepts `\#word`. Hand-edited files show the backslash.
- Tags ignore case. A Tag used with different spellings is shown with the spelling of the earliest Task that has it.
- Renaming a Tag everywhere means editing the Details of every Task that has it; there is no rename command.
