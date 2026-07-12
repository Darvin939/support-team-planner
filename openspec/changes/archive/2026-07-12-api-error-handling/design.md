## Context

Two distinct SQLite constraint failures currently reach the API layer as generic Python exceptions: UNIQUE
violations on create/update (duplicate name) — real for `teams`, `blocks`, `segments`, `block_templates`, all of
which have `UNIQUE(name)` — and FK violations on delete. **Verified against `db/sqlite.py`'s actual schema during
implementation**: the FK violation case is only reachable for `segments`, because `tasks.segment_id` and
`block_templates.segment_id` have no `ON DELETE` clause. Every other delete path this proposal initially assumed
could fail the same way — `delete_team`, `delete_block`, `delete_template` — actually cannot: their referencing
FKs (`tasks.team_id`, `team_templates.team_id`/`template_id`, `template_blocks.template_id`/`block_id`) are all
`ON DELETE CASCADE`, so SQLite silently removes the referencing rows instead of raising. This was caught by a
manual test during implementation (deleting a block still used by 3 templates returned `200`, not the expected
`400`, and the block was cleanly cascaded out of those templates) — not by static analysis, which is why the
original version of this design document got it wrong.

`db/backend.py` already exposes `duplicate_error` as the backend-specific exception class to catch
(`sqlite3.IntegrityError` for `SQLiteBackend`), but nothing in `db/__init__.py` currently uses it outside
`create_user`'s sentinel-return pattern (`raise_on_error=False` + `default_return=None`).

## Goals / Non-Goals

**Goals:**
- One consistent way for a DAO write to signal "this failed because of a constraint the user can fix" (rename,
  or remove the thing referencing it) vs. "this failed because of a bug".

**Non-Goals:**
- ~~Close the gap where `delete_team`/`delete_block` currently have no handling at all~~ — retracted: there is no
  gap. Those functions cannot raise a constraint violation given the current schema's cascading FKs, so adding
  handling for them would be dead code (a `try/except` branch that can never execute), which this codebase's
  conventions explicitly discourage ("don't add error handling for scenarios that can't happen").
- Touching `create_user`/`update_user`'s existing sentinel-return pattern (`None`/`False` on duplicate) — it's a
  different, already-consistent convention used only by the users routes, which have richer validation needs
  (bootstrap-admin branch) that don't fit a plain exception cleanly. Not in scope here.
- Any change to which operations are allowed to fail with a constraint error (no new validation rules).

## Decisions

- **One exception class, not a hierarchy.** `db.IntegrityConstraintError(Exception)` carrying a ready-to-display
  Russian message, rather than separate `DuplicateNameError`/`EntityInUseError` subclasses — the route layer only
  ever needs to catch-and-400 with the message as-is; splitting into subclasses would add indirection with no
  caller that needs to distinguish them.
- **Message is constructed at the DAO layer, not the route layer**, since the DAO function knows which operation
  and entity failed (e.g. `update_segment` knows it's a segment name collision) — the route just needs to catch
  and forward `str(e)`.
- **Catch `_backend.duplicate_error` inside each DAO function**, not by wrapping `with_db_connection` itself —
  the decorator is deliberately generic (used by ~40 functions); adding constraint-translation logic there would
  force every caller to reason about it. A local `try/except _backend.duplicate_error: raise IntegrityConstraintError(...)`
  around just the `INSERT`/`UPDATE`/`DELETE` statement in the 8 functions where it's actually reachable (7
  create/update functions + `delete_segment`) is more local and readable.
- **`delete_team`/`delete_block`/`delete_template` get a one-line comment, not a try/except**, naming the specific
  `ON DELETE CASCADE` FK that makes the failure unreachable — so a future schema change removing that cascade has
  an obvious place to add the same pattern back, without carrying dead code until then.

## Risks / Trade-offs

- [Risk] SQLite's `IntegrityError` doesn't distinguish UNIQUE from FK violations by type — a function could
  theoretically raise the "wrong" friendly message if a different constraint fails unexpectedly → Mitigation:
  each affected table has exactly one constraint that can realistically fire for that statement (UNIQUE(name) for
  create/update, the segment FK for `delete_segment`), so this is a non-issue in practice; if it ever becomes
  ambiguous, `e.args` still contains SQLite's own detail for debugging via logs (exception isn't swallowed, just
  re-raised under a new type).
- [Risk] Un-related exceptions now propagate as 500 instead of 400 for these 8 functions → Mitigation: this is the
  intended fix, not a regression — see proposal.md "Why".
- [Risk] The original proposal/design shipped with an incorrect assumption (FK violations reachable on
  team/block/template delete) that wasn't caught until implementation-time testing → Mitigation: this is exactly
  why tasks.md's verification section requires exercising the actual delete-a-referenced-entity scenario, not
  just trusting the schema read at proposal time. Documented here as a reminder that "no existing tests" (per
  CLAUDE.md) means this kind of assumption error is realistically the main way this class of bug gets introduced.
