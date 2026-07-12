## 1. DB layer

- [x] 1.1 Add `_request_conn: contextvars.ContextVar = contextvars.ContextVar('request_conn', default=None)` to
      `db/__init__.py`.
- [x] 1.2 Add `set_request_connection(conn)` (returns the `Token`) and `clear_request_connection(token)` helpers
      wrapping `_request_conn.set`/`.reset`, for the middleware to call.
- [x] 1.3 Update `with_db_connection`'s `wrapper`: read `_request_conn.get()`; if set, use it and skip
      opening/closing (still commit/rollback per the function's own flags); if not set, fall back to today's
      open-then-close-in-finally behavior unchanged. **Extra fix found during implementation**: added an explicit
      `conn.rollback()` in the `except _backend.db_error` branch — without it, a `raise_on_error=False` function
      (e.g. `create_user`) that hits a constraint error on a *shared* connection would leave a dangling
      uncommitted transaction that the *next* DAO call's `commit()` in the same request would silently commit
      alongside its own work. Previously this was masked because every call got its own connection, and
      `conn.close()` implicitly rolled back on failure.
- [x] 1.3b **Critical fix found during implementation, not in the original task list**: added
      `check_same_thread=False` to `sqlite3.connect()` in `SQLiteBackend.connect()` (`db/sqlite.py`). Without it,
      the very first end-to-end test failed with `sqlite3.ProgrammingError: SQLite objects created in a thread
      can only be used in that same thread` — the new middleware opens the connection in the event-loop thread,
      but FastAPI runs sync route handlers via `anyio.to_thread.run_sync` in a *different* worker thread. Safe
      here because the connection is never used by two threads *simultaneously*, only sequentially within one
      request (middleware → require_login → route → middleware). See design.md and specs for the corrected
      requirement.

## 2. Middleware

- [x] 2.1 Add a new `@app.middleware('http')` function in `support_planner.py` that: skips `/react-assets/*`
      (same check as `require_login`), otherwise opens a connection via `db.get_db_connection()`, sets it via
      `db.set_request_connection`, calls `await call_next(request)` inside try/finally, and closes the connection
      + clears the context var in `finally`.
- [x] 2.2 Registered `db_connection_per_request`'s `@app.middleware('http')` decorator textually **after**
      `require_login`'s but **before** `app.add_middleware(SessionMiddleware, ...)`, giving execution order
      `SessionMiddleware → db_connection_per_request → require_login → route`.
- [x] 2.3 Added explanatory comments at both registration points (above `require_login` and above
      `db_connection_per_request`) describing the 3-way ordering requirement.

## 3. Verification

- [x] 3.1 Verified via a scratch script (`starlette.testclient.TestClient` + monkeypatching
      `SQLiteBackend.connect` to count calls, not committed to the repo): `GET /api/tasks/1` (which internally
      calls `get_tasks_by_team` + `get_tasks_count_by_team`, 2 DAO functions) opened exactly **1** connection.
- [x] 3.2 Confirmed responses unchanged: login (`200 {"success": true}`), `GET /api/tasks/1` (`200`), `GET
      /api/tasks/999999` (`200`, empty list) — same shapes as before this change.
- [x] 3.3 Triggered an unhandled `ValueError` (`GET /api/assignments/1?task_ids=abc`, the known
      non-numeric-CSV-value gap) — confirmed only 1 connection was opened for that request (no leak on the error
      path, thanks to the `finally` in `db_connection_per_request`), and a follow-up request immediately after
      still worked normally (no lock/hang carried over).
- [x] 3.4 Did **not** run `python seed_demo_data.py` against the real `database.db` (risk of duplicating/
      conflicting with existing demo data, and the script's idempotency wasn't verified as in-scope for this
      change). Instead verified the underlying mechanism directly: called `db.get_all_teams()` and
      `db.get_all_segments()` with no request context active (`_request_conn` at its default `None`) and
      confirmed each call opened and closed its own connection (1 `connect()` call per call, not accumulating) —
      this is exactly the fallback path `seed_demo_data.py`/`init_db()` rely on.
- [x] 3.5 Confirmed app startup (`init_db()` at import time) works: `import support_planner` succeeded without
      error in every run of the verification script above (this call happens before any request/middleware
      exists, at module-import time, and is unaffected by this change since `_request_conn` defaults to `None`).
