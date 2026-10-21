# Secured Notes encrypt the Body with one Notebook password kept in the Keychain

A Secured Note's Body is encrypted in its file with AES-256-GCM, and the key comes from the Notebook password through scrypt (a fresh salt and nonce for every save). The Title, Tags, dates and Type stay readable, so the Notebook's table, sorting and Tag sidebar work without the password. One password opens every Secured Note. It is asked for once a session, and every typed password is checked against the copy in the macOS Keychain, never in the app's own files. The real app and the test build share that Keychain entry.

## Considered Options

- **A password per Note:** stronger isolation, but there are many passwords to remember and nowhere to check them.
- **Only lock the screen, not the file:** simple, but anyone who opens the folder in Finder reads every "secured" Note.
- **Encrypt the whole file:** this hides the Title and Tags too, but then the table and Tag filter can't show a locked Note.

## Consequences

- Without the password, a Secured Note can't be read. The Keychain copy is the way back (Keychain Access, "Unlimilist").
- Don't put secrets in a Secured Note's Title or Tags.
- Changing the password reads every Secured Note with the old one first. If any doesn't open, nothing changes.
- Deleting a Secured Note asks for the password and removes its file outright, unlike Open Notes and Tasks (ADR 0004), which keep a `-deleted` file.
