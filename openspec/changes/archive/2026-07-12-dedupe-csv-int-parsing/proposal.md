## Why

The expression `[int(x) for x in s.split(',') if x.strip()] if s else None` — parsing a comma-separated query
param into an optional list of ints — is repeated four times in `support_planner.py`: `task_ids` in
`get_assignments_api`, `task_ids` in `get_team_deps`, `include_ids` in `get_active_tasks_list`, and `team_ids` in
`get_active_assignments_api`. Same logic, four copies.

## What Changes

- Add a small helper `_parse_int_csv(value: Optional[str]) -> Optional[List[int]]` in `support_planner.py`.
- Replace all four call sites with `_parse_int_csv(...)`.

## Capabilities

### New Capabilities
- `csv-id-query-params`: shared parsing contract for comma-separated id query params (`task_ids`, `include_ids`,
  `team_ids`) across the four affected endpoints.

### Modified Capabilities
- (none)

## Impact

- `support_planner.py`: new private helper; four query-param parsing call sites updated to use it.
