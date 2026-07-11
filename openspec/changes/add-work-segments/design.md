## Context

Block templates (`block_templates`) are currently scoped only to a team via the `team_templates` M:N join table (`db/sqlite.py:99-103`) — `AssignmentModal.tsx` fetches `useTeamTemplates(teamId)` and offers every template allowed for the task's team, with no finer-grained restriction. Tasks (`tasks`) currently carry `team_id`, `criticality`, and `priority` but nothing that distinguishes what kind of work they are beyond team membership.

This change introduces `segments` as a new required classifier on both `tasks` and `block_templates`, and uses it to narrow the block-template choices an assignment/auto-schedule flow offers for a given task, on top of (not instead of) the existing team scoping.

## Goals / Non-Goals

**Goals:**
- A `segments` lookup entity with CRUD in Settings, following the existing `blocks`/`teams` pattern exactly (flat list, name-only, unique).
- `block_templates.segment_id`: one segment per template (required, set in the Settings template form).
- `tasks.segment_id`: one segment per task (required, set in the task create/edit modal).
- Assignment creation and auto-scheduling offer only block templates that are both team-allowed (existing `team_templates`) **and** tagged with the task's segment.
- A segment filter on the Planning task list, consistent with the existing criticality/status filters.
- Zero-downtime migration: a default segment is seeded and backfilled onto every existing `block_templates`/`tasks` row so the new required columns are never `NULL` on an upgraded database.

**Non-Goals:**
- No M:N relationship between segments and block templates — a template belongs to exactly one segment (matches "в шаблоне блоков можно указать сегмент", singular).
- No change to team-level scoping (`team_templates`) — segment narrows within it, it doesn't replace it.
- No server-side pagination-aware segment filter — the new filter follows the same client-side post-filter pattern already used for criticality/status on `PlanningPage.tsx`, not a new `/api/tasks/{team_id}?segment_id=` query param.
- No segment-level history/audit trail — segments are a pure lookup entity like `blocks`/`teams`, neither of which is history-tracked today.
- No protection against deleting the "default" segment beyond the same FK-restrict behavior applied to every other segment.

## Decisions

**1. `block_templates.segment_id` is a single required FK, not a join table.**
Alternative considered: a `segment_templates` M:N table mirroring `team_templates`, allowing one template to serve multiple segments. Rejected: the requirement text ("в шаблоне блоков можно указать сегмент") is singular, and a template representing one deployment/work track conceptually belongs to one segment. This is also simpler to migrate and to reason about in the UI (one `<Select>` instead of a multi-picker).

**2. Team-allowed templates are narrowed by segment on the client, not via a new intersection endpoint.**
`db.get_team_allowed_templates` (used by `GET /api/teams/{team_id}` → `.templates`) is extended to also return each template's `segment_id` in the payload. `AssignmentModal.tsx` already knows the task's `segment_id` (task is passed in as a prop), so it filters the existing `templates` array client-side (`t.segment_id === task.segment_id`) before rendering the template picker and before calling `computeAutoAssignDates`. Alternative considered: a new `GET /api/tasks/{task_id}/templates` endpoint that does the intersection server-side, or a `?segment_id=` query param added to the team endpoint. Rejected in favor of the simpler payload-enrichment approach — it avoids touching `GET /api/teams/{team_id}`'s existing (unfiltered) usage in `SettingsPage`'s `TeamsTab`, requires no new route, and matches the codebase's established convention of computing derived UI state client-side (auto-schedule dates, existing filters).
`db.get_blocks_for_team` (→ `GET /api/teams/{team_id}/blocks`, used for `teamBlocks`) gets the same treatment: an optional `segment_id` query param that, when present, restricts the join to templates matching that segment — used wherever the raw block set (not the template list) needs to reflect the segment-narrowed set.

**3. Default segment is created only when there's pre-existing data to backfill — never unconditionally.**
The default segment exists solely to give old `block_templates`/`tasks` rows a non-NULL value when the required `segment_id` column is retrofitted onto them; it is not a general-purpose "starter" segment. `_migrate_add_segment_columns` first checks, per table, whether `block_templates`/`tasks` already exist *and* already lack `segment_id` (via `PRAGMA table_info`). Only if at least one of them needs the column does the migration create the `segments` table (if missing) and insert `'По умолчанию'` via `INSERT OR IGNORE`; it then resolves that row's id and runs `ALTER TABLE <table> ADD COLUMN segment_id INTEGER NOT NULL DEFAULT <resolved_id> REFERENCES segments(id)` for each table that needed it, backfilling every existing row in the same statement (SQLite applies the `DEFAULT` to existing rows when adding a `NOT NULL` column).
A fresh database (both tables absent, or already migrated with `segment_id` present) never triggers this path at all — `segments` ends up empty, seeded via `_SCHEMA`'s plain `CREATE TABLE IF NOT EXISTS segments (...)` with no default row inserted. `_SCHEMA`'s `CREATE TABLE` statements for `block_templates`/`tasks` declare `segment_id INTEGER NOT NULL REFERENCES segments(id)` directly with no `DEFAULT`, and since those tables start empty on a fresh DB the constraint is satisfiable from the first insert — the user must create at least one segment via Settings before they can create their first task or block template, exactly as they already must create at least one team/block. This was a deliberate change from an earlier draft of this design that seeded the default segment unconditionally on every startup — that made every fresh install start with a "По умолчанию" segment nobody asked for, when the whole point of the default segment is strictly to keep pre-existing data valid across the migration, not to pre-populate new installs.
This mirrors the existing `_migrate_add_criticality_column` idiom (`db/sqlite.py:354-369`), extended to resolve a real FK id instead of a constant string literal, and to only run its side effect conditionally.

**4. Segment deletion relies on FK-restrict, no special-casing.**
`delete_segment` is a plain `DELETE FROM segments WHERE id = ?`, exactly like `delete_block`. With `PRAGMA foreign_keys = ON` and no `ON DELETE CASCADE`/`SET NULL` on `block_templates.segment_id`/`tasks.segment_id`, SQLite raises an `IntegrityError` if any row still references the segment, which the route layer turns into a 400 JSON error (same try/except pattern already used for duplicate-name conflicts on `blocks`/`teams`). This includes the default segment itself once nothing references it anymore — it is not permanently protected the way the bootstrap admin user is, since unlike that account it has no special runtime meaning after migration completes.

**5. Segment filter on Planning is a client-side post-filter.**
Consistent with `critFilter`/`taskStatusFilter`/`statusFilter` (`PlanningPage.tsx`), which all filter the already-fetched page rather than adding a server query param. A `segmentFilter: number[]` state + `Select mode="multiple"` follows the identical shape, fed by `useSegments()` for its options and applied in the same `filteredTasks` `useMemo`.

## Risks / Trade-offs

- **[Risk]** Existing `block_templates`/`tasks` rows all collapse onto one default segment after migration, so the new segment-based template narrowing is a no-op until an admin manually re-tags templates/tasks into more specific segments. → **Mitigation**: this is inherent to introducing a new required classifier on existing data; documented behavior, not a bug. The feature is additive and non-breaking to existing workflows immediately after migration (everything still resolves to "По умолчанию" and behaves as before).
- **[Risk]** Client-side team∩segment intersection means `AssignmentModal` must always have the task's `segment_id` available before rendering the template picker — if `segment_id` is ever missing on an older cached task payload client-side, the filtered list would silently be empty. → **Mitigation**: `segment_id` becomes a required field on the `Task` type end-to-end (backend guarantees non-null after migration; TypeScript type marks it required, not optional), so this can only happen from a stale client build, same class of risk as any other schema/type drift.
- **[Risk]** SQLite `ALTER TABLE ... ADD COLUMN ... NOT NULL DEFAULT <id> REFERENCES segments(id)` — SQLite does not retroactively validate the FK for rows written before `PRAGMA foreign_keys = ON` was enabled in a session, but since the default id is resolved from a row that was just inserted in the same migration, this is a non-issue in practice. → **Mitigation**: none needed, noted for implementer awareness.

## Migration Plan

1. On startup, before `_SCHEMA` is executed: check whether `block_templates` and/or `tasks` exist and already lack `segment_id` (via `PRAGMA table_info`).
2. If neither needs it (fresh DB, or already migrated), do nothing — no default segment is created.
3. Otherwise: `CREATE TABLE IF NOT EXISTS segments (...)`, `INSERT OR IGNORE INTO segments (name) VALUES ('По умолчанию')`, resolve its id, and for each table that needs it run `ALTER TABLE ... ADD COLUMN segment_id INTEGER NOT NULL DEFAULT <id> REFERENCES segments(id)`.
4. `_SCHEMA`'s `CREATE TABLE IF NOT EXISTS` statements for `segments`, `block_templates`, and `tasks` are updated so a fresh database gets the final shape directly (segment_id declared `NOT NULL REFERENCES segments(id)`, no `DEFAULT` needed since those tables start empty on a fresh DB, and `segments` itself starts with zero rows).
5. No rollback path is provided beyond restoring a pre-migration DB backup — consistent with how every other additive schema migration in this codebase is handled (no down-migrations exist anywhere in `db/sqlite.py`).

## Open Questions

None — the client-side intersection approach (Decision 2) and the client-side filter approach (Decision 5 goal) were chosen specifically to avoid open-ended server API design; if segment/task volume ever grows large enough to need server-side paginated segment filtering, that's a separate follow-up change.
