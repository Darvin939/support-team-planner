# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Support Team Planner — a FastAPI web app (Russian UI) for scheduling support team tasks. Teams have tasks with criticality levels; tasks get assigned to dates with employees, statuses, and optional deployment blocks.

## Commands

```bash
pip install -r requirements.txt   # Install dependencies (fastapi, uvicorn, jinja2)
python app.py                     # Run dev server on http://localhost:5000
```

No test suite, linter, or formatter is configured.

## Architecture

Monolithic FastAPI app with three Python files:

- **`app.py`** — FastAPI routes: page renders (`/`, `/planning/{team_id}`, `/settings`, `/statistics`) and REST API endpoints under `/api/`. Request bodies use Pydantic models. API errors return `JSONResponse({"error": "..."}, status_code=...)`. Route handlers use sync `def` (not `async def`) since DB calls are blocking — FastAPI runs them in a thread pool.
- **`database.py`** — SQLite DAO layer. Every DB function uses the `@with_db_connection` decorator which handles connection lifecycle, commit, and error handling. The first parameter (`conn`) is injected by the decorator — callers do not pass it. DB is auto-created on import via `init_db()` / `ensure_schema()`.
- **`utils.py`** — Single helper: `format_employee_name()` for "Фамилия И.О." formatting.

Frontend is vanilla JS + Jinja2 templates inheriting from `base.html` (blocks: `title`, `content`, `scripts`). Static files mounted at `/static`. JS is split per page:

- `static/js/script.js` — shared utilities (dropdown toggles, URL linkification)
- `static/js/planning.js` — planning grid with drag-scroll, auto-scheduling, assignment CRUD
- `static/js/settings.js` — teams/employees/freeze-days management modals
- `static/js/statistics.js` — statistics dashboard data loading

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
- **Team blocks**: named deployment stages (e.g., "ГФ", "Б1") with a day offset from the base assignment date, used for auto-scheduling across blocks

## Conventions

- Commit messages are in Russian
- API errors return `{'error': '...'}` with HTTP 400/404
- `@formatter:off` / `@formatter:on` markers are used for IDEA formatting control in SQL blocks
- The `@with_db_connection` decorator accepts `default_return`, `raise_on_error`, and `commit_on_success` parameters for fine-grained control per function
