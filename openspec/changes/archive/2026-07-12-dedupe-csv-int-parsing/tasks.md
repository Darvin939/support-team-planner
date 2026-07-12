## 1. Implementation

- [x] 1.1 Added `_parse_int_csv(value: Optional[str]) -> Optional[List[int]]` to `support_planner.py`, next to
      `_task_is_locked`.
- [x] 1.2 Replaced the inline expression in `get_assignments_api` (`task_ids`) with `_parse_int_csv(task_ids)`.
- [x] 1.3 Replaced the inline expression in `get_team_deps` (`task_ids`) with `_parse_int_csv(task_ids)`.
- [x] 1.4 Replaced the inline expression in `get_active_tasks_list` (`include_ids`) with `_parse_int_csv(include_ids)`.
- [x] 1.5 Replaced the inline expression in `get_active_assignments_api` (`team_ids`) with `_parse_int_csv(team_ids)`.

## 2. Verification

- [x] 2.1 Manual check (via `starlette.testclient.TestClient` against the real app): called all four endpoints
      with an `?...ids=1,5` (or `1,2` for teams) filter — each returned a subset whose ids were all within the
      requested set (`assignments`: 2/37, scoped to tasks 1&5; `deps`: 3/31; `active-list`: 3 with
      `limit=1&include_ids=1,5`, matching the documented UNION-with-base-query semantics;
      `active-assignments`: 25/32, scoped to teams 1&2).
- [x] 2.2 Manual check: called all four endpoints with the id param omitted — each returned the full unfiltered
      set, matching the "before filter" counts above.
