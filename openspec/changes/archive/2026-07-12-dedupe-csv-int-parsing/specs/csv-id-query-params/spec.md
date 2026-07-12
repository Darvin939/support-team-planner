## ADDED Requirements

### Requirement: Comma-separated id query params parse consistently
`task_ids`, `include_ids`, and `team_ids` query parameters SHALL be parsed by one shared function: a comma-split,
non-empty tokens converted to `int`, or `None` when the parameter is absent/empty.

#### Scenario: Absent parameter
- **WHEN** the query param is not provided
- **THEN** the parsed result is `None` (no filtering applied)

#### Scenario: Comma-separated ids
- **WHEN** the query param is `"3,7,12"`
- **THEN** the parsed result is `[3, 7, 12]`

#### Scenario: Trailing/stray commas are tolerated
- **WHEN** the query param is `"3,,7,"`
- **THEN** the parsed result is `[3, 7]` (empty tokens skipped)

#### Scenario: Non-numeric token still fails loudly
- **WHEN** the query param contains a non-numeric token (e.g. `"3,abc"`)
- **THEN** the request fails with an unhandled `ValueError` (500) — unchanged from current behavior, not a
  regression introduced by this refactor
