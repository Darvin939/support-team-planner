## Why

`POST /api/task` silently creates a brand-new task (with a new id) when the client submits an edit for a `task_id`
that no longer exists (deleted, or never existed) — instead of returning a 404. The route only checks task status
when `db.get_task_status(task_id)` finds a row; if it doesn't, the check is skipped entirely and
`db.create_or_update_task` falls into its CREATE branch. A user "editing" a stale/deleted task gets an invisible
duplicate rather than a clear error, and there is no way from the client to distinguish this from a normal save.

## What Changes

- `save_task_api` (`support_planner.py`) explicitly verifies a truthy `data.task_id` refers to an existing task
  before calling `db.create_or_update_task`, returning `404 {'error': 'Задача не найдена'}` if it doesn't.
- `db.create_or_update_task`'s own behavior is unchanged: called with `task_id=None` it must keep creating; this
  fix only closes the route-level gap for a truthy-but-nonexistent `task_id`.

## Capabilities

### New Capabilities
- `task-management`: baseline behavior for `POST /api/task` — create when no `task_id` is given, update when it
  refers to an existing non-deleted task, 404 when it refers to a task that doesn't exist. (No `specs/` capability
  currently documents task CRUD behavior, so this proposal establishes the baseline for the one requirement it
  touches rather than modifying an existing spec.)

### Modified Capabilities
- (none — no existing spec covers this yet)

## Impact

- `support_planner.py`: `save_task_api` gains an existence check before the `create_or_update_task` call.
- No DB schema change, no frontend change required (the frontend already surfaces `{'error': ...}` responses from
  failed saves via its existing error-toast handling in `TaskModal.tsx`).
