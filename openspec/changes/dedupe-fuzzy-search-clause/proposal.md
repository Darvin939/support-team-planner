## Why

`db/__init__.py` builds the fuzzy-search `WHERE` clause and its parameter list with the same logic in three
places — `get_tasks_by_team`, `get_tasks_count_by_team`, `get_active_tasks_flat` — each splitting `search` into
words and building `(fuzzy_word_in(name, ?) OR fuzzy_word_in(description, ?)) AND ...` per word, with only the
column qualification differing (`tasks.name`/`tasks.description` in `get_tasks_by_team` since it joins
`segments`, vs. bare `name`/`description` in the other two).

## What Changes

- Add a private helper `_fuzzy_search_clause(search, name_col='name', description_col='description')` in
  `db/__init__.py` returning `(clause_sql, params)` — an empty string and `[]` when `search` is falsy.
- Replace the duplicated word-splitting/clause-building block in all three functions with a call to this helper,
  passing qualified column names where needed (`get_tasks_by_team` passes `tasks.name`/`tasks.description`).

## Capabilities

### New Capabilities
- `task-fuzzy-search`: shared clause-building contract for fuzzy task search across the three affected DAO
  functions (per-word AND of OR-matched name/description, ~1 typo per 7 characters).

### Modified Capabilities
- (none)

## Impact

- `db/__init__.py`: new private helper; three functions' search-clause-building blocks replaced with calls to it.
- No behavior change — fuzzy search results are identical before/after (verified by the SQL fragment being
  identical, only its construction is centralized).
