## Why

Block templates today are only scoped to a team (`team_templates`), so any team member creating an assignment sees every block template allowed for their team regardless of what kind of work the task actually is. Support work naturally splits into distinct segments (e.g. different product lines or deployment tracks), and each segment should only expose the block templates relevant to it. There's currently no way to tag a task or a block template with that distinction, so users must manually pick the right template out of an undifferentiated list, and auto-scheduling can't help narrow it down.

## What Changes

- Add a new `segments` reference entity (id, unique name), managed via CRUD in Settings — modeled directly on the existing `blocks`/`teams` pattern (a new Settings tab, list + create/edit/delete modal).
- Add a required `segment_id` FK to `block_templates` — each block template belongs to exactly one segment (set when creating/editing a template in Settings).
- Add a required `segment_id` FK to `tasks` — set via a new required "Сегмент" select in the task create/edit modal.
- The set of block templates offered when creating an assignment and when auto-scheduling is now the **intersection** of the task's team-allowed templates (existing `team_templates` linkage) and the templates whose `segment_id` matches the task's `segment_id`.
- Add a segment filter to the task list on the Planning page, alongside the existing criticality/status filters.
- **BREAKING (data migration)**: `block_templates.segment_id` and `tasks.segment_id` become required columns. A default segment ("По умолчанию") is created and backfilled onto every pre-existing `block_templates` and `tasks` row only when such a backfill is actually needed (upgrading an existing database) — a fresh install or an already-migrated database never gets an auto-created segment.

## Capabilities

### New Capabilities
- `work-segments`: segment reference-entity CRUD (Settings), required segment on tasks and block templates, segment-based narrowing of available block templates for assignment creation and auto-scheduling, segment filter on the Planning task list, and the default-segment backfill migration for existing data.

### Modified Capabilities
(none — no existing `openspec/specs/` capabilities exist yet to modify)

## Impact

- **DB schema** (`db/sqlite.py`): new `segments` table; new required `segment_id` column on `block_templates` and `tasks`; a migration routine that seeds the default segment and backfills both columns on upgrade, following the existing `_migrate_add_criticality_column` idiom.
- **DAO layer** (`db/__init__.py`): new `segments` CRUD functions; `create_or_update_template`/`create_or_update_task`-equivalents extended to accept/persist `segment_id`; `get_tasks_by_team`/`get_tasks_count_by_team` extended with an optional segment filter; a new helper to compute the team∩segment template intersection for a given task.
- **API** (`support_planner.py`): new `SegmentIn` model and `/api/segments` CRUD routes; `TaskIn`/`BlockTemplateIn` gain required `segment_id`; task list endpoint gains a segment filter query param; assignment/auto-schedule template lookup narrowed by segment.
- **Frontend** (`frontend/src/`): new `SegmentsTab.tsx` in Settings; `useSegments()` query hook; required Segment `<Select>` in `TaskModal.tsx` and in the block-template form; segment-aware template/block fetching in `AssignmentModal.tsx`; segment filter control on `PlanningPage.tsx`.
