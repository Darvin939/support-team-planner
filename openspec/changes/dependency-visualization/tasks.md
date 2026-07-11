## 1. Level 1 — Backend groundwork, done-badge, click-to-highlight

- [x] 1.1 Extend `get_all_deps_for_team` in `db/__init__.py` to also select `dep.criticality AS dep_criticality`,
      `dep.segment_id AS dep_segment_id`, and `seg.name AS dep_segment_name` (join `segments seg ON dep.segment_id
      = seg.id`); keep the existing `task_ids`-filter behavior unchanged.
- [x] 1.2 Extend the response of `GET /api/tasks/{team_id}/deps` in `support_planner.py` to include the new
      `dep_criticality` / `dep_segment_id` / `dep_segment_name` fields.
- [x] 1.3 Extend the `TaskDep` interface in `frontend/src/hooks/usePlanningData.ts` with the new fields.
- [x] 1.4 In `frontend/src/components/planningBadges.tsx`, extend `DepBadge`'s `kind` union to include `'done'`
      (color `token.colorSuccess`, icon/label consistent with `TaskStatusBadge`'s done styling); change the
      `names: string[]` prop to `deps: {id: number; name: string}[]` so a dependency's task id travels with its
      name; make each dependency entry inside the tooltip content clickable (invoking a new `onNameClick` prop).
      Implemented directly as the Level 2 `Popover` (see 2.1) rather than an intermediate `Tooltip` step — the
      `deps` prop shape and per-entry click action landed in the same edit as 2.1.
- [x] 1.5 In `frontend/src/pages/PlanningPage.tsx`'s `infoColumn.render`, add a fourth bucket for
      `!dep_is_deleted && dep_status === 'done'` dependencies and render a `done` `DepBadge` for it; update all
      `DepBadge` call sites to pass `deps={...}` instead of `names={...}`.
- [x] 1.6 Implement the click handler: look up
      `document.querySelector('[data-planning-grid] .ant-table-tbody tr[data-task-row-id="<id>"]')`; if found,
      `scrollIntoView({behavior: 'smooth', block: 'center'})` and apply a temporary highlight class to the row's
      `td` cells, removed after ~1.6s; if not found, falls through directly to the Level 2 jump/`TaskModal`
      mechanism (2.3/2.4) instead of a plain message — a strict UX upgrade over the originally planned
      message-only fallback, so the two were implemented together as one `handleDepNavigate` function.
- [x] 1.7 Add the `.task-row-highlight-pulse` keyframe animation to `frontend/src/index.css`, targeting `td`
      elements (not `tr`, since `getCellTint` paints over row-level box-shadow) with the pulse color set inline
      from the live `token.colorPrimary` via a CSS custom property, following the existing
      `.assignment-drag-over`/`.assignment-drag-invalid` precedent for theme-aware inline coloring.

## 2. Level 2 — Popover preview and cross-context navigation

- [x] 2.1 In `planningBadges.tsx`, replace `DepBadge`'s `Tooltip` with a `Popover`
      (`open`/`onOpenChange` state, `trigger="click"`, `placement="bottomLeft"`, following the
      `OverdueNotifications.tsx` convention), rendering per-dependency: `TaskStatusBadge`, `CriticalityBadge
      value={dep.dep_criticality}`, the dependency's segment name, and a `Button size="small" type="link"`
      labeled "Перейти к задаче". Cap the panel's height with scroll for tasks with many dependencies.
- [x] 2.2 For soft-deleted dependencies, render the popover's dependency row as clearly deleted (no navigate
      button offered).
- [x] 2.3 In `PlanningPage.tsx`, extend the existing `location.state.jumpTaskId` / `useTaskById` / `useEffect`
      navigation pattern (currently only opens `AssignmentModal` for the Journal → Planning transition) so it can
      also open `TaskModal` for a plain task-id navigation with no associated date. Implemented as a sibling
      `depJumpTaskId` state + `useTaskById` + `useEffect` (same resolve-then-open shape) rather than overloading
      `location.state`, since this navigation never crosses a route — it happens while already on `PlanningPage`.
- [x] 2.4 Wire the popover's "Перейти к задаче" button to: first attempt the Level 1 DOM scroll+highlight; if the
      row isn't found, invoke the extended jump mechanism from 2.3 to open `TaskModal` for that dependency task.
- [x] 2.5 Ensure `TaskModal`'s `existingDepIds` is correctly populated when opened via this fallback path — merge
      the jumped-to task id into the `taskIds` array already passed to `useTaskDeps` rather than issuing a second
      query.
- [x] 2.6 If `dep.dep_is_deleted` is true, skip the jump/`TaskModal` attempt entirely and show the "задача
      удалена" message directly (consistent with 1.6 and 2.2). Implemented at the badge level: deleted entries in
      the popover never render a navigate button at all, so `handleDepNavigate`/the jump path is structurally
      unreachable for them (stronger guarantee than a runtime check).

## 3. Level 3 — Dependency graph view

- [x] 3.1 Add `reactflow` (`@xyflow/react`) and `dagre` to `frontend/package.json`. Also added `@types/dagre` as
      a dev dependency (dagre ships no bundled types) — required for `tsc -b` to pass.
- [x] 3.2 Add `get_dependency_graph_for_team(conn, team_id)` to `db/__init__.py`: one query for nodes (`id, name,
      task_status, criticality` from `tasks WHERE team_id = ? AND is_deleted = 0`), one query for edges (`task_id,
      dep_id` from `task_dependencies` joined to both `tasks`, filtered `is_deleted = 0` on both sides), returning
      `{nodes: [...], edges: [...]}`.
- [x] 3.3 Add `GET /api/tasks/{team_id}/dependency-graph` in `support_planner.py`, returning the DAO result as-is;
      no role restriction beyond standard login (read-only, available to every role).
- [x] 3.4 Add `useDependencyGraph(teamId, enabled)` to `frontend/src/hooks/usePlanningData.ts`
      (`queryKey: ['dependency-graph', teamId]`), gated by `enabled` so the payload is only fetched when the
      graph view is actually open.
- [x] 3.5 Create `frontend/src/pages/planning/DependencyGraphModal.tsx` (lazy-loaded via `React.lazy`): a
      full-screen antd `Modal` containing a `ReactFlow` canvas; compute node positions via `dagre` layout in a
      `useMemo` keyed on the fetched nodes/edges; a custom node renderer reuses `CriticalityBadge`/
      `TaskStatusBadge` for consistent coloring/status display.
- [x] 3.6 Wire graph node clicks to the same jump-to-`TaskModal` mechanism built in task 2.3/2.4 (factor into a
      small shared helper/hook if that avoids duplicating the resolve-then-open logic). Node click closes the
      graph modal and sets `depJumpTaskId` directly (skips the DOM-scroll attempt, since the table isn't visible
      behind a full-screen graph modal).
- [x] 3.7 Add a "Граф зависимостей" button to `PlanningPage.tsx`'s toolbar (near the "Добавить работу" button),
      gated only on a team being selected, opening `DependencyGraphModal`.
- [x] 3.8 Import `@xyflow/react`'s stylesheet in the new modal component (bundled by Vite, not loaded from a
      CDN — consistent with the self-hosting rule).

## 4. Verification

- [x] 4.1 Manually verify Level 1: a task with `done`, `pending`, `cancelled`, and `deleted` dependencies shows
      all four badge kinds; clicking a dependency whose row is on-screen scrolls and highlights it; clicking one
      that's filtered out shows the appropriate message. Verified live (Playwright against team 2, task 3, which
      has real `done`/`pending` dependency data): the green "✔ выполнено: 3" badge renders next to the "⏳
      ожидает: 2" badge — done dependencies were previously invisible, now shown. `deleted`/`cancelled` kinds were
      not exercised against live data (no seeded fixture for them) but share the same code path and were verified
      by code inspection.
- [x] 4.2 Manually verify Level 2: the popover shows correct status/criticality/segment per dependency; "Перейти
      к задаче" opens `TaskModal` correctly for an off-screen dependency, with its dependency checklist populated.
      Verified live: clicking the done badge opened a popover listing all 3 dependencies with criticality badge +
      status check + segment name ("Сотрудники") + "Перейти к задаче" link each; clicking it opened `TaskModal`
      for that dependency (not on the current paginated page) with its "Зависит от" checklist correctly
      pre-checked for all 5 of that task's own dependencies.
- [x] 4.3 Manually verify Level 3: the graph renders every non-deleted task in a team as a node, edges match known
      dependency relationships, isolated (no-dependency) tasks still appear, and clicking a node opens that task.
      Verified live: graph modal rendered 15 nodes / 7 edges (matches `GET .../dependency-graph` response exactly,
      cross-checked via curl), edges visibly converge on the two tasks with real dependencies (task 3 and task 9),
      isolated tasks appear as unconnected nodes; clicking a node closed the graph and opened that task's
      `TaskModal`. No browser console errors observed throughout.
- [x] 4.4 Confirm no regressions in the existing dependency picker in `TaskModal` (creating/editing dependencies,
      cycle rejection) — this change must not touch that flow's behavior. Confirmed by code inspection (no lines
      in the picker's render/submit logic were touched — only the `existingDepIds` source and the modal's *open*
      trigger changed) and live: the picker's checkbox list, search, and pre-checked state all rendered correctly
      in the screenshots from 4.2/4.3.
