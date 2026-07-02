# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Support Team Planner — a FastAPI web app (Russian UI) for scheduling support team tasks. Teams have tasks with
criticality levels; tasks get assigned to dates with employees, statuses, and optional deployment blocks (with
dependency tracking and fuzzy search). Every task/assignment edit is logged to an audit history, and the whole app sits
behind a lightweight per-employee login.

## Commands

```bash
pip install -r requirements.txt   # Install dependencies
python support_planner.py         # Run dev server on http://localhost:5093
python -m pytest tests/ -v        # Run tests (currently only db/postgres.py unit tests + a live-PG integration test, auto-skipped if no PG server)
```

`requirements.txt` currently lists `fastapi`, `uvicorn[standard]`, `jinja2`, `pydantic`, `starlette`, plus
`psycopg2-binary` (only needed for `PostgresBackend`). **Known gap:** the login feature also needs `itsdangerous` (used
internally by `starlette.middleware.sessions.SessionMiddleware` to sign the session cookie) and `python-multipart` (
needed by FastAPI to parse the `Form(...)` fields on `POST /login`) — neither is currently declared in
`requirements.txt`, so a fresh `pip install -r requirements.txt` will raise `RuntimeError`/`AssertionError` at startup
or on first login unless these are installed separately.

`run.sh` / `check.sh` are production launch helpers (used via cron/nohup on the deploy host): `check.sh` checks if
`python3 support_planner.py` is already running and, if not, starts `run.sh` in the background, logging to
`support-team-planner.log`. No linter or formatter is configured.

Session secret: set the `SESSION_SECRET_KEY` env var for production. If unset, the app falls back to a hardcoded
insecure default (logged as a warning at startup) — fine for local dev since it's stable across restarts, but must be
set for any real deployment.

## Architecture

FastAPI app split across a handful of modules:

- **`support_planner.py`** — all FastAPI routes and API endpoints (this is the app entrypoint — there is no `app.py`).
  `/` redirects to `/planning`. Pages: `/planning`, `/planning/{team_id}`, `/settings`, `/statistics`, `/login`. API
  under `/api/`. Request bodies use Pydantic models (`AssignmentIn`, `TaskIn`, `TeamIn`, `BlockIn`, `BlockTemplateIn`,
  `EmployeeIn`, `FreezeDayIn`, `FreezeDayMonthIn`, `TaskStatusIn`). API errors return
  `JSONResponse({"error": "..."}, status_code=...)`. Route handlers use sync `def` (not `async def`) since DB calls are
  blocking — FastAPI runs them in a thread pool. `VALID_TASK_TRANSITIONS` here must stay in sync with the copy in
  `planning.js`.
    - **Auth middleware ordering gotcha:** `require_login` (an `@app.middleware('http')` function) is registered
      *before* `app.add_middleware(SessionMiddleware, ...)` in the file, and this order is load-bearing, not incidental.
      Starlette's `add_middleware()` prepends to the middleware stack, so whichever middleware is added *last* runs
      *first* on an incoming request. `require_login` reads `request.session`, which only exists once
      `SessionMiddleware` has run — so `SessionMiddleware` must end up as the outer/first-executed layer, which means it
      must be the *last* one registered. Swapping this order reintroduces
      `AssertionError: SessionMiddleware must be installed to access request.session`. `_PUBLIC_PATHS` (`/login`,
      `/logout`) plus anything under `/static/` bypass the login check entirely; every other route (including `/docs`/
      `/openapi.json`) requires a session.
- **`auth.py`** — password hashing only (`hash_password`/`verify_password`, stdlib `hashlib.pbkdf2_hmac` + `secrets`,
  self-describing `pbkdf2_sha256$<iterations>$<salt>$<hash>` format, no external crypto dependency). No
  JWT/roles/permissions — a session cookie just holds `employee_id`; any logged-in employee can act as any other (e.g.,
  reset another employee's password via the Settings UI).
- **`db/` package** — DAO layer, swappable between SQLite and PostgreSQL:
    - `db/__init__.py` — all DAO functions (teams, blocks, block templates, employees, freeze days, tasks, task
      dependencies, assignments, statistics, change history), each wrapped in `@with_db_connection`, which handles
      connection lifecycle, commit, and error handling. The first parameter (`conn`) is injected by the decorator —
      callers do not pass it. It accepts `default_return`, `raise_on_error`, and `commit_on_success` for fine-grained
      control per function. The module-level `_backend: DBBackend = SQLiteBackend()` selects the active backend;
      `init_db()` runs on import.
        - Mutating functions on tasks/assignments (`create_or_update_task`, `update_task_status`, `delete_task`,
          `create_or_update_assignment`, `delete_assignment`, `delete_employee`) all accept a trailing optional
          `changed_by=None` kwarg — the acting employee's id, threaded from the route layer via
          `request.session.get('employee_id')`. Each of these diffs old vs. new values and writes one `task_history`/
          `assignment_history` row per changed field (or one summary row for create/delete), via the internal (non-
          `@with_db_connection`) helpers `_record_task_history`/`_record_assignment_history`, so the history insert
          commits atomically with the mutation itself.
        - Read side: `get_task_history`, `get_assignment_history` (+ `get_assignment_history_count`), and
          `get_task_full_history` (+ `get_task_full_history_count`) — the "full" variant `UNION ALL`s `task_history`
          with `assignment_history` filtered by `task_id` (not `assignment_id`), sorted by `changed_at DESC`, so a
          task's combined timeline still shows history for assignments that have since been deleted.
    - `db/backend.py` — `DBBackend` ABC defining the interface a backend must implement (`connect`, `setup_connection`,
      `last_insert_id`, `db_error`, `duplicate_error`, `init_schema`).
    - `db/sqlite.py` — `SQLiteBackend`, the default. Owns the canonical schema (`_SCHEMA`) and a custom
      `fuzzy_word_in(text, word)` SQLite function (sliding-window typo-tolerant substring match) registered via
      `conn.create_function`, used by task search. `init_schema()` also runs defensive `ALTER TABLE ... ADD COLUMN`
      statements (wrapped in try/except, since SQLite has no `IF NOT EXISTS` for that) to migrate pre-existing
      `database.db` files forward — this is how `employees.password_hash` gets added to a DB that predates the login
      feature.
    - `db/postgres.py` — `PostgresBackend`, opt-in alternative (switch by changing `_backend` in `db/__init__.py`).
      Wraps `psycopg2` connections/cursors to mimic the `sqlite3` interface (`conn.execute(...)` returning a
      fetchone/fetchall-capable cursor), translates `?` placeholders to `%s` and `INSERT OR IGNORE` to
      `... ON CONFLICT DO NOTHING` via `_adapt_sql`, and reimplements `fuzzy_word_in` as a PL/pgSQL function. Keep
      schema and query dialect changes mirrored between the two backends. Unlike SQLite, there's no `ALTER TABLE`-based
      migration path here — `_PG_SCHEMA_STMTS` is pure `CREATE TABLE IF NOT EXISTS`, so this backend is effectively
      fresh-install-only.
- **`utils.py`** — Single helper: `format_employee_name()` for "Фамилия И.О." formatting.

Frontend is vanilla JS + Jinja2 templates inheriting from `base.html` (blocks: `title`, `content`, `scripts`). Static
files mounted at `/static`. JS is split per page:

- `static/js/script.js` — shared utilities: dropdown toggles, URL linkification, modal close handlers,
  `lockBodyScroll()`/`unlockBodyScroll()` (called around every modal open/close across pages so the page behind a modal
  can't be scrolled — `unlockBodyScroll` re-checks whether *any* `.modal` is still visible before actually releasing the
  lock, guarding against overlapping modals), `clampDateRange(fromId, toId)` for 60-day max period enforcement,
  localStorage helpers (`saveTeamId`, `getSavedTeamId`, `saveDateRange`, `getSavedDateRange`) for persisting selected
  team and date filters across pages.
- `static/js/planning.js` — planning grid with drag-scroll, auto-scheduling, assignment CRUD, today-scroll, today
  counters; also holds the `VALID_TASK_TRANSITIONS` copy that must match `support_planner.py`. Also owns the
  history-panel UI for the task/assignment modals (see Domain Concepts below) — `toggleHistoryPanel`, `loadHistoryPage`,
  `renderHistoryEntries`, `historyPanelEl`/`resetHistoryPanel` state helpers.
- `static/js/settings.js` — teams/employees/blocks/block-templates/freeze-days management via modals; the employee modal
  has an optional password field (blank = leave unchanged, matching `update_employee`'s `password_hash=None`
  convention).
- `static/js/statistics.js` — active assignments tables (period + today) with counters.

## Database Schema

SQLite by default (`database.db`, gitignored, auto-created); PostgreSQL is a drop-in alternative via `PostgresBackend`.
Foreign keys are enforced (`PRAGMA foreign_keys = ON` for SQLite; on by default in Postgres). Key relationships:

- `teams` 1→N `tasks` (cascade delete)
- `blocks` — named deployment stages (e.g., "ГФ", "Б1"); names stored uppercase
- `block_templates` 1→N `template_blocks` → `blocks`, each with a `schedule_offset` (day shift from the base assignment
  date)
- `teams` N↔N `block_templates` via `team_templates` — a team's allowed templates determine which blocks it can
  auto-schedule against
- `tasks` 1→N `assignments` (cascade delete), unique on `(task_id, date)`
- `tasks` N↔N `tasks` via `task_dependencies` (`task_id` depends on `depends_on_task_id`), cycle-checked before insert (
  `has_dependency_cycle`, BFS)
- `employees` 1→N `assignments` (set NULL on employee delete, not cascade); also carries `password_hash` (nullable — an
  employee without a hash set simply can't log in yet)
- `task_history` / `assignment_history` — append-only audit log of field-level changes (see Domain Concepts). *
  *Deliberately have no FOREIGN KEY** on `task_id`/`assignment_id`/`changed_by_employee_id`, breaking the repo's usual "
  FKs everywhere" convention on purpose: an audit row must outlive the row it describes (a cascading FK would erase a
  deletion's own audit record; a non-cascading FK would instead block the delete). `assignment_history` denormalizes
  `task_id` and `date` so a task's history view still makes sense for assignments that no longer exist.

Note: `team_blocks` (a legacy flat per-team block table) is created then immediately `DROP TABLE`d by
`SQLiteBackend.init_schema()` — it has been fully superseded by `blocks` / `block_templates` / `team_templates`, kept
only as a migration step for existing DBs.

**Known pre-existing gap in `db/postgres.py`:** `_PG_SCHEMA_STMTS` has no `blocks`/`block_templates`/`template_blocks`/
`team_templates` tables at all (only `db/sqlite.py`'s `_SCHEMA` defines them) — switching to `PostgresBackend` will
break the first time team block-templates are touched. Not related to the history/auth work; just not yet fixed.

## Domain Concepts

Two separate status machines coexist — do not confuse them:

- **Assignment statuses** (`assignments.status`): `new` → `planned` → `success` | `rollback`. Saving an assignment with
  status `planned` auto-advances the parent task to `in_progress` via `maybe_advance_task_to_in_progress()`. Assignments
  also carry an `is_psi` boolean marker (ПСИ).
- **Task statuses** (`tasks.task_status`): `new` → `ready` → `in_progress` → `done` | `cancelled`. Valid transitions are
  enforced in both `support_planner.py:VALID_TASK_TRANSITIONS` and `planning.js:VALID_TASK_TRANSITIONS` — keep them in
  sync. Tasks in terminal states (`done`, `cancelled`) block all assignment/task edits.
- **Criticality**: `high`, `medium`, `low` (sorted in that order in queries; tasks list is sorted criticality-first,
  then task_status)
- **Task dependencies**: arbitrary DAG between tasks within a team; cycle creation is rejected at the API level (
  `POST /api/task` returns 400 if `has_dependency_cycle` detects one)
- **Freeze days**: dates when no changes are deployed; can be added individually, as ranges, or by full-month
  replacement (`set_freeze_days_for_month`)
- **Blocks / block templates**: a block is a named deployment stage with a `schedule_offset`; block templates group
  blocks together with offsets; teams are assigned a set of allowed templates, which drives auto-scheduling across
  blocks for that team
- **Fuzzy search**: `GET /api/tasks/{team_id}?search=` matches each search word against task name/description with up
  to ~1 typo per 7 characters, via the custom `fuzzy_word_in` SQL function (implemented per-backend — Python in SQLite,
  PL/pgSQL in Postgres)
- **Active assignments**: assignment statuses `new` or `planned` on tasks not in terminal states, served by
  `/api/active-assignments/{team_id}` (team_id=0 for all teams)
- **Authentication**: per-employee login (no roles) via `GET/POST /login` and `POST /logout`. The whole app (pages and
  `/api/*`) sits behind the `require_login` middleware in `support_planner.py` except `/login`, `/logout`, and
  `/static/*`. There's no self-service signup, but there is a bootstrap account: `SQLiteBackend.init_schema()` /
  `PostgresBackend.init_schema()` both seed an `employees` row named `Администратор` (empty first/middle name) with
  password `q123456789` via `INSERT OR IGNORE`, on every startup. This relies on `middle_name` being `''` rather than
  `NULL` in that seed row — `UNIQUE(last_name, first_name, middle_name)` never treats two `NULL`s as equal, so a `NULL`
  `middle_name` would silently defeat the `OR IGNORE` dedup and create a fresh duplicate admin row on every restart.
  Any other brand-new `employees` row still starts with `password_hash = NULL` and can't log in until a password is
  set for it via the Settings employee modal (which itself requires being logged in as someone else first).
- **Change history**: every create/update/delete on a task or assignment is logged (see `task_history`/
  `assignment_history` above), attributed to whichever employee is in the current session (`changed_by`, nullable —
  history rows from before the login feature existed, or written with no session, have `changed_by_employee_id = NULL`).
  Surfaced in the UI as a collapsible right-hand panel inside the existing task/assignment edit modals (
  `GET /api/task/{id}/history` for the combined task+assignments view, `GET /api/assignment/{id}/history` for a single
  assignment), paginated (`?offset=&limit=`, default page size 20 server-side / 10 in the `planning.js` UI).

## Conventions

- Commit messages are in Russian
- API errors return `{"error": "..."}` with HTTP 400/404/401
- `@formatter:off` / `@formatter:on` markers are used for IDEA formatting control in SQL blocks (`db/__init__.py`, `db/sqlite.py`)
- Date inputs are clamped to 2000–2099 range (`min`/`max` attributes) and max period of 60 days (`clampDateRange` in script.js)
- Selected team and date filters persist in localStorage across planning and statistics pages
- Use `localDateStr(new Date())` (not `toISOString()`) for today's date in JS to avoid UTC timezone shift
- `GET /api/tasks/{team_id}` supports `offset`, `limit`, `search`, and `show_completed` query params; default page size is 20
- `static/css/style.css` is organized into numbered sections (`/* --- N. Name --- */` comments); the responsive `@media (max-width: 768px)` block is always the *last* section on purpose — later source position lets its overrides win at equal CSS specificity without needing extra specificity hacks. Add new component styles as their own numbered section before it, not appended after.
- When adding/changing a query, mirror the dialect difference in both `db/sqlite.py` and `db/postgres.py` if PostgresBackend support matters (placeholder style, `INSERT OR IGNORE`, etc. — see `_adapt_sql` in `db/postgres.py`)
