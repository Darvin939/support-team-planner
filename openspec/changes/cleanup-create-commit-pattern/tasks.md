## 1. Implementation

- [x] 1.1 `create_team`: removed `conn.commit()` and changed `@with_db_connection(commit_on_success=False)` to
      `@with_db_connection()`.
- [x] 1.2 `create_segment`: same removal.
- [x] 1.3 `create_block`: same removal.
- [x] 1.4 `create_template`: same removal.
- [x] 1.5 `create_or_update_task`: removed both `conn.commit()` calls (one in the `existing` branch, one in the
      create branch) and the `commit_on_success=False` override.

## 2. Verification

- [x] 2.1 Manual check (via `starlette.testclient.TestClient` against the real app): created a team, segment,
      block, block template, and task — each was immediately visible via its corresponding `GET` right after
      creation, confirming the decorator's own `commit_on_success=True` commits correctly without the removed
      manual calls.
- [x] 2.2 Manual check: edited the just-created task (`existing` branch of `create_or_update_task`) — the new
      name was immediately visible via `GET /api/tasks/{team_id}`.
- [x] 2.3 Confirmed `grep -n "conn.commit()" db/__init__.py` no longer shows any of the five target call sites —
      only the decorator's own commit (`with_db_connection`'s wrapper) and `create_user`'s manual commit remain,
      the latter correctly out of scope for this change (not one of the 5 functions in the proposal).

**Side note from cleanup**: while cleaning up test data created for 2.1/2.2, deleting the test segment failed
(400, `IntegrityConstraintError`) while a *soft-deleted* test task still referenced it — soft delete doesn't
clear `tasks.segment_id`, so the FK reference persists until the row is hard-deleted (e.g. via a team's `ON
DELETE CASCADE`). This is `api-error-handling`'s segment-delete protection working exactly as designed, not a
bug introduced by this change — mentioned here only because it required an extra manual cleanup step (delete the
team first, which cascades away the task, then the now-unreferenced segment).
