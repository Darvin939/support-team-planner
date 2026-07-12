## 1. DAO layer

- [x] 1.1 Add `class IntegrityConstraintError(Exception): pass` to `db/__init__.py`.
- [x] 1.2 `create_team`/`update_team`: catch `_backend.duplicate_error` around the `INSERT`/`UPDATE`, raise
      `IntegrityConstraintError('Команда с таким названием уже существует')`.
- [x] 1.3 `create_block`: same, `IntegrityConstraintError('Блок с таким названием уже существует')`.
- [x] 1.4 `create_template`/`update_template`: same, `IntegrityConstraintError('Шаблон с таким названием уже существует')`.
- [x] 1.5 `create_segment`/`update_segment`: same, `IntegrityConstraintError('Сегмент с таким названием уже существует')`.
- [x] 1.6 ~~`delete_team`: catch `_backend.duplicate_error`...~~ **Revised during implementation**: `delete_team`
      cannot raise a constraint violation (`tasks.team_id`/`team_templates.team_id` are both `ON DELETE CASCADE`)
      — added an explanatory comment instead of dead try/except code. See design.md.
- [x] 1.7 ~~`delete_block`: same...~~ **Revised**: `delete_block` cannot raise either (`template_blocks.block_id`
      is `ON DELETE CASCADE`) — comment added, no try/except.
- [x] 1.8 ~~`delete_template`: same...~~ **Revised**: `delete_template` cannot raise either
      (`template_blocks.template_id`/`team_templates.template_id` are both `ON DELETE CASCADE`) — comment added,
      no try/except.
- [x] 1.9 `delete_segment`: wrapped its `DELETE` in `try/except _backend.duplicate_error: raise
      IntegrityConstraintError(...)` — this one genuinely can fail (`tasks.segment_id`/`block_templates.segment_id`
      have no `ON DELETE`).

## 2. Route layer

- [x] 2.1 `create_team_api`/`update_team_api`: narrowed `except Exception as e` to `except db.IntegrityConstraintError as e`.
- [x] 2.2 `create_block_api`: same narrowing.
- [x] 2.3 `create_template_api`/`update_template_api`: same narrowing. (Also narrowed `delete_template_api`'s
      handling to match — see note under task 2.6.)
- [x] 2.4 `create_segment_api`/`update_segment_api`/`delete_segment_api`: same narrowing.
- [x] 2.5 ~~`delete_team_api`: wrap in try/except...~~ **Revised**: not added — `delete_team` cannot raise, so a
      try/except here would be dead code. Reverted to no handling (same as before this change).
- [x] 2.6 ~~`delete_block_api`: same new try/except.~~ **Revised**: same reasoning, not added.
      `delete_template_api` was initially given a try/except too (an extra fix beyond the original task list,
      since `delete_template`'s DAO function was going to raise but nothing caught it) — then reverted for the
      same reason once 1.8 was revised: `delete_template` doesn't raise either, so there's nothing to catch.

## 3. Verification

- [x] 3.1 Manual check: created a team named `Поддержка Розницы` (already exists) → `400
      {"error":"Команда с таким названием уже существует"}`. Confirmed.
- [x] 3.2 Manual check: deleted block `ГФ` (id 1), which was referenced by all 3 block templates → **got 200, not
      400** — this is what surfaced the wrong assumption in the original proposal/design (see design.md). The
      block was cascade-removed from all 3 templates. Restored the demo data afterward (recreated `ГФ` as a new
      block id, re-added it to the 3 templates with their original `shift_days`) and confirmed the templates
      matched their pre-test state.
- [x] 3.3 Manual check: `delete_team`/`delete_block`/`delete_template` on unreferenced rows still succeed (200) —
      implicitly confirmed by 3.2's restoration steps (recreating the block and re-attaching it via `PUT
      /api/block-templates/{id}` all returned 200).
- [x] 3.4 Grep confirmed: `grep -n "except Exception" support_planner.py` returns no matches.
