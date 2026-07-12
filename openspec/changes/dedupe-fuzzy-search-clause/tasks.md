## 1. Implementation

- [x] 1.1 Added `_fuzzy_search_clause(search, name_col='name', description_col='description')` to `db/__init__.py`,
      returning `("", [])` when `search` is falsy, else `(f"AND ({word_clauses})", params)` matching the original
      inline logic exactly.
- [x] 1.2 Updated `get_tasks_by_team` to call `_fuzzy_search_clause(search, 'tasks.name', 'tasks.description')`,
      merging its params into `params` at the same position as before (right after `team_id`, before `task_id`).
- [x] 1.3 Updated `get_tasks_count_by_team` to call `_fuzzy_search_clause(search)` (bare column names).
- [x] 1.4 Updated `get_active_tasks_flat` to call `_fuzzy_search_clause(search)` (bare column names).

## 2. Verification

- [x] 2.1 Manual check (via `starlette.testclient.TestClient` against the real app): searched tasks by
      "отчёт" (an exact word from seeded task names) → 3 results; searched by "отчт" (one letter dropped,
      a typo) → **also 3 results**, confirming fuzzy typo-tolerance is preserved through the refactor.
- [x] 2.2 Manual check: `GET /api/tasks/1?search=отчёт` returned `total=3` and `len(tasks)=3` — pagination total
      (`get_tasks_count_by_team`) matches the actual row count (`get_tasks_by_team`) for the same search term.
- [x] 2.3 Manual check: `GET /api/tasks/1/active-list?search=отчёт` (the dependency-picker search,
      `get_active_tasks_flat`) returned 3 matches, consistent with the other two functions; a garbage/nonsense
      search term correctly returned 0 results, confirming the search clause is actually filtering (not silently
      matching everything).
