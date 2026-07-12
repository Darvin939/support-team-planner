## Context

`support_planner.py` has four near-identical guards checking whether a task blocks further edits, each written
inline at the call site:
- `save_assignment_api` (line ~340)
- `delete_assignment_api` (line ~365, via `get_task_status_by_assignment`)
- `save_task_api` (line ~418)
- `delete_task_api` (line ~512)

## Goals / Non-Goals

**Goals:** one function computing the boolean; behavior identical to today at every call site.

**Non-Goals:** unifying the *error messages* (they legitimately differ — "изменять" for saves, "удалить" for
deletes) or the surrounding response-building code — only the condition itself is deduplicated.

## Decisions

- **Plain function, not a method on a row wrapper.** `task` is a `sqlite3.Row` (or `None`), not a class instance,
  so `_task_is_locked(task)` is a free function taking the row, matching the existing style of small private
  helpers in this file (`_required_rank`, `_validate_task_dependency_edit`).
- **Accepts `task` that may be `None`?** No — at all four call sites, the `None`/not-found case is already
  checked separately before this condition runs (e.g. `if not db.task_exists(...)`), so `_task_is_locked` can
  assume a non-`None` row with `task_status`/`is_deleted` keys, matching today's inline expressions which make
  the same assumption.

## Risks / Trade-offs

- [Risk] None — this is a byte-for-byte-equivalent extraction of an existing expression.
