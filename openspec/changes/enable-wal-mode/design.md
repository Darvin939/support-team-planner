## Context

`setup_connection` runs on every new `sqlite3.connect()` (`db/sqlite.py:182-184`), currently just enabling FK
enforcement. SQLite's default rollback-journal mode serializes writers against readers at the whole-file level.
The `sqlite-connection-reuse` change (separate proposal) reduces how often connections are opened/closed, but
does not by itself change lock contention behavior — that's what WAL mode addresses.

## Goals / Non-Goals

**Goals:**
- Readers no longer block on an in-progress writer (and vice versa) for the common case of one write mixed with
  several concurrent reads (e.g. one editor saving an assignment while others are viewing the planner).

**Non-Goals:**
- Solving write-write contention — WAL still serializes concurrent writers (SQLite allows only one writer at a
  time regardless of journal mode); that's inherent to SQLite, not something this change addresses.
- Any change to backup/restore tooling — out of scope here, but noted as a follow-up concern in Risks below.

## Decisions

- **`PRAGMA journal_mode=WAL` set per-connection in `setup_connection`**, not once via a separate migration step.
  WAL is a persistent, file-level setting (survives across connections and processions once set), but setting it
  defensively on every connection is a no-op after the first time and keeps the intent local to the one function
  that already owns "how a connection is configured," rather than adding a special one-time-migration code path
  like the `_migrate_*` functions in `init_schema`.
- **Pair with `PRAGMA synchronous=NORMAL`.** WAL mode's own documentation recommends `NORMAL` over the default
  `FULL`: at `NORMAL`, an OS crash (not an application crash) could lose the most recent commit, but the database
  file itself can never become corrupted — an acceptable trade-off for this app's durability requirements
  (internal planning tool, not financial ledger), in exchange for less fsync overhead per write.

## Verification note

Confirmed by direct testing (see tasks.md §3): `db.get_db_connection()` reports `journal_mode=wal` and
`synchronous=1` (NORMAL); a reader connection issuing `SELECT` while a separate writer connection holds an
uncommitted transaction open completes instantly, unblocked — the actual goal of this change, not just the
PRAGMA being set.

## Risks / Trade-offs

- [Risk] WAL adds two sidecar files (`database.db-wal`, `database.db-shm`) next to `database.db` while a
  connection has an open transaction → Mitigation: `.gitignore` did **not** already exclude them (`*.db` doesn't
  match a `-wal`/`-shm` suffix) — added explicit entries, confirmed by testing that they no longer show as
  untracked. Confirmed the files are genuinely transient in this app specifically because of its per-request
  connection lifecycle (`sqlite-connection-reuse`): SQLite auto-checkpoints and removes them as soon as the last
  open connection to the database closes, which is every request's end under normal (non-concurrent) load —
  verified directly by holding a connection open mid-transaction (files present) then closing it (files gone).
- [Risk] A copy of `database.db` alone (e.g. for a manual backup) can miss uncommitted WAL data if copied while
  the app is running → Mitigation: not a new risk introduced by this change (the app has no documented backup
  procedure today), but worth a one-line README note that a live backup should either stop the app first or copy
  all three files together.
- [Risk] Deploying to a filesystem that doesn't support WAL's shared-memory locking (e.g. some network mounts)
  would silently fall back to rollback mode or error → Mitigation: not applicable to this app's current
  deployment (local disk via `run.sh`/`check.sh`), documented as an assumption rather than actively guarded
  against.
