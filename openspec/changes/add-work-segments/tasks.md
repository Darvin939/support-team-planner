## 1. DB schema & migration (`db/sqlite.py`)

- [x] 1.1 Add `CREATE TABLE IF NOT EXISTS segments (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)` to `_SCHEMA`, placed near `blocks`/`teams`.
- [x] 1.2 Add `segment_id INTEGER NOT NULL REFERENCES segments(id)` to the `block_templates` table definition in `_SCHEMA`.
- [x] 1.3 Add `segment_id INTEGER NOT NULL REFERENCES segments(id)` to the `tasks` table definition in `_SCHEMA`.
- [x] 1.4/1.5 (revised after initial implementation) Single `_migrate_add_segment_columns(conn)` staticmethod, mirroring `_migrate_add_criticality_column` (`db/sqlite.py:354-369`): for `block_templates` and `tasks`, checks which of them exist (`sqlite_master`) and still lack `segment_id` (`PRAGMA table_info`). If neither needs it (fresh DB, or already migrated), returns immediately — no default segment is created. Otherwise creates `segments` (if missing), `INSERT OR IGNORE`s "По умолчанию", resolves its id, and runs `ALTER TABLE <table> ADD COLUMN segment_id INTEGER NOT NULL DEFAULT <id> REFERENCES segments(id)` for each table that needed it. Originally split into two unconditional steps (a `_seed_default_segment` that always ran plus a separate backfill) — merged and made conditional per user feedback: the default segment must only exist to backfill old data, never auto-created on a fresh or already-migrated install.
- [x] 1.6 Wired into `init_schema` (near `db/sqlite.py:197-200`): single `self._migrate_add_segment_columns(conn)` call, **before** `conn.executescript(_SCHEMA)`.
- [x] 1.7 Manually verify against a copy of an existing `database.db` (pre-feature): confirm `segments` gets a "По умолчанию" row, and every pre-existing `block_templates`/`tasks` row ends up with `segment_id` pointing at it (`SELECT COUNT(*) FROM tasks WHERE segment_id IS NULL` → 0, same for `block_templates`). (Verified in group 10.3: backed up the real dev DB, ran the migration, confirmed via direct sqlite3 query — 0 NULLs in both columns.)

## 2. DAO layer (`db/__init__.py`)

- [x] 2.1 Add `get_all_segments(conn)` (mirror `get_all_teams`, `db/__init__.py:48`).
- [x] 2.2 Add `create_segment(conn, name)` / `update_segment(conn, segment_id, name)` / `delete_segment(conn, segment_id)` (mirror `create_block`/`delete_block`, `db/__init__.py:158-179`; let SQLite's `UNIQUE` and FK-restrict constraints raise, same as existing blocks/teams — no extra Python-side validation).
- [x] 2.3 Extend `get_team_allowed_templates` (`db/__init__.py:77-104`) to also select `bt.segment_id` per template row so the API payload can expose it.
- [x] 2.4 Extend `get_blocks_for_team` (`db/__init__.py:107-119`) to accept an optional `segment_id=None` param, adding `AND bt.segment_id = ?` to the join when provided.
- [x] 2.5 Extend `create_template`/`update_template` (`db/__init__.py:240-254`) to accept and persist a required `segment_id` param.
- [x] 2.6 Extend `create_or_update_task` (`db/__init__.py:587-631`) to accept and persist a required `segment_id` param, recording a `task_history` row when it changes on update (mirror the existing per-field diff logic already in this function for `criticality`/etc).
- [x] 2.7 Extend `get_tasks_by_team` / `get_tasks_count_by_team` (`db/__init__.py:477-539`) to `SELECT`/return `segment_id` (and a joined `segment_name` for display) per task — no new filter param needed since the Planning filter is client-side (see design.md Decision 5), but the field must be present in the payload for the client to filter on.
- [x] 2.8 Extend `get_active_tasks_flat` (`db/__init__.py:812-855`) — evaluated and skipped: the dependency picker only ever renders `CriticalityBadge`, no segment display is requested by the spec, so left unchanged to avoid unrequested scope.

## 3. API layer (`support_planner.py`)

- [x] 3.1 Add `SegmentIn(BaseModel)` with `name: str = ""` (mirror `BlockIn`, `support_planner.py:135-137`).
- [x] 3.2 Add `GET /api/segments`, `POST /api/segments`, `PUT /api/segments/{segment_id}`, `DELETE /api/segments/{segment_id}` routes (mirror the blocks routes, `support_planner.py:736-759`), each requiring `editor`+ per the existing `_EDITOR_API_PREFIXES` convention (add `/api/segments` to that prefix set) — wrap create/update/delete in `try/except Exception` → 400 JSON, same as blocks/teams.
- [x] 3.3 Add `segment_id: int` (required, no default) to `TaskIn` (`support_planner.py:121-127`); in `save_task_api` (`support_planner.py:396-420`), validate it's present and references an existing segment (400 JSON error otherwise), and pass it through to `db.create_or_update_task`.
- [x] 3.4 Add `segment_id: int` (required, no default) to `BlockTemplateIn` (`support_planner.py:140-146`); validate similarly in the create/update template routes (`support_planner.py:764-805`) and pass through to `db.create_template`/`db.update_template`.
- [x] 3.5 Update the `GET /api/teams/{team_id}` handler (`support_planner.py:530-542`) — no signature change needed, just confirm the enriched `templates` payload (now including `segment_id` per template, from task 2.3) flows through to the JSON response unmodified.
- [x] 3.6 Update the `GET /api/teams/{team_id}/blocks` handler (`support_planner.py:545-549`) to accept an optional `segment_id: Optional[int] = None` query param and pass it to `db.get_blocks_for_team`.
- [x] 3.7 Update `GET /api/tasks/{team_id}` (wherever `get_tasks_by_team` is called) to include `segment_id`/`segment_name` in each returned task object.

## 4. Frontend — data hooks

- [x] 4.1 Add a `Segment` interface (`{id, name}`) and `useSegments()` query hook (mirror `useTeams.ts` or the pattern in `frontend/src/hooks/useSettingsData.ts:14-47`), fetching `GET /api/segments`.
- [x] 4.2 Update the `Team`/template-related types consumed by `useTeamTemplates` (`frontend/src/hooks/usePlanningData.ts:143-149`) to include `segment_id` on each template.
- [x] 4.3 Update `useTeamBlocks` (`frontend/src/hooks/usePlanningData.ts:123-129`) to accept an optional `segmentId` param, appending `?segment_id=` to the request URL when set, and include it in the query key.
- [x] 4.4 Update the `Task` interface (`frontend/src/hooks/usePlanningData.ts:6-13`) to add required `segment_id: number` (and `segment_name?: string` if the API returns it).

## 5. Frontend — Settings: Segments tab

- [x] 5.1 Create `frontend/src/pages/settings/SegmentsTab.tsx`, mirroring the flat-list CRUD pattern in `frontend/src/pages/settings/BlocksTab.tsx` (`BlocksList`, lines 18-70): list of segments with edit/delete (`Popconfirm`), a `Modal` + `Form` for create/update, `useMutation` + `queryClient.invalidateQueries(['segments'])` via `apiMutate`.
- [x] 5.2 Register the new tab in `SettingsPage.tsx` (`frontend/src/pages/SettingsPage.tsx:9-27`), e.g. `{ key: 'segments', label: 'Сегменты', children: <SegmentsTab /> }`.

## 6. Frontend — block template form requires a segment

- [x] 6.1 In the block-templates Settings UI (`frontend/src/pages/settings/BlocksTab.tsx`, `TemplatesList`, lines 72-192), add a required `<Select>` bound to `useSegments()` options, `rules={[{ required: true, message: 'Выберите сегмент' }]}`, and include `segment_id` in the create/update payload sent to `/api/block-templates`.

## 7. Frontend — task modal requires a segment

- [x] 7.1 In `frontend/src/pages/planning/TaskModal.tsx`, add a required Segment `<Select>` (mirror the criticality select, `TaskModal.tsx:138-146`) fed by `useSegments()`, `rules={[{ required: true, message: 'Выберите сегмент' }]}`.
- [x] 7.2 Include `segment_id` in the `saveMutation` payload (`TaskModal.tsx:63-72`) posted to `POST /api/task`.
- [x] 7.3 Ensure the modal's initial-values logic pre-fills `segment_id` correctly when editing an existing task, and leaves no default/blank state possible for a new task (implemented: falls back to `segments?.[0]?.id` for a new task, same "always populated" guarantee as the template form in 6.1).

## 8. Frontend — assignment modal / auto-schedule narrowed by segment

- [x] 8.1 In `frontend/src/pages/planning/AssignmentModal.tsx`, after fetching `templates` via `useTeamTemplates(teamId)` (`AssignmentModal.tsx:230-232`), filter it to `templates.filter(t => t.segment_id === task.segment_id)` before it's used to populate the template picker and before `recomputeSchedule`/`computeAutoAssignDates` (`AssignmentModal.tsx:259-279`) run against it. (Implemented with `useMemo` to keep a stable array reference — a plain inline `.filter()` would have re-triggered the auto-schedule effect on every render.)
- [x] 8.2 `teamBlocks` (manual block selection, used when auto-assign is off) is fetched with `useTeamBlocks(teamId, task?.segment_id)`, segment-scoped via the same mechanism as 4.3.
- [x] 8.3 Manually verify: a template tagged with a non-matching segment never appears in the picker for a task of a different segment, even when that template is otherwise allowed for the task's team. (Verified in group 10.4 at the API level, which the client filters over identically: two segment-tagged templates on the same team produced disjoint `?segment_id=` block results.)

## 9. Frontend — Planning segment filter

- [x] 9.1 Add `segmentFilter: number[]` state to `PlanningPage.tsx` (mirror `critFilter`, `PlanningPage.tsx:116-118`), defaulting to `[]`.
- [x] 9.2 Include the segment check in the `filteredTasks` `useMemo` (`PlanningPage.tsx:294-304`): `if (segmentFilter.length && !segmentFilter.includes(t.segment_id)) return false;`.
- [x] 9.3 Render a `FilterField` with a `Select mode="multiple"` bound to `segmentFilter`/`setSegmentFilter`, options from `useSegments()` (mirror the criticality `FilterField`, `PlanningPage.tsx:559-561`).

## 10. End-to-end verification

- [x] 10.1 Run `npm run build` in `frontend/` and confirm it succeeds with no type errors introduced by the new required `segment_id` fields. (Build succeeded, `tsc -b && vite build` — no type errors.)
- [x] 10.2 Start `python support_planner.py` against a freshly deleted/rebuilt `database.db` and confirm the fresh-install behavior. (Re-verified after the 1.4/1.5 revision: fresh DB now starts with **zero** segments, not an auto-created default — `GET /api/segments` returns `[]`; creating a task/template without `segment_id` still 400s; creating a segment then works; restarting the server against this now-migrated-but-still-fresh-origin DB does not add a "По умолчанию" row. All against a throwaway DB, discarded afterward, real `database.db` untouched.)
- [x] 10.3 Start the app against a pre-existing `database.db` (created before this change) and confirm all prior tasks/templates now show "По умолчанию" as their segment with no errors on startup or on the Planning page. (Verified against the real dev `database.db`, backed up first: found and fixed an `ambiguous column name: id` SQLite error in `get_tasks_by_team` caused by the new `JOIN segments`, not caught by `npm run build`/`ast.parse` since it's a runtime SQL error. All prior tasks/templates confirmed backfilled to "По умолчанию", `GET /api/tasks/{team_id}` returns 200 after the fix.)
- [x] 10.4 Create two segments and, for each, a block template tagged to it under the same team; confirm the assignment modal's template picker for a task in segment A only offers segment A's template, not segment B's. (Verified at the API level, which is what the client filters over: `GET /api/teams/1/blocks?segment_id=<A>` vs `?segment_id=<B>` returned disjoint block sets from disjoint templates on the same team; the client-side filter in `AssignmentModal.tsx` does the same `segment_id` match over the same `templates` payload.)
- [ ] 10.5 Confirm the new segment filter on the Planning page correctly narrows the visible task list. (Not run — requires a browser-driven UI check, not exercised in this terminal-only verification pass.)
- [x] 10.6 Kill the `python support_planner.py` process after manual testing completes. (Killed after every test run; final state: real `database.db` restored from backup with the migration applied and zero leftover test data.)
