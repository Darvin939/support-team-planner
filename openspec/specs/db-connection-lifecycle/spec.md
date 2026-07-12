# db-connection-lifecycle Specification

## Purpose
TBD - created by archiving change sqlite-connection-reuse. Update Purpose after archive.
## Requirements
### Requirement: One SQLite connection per HTTP request
The application SHALL open at most one SQLite connection per HTTP request (excluding requests under
`/react-assets/`), reused by every DAO call made while handling that request, and SHALL close it after the
response is produced regardless of success or failure.

#### Scenario: Multiple DAO calls in one request share a connection
- **WHEN** a request handler calls two or more `db.*` functions (e.g. `GET /api/tasks/{team_id}` calling
  `get_tasks_by_team` and `get_tasks_count_by_team`)
- **THEN** both calls execute against the same underlying SQLite connection object, opened once for the request

#### Scenario: require_login's own DB call is included
- **WHEN** any non-public request passes through the `require_login` middleware, which calls `db.user_exists`
- **THEN** that call reuses the same request-scoped connection as the route handler that runs afterward

#### Scenario: Connection is closed after the response, even on error
- **WHEN** a route handler raises an unhandled exception
- **THEN** the request-scoped connection is still closed before the response cycle completes (no leaked
  connections)

#### Scenario: Non-request call sites are unaffected
- **WHEN** `db.*` functions are called outside of an HTTP request (`init_db()` at module import, or
  `seed_demo_data.py`)
- **THEN** they continue to open and close their own connection per call, exactly as before this change

#### Scenario: Static asset requests don't open a connection
- **WHEN** a request path starts with `/react-assets/`
- **THEN** no request-scoped SQLite connection is opened for it

#### Scenario: The shared connection works across the event-loop and worker threads
- **WHEN** a request's connection is opened on the event-loop thread (by `db_connection_per_request`) and then
  used by a synchronous route handler running on a thread-pool worker thread (`anyio.to_thread.run_sync`)
- **THEN** the DB call succeeds without a `sqlite3.ProgrammingError` about cross-thread use — the connection is
  opened with `check_same_thread=False`, which is safe because it's never accessed by two threads simultaneously,
  only sequentially within one request

#### Scenario: A failed DAO call doesn't poison a later call in the same request
- **WHEN** one DAO call in a request fails with a DB constraint error and is caught internally
  (`raise_on_error=False`), and a later DAO call in the *same* request succeeds and commits
- **THEN** the failed call's own (uncommitted) work was rolled back before returning, so the later call's commit
  does not also commit the failed call's partial state

