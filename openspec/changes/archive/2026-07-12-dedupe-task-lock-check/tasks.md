## 1. Implementation

- [x] 1.1 Added `def _task_is_locked(task) -> bool: return task['task_status'] in ('done', 'cancelled') or task['is_deleted']`
      near `VALID_TASK_TRANSITIONS` in `support_planner.py`.
- [x] 1.2 Replaced the inline condition in `save_assignment_api` with `_task_is_locked(task)`.
- [x] 1.3 Replaced the inline condition in `delete_assignment_api` with `_task_is_locked(task)`.
- [x] 1.4 Replaced the inline condition in `save_task_api` with `_task_is_locked(task)`.
- [x] 1.5 Replaced the inline condition in `delete_task_api` with `_task_is_locked(task)`.
      Confirmed a 5th, structurally different match (`_validate_task_dependency_edit`'s
      `task['task_status'] in ('done', 'cancelled')` without the `is_deleted` part, which already has its own
      separate `is_deleted` check) is correctly out of scope and was left untouched.

## 2. Verification

- [x] 2.1 Manual check (via `starlette.testclient.TestClient` against the real app, using existing seeded demo
      tasks already in `done`/`cancelled` status — task id 5, `done`): `POST /api/task` (edit), `DELETE
      /api/task/5`, `POST /api/assignment`, and `DELETE /api/assignment/{id}` (on an assignment belonging to task
      5) all returned `400` with the expected error messages, unchanged from before.
- [x] 2.2 Manual check: created a throwaway task (`new` status) via `POST /api/task`, edited it, added an
      assignment, deleted the assignment, then deleted the task itself — every step returned `200`, and the task
      was fully cleaned up (deletable since it never left `new` status), leaving no residue in the shared demo
      database.
