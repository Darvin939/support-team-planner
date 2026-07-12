## 1. Backend fix

- [x] 1.1 In `save_task_api` (`support_planner.py`), when `data.task_id` is truthy, call `db.task_exists(data.task_id)`
      before the existing terminal-status check; return `JSONResponse({'error': 'Задача не найдена'}, status_code=404)`
      if it's falsy.
- [x] 1.2 Confirm the existing terminal-status block (`db.get_task_status`) still runs only after the existence
      check passes, so it never needs to handle a `None` row.

## 2. Verification

- [x] 2.1 Manual check: edit an existing task → still saves successfully (200).
- [x] 2.2 Manual check: delete a task, then replay a save with its old `task_id` (e.g. via `/docs` or curl) →
      expect 404, and confirm no new row was created in `tasks`.
- [x] 2.3 Manual check: create a new task (`task_id` omitted) → still creates as before (200).
