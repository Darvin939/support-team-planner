## Context

`save_task_api` (`support_planner.py`) currently only guards against editing a *terminal-status* task when
`db.get_task_status(data.task_id)` returns a row. If `task_id` doesn't resolve to any row at all (deleted task,
stale client state, typo'd id), that guard is skipped and `db.create_or_update_task` — which distinguishes
create/update purely by whether `SELECT ... FROM tasks WHERE id = ?` finds a row — falls into its create branch.

## Goals / Non-Goals

**Goals:**
- `POST /api/task` with a `task_id` that doesn't exist (or is soft-deleted) returns `404` instead of creating a
  new task.

**Non-Goals:**
- Changing `create_or_update_task`'s DAO-level contract (it must still create when called with `task_id=None`).
- Touching any other endpoint — this is scoped to `save_task_api` only.

## Decisions

- **Check existence at the route layer, not the DAO layer.** `db.task_exists(task_id)` already does exactly this
  (`SELECT 1 FROM tasks WHERE id = ? AND is_deleted = 0`) and is already used by `save_assignment_api` for the
  same purpose. Reusing it keeps the fix a small, local diff instead of changing `create_or_update_task`'s
  behavior (which other callers may rely on for its create-on-missing-id semantics, even though today the only
  caller is this same route).
- **Order of checks**: existence check first, then the existing terminal-status check (which already assumes the
  row exists). This avoids a redundant second query — `get_task_status` is only called once existence is confirmed.

## Risks / Trade-offs

- [Risk] A legitimate client race (task deleted by another user between page load and save) now surfaces as a
  404 toast instead of silently succeeding as a new task → Mitigation: this is the intended, correct behavior —
  silently creating a duplicate was the actual bug.
