## Context

`with_db_connection` (`db/__init__.py:19-38`) is the single choke point every DAO function goes through — it
calls `get_db_connection()` (which does `_backend.connect()` + `_backend.setup_connection()`, i.e.
`sqlite3.connect()` + `PRAGMA foreign_keys = ON` + registering the `fuzzy_word_in` SQL function) and unconditionally
closes it in `finally`, on every call. Route handlers in `support_planner.py` routinely call 2+ DAO functions per
request, and `require_login` (`support_planner.py`'s global middleware) calls `db.user_exists` on literally every
request. FastAPI/Starlette run sync route handlers via `anyio.to_thread.run_sync`, which propagates the calling
async task's `contextvars.Context` into the worker thread — so a `ContextVar` set in middleware (async context) is
visible inside a sync route handler (thread-pool context), making a context-var-based "current connection" handle
viable without passing a connection parameter through every function signature.

## Goals / Non-Goals

**Goals:**
- One SQLite connection per HTTP request, shared across every `db.*` call that request makes (including the one
  inside `require_login`).
- Zero behavior change for non-request call sites (`init_db()` at import, `seed_demo_data.py`) — they keep
  today's open-per-call-then-close behavior.
- Zero change to per-function commit/rollback semantics — only connection lifecycle is deduplicated.

**Non-Goals:**
- Connection *pooling* across requests (e.g. a pool of N reusable connections) — SQLite is a local single-file
  DB; a fresh `sqlite3.connect()` per request is already cheap once it's only happening once instead of 2-4
  times. A real pool would add complexity (sizing, health checks) disproportionate to the benefit here.
- Changing transaction boundaries — a request that calls 3 DAO functions still does 3 independent
  commits, not one request-level transaction. Making assignment+task edits atomic across calls is a separate,
  larger change (would need `with_db_connection` callers to opt into an explicit transaction), out of scope.

## Decisions

- **`contextvars.ContextVar`, not `request.state`.** `request.state` would require every DAO function to accept a
  `request` parameter (or be called only from within a route handler), which `with_db_connection`-wrapped
  functions currently never do — they're called from route handlers, `seed_demo_data.py`, and once from
  `init_db()` at import time. A `ContextVar` lets `with_db_connection`'s wrapper check "is there a request-scoped
  connection right now?" without any call-site changes.
- **Fallback to open-per-call when no context var is set**, rather than requiring every entry point to explicitly
  open a request/script-scoped connection. This keeps `seed_demo_data.py` and `init_db()` working unmodified.
- **Middleware placement**: registered between `require_login` and `SessionMiddleware` (see proposal's "What
  Changes" section for the exact ordering rule) specifically so `require_login`'s `db.user_exists` call — which
  runs before any route code — also reuses the request connection instead of opening its own.
- **Still skip `/react-assets/*`**: static asset requests never touch the DB; opening/closing a connection for
  every JS/CSS/font request would be pure waste, mirroring `require_login`'s existing exclusion list.

## Risks / Trade-offs

- **[Confirmed during implementation, not just a theoretical risk]** Sharing one `sqlite3` connection object
  across the event-loop thread (where `db_connection_per_request` opens it) and the thread-pool worker thread
  (where FastAPI runs sync route handlers via `anyio.to_thread.run_sync`) hits `sqlite3`'s default
  `check_same_thread=True` guard — the very first end-to-end test failed with `sqlite3.ProgrammingError: SQLite
  objects created in a thread can only be used in that same thread`. **Fix**: `SQLiteBackend.connect()` now passes
  `check_same_thread=False`. This is safe specifically because the connection is never accessed from two threads
  *concurrently* — only *sequentially* within a single request's lifecycle (middleware opens it on the event-loop
  thread → `require_login` uses it on the same event-loop thread → the route handler uses it on a worker thread →
  middleware closes it back on the event-loop thread). `check_same_thread=False` would be unsafe if two different
  requests' connections were ever shared, which they never are (one connection per request, never reused across
  requests).
- [Risk] Context propagation into the thread pool is an anyio implementation detail, not a Starlette-guaranteed
  contract — if it ever changes, the fallback path (open-per-call) is silently correct but slow, not broken. →
  Mitigation: verified directly in tasks.md's verification section (connection identity/count checked via a
  monkeypatched connect() counter across multiple DAO calls within one request).
- [Risk] An exception inside a route handler must still close the request connection → Mitigation: the middleware
  closes it in a `finally` around `call_next`, matching how `SessionMiddleware` and `require_login` themselves
  are unaffected by handler exceptions (Starlette already ensures `finally` blocks in `@app.middleware('http')`
  functions run on handler exceptions).
- [Risk] A DAO function that itself catches `_backend.db_error` and returns `default_return` (many do) currently
  still closes its *own* connection in `finally` — with a shared connection, that `finally` must NOT close it.
  This is exactly what the context-var check handles, but it's the single detail most likely to be gotten wrong
  in review → Mitigation: single source of truth for "should I close this connection" lives only in
  `with_db_connection`'s wrapper, never duplicated elsewhere.
