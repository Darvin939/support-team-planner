## Why

`create_team`, `create_segment`, `create_block`, `create_template`, and `create_or_update_task` in `db/__init__.py`
all explicitly set `@with_db_connection(commit_on_success=False)` and then call `conn.commit()` manually inside
the function body — even though `with_db_connection`'s wrapper already commits automatically right after the
wrapped function returns (its default `commit_on_success=True`), before control ever returns to the caller. There
is no functional reason found for the manual commit: reads within the same function already see uncommitted
writes on the same connection (same SQLite transaction), so nothing inside these functions depends on an early
commit. This looks like a historical leftover from an earlier version of the code, not an intentional pattern —
worth removing for consistency with the ~35 other DAO functions that just rely on the decorator's default commit.

## What Changes

- Remove the manual `conn.commit()` calls from `create_team`, `create_segment`, `create_block`, `create_template`,
  and `create_or_update_task`.
- Remove the explicit `commit_on_success=False` override from their `@with_db_connection(...)` decorators,
  falling back to the (equivalent) default `commit_on_success=True`.

## Capabilities

### New Capabilities
- `dao-commit-consistency`: every `@with_db_connection`-wrapped write commits via the decorator's own
  `commit_on_success`, with no function managing its own commit — a single, uniform commit-timing contract.

### Modified Capabilities
- (none)

## Impact

- `db/__init__.py`: five functions lose their manual `conn.commit()` call and `commit_on_success=False` override.
- No behavior change. Note: this touches the same five call sites (minus `create_or_update_task`, which
  `api-error-handling` doesn't touch) that a separate change, `api-error-handling`, also edits (adding a
  try/except around the same `INSERT`/`UPDATE` statements) — see design.md for sequencing.
