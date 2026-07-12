## Why

`SQLiteBackend.setup_connection` (`db/sqlite.py:182-184`) only sets `PRAGMA foreign_keys = ON`; SQLite's journal
mode is left at its default (`DELETE`, i.e. a rollback journal). Under the rollback journal, a writer holds an
exclusive lock on the whole database file for the duration of its transaction, blocking all readers until it
commits. Combined with the app opening a fresh connection per DAO call today (and, after `sqlite-connection-reuse`,
per request), a planner tool used concurrently by several editors clicking around is a realistic candidate for
`database is locked` errors under the rollback journal. `PRAGMA journal_mode=WAL` lets readers proceed
concurrently with a single writer, which is the standard recommendation for exactly this access pattern.

## What Changes

- `SQLiteBackend.setup_connection` additionally executes `PRAGMA journal_mode=WAL;` (and, conventionally,
  `PRAGMA synchronous=NORMAL;`, which is the safe/recommended pairing with WAL — full `FULL` synchronous is
  unnecessary overhead once WAL guarantees the WAL file itself is crash-safe at NORMAL).
- `database.db` gains sidecar files `database.db-wal` and `database.db-shm` while any connection is open with an
  active transaction. **Corrected during implementation**: with this app's per-request connection lifecycle (see
  `sqlite-connection-reuse`), these files are transient, not persistently visible at rest — SQLite
  auto-checkpoints and removes them as soon as the last open connection closes, which happens at the end of every
  request when there's no concurrent traffic. They were **not** already covered by `.gitignore`: `*.db` only
  matches files ending in `.db`, not `database.db-wal`/`database.db-shm` — new entries were needed (see Impact).

## Capabilities

### New Capabilities
- `sqlite-storage-mode`: the database runs in WAL journal mode, so concurrent reads are not blocked by an
  in-progress write.

### Modified Capabilities
- (none)

## Impact

- `db/sqlite.py`: `setup_connection` gains two `PRAGMA` statements.
- `.gitignore`: added `*.db-wal`/`*.db-shm` — confirmed missing, not already covered by `*.db`.
- Deployment note: WAL mode requires the database file to live on a filesystem that supports the shared-memory
  file locking WAL uses (standard on Linux/Windows local disks; NOT reliably supported on network filesystems
  like NFS) — not a concern for this app's current single-host SQLite deployment, but worth stating explicitly.
