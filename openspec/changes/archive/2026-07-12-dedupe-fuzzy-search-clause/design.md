## Context

`get_tasks_by_team` (`db/__init__.py:520-563`), `get_tasks_count_by_team` (`566-584`), and `get_active_tasks_flat`
(`980-1023`) each independently do:
```python
words = search.split()
word_clauses = " AND ".join("(fuzzy_word_in(<name_col>, ?) OR fuzzy_word_in(<desc_col>, ?))" for _ in words)
search_clause = f"AND ({word_clauses})"
for word in words:
    params += [word, word]
```
`get_tasks_by_team` uses `tasks.name`/`tasks.description` (it joins `segments`, so columns must be qualified to
avoid ambiguity); the other two use bare `name`/`description` (no join, no ambiguity).

## Goals / Non-Goals

**Goals:** one function producing the exact same SQL fragment + params tuple as each of the three call sites does
today, parameterized by column names.

**Non-Goals:** changing the fuzzy-match algorithm itself (`fuzzy_word_in`, in `db/sqlite.py`) — out of scope,
untouched.

## Decisions

- **Helper returns `(sql_fragment, params_list)` rather than mutating a shared `params` list in place** — keeps
  it a pure function callers compose into their own query/param building, matching the existing style of
  `_active_assignments_where` (also in `db/__init__.py`), which already returns `(where, params)` for a similar
  reason.
- **Column names as parameters, not a fixed default of `tasks.name`** — defaulting to unqualified `name`/
  `description` (matching 2 of 3 call sites) and letting `get_tasks_by_team` pass `tasks.name`/`tasks.description`
  explicitly, since unqualified is the more common case here.

## Risks / Trade-offs

- [Risk] None — this reuses `_active_assignments_where`'s existing `(clause, params)`-tuple convention already
  established in the same file, so it's not introducing a new pattern.
