## Context

`with_db_connection`'s wrapper (`db/__init__.py:19-38`):
```python
result = func(conn, *args, **kwargs)
if commit_on_success:
    conn.commit()
return result
```
runs the wrapped function, then commits, then returns — all before the caller (a route handler or another DAO
function) regains control. `create_team`, `create_segment`, `create_block`, `create_template`, and
`create_or_update_task` currently set `commit_on_success=False` and call `conn.commit()` themselves partway
through (e.g. right after the `INSERT` and before returning `_backend.last_insert_id(cursor)`), which is
functionally a no-op difference from letting the decorator commit — `last_insert_id` doesn't require a commit to
read (SQLite's `cursor.lastrowid` is available immediately after `execute()`, uncommitted).

## Goals / Non-Goals

**Goals:** remove the redundant manual commits; verify no test/caller actually depends on the commit happening
*before* the function returns (as opposed to immediately after, which is what the decorator already guarantees).

**Non-Goals:** changing transaction boundaries or introducing multi-statement atomicity — out of scope (see
`sqlite-connection-reuse`'s design.md Non-Goals for the related, larger discussion of request-level transactions).

## Decisions

- **Just delete the manual commits and the decorator override.** No behavioral design decision needed here — this
  is confirmed dead weight, not an alternate valid pattern being weighed against another.
- **Sequencing with `api-error-handling`**: that change wraps the same `INSERT`/`UPDATE` statements in
  `try/except _backend.duplicate_error` inside these same five (four, excluding `create_or_update_task`)
  functions. Whichever change lands second should rebase its diff on the other rather than the two being applied
  blind to each other, since both touch the same few lines. No dependency ordering is required — either sequence
  works — but this is noted so whoever applies these two tasks does the smaller mechanical merge, not because
  the changes are otherwise coupled.

## Risks / Trade-offs

- [Risk] None functionally — `conn.commit()` is idempotent (committing with nothing pending, or that was already
  committed, is a safe no-op), so even if this were somehow wrong, the worst case is byte-identical behavior to
  today.
