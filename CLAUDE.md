# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Support Team Planner — a FastAPI web app (Russian UI) for scheduling support team tasks. Teams have tasks with
a manually-ordered priority; tasks get assigned to dates with users, statuses, and optional deployment blocks
(with dependency tracking and fuzzy search). Every task/assignment edit is logged to an audit history, and the whole
app sits behind a lightweight per-user login.

## Commands

```bash
pip install -r requirements.txt   # Install dependencies
python support_planner.py         # Run dev server on http://localhost:5093 (HTTP, unless Vault certs are available — see SSL/TLS below)
```

There is currently no runnable test suite — `tests/` contains only stale `__pycache__` bytecode with no tracked
`.py` sources (`python -m pytest tests/ -v` collects 0 items). No linter or formatter is configured either.

**Frontend (React + Ant Design, `frontend/`):** the full Jinja2/vanilla-JS frontend migration is complete — every
page (`/login`, `/planning`, `/planning/{team_id}`, `/statistics`, `/journal`, `/journal/{team_id}`, `/settings`)
now serves the built React SPA; `templates/`, `static/`, and the old vanilla-JS/CSS assets have all been deleted
— there is no top-level `static/` directory at all anymore. All pages share one React Router layout (
`AuthenticatedLayout` + `AppShell`,
fetches `GET /api/me` for role-gated nav), so navigating between them is a client-side route change, not a full
page reload — a full browser navigation only happens crossing into/out of the unauthenticated `/login` page, or
on a manual refresh. **`frontend/dist/` (built via Vite) is required, not optional** — every page route calls
`_serve_react_index()`; without a build, nothing loads at all. Run `npm run build` after cloning/pulling before
starting `support_planner.py`.

`frontend/src/theme.ts` sets `fontFamily` to `'InterVariable', 'Inter', ...` and `'JetBrains Mono Variable'` is
used ad hoc in a few components; `frontend/src/index.css` declares the matching `@font-face` rules pointing at
the self-hosted files in Vite's `frontend/public/fonts/` directory (fonts are self-hosted, never loaded from an
external CDN at runtime). `index.css` references them by the absolute path `/fonts/InterVariable.woff2` /
`/fonts/JetBrainsMono-Variable.woff2` — Vite serves `public/` at server root in dev, and at build time rewrites
that root-relative `url()` to the `/react-assets/` base and copies the files to `frontend/dist/fonts/`, so no
separate FastAPI static mount is needed for them.

```bash
cd frontend && npm install   # Install frontend dependencies (first time only)
npm run dev                  # Vite dev server (proxies /api, /login, /logout to :5093 — run support_planner.py too)
npm run build                # Production build -> frontend/dist/, served by FastAPI at /react-assets/*
```

The login page is a plain логин+пароль form (no user picker, no public user-listing
endpoint) — `POST /login` takes `login`/`password` form fields, looks the user up by
`users.login` (`db.get_user_auth_by_login`), and verifies the password hash. `POST /login`
returns JSON (`{success: true}` / `{"error": "..."}`) instead of a redirect or a re-rendered Jinja
page, matching the rest of the app's `/api/*` convention — the React login page does the
`window.location.href = '/planning'` navigation itself on success.

`requirements.txt` currently lists `fastapi`, `uvicorn[standard]`, `pydantic`, `starlette`, `python-multipart`,
`requests`, `python-dotenv`, `urllib3`. **Known gap:** the login feature also needs `itsdangerous` (used
internally by `starlette.middleware.sessions.SessionMiddleware` to sign the session cookie) — it isn't declared
in `requirements.txt`, so a fresh `pip install -r requirements.txt` will raise `AssertionError` on first login
unless it's installed separately (it's a transitive dep of some `starlette`/`fastapi` extras, but not guaranteed).

**SSL/TLS via Vault (`ssl_context.py`):** on startup, `support_planner.py`'s `__main__` block calls `get_cert()`,
which authenticates to a HashiCorp Vault instance via AppRole (`VAULT_ADDR`, `VAULT_TENANT`, `VAULT_KV_PATH`,
`ROLE_ID`, `SECRET_ID` env vars — loaded from `.env` via `python-dotenv`), pulls a `portal_chain`/`portal_key`
cert pair out of the KV secret, and writes them to a temp dir (cleaned up at exit via `atexit`). If any of that
fails, `get_cert()` swallows the exception, prints it, and returns `(None, None)` — `uvicorn.run(...)` then falls
back to plain HTTP automatically. So a missing/misconfigured Vault setup degrades to HTTP locally rather than
crashing; only a real deployment needs the Vault env vars populated.

`run.sh` / `check.sh` are production launch helpers (used via cron/nohup on the deploy host): `check.sh` checks if
`python3 support_planner.py` is already running and, if not, starts `run.sh` in the background, logging to
`support-team-planner.log`.

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
  `UserIn`, `MyPasswordIn`, `FreezeDayIn`, `FreezeDayMonthIn`, `TaskStatusIn`, `TaskReorderIn`, `TaskPriorityIn`).
  API errors return `JSONResponse({"error": "..."}, status_code=...)`. Route handlers use sync `def` (not
  `async def`) since DB calls are blocking — FastAPI runs them in a thread pool. `VALID_TASK_TRANSITIONS` here
  must stay in sync with the copy in `frontend/src/pages/PlanningPage.tsx`.
    - **Auth middleware ordering gotcha:** `require_login` (an `@app.middleware('http')` function) is registered
      *before* `app.add_middleware(SessionMiddleware, ...)` in the file, and this order is load-bearing, not incidental.
      Starlette's `add_middleware()` prepends to the middleware stack, so whichever middleware is added *last* runs
      *first* on an incoming request. `require_login` reads `request.session`, which only exists once
      `SessionMiddleware` has run — so `SessionMiddleware` must end up as the outer/first-executed layer, which means it
      must be the *last* one registered. Swapping this order reintroduces
      `AssertionError: SessionMiddleware must be installed to access request.session`. `_PUBLIC_PATHS` (`/login`,
      `/logout`) plus anything under `/react-assets/` bypass the login check
      entirely; every other route (including `/docs`/`/openapi.json`) requires a session. Beyond the session check,
      `require_login` also enforces role: it reads `role` fresh from the DB on every request (not from the session,
      so a role change takes effect without re-login), stores it on `request.state.role`, and compares it against
      `_required_rank(method, path)` — a 403 JSON error for `/api/*`, a redirect to `/planning` for pages. `GET`
      requests are always allowed at any role; `/settings` requires `editor`+; `/api/users` mutations require
      `admin`; `/api/teams`, `/api/freeze-days`, `/api/blocks`, `/api/block-templates` mutations require `editor`+;
      everything else (including task/assignment mutations) only requires being logged in (`user`+) at the
      middleware level — but see the route-level `user` restrictions below, which go further than the prefix
      tables can express.
    - **Route-level `user`-role restrictions (on top of the middleware):** a handful of handlers additionally check
      `request.state.role == 'user'` themselves, since these rules aren't expressible as a path-prefix rank: a
      plain `user` can create/edit an assignment only while its status is (or would become) `'new'`
      (`save_assignment_api`), can't delete an assignment whose status isn't `'new'` (`delete_assignment_api`),
      can't delete a task that has any non-`'new'` assignment (`delete_task_api`, via
      `db.task_has_active_assignments`), and is blocked outright from `update_task_status_api` (task status
      changes require `editor`+). In short: `user` can freely touch things that haven't progressed past `new`,
      but can't touch anything once it's been planned/executed.
- **`auth.py`** — password hashing only (`hash_password`/`verify_password`, stdlib `hashlib.pbkdf2_hmac` + `secrets`,
  self-describing `pbkdf2_sha256$<iterations>$<salt>$<hash>` format, no external crypto dependency). No JWT — role
  authorization itself lives in `support_planner.py`'s `require_login` middleware (see above), not here.
- **`db/` package** — DAO layer, SQLite-only (the old Postgres backend has been removed):
    - `db/__init__.py` — all DAO functions (teams, blocks, block templates, users, freeze days, tasks, task
      dependencies, assignments, statistics, change history), each wrapped in `@with_db_connection`, which handles
      connection lifecycle, commit, and error handling. The first parameter (`conn`) is injected by the decorator —
      callers do not pass it. It accepts `default_return`, `raise_on_error`, and `commit_on_success` for fine-grained
      control per function. The module-level `_backend: DBBackend = SQLiteBackend()` is hardcoded (no more
      backend-swap story); `init_db()` runs on import.
        - Mutating functions on tasks/assignments (`create_or_update_task`, `update_task_status`, `delete_task`,
          `create_or_update_assignment`, `delete_assignment`, `delete_user`) all accept a trailing optional
          `changed_by=None` kwarg — the acting user's id, threaded from the route layer via
          `request.session.get('user_id')`. Each of these diffs old vs. new values and writes one `task_history`/
          `assignment_history` row per changed field (or one summary row for create/delete), via the internal (non-
          `@with_db_connection`) helpers `_record_task_history`/`_record_assignment_history`, so the history insert
          commits atomically with the mutation itself.
        - `delete_task`/`delete_assignment` are **soft deletes** (`UPDATE ... SET is_deleted = 1`), not physical
          `DELETE`s — see Database Schema below for why. `delete_user` is a real physical delete (users aren't
          soft-deleted), and it nulls out any `assignments.user_id` pointing at the deleted user at the app level
          (there's no `ON DELETE SET NULL` FK for `assignments.user_id`), recording an `assignment_history` row
          for each affected assignment. The seeded bootstrap admin can't be deleted (`_is_bootstrap_admin` guard).
        - Read side: `get_assignment_history` (+ `get_assignment_history_count`), and
          `get_task_full_history` (+ `get_task_full_history_count`) — the "full" variant `UNION ALL`s `task_history`
          with `assignment_history` filtered by `task_id` (not `assignment_id`), sorted by `changed_at DESC`, so a
          task's combined timeline still shows history for assignments that have since been deleted.
    - `db/backend.py` — `DBBackend` ABC defining the interface a backend must implement (`connect`, `setup_connection`,
      `last_insert_id`, `db_error`, `duplicate_error`, `init_schema`). `SQLiteBackend` is the only implementation
      left, but the ABC boundary is still there if a second backend is ever added back.
    - `db/sqlite.py` — `SQLiteBackend`, the only backend. Owns the canonical schema (`_SCHEMA`) and a custom
      `fuzzy_word_in(text, word)` SQLite function (sliding-window typo-tolerant substring match) registered via
      `conn.create_function`, used by task search. `init_schema()` runs `_migrate_employees_to_users()` — a
      one-time migration for pre-existing DBs that renames the old `employees` table to `users` (SQLite rewrites
      `REFERENCES employees(...)` to `REFERENCES users(...)` automatically on `ALTER TABLE ... RENAME TO`), rebuilds
      the table to add `is_assignee` if missing (defaulting existing rows to `1`), and re-adds the `login` unique
      index. This is how a DB created before the `employees`→`users` rename gets migrated forward; the pre-rename
      `ALTER TABLE employees ADD COLUMN login TEXT` step (from the earlier логин/пароль login feature) still runs
      first, wrapped in try/except since SQLite has no `IF NOT EXISTS` for that.
- **`utils.py`** — Single helper: `format_user_name()` for "Фамилия И.О." formatting.

`plugins/` and part of `tests/` currently contain only stale, untracked `__pycache__` bytecode with no matching
`.py` source on disk — leftover cruft from past work, not live functionality. Don't rely on anything in either
directory being real without first checking whether the source file actually exists.

Frontend is React + TypeScript + Vite (antd v6, TanStack Query, React Router), built to `frontend/dist/` and served
statically. `frontend/src/` layout:

- `pages/` — one component per route: `LoginPage`, `PlanningPage`, `StatisticsPage`, `JournalPage`, `SettingsPage`.
  `pages/planning/` holds Planning-specific pieces split out for size:
    - `TaskModal.tsx` / `AssignmentModal.tsx` — CRUD modals, each embedding a `HistoryPanel` (see Domain Concepts
      below) and a footer toggle button to show/hide it. `AssignmentModal.tsx`'s assignee dropdown filters
      `users` to `is_assignee === true`, but keeps an already-assigned user selectable on that record even if their
      flag was later unset, so editing an existing assignment never looks broken.
    - `HistoryPanel.tsx` — collapsible paginated history list + `useHistoryToggle` (resets closed, or auto-opens,
      every time the owning modal transitions to open) shared by both modals.
    - `useAssignmentDrag.ts` — custom mouse-event-driven drag-and-drop for rescheduling an assignment to a
      different date on the grid (cloned floating ghost clamped to the scrollable area, edge auto-scroll,
      `elementFromPoint`-based occupied-cell detection). Deliberately not built on a drag-and-drop library
      (dnd-kit was the original plan) — a raw port of the original vanilla-JS `setupAssignmentDrag` behavior was a
      better fit than rect-based collision detection against antd `Table`'s sticky-column DOM.
    - `useTaskRowDrag.ts` — same style of hand-rolled drag-and-drop, for reordering task rows (priority — see
      Domain Concepts below) instead of assignment cells. Both this hook and `useAssignmentDrag.ts` guard
      `if (e.button !== 0) return;` so dragging only starts on a left-click, not e.g. a right-click that's meant
      to open the context menu.
- `components/` — shared UI: `AppShell`/`AuthenticatedLayout` (sidebar, role-gated nav via `GET /api/me`,
  all nav clicks are plain client-side `navigate()` — every route is React now, so there's no split between
  migrated/legacy paths), `MyAccountModal.tsx` (self-service login/password change, see Domain Concepts),
  `planningBadges.tsx` (status/dependency/schedule badges shared across
  Planning and Journal), `StatTile.tsx`.
- `hooks/` — one thin TanStack Query wrapper per data domain: `usePlanningData.ts`, `useSettingsData.ts`,
  `useTeams.ts`, `useMe.ts`, `useUserNames.ts`.
- `lib/` — pure helpers: `apiMutate.ts` (shared POST/PUT/PATCH/DELETE fetch wrapper), `autoSchedule.ts`
  (freeze-day-aware auto-scheduling date math, ported from the original block-template scheduling logic),
  `historyFormat.ts` (change-history field labels/formatting, shared by the Journal page and `HistoryPanel`).
- `theme.ts` — antd `ConfigProvider` tokens (dark/light `ThemeConfig`s), seeded from `@ant-design/colors`'
  official palette rather than hand-picked values, plus the sidebar "chrome" colors.

## Database Schema

SQLite only (`database.db`, gitignored, auto-created); `PRAGMA foreign_keys = ON`. Key relationships:

- `teams` 1→N `tasks` (cascade delete at the schema level, though in practice tasks are soft-deleted — see below)
- `blocks` — named deployment stages (e.g., "ГФ", "Б1"); names stored uppercase
- `block_templates` 1→N `template_blocks` → `blocks`, each with a `schedule_offset` (day shift from the base assignment
  date)
- `teams` N↔N `block_templates` via `team_templates` — a team's allowed templates determine which blocks it can
  auto-schedule against
- `tasks` 1→N `assignments` (cascade delete at the schema level), unique on `(task_id, date)` **where
  `is_deleted = 0`** (a partial unique index — a soft-deleted assignment doesn't block re-creating one on the same
  date)
- `tasks` N↔N `tasks` via `task_dependencies` (`task_id` depends on `depends_on_task_id`), cycle-checked before insert (
  `has_dependency_cycle`, BFS)
- `users` 1→N `assignments` (`assignments.user_id`, nulled out at the app level on user delete — see
  `db.delete_user` above, not a DB-level `ON DELETE SET NULL`). `users` also carries `login` (nullable, unique — a
  user without a login set simply can't log in yet, same as a missing `password_hash`), `password_hash` (nullable,
  same reasoning), `role` (`NOT NULL DEFAULT 'user'`, one of `user`/`editor`/`admin` — see Domain Concepts), and
  `is_assignee` (`NOT NULL DEFAULT 1` — whether this user shows up in assignment-picker dropdowns; a login-only
  account like the bootstrap admin is seeded with `is_assignee = 0`)
- **Soft deletes:** `tasks.is_deleted` / `assignments.is_deleted` (`INTEGER NOT NULL DEFAULT 0`) — tasks and
  assignments are never physically `DELETE`d anymore, only flagged. This is why `task_history` /
  `assignment_history` can now carry real `FOREIGN KEY`s (`ON DELETE CASCADE` to `tasks`/`assignments`, `ON DELETE
  SET NULL` to `users` for `changed_by_user_id`) where the old schema deliberately had none — a soft-deleted row
  never actually disappears, so a cascading FK on it is safe, and it's what makes an audit row for a "deleted" task
  still resolvable. `assignment_history` also denormalizes `task_id` and `date` so a task's history view still
  makes sense for assignments that are (soft-)deleted.

Note: `team_blocks` (a legacy flat per-team block table) is created then immediately `DROP TABLE`d by
`SQLiteBackend.init_schema()` — it has been fully superseded by `blocks` / `block_templates` / `team_templates`, kept
only as a migration step for existing DBs.

## Domain Concepts

Two separate status machines coexist — do not confuse them:

- **Assignment statuses** (`assignments.status`): `new` → `planned` → `success` | `rollback`. Assignments also
  still carry a legacy `is_psi` column (ПСИ) in the schema and in `assignment_history`/`historyFormat.ts` labels
  for old records, but it's no longer settable through `AssignmentIn` — new assignments can't set it.
- **Task statuses** (`tasks.task_status`): `new` → `done` | `cancelled` (the old intermediate `ready`/
  `in_progress` states were removed — a one-time migration folds any existing `ready`/`in_progress` rows back to
  `new`). Valid transitions are enforced in both `support_planner.py:VALID_TASK_TRANSITIONS` and
  `frontend/src/pages/PlanningPage.tsx:VALID_TASK_TRANSITIONS` — keep them in
  sync (currently just `{'new': {'done', 'cancelled'}}`). Tasks in terminal states (`done`, `cancelled`) block all
  assignment/task edits. Changing task status requires `editor`+ (see the route-level restrictions above) — a
  plain `user` never sees these transitions offered in the UI (`PlanningPage.tsx` short-circuits to an empty
  transitions list when `isUser`).
- **Priority**: `tasks.priority` — an integer, higher = more important; the sole, fully-manual sort key for a
  team's task list (`ORDER BY priority DESC, id`; task status no longer affects order). New tasks are appended to
  the end (`MIN(priority) - _PRIORITY_GAP`). Reordered via drag-and-drop within the currently loaded page
  (`PATCH /api/tasks/{team_id}/reorder`, `db.reorder_team_tasks` — permutes only the already-owned priority values
  of that page's tasks, so it can never encroach on another page's range, driven by `useTaskRowDrag.ts` — see
  above) or via a right-click context menu's "move to start/end of the whole team's list"
  (`PATCH /api/task/{task_id}/priority`, `db.move_task_to_edge`).
- **Task dependencies**: arbitrary DAG between tasks within a team; cycle creation is rejected at the API level (
  `POST /api/task` returns 400 if `has_dependency_cycle` detects one)
- **Freeze days**: dates when no changes are deployed; can be added individually, as ranges, or by full-month
  replacement (`set_freeze_days_for_month`)
- **Blocks / block templates**: a block is a named deployment stage with a `schedule_offset`; block templates group
  blocks together with offsets; teams are assigned a set of allowed templates, which drives auto-scheduling across
  blocks for that team
- **Fuzzy search**: `GET /api/tasks/{team_id}?search=` matches each search word against task name/description with up
  to ~1 typo per 7 characters, via the custom `fuzzy_word_in` SQLite function
- **Active assignments**: assignment statuses `new` or `planned` on tasks not in terminal states, served by
  `/api/active-assignments/{team_id}` (team_id=0 for all teams)
- **Authentication & roles**: per-user login via `GET/POST /login` and `POST /logout`, authenticating by
  `login`+password (`db.get_user_auth_by_login`) rather than by picking a user from a list — `login` is
  a separate, nullable, unique column on `users` (independent of `last_name`/`first_name`/`middle_name`), set
  via the Settings user modal same as the password is. Plus a three-tier role
  system — `users.role` is `user` < `editor` < `admin` (each rank includes the ones below it), enforced by
  `require_login` (see above) via `_ROLE_RANK`/`_required_rank`/`_VALID_ROLES` in `support_planner.py`. In short:
  any logged-in user can read everything and create/edit tasks and assignments up to `status: 'new'` (see the
  route-level restrictions above); `editor`+ additionally gets the whole `/settings` page, team/freeze-day/
  block/block-template mutations, task status changes, and editing/deleting assignments past `new`; only `admin`
  can create, edit, or delete other users (including resetting their password/login, changing their role, or
  toggling `is_assignee`) — `GET /api/users` itself stays open to every role since the planner's assignee
  dropdowns need it. `GET /api/me` exposes the current user + role as JSON for the React nav
  (`AuthenticatedLayout`/`AppShell` role-gate the Settings nav item on `role === 'admin' || role === 'editor'`,
  and also format the current user's "Фамилия И.О." next to the sidebar's "Выйти" button via `formatDisplayName`
  from `useUserNames.ts`). That name label is itself a button (`frontend/src/components/MyAccountModal.tsx`,
  opened via `AppShell`'s `onOpenProfile` prop) letting **any** logged-in user change their own `login`/password
  via `PUT /api/me` — unlike `/api/users` (admin-only, can edit anyone), this endpoint isn't in
  `_ADMIN_ONLY_API_PREFIXES`/`_EDITOR_API_PREFIXES` so it defaults to `user`+, and always acts on
  `request.session['user_id']` rather than a path param, so it can only ever touch the caller's own row; it never
  touches ФИО/role (`db.update_own_credentials`, the same login/password-only update the bootstrap-admin branch of
  `db.update_user` uses, factored into `_update_login_and_password`). The whole app (pages and `/api/*`) sits
  behind `require_login` in `support_planner.py` except `/login`, `/logout`, and `/react-assets/*` (the built
  React bundle itself must be loadable before the user is authenticated — see the React migration note above).
  There's no self-service signup, but there is a bootstrap account: `SQLiteBackend.init_schema()` seeds a `users`
  row named `Администратор` (empty first/middle name, role `admin`, `is_assignee = 0` since it's a system account
  rather than a support engineer) with login `admin` and password `q12345678` via `INSERT OR IGNORE`, on every
  startup — additionally backfills `login = 'admin'` on that row for pre-existing DBs where `INSERT OR IGNORE` is
  a no-op (ФИО already matches) but `login` is still `NULL`, guarded by `login IS NULL` so a login already changed
  via Settings is never overwritten. This relies on `middle_name` being `''` rather than `NULL` in that seed row —
  `UNIQUE(last_name, first_name, middle_name)` never treats two `NULL`s as equal, so a `NULL` `middle_name` would
  silently defeat the `OR IGNORE` dedup and create a fresh duplicate admin row on every restart. This bootstrap
  admin also can't be deleted via `DELETE /api/users/{id}` (`_is_bootstrap_admin` guard in `db.delete_user`). Any
  other brand-new `users` row still starts with `login = NULL`/`password_hash = NULL` and can't log in until both
  are set for it via the Settings user modal (which itself requires being logged in as an `admin`).
- **Change history**: every create/update/delete on a task or assignment is logged (see `task_history`/
  `assignment_history` above), attributed to whichever user is in the current session (`changed_by`, nullable —
  history rows from before the login feature existed, or written with no session, have `changed_by_user_id = NULL`).
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
  drag-and-drop ghost/highlight classes used by `useAssignmentDrag.ts`/`useTaskRowDrag.ts`, since that ghost
  element is a raw DOM clone outside React's render tree and needs real CSS classes, not inline styles)
