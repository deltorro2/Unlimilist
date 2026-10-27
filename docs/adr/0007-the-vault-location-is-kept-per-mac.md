# The Vault's location is kept per Mac, and the test build has no Vault

A Vault is the folder holding the user's Tasks (`tasks/`) and Notes (`notes/`). It can be anywhere, often in a folder that Dropbox, Google Drive or a similar service syncs between Macs. Which folder is the Vault is saved in `settings.json`, in `~/Library/Application Support/Unlimilist`, along with the other settings (card font size, the Stale days). The Notebook password stays in each Mac's Keychain. So the Vault holds data only: nothing in it says how a particular Mac shows or unlocks it.

The test build ignores all of this. It always reads `test/` and `test-notes/` beside `settings.json`, never runs Setup, has no My Vault tab, and never reads or writes the Vault setting. Running the normal build locally would read the real Tasks and Notes, so a build that could switch Vaults is too easy a way to touch them.

## Considered Options

- **Settings inside the Vault:** card font size and Stale days would follow the user to every Mac. But the app has to know where the Vault is before it can read anything from it, so its location would still need a file on each Mac. Two Macs editing one synced settings file also risks conflicts from the sync service.
- **A marker file that identifies a Vault:** stricter, but an existing folder isn't a Vault until it is marked. The user chose to let any folder be a Vault.
- **A test build with its own Vault setting and Setup on demand:** Setup and the My Vault tab could then be tried by hand. It was turned down to keep the test build's folders fixed. Those parts are covered by automated tests only.

## Consequences

- Each Mac picks its Vault once, in Setup, and keeps its own display settings and Stale days.
- Upgrading moves nothing. With no Vault saved, the new version opens Setup, and the user points it at their data, including the old Application Support folder if they like.
- Choosing another Vault only switches. It never moves or copies files.
- A Vault shared between Macs needs the same Notebook password on each. Setup checks a new password against the Vault's Secured Notes.
- `settings.json` is still shared by both builds, so the test build must never write the Vault setting.
