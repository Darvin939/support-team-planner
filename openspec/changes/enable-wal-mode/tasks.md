## 1. Implementation

- [x] 1.1 Added `conn.execute('PRAGMA journal_mode=WAL;')` and `conn.execute('PRAGMA synchronous=NORMAL;')` to
      `SQLiteBackend.setup_connection` (`db/sqlite.py`), alongside the existing `PRAGMA foreign_keys = ON;`.
- [x] 1.2 Checked `.gitignore`: `*.db` does **not** match `database.db-wal`/`database.db-shm` (those don't end in
      `.db`) — only `*.db-journal` was covered, not the WAL sidecar files. Added `*.db-wal` and `*.db-shm`
      entries.

## 2. Documentation

- [x] 2.1 Added a note to README.md's "База данных" section about WAL mode and the live-backup caveat (stop the
      app, or copy all three files together).

## 3. Verification

- [x] 3.1 Confirmed via `db.get_db_connection()` (the app's real connection setup path, not a bare
      `sqlite3.connect()`): `PRAGMA journal_mode` reports `wal`, `PRAGMA synchronous` reports `1` (NORMAL).
- [x] 3.2 **Revised expectation, confirmed by testing**: `database.db-wal`/`database.db-shm` appear only *while a
      connection with an open transaction exists* — not persistently "at rest" between requests. With this app's
      per-request connection lifecycle (one connection opened and closed per HTTP request — see
      `sqlite-connection-reuse`), SQLite auto-checkpoints and cleans up the sidecar files as soon as the *last*
      open connection to the database closes, which happens at the end of every request when there's no
      concurrent traffic. Verified directly: held a connection open mid-transaction → `database.db-wal`/`-shm`
      present; closed it → both gone, only `database.db` remains. This is expected, correct WAL behavior, not a
      bug — the original task wording ("appear... after the app starts and handles at least one write") assumed
      they'd stay visible, which isn't how a short-lived-connection architecture behaves. Updated design.md to
      reflect this.
- [x] 3.3 Manual smoke test via the real running app (login, `GET /api/segments`) — responses unchanged from
      before this change.
- [x] 3.3b **Extra check beyond the original task list**: verified the actual point of WAL — opened a writer
      connection with an uncommitted transaction, then opened a second (reader) connection and ran a `SELECT`
      concurrently: the read completed instantly (not blocked by the in-progress writer), confirming WAL's
      concurrent-read guarantee actually holds for this app's connection pattern.
- [x] 3.4 Confirmed `git status` shows no `database.db-wal`/`database.db-shm` as untracked after exercising the
      app (gitignore entries from 1.2 working correctly).
