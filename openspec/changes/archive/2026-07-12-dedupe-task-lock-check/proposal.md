## Why

The expression `task['task_status'] in ('done', 'cancelled') or task['is_deleted']` — "is this task locked from
further edits?" — appears verbatim four times in `support_planner.py` (`save_assignment_api`,
`delete_assignment_api`, `save_task_api`, `delete_task_api`), each paired with the same error message "Нельзя
изменять/удалить завершённую или отменённую задачу". Four independent copies mean a future change to the locking
rule (e.g. adding a new terminal status) requires four synchronized edits instead of one.

## What Changes

- Add a small helper `_task_is_locked(task) -> bool` in `support_planner.py` encapsulating the condition.
- Replace all four call sites with `_task_is_locked(task)`. Error message text at each call site is unchanged
  (they differ slightly — "изменять" vs "удалить" — only the boolean condition is deduplicated, not the message).

## Capabilities

### New Capabilities
- `task-edit-locking`: baseline behavior contract for "a task in a terminal status, or soft-deleted, blocks
  further task/assignment edits" — documents what the four call sites already enforce, now from one shared
  helper.

### Modified Capabilities
- (none)

## Impact

- `support_planner.py`: new private helper function; four call sites updated to use it.
- No API/behavior change — this is a pure refactor verified by the fact that all four call sites already computed
  the identical boolean expression.
