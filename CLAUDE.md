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

**Frontend (React + Ant Design, `frontend/`):** the full Jinja2/vanilla-JS frontend migration is complete — every
page (`/login`, `/planning`, `/planning/{team_id}`, `/statistics`, `/journal`, `/journal/{team_id}`, `/settings`)
now serves the built React SPA; `templates/`, `static/js/`, and `static/css/` have all been deleted (`static/`
now only holds `static/fonts/`). All pages share one React Router layout (`AuthenticatedLayout` + `AppShell`,
fetches `GET /api/me` for role-gated nav), so navigating between them is a client-side route change, not a full
page reload — a full browser navigation only happens crossing into/out of the unauthenticated `/login` page, or
on a manual refresh. **`frontend/dist/` (built via Vite) is required, not optional** — every page route calls
`_serve_react_index()`; without a build, nothing loads at all. Run `npm run build` after cloning/pulling before
starting `support_planner.py`.

`frontend/src/theme.ts` sets `fontFamily` to `'InterVariable', 'Inter', ...` and `'JetBrains Mono Variable'` is
used ad hoc in a few components; `frontend/src/index.css` declares the matching `@font-face` rules pointing at
the self-hosted files at `static/fonts/InterVariable.woff2` / `static/fonts/JetBrainsMono-Variable.woff2` (fonts
are self-hosted, never loaded from an external CDN at runtime).

```bash
cd frontend && npm install   # Install frontend dependencies (first time only)
npm run dev                  # Vite dev server (proxies /api, /login, /logout to :5093 — run support_planner.py too)
npm run build                # Production build -> frontend/dist/, served by FastAPI at /react-assets/*
```

`GET /api/login-employees` is a deliberately public (unauthenticated) endpoint — `require_login`'s
`_PUBLIC_PATHS` includes it — feeding the login page's employee picker; it exposes the same non-sensitive
fields (`id`/`last_name`/`first_name`/`middle_name`) the old `login.html` already rendered to anyone
unauthenticated, so this isn't a new information disclosure. `POST /login` and `/api/me` are unchanged in
spirit but `POST /login` now returns JSON (`{success: true}` / `{"error": "..."}`) instead of a redirect or a
re-rendered Jinja page, matching the rest of the app's `/api/*` convention — the React login page does the
`window.location.href = '/planning'` navigation itself on success.

`requirements.txt` currently lists `fastapi`, `uvicorn[standard]`, `pydantic`, `starlette`, plus
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
  `/` redirects to `/planning`. All pages (`/login`, `/planning`, `/planning/{team_id}`, `/settings`, `/statistics`,
  `/journal`, `/journal/{team_id}`) serve the built React SPA via `_serve_react_index()` — see the frontend note
  above; `{team_id}` validity for `/planning/{team_id}` and `/journal/{team_id}` is checked client-side, not
  server-side (an invalid id just means the React page fails its own data fetch). API under `/api/`. Request
  bodies use Pydantic models (`AssignmentIn`, `TaskIn`, `TeamIn`, `BlockIn`, `BlockTemplateIn`,
  `EmployeeIn`, `FreezeDayIn`, `FreezeDayMonthIn`, `TaskStatusIn`). API errors return
  `JSONResponse({"error": "..."}, status_code=...)`. Route handlers use sync `def` (not `async def`) since DB calls are
  blocking — FastAPI runs them in a thread pool. `VALID_TASK_TRANSITIONS` here must stay in sync with the copy in
  `frontend/src/pages/PlanningPage.tsx`.
    - **Auth middleware ordering gotcha:** `require_login` (an `@app.middleware('http')` function) is registered
      *before* `app.add_middleware(SessionMiddleware, ...)` in the file, and this order is load-bearing, not incidental.
      Starlette's `add_middleware()` prepends to the middleware stack, so whichever middleware is added *last* runs
      *first* on an incoming request. `require_login` reads `request.session`, which only exists once
      `SessionMiddleware` has run — so `SessionMiddleware` must end up as the outer/first-executed layer, which means it
      must be the *last* one registered. Swapping this order reintroduces
      `AssertionError: SessionMiddleware must be installed to access request.session`. `_PUBLIC_PATHS` (`/login`,
      `/logout`, `/api/login-employees`) plus anything under `/static/` or `/react-assets/` bypass the login check
      entirely; every other route (including `/docs`/`/openapi.json`) requires a session. Beyond the session check,
      `require_login` also enforces role: it reads `role` fresh from the DB on every request (not from the session,
      so a role change takes effect without re-login), stores it on `request.state.role`, and compares it against
      `_required_rank(method, path)` — a 403 JSON error for `/api/*`, a redirect to `/planning` for pages. `GET`
      requests are always allowed at any role; `/settings` requires `editor`+; `/api/employees` mutations require
      `admin`; `/api/teams`, `/api/freeze-days`, `/api/blocks`, `/api/block-templates` mutations require `editor`+;
      everything else (including task/assignment mutations) only requires being logged in (`user`+).
- **`auth.py`** — password hashing only (`hash_password`/`verify_password`, stdlib `hashlib.pbkdf2_hmac` + `secrets`,
  self-describing `pbkdf2_sha256$<iterations>$<salt>$<hash>` format, no external crypto dependency). No JWT — role
  authorization itself lives in `support_planner.py`'s `require_login` middleware (see above), not here.
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

Frontend is React + TypeScript + Vite (antd v6, TanStack Query, React Router), built to `frontend/dist/` and served
statically. `frontend/src/` layout:

- `pages/` — one component per route: `LoginPage`, `PlanningPage`, `StatisticsPage`, `JournalPage`, `SettingsPage`.
  `pages/planning/` holds Planning-specific pieces split out for size:
    - `TaskModal.tsx` / `AssignmentModal.tsx` — CRUD modals, each embedding a `HistoryPanel` (see Domain Concepts
      below) and a footer toggle button to show/hide it.
    - `HistoryPanel.tsx` — collapsible paginated history list + `useHistoryToggle` (resets closed, or auto-opens,
      every time the owning modal transitions to open) shared by both modals.
    - `useAssignmentDrag.ts` — custom mouse-event-driven drag-and-drop for rescheduling an assignment to a
      different date on the grid (cloned floating ghost clamped to the scrollable area, edge auto-scroll,
      `elementFromPoint`-based occupied-cell detection). Deliberately not built on a drag-and-drop library
      (dnd-kit was the original plan) — a raw port of the original vanilla-JS `setupAssignmentDrag` behavior was a
      better fit than rect-based collision detection against antd `Table`'s sticky-column DOM.
- `components/` — shared UI: `AppShell`/`AuthenticatedLayout` (sidebar, role-gated nav via `GET /api/me`,
  client-side route dispatch — see `MIGRATED_BASE_PATHS` in `AuthenticatedLayout.tsx`), `planningBadges.tsx`
  (criticality/status/dependency/schedule badges shared across Planning and Journal), `StatTile.tsx`.
- `hooks/` — one thin TanStack Query wrapper per data domain: `usePlanningData.ts`, `useSettingsData.ts`,
  `useTeams.ts`, `useMe.ts`, `useEmployeeNames.ts`.
- `lib/` — pure helpers: `apiMutate.ts` (shared POST/PUT/PATCH/DELETE fetch wrapper), `autoSchedule.ts`
  (freeze-day-aware auto-scheduling date math, ported from the original block-template scheduling logic),
  `historyFormat.ts` (change-history field labels/formatting, shared by the Journal page and `HistoryPanel`).
- `theme.ts` — antd `ConfigProvider` tokens (dark/light `ThemeConfig`s), seeded from `@ant-design/colors`'
  official palette rather than hand-picked values, plus the sidebar "chrome" colors.

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
  employee without a hash set simply can't log in yet) and `role` (`NOT NULL DEFAULT 'user'`, one of `user`/
  `editor`/`admin` — see Domain Concepts)
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
  enforced in both `support_planner.py:VALID_TASK_TRANSITIONS` and
  `frontend/src/pages/PlanningPage.tsx:VALID_TASK_TRANSITIONS` — keep them in
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
- **Authentication & roles**: per-employee login via `GET/POST /login` and `POST /logout`, plus a three-tier role
  system — `employees.role` is `user` < `editor` < `admin` (each rank includes the ones below it), enforced by
  `require_login` (see above) via `_ROLE_RANK`/`_required_rank`/`_VALID_ROLES` in `support_planner.py`. In short:
  any logged-in employee can read everything and create/edit/delete tasks and assignments; `editor`+ additionally
  gets the whole `/settings` page and team/freeze-day/block/block-template mutations; only `admin` can create,
  edit, or delete other employees (including resetting their password or changing their role) — `GET
  /api/employees` itself stays open to every role since the planner's assignee dropdowns need it. `GET /api/me`
  exposes the current employee + role as JSON for the React nav (`AuthenticatedLayout`/`AppShell` role-gate the
  Settings nav item on `role === 'admin' || role === 'editor'`). The whole app (pages and `/api/*`) sits behind
  `require_login` in `support_planner.py` except `/login`, `/logout`, `/api/login-employees`, `/static/*`, and
  `/react-assets/*` (the built React bundle itself must be loadable before the user is authenticated — see the
  React migration note above). There's no self-service signup, but there is a bootstrap account:
  `SQLiteBackend.init_schema()` / `PostgresBackend.init_schema()` both seed an `employees` row named
  `Администратор` (empty first/middle name, role `admin`) with password `q12345678` via `INSERT OR IGNORE`, on
  every startup. This relies on `middle_name` being `''` rather than `NULL` in that seed row — `UNIQUE(last_name,
  first_name, middle_name)` never treats two `NULL`s as equal, so a `NULL` `middle_name` would silently defeat the
  `OR IGNORE` dedup and create a fresh duplicate admin row on every restart. Any other brand-new `employees` row
  still starts with `password_hash = NULL` and can't log in until a password is set for it via the Settings
  employee modal (which itself requires being logged in as an `admin`).
- **Change history**: every create/update/delete on a task or assignment is logged (see `task_history`/
  `assignment_history` above), attributed to whichever employee is in the current session (`changed_by`, nullable —
  history rows from before the login feature existed, or written with no session, have `changed_by_employee_id = NULL`).
  Surfaced in the UI as a collapsible right-hand panel inside the task/assignment edit modals
  (`frontend/src/pages/planning/HistoryPanel.tsx` — `GET /api/task/{id}/history` for the combined task+assignments
  view, `GET /api/assignment/{id}/history` for a single assignment), paginated (`?offset=&limit=`, default page
  size 20 server-side / 10 in the React UI). A terminal (`done`/`cancelled`) task's read-only view auto-opens the
  panel on load, since viewing why a finished task looks the way it does is the point of opening it read-only.

## Conventions

- Commit messages are in Russian
- API errors return `{"error": "..."}` with HTTP 400/404/401
- `@formatter:off` / `@formatter:on` markers are used for IDEA formatting control in SQL blocks (`db/__init__.py`, `db/sqlite.py`)
- Date inputs are clamped to 2000–2099 range (`minDate`/`maxDate` on antd `DatePicker`s) and a max period of 60 days
  (`MAX_PERIOD_DAYS` in `PlanningPage.tsx`)
- Selected team and date filters persist in localStorage across planning and statistics pages
- `GET /api/tasks/{team_id}` supports `offset`, `limit`, `search`, and `show_completed` query params; default page size is 20
- Frontend styling is antd `ConfigProvider` theme tokens (`frontend/src/theme.ts`) plus inline `style={}` per
  component — there is no separate app stylesheet beyond `frontend/src/index.css` (a minimal reset plus the
  drag-and-drop ghost/highlight classes used by `useAssignmentDrag.ts`, since that ghost element is a raw DOM
  clone outside React's render tree and needs real CSS classes, not inline styles)
- When adding/changing a query, mirror the dialect difference in both `db/sqlite.py` and `db/postgres.py` if PostgresBackend support matters (placeholder style, `INSERT OR IGNORE`, etc. — see `_adapt_sql` in `db/postgres.py`)
