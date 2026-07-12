# dao-commit-consistency Specification

## Purpose
TBD - created by archiving change cleanup-create-commit-pattern. Update Purpose after archive.
## Requirements
### Requirement: DAO writes commit only via the decorator
Every DAO write function wrapped by `with_db_connection` SHALL rely solely on the decorator's `commit_on_success`
behavior for committing its transaction — no wrapped function calls `conn.commit()` itself.

#### Scenario: create_team commits exactly once
- **WHEN** `create_team` is called and succeeds
- **THEN** the new row is committed and visible to other connections immediately after `create_team` returns,
  with exactly one `conn.commit()` call happening (inside the decorator, not inside `create_team`)

#### Scenario: Result value doesn't depend on commit timing
- **WHEN** `create_team`, `create_segment`, `create_block`, `create_template`, or `create_or_update_task` reads
  back a value it just wrote (e.g. `_backend.last_insert_id(cursor)`) before returning
- **THEN** that read succeeds correctly whether or not a commit has happened yet, since it's read on the same
  connection within the same uncommitted transaction

