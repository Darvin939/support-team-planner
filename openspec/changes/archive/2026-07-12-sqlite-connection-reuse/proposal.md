## Why

`with_db_connection` (`db/__init__.py`) opens a fresh `sqlite3.connect()` and closes it on *every single DAO
function call*, not once per HTTP request. A typical API request calls several DAO functions — e.g.
`GET /api/tasks/{team_id}` calls both `get_tasks_by_team` and `get_tasks_count_by_team` — and `require_login`
itself calls `db.user_exists` on every request (any page or API call). That means a single request routinely opens
and closes 2-4+ separate SQLite connections. Reusing one connection per request removes this redundant
open/setup/close overhead and is also a prerequisite for `enable-wal-mode` (a separate change) to pay off fully,
since short-lived connections gain less benefit from WAL than a connection held for the request's duration.

## What Changes

- A new `contextvars.ContextVar` in `db/__init__.py` holds an optional "current request connection".
- A new ASGI middleware in `support_planner.py` opens one connection at the start of each request (except
  `/react-assets/*`, mirroring `require_login`'s existing exclusion), stores it in the context var, and closes it
  in a `finally` block after the response — regardless of success or failure.
- `with_db_connection`'s wrapper checks the context var first: if a request-scoped connection exists, it's reused
  (not closed after this individual call); otherwise the wrapper falls back to today's open-per-call-then-close
  behavior, so non-request contexts (`init_db()` at import time, `seed_demo_data.py`) are unaffected.
- Per-call commit semantics are unchanged — each `with_db_connection`-wrapped function still commits (or not,
  per its own `commit_on_success` flag) independently; only connection open/close is deduplicated, not
  transaction boundaries.
- **Middleware ordering**: the new middleware must run *between* `SessionMiddleware` (outermost) and
  `require_login` (innermost) so that `require_login`'s own `db.user_exists` call also benefits from the shared
  connection — this means registering it via `@app.middleware('http')` textually after `require_login` but
  before `app.add_middleware(SessionMiddleware, ...)`, per Starlette's last-registered-runs-first rule (already
  documented in CLAUDE.md for the existing two middlewares).

## Capabilities

### New Capabilities
- `db-connection-lifecycle`: one SQLite connection is opened and closed per HTTP request rather than per DAO call;
  behavior is observationally identical to callers (same commit/rollback semantics per function).

### Modified Capabilities
- (none)

## Impact

- `db/__init__.py`: `with_db_connection` gains a context-var check; new `get_db_connection`/`_request_conn`
  plumbing.
- `support_planner.py`: new middleware registered between `require_login` and `SessionMiddleware`.
- No API/behavior change visible to clients — this is purely an internal efficiency change.
