# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Support Team Planner — a FastAPI web app (Russian UI) for scheduling support team tasks. Teams have tasks with criticality levels; tasks get assigned to dates with employees, statuses, and optional deployment blocks (with dependency tracking and fuzzy search).

## Commands

```bash
pip install -r requirements.txt   # Install dependencies (fastapi, uvicorn, jinja2, pydantic; psycopg2-binary only needed for PostgresBackend)
python support_planner.py         # Run dev server on http://localhost:5093
python -m pytest tests/ -v        # Run tests (currently only db/postgres.py unit tests + a live-PG integration test, auto-skipped if no PG server)
```

`run.sh` / `check.sh` are production launch helpers (used via cron/nohup on the deploy host): `check.sh` checks if `python3 support_planner.py` is already running and, if not, starts `run.sh` in the background, logging to `support-team-planner.log`. No linter or formatter is configured.

## Architecture

FastAPI app split across a handful of modules:

- **`support_planner.py`** — all FastAPI routes and API endpoints (this is the app entrypoint — there is no `app.py`). `/` redirects to `/planning`. Pages: `/planning`, `/planning/{team_id}`, `/settings`, `/statistics`. API under `/api/`. Request bodies use Pydantic models (`AssignmentIn`, `TaskIn`, `TeamIn`, `BlockIn`, `BlockTemplateIn`, `EmployeeIn`, `FreezeDayIn`, `FreezeDayMonthIn`, `TaskStatusIn`). API errors return `JSONResponse({"error": "..."}, status_code=...)`. Route handlers use sync `def` (not `async def`) since DB calls are blocking — FastAPI runs them in a thread pool. `VALID_TASK_TRANSITIONS` here must stay in sync with the copy in `planning.js`.
- **`db/` package** — DAO layer, swappable between SQLite and PostgreSQL:
  - `db/__init__.py` — all DAO functions (teams, blocks, block templates, employees, freeze days, tasks, task dependencies, assignments, statistics), each wrapped in `@with_db_connection`, which handles connection lifecycle, commit, and error handling. The first parameter (`conn`) is injected by the decorator — callers do not pass it. It accepts `default_return`, `raise_on_error`, and `commit_on_success` for fine-grained control per function. The module-level `_backend: DBBackend = SQLiteBackend()` selects the active backend; `init_db()` runs on import.
  - `db/backend.py` — `DBBackend` ABC defining the interface a backend must implement (`connect`, `setup_connection`, `last_insert_id`, `db_error`, `duplicate_error`, `init_schema`).
  - `db/sqlite.py` — `SQLiteBackend`, the default. Owns the canonical schema (`_SCHEMA`) and a custom `fuzzy_word_in(text, word)` SQLite function (sliding-window typo-tolerant substring match) registered via `conn.create_function`, used by task search.
  - `db/postgres.py` — `PostgresBackend`, opt-in alternative (switch by changing `_backend` in `db/__init__.py`). Wraps `psycopg2` connections/cursors to mimic the `sqlite3` interface (`conn.execute(...)` returning a fetchone/fetchall-capable cursor), translates `?` placeholders to `%s` and `INSERT OR IGNORE` to `... ON CONFLICT DO NOTHING` via `_adapt_sql`, and reimplements `fuzzy_word_in` as a PL/pgSQL function. Keep schema and query dialect changes mirrored between the two backends.
- **`utils.py`** — Single helper: `format_employee_name()` for "Фамилия И.О." formatting.

Frontend is vanilla JS + Jinja2 templates inheriting from `base.html` (blocks: `title`, `content`, `scripts`). Static files mounted at `/static`. JS is split per page:

- `static/js/script.js` — shared utilities: dropdown toggles, URL linkification, modal close handlers, `clampDateRange(fromId, toId)` for 60-day max period enforcement, localStorage helpers (`saveTeamId`, `getSavedTeamId`, `saveDateRange`, `getSavedDateRange`) for persisting selected team and date filters across pages
- `static/js/planning.js` — planning grid with drag-scroll, auto-scheduling, assignment CRUD, today-scroll, today counters; also holds the `VALID_TASK_TRANSITIONS` copy that must match `support_planner.py`
- `static/js/settings.js` — teams/employees/blocks/block-templates/freeze-days management via modals
- `static/js/statistics.js` — active assignments tables (period + today) with counters

## Database Schema

SQLite by default (`database.db`, gitignored, auto-created); PostgreSQL is a drop-in alternative via `PostgresBackend`. Foreign keys are enforced (`PRAGMA foreign_keys = ON` for SQLite; on by default in Postgres). Key relationships:

- `teams` 1→N `tasks` (cascade delete)
- `blocks` — named deployment stages (e.g., "ГФ", "Б1"); names stored uppercase
- `block_templates` 1→N `template_blocks` → `blocks`, each with a `schedule_offset` (day shift from the base assignment date)
- `teams` N↔N `block_templates` via `team_templates` — a team's allowed templates determine which blocks it can auto-schedule against
- `tasks` 1→N `assignments` (cascade delete), unique on `(task_id, date)`
- `tasks` N↔N `tasks` via `task_dependencies` (`task_id` depends on `depends_on_task_id`), cycle-checked before insert (`has_dependency_cycle`, BFS)
- `employees` 1→N `assignments` (set NULL on employee delete, not cascade)

Note: `team_blocks` (a legacy flat per-team block table) is created then immediately `DROP TABLE`d by `SQLiteBackend.init_schema()` — it has been fully superseded by `blocks` / `block_templates` / `team_templates`, kept only as a migration step for existing DBs.

## Domain Concepts

Two separate status machines coexist — do not confuse them:

- **Assignment statuses** (`assignments.status`): `new` → `planned` → `success` | `rollback`. Saving an assignment with status `planned` auto-advances the parent task to `in_progress` via `maybe_advance_task_to_in_progress()`. Assignments also carry an `is_psi` boolean marker (ПСИ).
- **Task statuses** (`tasks.task_status`): `new` → `ready` → `in_progress` → `done` | `cancelled`. Valid transitions are enforced in both `support_planner.py:VALID_TASK_TRANSITIONS` and `planning.js:VALID_TASK_TRANSITIONS` — keep them in sync. Tasks in terminal states (`done`, `cancelled`) block all assignment/task edits.
- **Criticality**: `high`, `medium`, `low` (sorted in that order in queries; tasks list is sorted criticality-first, then task_status)
- **Task dependencies**: arbitrary DAG between tasks within a team; cycle creation is rejected at the API level (`POST /api/task` returns 400 if `has_dependency_cycle` detects one)
- **Freeze days**: dates when no changes are deployed; can be added individually, as ranges, or by full-month replacement (`set_freeze_days_for_month`)
- **Blocks / block templates**: a block is a named deployment stage with a `schedule_offset`; block templates group blocks together with offsets; teams are assigned a set of allowed templates, which drives auto-scheduling across blocks for that team
- **Fuzzy search**: `GET /api/tasks/{team_id}?search=` matches each search word against task name/description with up to ~1 typo per 7 characters, via the custom `fuzzy_word_in` SQL function (implemented per-backend — Python in SQLite, PL/pgSQL in Postgres)
- **Active assignments**: assignment statuses `new` or `planned` on tasks not in terminal states, served by `/api/active-assignments/{team_id}` (team_id=0 for all teams)

## Conventions

- Commit messages are in Russian
- API errors return `{"error": "..."}` with HTTP 400/404
- `@formatter:off` / `@formatter:on` markers are used for IDEA formatting control in SQL blocks (`db/__init__.py`, `db/sqlite.py`)
- Date inputs are clamped to 2000–2099 range (`min`/`max` attributes) and max period of 60 days (`clampDateRange` in script.js)
- Selected team and date filters persist in localStorage across planning and statistics pages
- Use `localDateStr(new Date())` (not `toISOString()`) for today's date in JS to avoid UTC timezone shift
- `GET /api/tasks/{team_id}` supports `offset`, `limit`, `search`, and `show_completed` query params; default page size is 20
- `templates/login.html` exists but has no route in `support_planner.py` — it's an unused draft
- When adding/changing a query, mirror the dialect difference in both `db/sqlite.py` and `db/postgres.py` if PostgresBackend support matters (placeholder style, `INSERT OR IGNORE`, etc. — see `_adapt_sql` in `db/postgres.py`)
