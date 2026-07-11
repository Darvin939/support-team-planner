## Context

`task_dependencies` (an arbitrary DAG within a team, cycle-checked server-side via `has_dependency_cycle`) is
fully modeled in the DB/API layer but the only UI surface today is `DepBadge`
(`frontend/src/components/planningBadges.tsx:39-60`) — a colored pill wrapped in a plain-text antd `Tooltip`. It
buckets a task's dependencies into `deleted` / `cancelled` / `pending` (anything not `done`/`cancelled`); `done`
dependencies are never shown. There is no click-through to a dependency, no preview of its status/criticality,
and no way to see the shape of a long dependency chain across a team.

The planning table (`PlanningPage.tsx`) already has two relevant precedents this design builds on rather than
reinventing:
- Every `<tr>` carries `data-task-row-id={task.id}` (set via `onRow`, `PlanningPage.tsx:630`), and
  `useTaskRowDrag.ts` already queries rows via
  `document.querySelectorAll('[data-planning-grid] .ant-table-tbody tr[data-task-row-id]')` — the same selector
  root this change reuses for scroll-to-row.
- A `location.state: { jumpTaskId, jumpDate }` → `useTaskById` → `useEffect` pattern already opens
  `AssignmentModal` for a task that isn't part of the currently loaded table state (used by the Journal →
  Planning transition, `PlanningPage.tsx` ~lines 103, 202-215). This is the existing "open a task the current
  page doesn't have loaded" mechanism and is reused (not duplicated) for opening `TaskModal` from a dependency
  popover or graph node.
- `OverdueNotifications.tsx` establishes the `Popover` (click-triggered rich panel) convention already used
  elsewhere in this codebase, as opposed to `Tooltip` (passive hover text) — this change follows that precedent
  for the dependency mini-card rather than inventing a new interaction pattern.

## Goals / Non-Goals

**Goals:**
- Make a dependency's status (including "satisfied"/`done`, currently invisible) visible at a glance.
- Let a user go from "this task depends on X" to actually looking at X in one or two clicks, whether or not X is
  currently rendered in the table.
- Give teams with non-trivial dependency chains a single overview (the graph) instead of forcing them to click
  through badges one at a time.
- Reuse existing conventions (`data-task-row-id` lookup, the `jumpTaskId` pattern, `Popover` for rich hover
  panels, antd tokens for coloring) rather than introducing parallel mechanisms.

**Non-Goals:**
- No changes to how dependencies are *created or edited* — the `TaskModal` checkbox picker and
  `set_task_dependencies`/`has_dependency_cycle` logic are untouched.
- No new permission tiers — this is entirely read-only visualization, available to every logged-in role like any
  other `GET` endpoint.
- No pagination/virtualization of the dependency graph at v1 — team-scoped task counts in this domain are
  realistically tens to low hundreds, not thousands.
- No attempt to fix or paper over the pre-existing latent gap where `has_dependency_cycle` /
  `set_task_dependencies` don't enforce same-team dependencies at the DB layer (see Risks below) — out of scope
  for a visualization-only change.

## Decisions

### 1. Extend `get_all_deps_for_team` instead of adding a parallel endpoint for popover data
`get_all_deps_for_team` (`db/__init__.py:811`) already returns per-edge rows scoped to the currently-loaded
`task_ids`. Adding `dep.criticality`, `dep.segment_id`, and a joined segment name to its existing `SELECT` is a
pure additive change (no new query shape, no new round trip) and keeps `useTaskDeps`'s existing cache key
(`['task-deps', teamId, taskIds]`) valid for both the badge count and the popover content. Alternative considered
— a dedicated `/api/task/{id}/deps-detail` endpoint per dependency — was rejected: it would mean N extra requests
when a task has multiple dependencies, against one already-batched call today.

### 2. Reuse the `jumpTaskId` pattern for "open a dependency not on the current page/filter" instead of a new state variable
`PlanningPage.tsx` already solves "open a task by id that the currently loaded table state doesn't have a row
for" via `location.state.jumpTaskId` + `useTaskById` + a `useEffect` that opens `AssignmentModal` once the query
resolves. This change extends that same mechanism to also support opening `TaskModal` (for a dependency, no
`jumpDate` involved) rather than adding a second, differently-shaped piece of state that solves the identical
problem. This keeps "resolve task by id, then open the right modal" as one pattern in the codebase instead of
two.

### 3. `Popover` (click) replaces `Tooltip` (hover) on `DepBadge`
Following the `OverdueNotifications.tsx` precedent exactly (`open`/`onOpenChange` state, `trigger="click"`,
`placement="bottomLeft"`). A click-triggered panel is more appropriate than hover here because the panel now
contains an actionable button ("Перейти к задаче"), and hover-triggered actionable UI is inconsistent on
touch/tablet input and awkward to click without the panel closing.

### 4. Dependency graph: `reactflow`/`@xyflow/react` + `dagre`, not `@antv/g6`
Both are viable DAG-rendering options for React. `reactflow` renders each node as a real React component, which
means `CriticalityBadge`/`TaskStatusBadge` (existing components) can be reused directly for node content and
coloring — consistent with this codebase's "antd tokens + inline styles, no canvas drawing" convention. `g6` is
canvas-based with its own imperative rendering/interaction model, better suited to graphs with thousands of nodes
needing canvas-level performance — not this domain's scale (team task backlogs: tens to low hundreds of tasks).
`dagre` performs one-shot hierarchical layout for a DAG, which fits directly since the graph is already guaranteed
acyclic by `has_dependency_cycle` — no cycle-breaking heuristics needed in the layout step, a real simplification
this design gets "for free" from an existing server-side guarantee.

`@xyflow/react` ships its own stylesheet (`@xyflow/react/dist/style.css`). This is the one accepted exception to
the "no separate stylesheet beyond `index.css`" convention noted in `CLAUDE.md` — it's a vendored library's CSS,
bundled by Vite at build time like the rest of `node_modules`, not fetched from a CDN at runtime, so it doesn't
violate the self-hosting rule, it just isn't hand-rolled.

The graph modal component is loaded via `React.lazy`, so the `reactflow`/`dagre` bundle cost is only paid when a
user actually opens "Граф зависимостей", not on every `PlanningPage` load.

### 5. New `get_dependency_graph_for_team` DAO function + `GET /api/tasks/{team_id}/dependency-graph` endpoint
The graph needs the *whole* team's tasks and edges in one shot, which `get_all_deps_for_team` can't provide (it
requires a `task_ids` filter and returns per-edge denormalized rows, not a compact node/edge list). Two
queries — one for nodes (`id, name, task_status, criticality` from `tasks WHERE team_id = ? AND is_deleted = 0`),
one for edges (`task_id, dep_id` from `task_dependencies` joined to both `tasks`, same `is_deleted = 0` filter) —
avoid N+1 while keeping the response shape (`{nodes, edges}`) minimal; node metadata (name/status/criticality) is
carried once per node rather than repeated on every edge.

### 6. Row highlight uses a `td`-level CSS animation with an inline-set color, not a hardcoded box-shadow
`index.css` already documents (in the comment above `.assignment-drag-over`/`.assignment-drag-invalid`) why
highlight colors must be set inline from the live theme token rather than hardcoded in CSS: a static color can't
adapt to light/dark theme. The same reasoning applies to the new `.task-row-highlight-pulse` class. It's also
documented (comment above `.task-row-drag-indicator`) that per-cell backgrounds (`getCellTint`) paint over a
`<tr>`-level `box-shadow`, so the pulse animation must target `td` elements directly, not the row.

## Risks / Trade-offs

- **[Risk]** A dependency task in a *different* team is theoretically reachable — `has_dependency_cycle` and
  `set_task_dependencies` don't themselves enforce `task_id`/`depends_on_task_id` share a `team_id`, and
  `get_all_deps_for_team`'s join on `tasks dep` has no team filter on that side.
  **→ Mitigation**: not fixed by this change (pre-existing, out of scope). The popover/jump fallback degrades
  gracefully: `useTaskById(teamId, depId)` is itself team-scoped, so a cross-team dependency simply resolves to
  `null` and the UI falls back to the "not found" message rather than crashing. Flagged here for future
  awareness, not blocking.
- **[Risk]** A soft-deleted dependency task can't be resolved via `useTaskById` (excluded by `is_deleted = 0` in
  the underlying task list query), so the `TaskModal`-open fallback would silently fail if attempted.
  **→ Mitigation**: the click handler checks `dep.dep_is_deleted` synchronously (already known from the badge's
  own data, no extra fetch) and shows a "задача удалена" message directly, skipping the `TaskModal` fallback
  attempt entirely for deleted dependencies.
- **[Risk]** Bundle size growth from `reactflow` + `dagre` (roughly 150-250KB min before gzip).
  **→ Mitigation**: `React.lazy`-load the graph modal so the cost is paid only when a user opens it, not on every
  `PlanningPage` load.
- **[Risk]** Isolated nodes (tasks with no dependency edges at all) or multiple disconnected dependency
  components may lay out awkwardly under `dagre`'s single-DAG layout assumptions.
  **→ Mitigation**: acceptable at v1 (dagre places each disconnected component/isolated node in its own rank);
  documented as a layout-polish item to revisit only if it looks visually broken in practice, not a blocker.

## Migration Plan

No data migration — every change is additive (new SELECT columns, one new read endpoint, new frontend files/
components). Deployable and revertible independently per level:
1. **Level 1** (done-badge + click-to-scroll-highlight): ships alone, no dependency on Level 2/3.
2. **Level 2** (Popover + `TaskModal` fallback): depends on Level 1's `DepBadge` prop shape change
   (`names: string[]` → `deps: {id, name}[]`) and the widened `TaskDep` backend fields — lands after Level 1.
3. **Level 3** (graph view): fully additive (new endpoint, new DAO function, new npm dependency, new modal
   component, new toolbar button) — can land independently of Level 2 once Level 1's row-lookup/jump conventions
   exist, since the graph's node click reuses the same jump mechanism.

Rollback is simply reverting the relevant commit(s) per level — no schema changes to undo.

## Open Questions

- Exact wording for the "not found" navigation message(s) — left to implementation, should stay consistent with
  existing Russian-language UI copy conventions (see `DepBadge`'s existing labels).
- Whether the graph view gets a secondary entry point from within `TaskModal` (pre-centered on the open task) —
  noted as a nice-to-have in the proposal's scope but not required for Level 3's initial ship; sequence after the
  base graph modal works.
