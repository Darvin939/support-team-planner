## ADDED Requirements

### Requirement: Database runs in WAL journal mode
Every SQLite connection opened by the application SHALL run with `journal_mode=WAL` and `synchronous=NORMAL`, so
that concurrent readers are not blocked by an in-progress writer.

#### Scenario: New connection is configured for WAL
- **WHEN** the application opens a new SQLite connection (via `SQLiteBackend.connect()` +
  `setup_connection()`)
- **THEN** `PRAGMA journal_mode` reports `wal` and `PRAGMA synchronous` reports `1` (NORMAL) on that connection

#### Scenario: Reads are not blocked by a concurrent write
- **WHEN** one connection holds an open write transaction (e.g. saving an assignment)
- **THEN** a second, concurrent connection can still read (`SELECT`) without waiting for the writer to commit

#### Scenario: Existing behavior for readers/writers is otherwise unchanged
- **WHEN** any existing API endpoint is called
- **THEN** its response and data are identical to before this change — only concurrent-access timing improves,
  not query results
