# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Support Team Planner — a FastAPI web app (Russian UI) for scheduling support team tasks. Teams have tasks with criticality levels; tasks get assigned to dates with employees, statuses, and optional deployment blocks.

## Commands

```bash
pip install -r requirements.txt   # Install dependencies (fastapi, uvicorn, jinja2, pydantic)
python app.py                     # Run dev server on http://localhost:5000
```

No test suite, linter, or formatter is configured.

## Architecture

Monolithic FastAPI app with three Python files:

- **`app.py`** — FastAPI routes and API endpoints. `/` redirects to `/planning`. Pages: `/planning`, `/planning/{team_id}`, `/settings`, `/statistics`. API under `/api/`. Request bodies use Pydantic models. API errors return `JSONResponse({"error": "..."}, status_code=...)`. Route handlers use sync `def` (not `async def`) since DB calls are blocking — FastAPI runs them in a thread pool.
- **`database.py`** — SQLite DAO layer. Every DB function uses the `@with_db_connection` decorator which handles connection lifecycle, commit, and error handling. The first parameter (`conn`) is injected by the decorator — callers do not pass it. DB is auto-created on import via `init_db()` / `ensure_schema()`. All queries use explicit column lists (no `SELECT *`).
- **`utils.py`** — Single helper: `format_employee_name()` for "Фамилия И.О." formatting.

Frontend is vanilla JS + Jinja2 templates inheriting from `base.html` (blocks: `title`, `content`, `scripts`). Static files mounted at `/static`. JS is split per page:

- `static/js/script.js` — shared utilities: dropdown toggles, URL linkification, modal close handlers, `clampDateRange(fromId, toId)` for 60-day max period enforcement, localStorage helpers (`saveTeamId`, `getSavedTeamId`, `saveDateRange`, `getSavedDateRange`) for persisting selected team and date filters across pages
- `static/js/planning.js` — planning grid with drag-scroll, auto-scheduling, assignment CRUD, today-scroll, today counters
- `static/js/settings.js` — teams/employees/freeze-days management via modals
- `static/js/statistics.js` — active assignments tables (period + today) with counters

## Database Schema

SQLite (`database.db`, gitignored, auto-created). Foreign keys are enforced (`PRAGMA foreign_keys = ON`). Key relationships:

- `teams` 1→N `tasks` (cascade delete)
- `teams` 1→N `team_blocks` (cascade delete) — deployment blocks with `schedule_offset` (days shift)
- `tasks` 1→N `assignments` (cascade delete), unique on `(task_id, date)`
- `employees` 1→N `assignments` (set NULL on employee delete, not cascade)

## Domain Concepts

- **Statuses**: `new` → `planned` → `success` | `rollback`
- **Criticality**: `high`, `medium`, `low` (sorted in that order in queries)
- **Freeze days**: dates when no changes are deployed; can be added individually or as ranges
- **Team blocks**: named deployment stages (e.g., "ГФ", "Б1") with a day offset from the base assignment date, used for auto-scheduling across blocks. Names are stored uppercase.
- **Active assignments**: assignments with status `new` or `planned`, served by `/api/active-assignments/{team_id}` (team_id=0 for all teams)

## Conventions

- Commit messages are in Russian
- API errors return `{"error": "..."}` with HTTP 400/404
- `@formatter:off` / `@formatter:on` markers are used for IDEA formatting control in SQL blocks
- The `@with_db_connection` decorator accepts `default_return`, `raise_on_error`, and `commit_on_success` parameters for fine-grained control per function
- Date inputs are clamped to 2000–2099 range (`min`/`max` attributes) and max period of 60 days (`clampDateRange` in script.js)
- Selected team and date filters persist in localStorage across planning and statistics pages
- Use `localDateStr(new Date())` (not `toISOString()`) for today's date in JS to avoid UTC timezone shift
