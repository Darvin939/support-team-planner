## Why

The team-wide "Граф зависимостей" view (`DependencyGraphModal.tsx`, shipped by the `dependency-visualization`
change) renders **every** non-deleted task in a team as a node, regardless of whether it has any dependency edges.
For a team with tens of tasks but only a handful of real dependency chains, this buries the handful of meaningful
edges among dozens of unrelated, edge-less nodes that `dagre` scatters arbitrarily — in practice the graph reads
as a tangled "web" rather than a readable chain. There's also no way to jump straight from one task's context menu
to *just its own* dependency chain, no way to edit a dependency edge without leaving the graph and reopening
`TaskModal`'s checkbox picker, and the node/edge visual styling (1px borders, ellipsis-truncated name only, weak
edge-selection color, `Position.Top`/`Position.Bottom` handles on a left-to-right `rankdir: 'LR'` layout) hasn't
been revisited since the first version shipped.

## What Changes

- A new context-menu item on each task row, in its own menu group, opens the graph scoped to **only that task's**
  connected dependency component (its ancestors and descendants), instead of the whole team.
- `GET /api/tasks/{team_id}/dependency-graph` gains an optional `task_id` query parameter that scopes the
  returned node/edge set to the connected component reachable from that task (both directions), instead of every
  task in the team.
- The default (team-wide, no `task_id`) response drops isolated nodes (tasks with zero dependency edges) — the
  main source of the "web" clutter — while the task-scoped response always includes the focal task even if it
  turns out to have no edges.
- Node styling is reworked to show name, description, criticality, and segment, with long text wrapped via
  `whiteSpace: 'pre-wrap'` / `overflowWrap: 'anywhere'` instead of single-line ellipsis.
- Node borders and edge strokes are widened (from 1px to a visibly heavier stroke) for legibility at typical zoom
  levels.
- Edges become directly editable on the canvas: connecting two nodes' handles adds a dependency edge, dragging an
  edge endpoint to a different node reconnects it, and a delete affordance on a selected edge removes it. Each
  node's connection handles are rendered as small always-visible "+" affordances instead of the current
  fully-transparent (`opacity: 0`) handles, and are repositioned to `Left`/`Right` to match the existing
  `rankdir: 'LR'` layout (they are currently `Top`/`Bottom`, a latent mismatch).
- Selecting an edge (click) highlights it with a visibly bright, high-contrast color and thicker stroke, replacing
  the current subtle default `@xyflow/react` selection style.
- Layout switches `dagre`'s `ranker` to `'longest-path'` (so every node's rank is strictly its longest-path
  distance from a source node — "parent, level-1 children, level-2 children, …" fanning left to right) with wider
  `ranksep`/`nodesep` and `smoothstep` edges, so edges route around node boxes instead of visually crossing under
  them.
- Two new backend endpoints for single-edge mutation from the graph (`POST`/`DELETE /api/task-dependency`), reusing
  the existing cycle check but now also rejecting cross-team edges — closing a pre-existing gap flagged (but left
  unfixed) by the original `dependency-visualization` change.

## Capabilities

### New Capabilities

- `dependency-graph-editor`: an interactive, task-scoped or team-scoped dependency graph view — redesigned node/
  edge styling, left-to-right ranked layout, and on-canvas creation/reconnection/deletion of dependency edges.

### Modified Capabilities

(none on record in `openspec/specs/` — the prior `dependency-visualization` change that shipped the original
read-only graph modal was never archived/synced into `openspec/specs/`, so there is no existing spec file to
delta against. This change's spec fully supersedes that graph modal's behavior going forward.)

## Impact

- **Frontend**: `frontend/src/pages/planning/DependencyGraphModal.tsx` (node renderer, layout, edge styling,
  on-canvas edit handlers, `taskId`-scoped mode), `frontend/src/pages/PlanningPage.tsx` (new context-menu group/
  item, wiring to open the modal with a `taskId`), `frontend/src/hooks/usePlanningData.ts`
  (`useDependencyGraph` gains a `taskId` param, new mutation hooks for add/remove edge), `frontend/src/index.css`
  (edge-selection highlight, handle "+" affordance styles).
- **Backend**: `db/__init__.py` (`get_dependency_graph_for_team` gains connected-component filtering by `task_id`
  and isolated-node exclusion in the team-wide case; new `add_task_dependency`/`remove_task_dependency` DAO
  functions with same-team enforcement), `support_planner.py` (`GET /api/tasks/{team_id}/dependency-graph` gains
  `task_id` query param; new `POST`/`DELETE /api/task-dependency` endpoints).
- **No schema/migration changes** — `task_dependencies` table is unchanged; this is additive query logic plus two
  thin mutation endpoints over the existing table.
- **No new role restrictions** — editing dependencies from the graph is equivalent to editing them via
  `TaskModal`'s existing checkbox picker, which today only requires being logged in (`user`+), same as any other
  task-mutation route.
