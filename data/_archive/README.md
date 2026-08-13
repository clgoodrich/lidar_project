# Archive — nothing here is deleted

Two categories, and the difference matters:

- **`parked/`** — a human decided to stop working on this. Nothing replaced it.
  Un-archiving is a research decision, not a cleanup.
- **`superseded/`** — something better exists. The manifest names it.

`ARCHIVE_MANIFEST.csv` is the record: what moved, from where, when, why, what
replaced it, and the exact command that reverses it.

Everything below this directory is gitignored except this README and the
manifest. The contents are externally sourced, submitted documents, or
regenerable — but they are still on disk and still in the E: backup.

## Reversing a move

    python tools/apply_moves.py --undo --phase archive

If you un-archive a thread, re-check `.gitignore`: the rules anchored to the
original locations were deliberately left in place so coverage returns with the
files instead of silently leaking.
