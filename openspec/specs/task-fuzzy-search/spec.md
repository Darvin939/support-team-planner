# task-fuzzy-search Specification

## Purpose
TBD - created by archiving change dedupe-fuzzy-search-clause. Update Purpose after archive.
## Requirements
### Requirement: Fuzzy task search clause is built consistently
`get_tasks_by_team`, `get_tasks_count_by_team`, and `get_active_tasks_flat` SHALL build their fuzzy-search `WHERE`
clause via one shared function, requiring every search word to match (via `fuzzy_word_in`, ~1 typo per 7
characters) either the name or the description column.

#### Scenario: Empty search
- **WHEN** `search` is empty/`None`
- **THEN** no search clause is added and all (non-search) rows are eligible

#### Scenario: Multi-word search
- **WHEN** `search` is `"биллинг ошибка"`
- **THEN** only rows where *both* words individually match name-or-description (via fuzzy matching) are returned

#### Scenario: Same results across all three call sites
- **WHEN** the same `search` value and underlying data are used
- **THEN** `get_tasks_by_team`'s search filtering and `get_tasks_count_by_team`'s count agree (a task counted is a
  task returned), and `get_active_tasks_flat`'s search filtering uses the identical matching rule

