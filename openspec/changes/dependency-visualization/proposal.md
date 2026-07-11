## Why

Task dependencies (`task_dependencies`) are fully modeled in the database and API — an arbitrary DAG within a
team, with cycle protection via `has_dependency_cycle` — but on the UI a dependency is only a passive text badge
(`DepBadge`, a colored pill with a `Tooltip` listing names). Users must manually search the table for a
dependency task to see its status or act on it. Completed (`done`) dependencies are not shown at all today, so a
task that has "cleared" its dependencies still looks the same as one that hasn't. There is no way to preview a
dependency's status/criticality without navigating away, and there is no overview for teams with long dependency
chains. This change makes dependencies a first-class, navigable part of the planning UI instead of inert text.

## What Changes

- `DepBadge` gains a `done` state (previously only `deleted`/`cancelled`/`pending` were surfaced) and each
  dependency name becomes clickable.
- Clicking a dependency name scrolls to and highlights that task's row if it is currently rendered in the
  planning table.
- The plain-text tooltip is replaced by a clickable `Popover` mini-card showing the dependency's status,
  criticality, and segment, plus a "Перейти к задаче" action.
- If the dependency's row isn't currently visible (different page, filtered out by search/status), the "Перейти к
  задаче" action opens that task directly in `TaskModal` instead of failing silently, reusing the existing
  `jumpTaskId` cross-navigation pattern already used by the Journal → Planning transition.
- A new "Граф зависимостей" view visualizes every task in a team and the dependency edges between them as a DAG
  (auto-laid-out, status/criticality-colored nodes, click-to-open), for teams with long or non-obvious dependency
  chains.
- `GET /api/tasks/{team_id}/deps` response is extended with each dependency's criticality and segment.
- A new `GET /api/tasks/{team_id}/dependency-graph` endpoint returns the full node/edge list for a team's
  dependency graph in one round trip.
- A new frontend dependency (`reactflow`/`@xyflow/react` + `dagre`) is introduced, loaded lazily only when the
  graph view is opened.

## Capabilities

### New Capabilities

- `task-dependency-visualization`: visual, navigable representation of task dependencies in the planning UI —
  status-aware badges (including satisfied/`done` dependencies), click-to-navigate to a dependency's row or
  detail modal, and a team-wide dependency graph view.

### Modified Capabilities

(none — `task_dependencies` storage, cycle detection, and the dependency-picker in `TaskModal` are unchanged;
this change only adds new read/visualization surface on top of the existing data.)

## Impact

- **Frontend**: `frontend/src/components/planningBadges.tsx` (`DepBadge`), `frontend/src/pages/PlanningPage.tsx`
  (dependency bucket rendering, jump/navigation wiring, graph entry point), `frontend/src/hooks/usePlanningData.ts`
  (`TaskDep` shape, new `useDependencyGraph` hook), `frontend/src/pages/planning/TaskModal.tsx` (jump-open target),
  new file `frontend/src/pages/planning/DependencyGraphModal.tsx`, `frontend/src/index.css` (row highlight
  animation), `frontend/package.json` (new `reactflow`/`@xyflow/react` + `dagre` dependency).
- **Backend**: `db/__init__.py` (`get_all_deps_for_team` extended, new `get_dependency_graph_for_team`),
  `support_planner.py` (`GET /api/tasks/{team_id}/deps` response extended, new
  `GET /api/tasks/{team_id}/dependency-graph`).
- **No schema/migration changes** — purely additive SELECT columns and a new read endpoint; `task_dependencies`
  table and existing dependency-editing flow in `TaskModal` are untouched.
- **No new role restrictions** — the graph view and richer previews are read-only, available to every logged-in
  role (`GET` requests are unrestricted per existing `require_login` rules).
