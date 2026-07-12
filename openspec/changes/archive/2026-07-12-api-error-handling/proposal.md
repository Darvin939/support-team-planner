## Why

Eight endpoints in `support_planner.py` (create/update for teams, blocks, block templates, segments, plus
`delete_segment_api`) wrap their DAO call in `except Exception as e: return JSONResponse({'error': str(e)}, 400)`.
This has two problems: (1) it coerces *any* bug (AttributeError, TypeError, a genuine programming error) into a
400 response instead of surfacing as a 500, hiding real defects from logs/monitoring; (2) it leaks the raw Python
exception message to the API client, which is inconsistent and occasionally exposes internal details (e.g. raw
SQLite constraint text).

**Correction made during implementation:** the original version of this proposal also claimed `delete_team_api`
and `delete_block_api` were missing handling for an FK-constraint failure on delete, "closing an inconsistency"
with `delete_segment_api`. That assumption was wrong and was caught by testing during implementation (deleting a
block still referenced by a template returned 200, not the expected 400) — reading `db/sqlite.py`'s schema
confirms `template_blocks.block_id`/`template_id`, `team_templates.team_id`/`template_id`, and `tasks.team_id` are
all `ON DELETE CASCADE`, so `delete_team`/`delete_block`/`delete_template` can **never** raise a constraint
violation: SQLite just cascades the referencing rows away silently. `delete_segment` is the only delete of the
four that can genuinely fail, because `tasks.segment_id` and `block_templates.segment_id` have no `ON DELETE`
clause at all. This proposal's scope is corrected below to only add error handling where it's actually reachable.

## What Changes

- Introduce one domain exception in `db/__init__.py`, `db.IntegrityConstraintError(message: str)`, raised by DAO
  functions when they catch the backend's constraint-violation error (`_backend.duplicate_error`).
- `create_team`, `update_team`, `create_block`, `create_template`, `update_template`, `create_segment`,
  `update_segment` catch a UNIQUE-name violation and re-raise `db.IntegrityConstraintError` with a specific
  Russian message (e.g. "Команда с таким названием уже существует").
- `delete_segment` catches an FK violation (segment still referenced by a task or block template) and re-raises
  the same exception type — this is the *only* delete function where this is reachable (see Why).
- The corresponding routes in `support_planner.py` catch only `db.IntegrityConstraintError` → `400
  {'error': str(e)}`; every other exception propagates to FastAPI's default handler (500).
- `delete_team`, `delete_block`, `delete_template` (and their routes) are **not** touched — wrapping them in
  error handling for a scenario the schema makes unreachable would be dead code, and this codebase's convention
  is not to add handling for scenarios that can't happen. Each function gains a one-line comment noting which
  `ON DELETE CASCADE` FK makes the failure impossible, so a future schema change that removes that cascade would
  have an obvious place to add the same `IntegrityConstraintError` pattern back.

## Capabilities

### New Capabilities
- `admin-entity-crud`: error-response contract for team/block/block-template/segment create and update endpoints,
  plus segment delete (constraint violations → 400 with a specific message; everything else → 500).

### Modified Capabilities
- (none — no existing `openspec/specs/` capability currently documents this)

## Impact

- `db/__init__.py`: new `IntegrityConstraintError` exception class; `create_team`, `update_team`, `create_block`,
  `create_template`, `update_template`, `create_segment`, `update_segment`, `delete_segment` gain a narrow
  try/except around the mutating statement. `delete_team`/`delete_block`/`delete_template` are unchanged except
  for an explanatory comment.
- `support_planner.py`: the 8 existing broad `except Exception` blocks narrow to `except db.IntegrityConstraintError`.
  `delete_team_api`/`delete_block_api`/`delete_template_api` remain without a try/except, as before this change
  (correct, since the underlying DAO functions cannot raise).
- No frontend change — response shape (`{'error': '...'}`, status 400) is unchanged for the cases that were
  already handled.
