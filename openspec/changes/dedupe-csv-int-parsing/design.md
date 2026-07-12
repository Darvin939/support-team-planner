## Context

Four query-param handlers each inline the same `x.split(',')` + `int()` + empty-check logic:
`get_assignments_api` (task_ids), `get_team_deps` (task_ids), `get_active_tasks_list` (include_ids),
`get_active_assignments_api` (team_ids).

## Goals / Non-Goals

**Goals:** one function, identical behavior (including identical failure mode on non-numeric input).

**Non-Goals:** adding input validation that doesn't exist today (e.g. graceful handling of `task_ids=abc` — that
already 500s via an unhandled `ValueError`, and this refactor is not the place to change that).

## Decisions

- **Free function `_parse_int_csv(value)`** in `support_planner.py`, next to `_required_rank`/other module-level
  helpers — same rationale as `dedupe-task-lock-check`'s `_task_is_locked`.

## Risks / Trade-offs

- [Risk] None — byte-for-byte-equivalent extraction.
