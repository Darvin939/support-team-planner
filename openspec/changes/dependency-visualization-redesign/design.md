## Context

The current implementation (`frontend/src/pages/planning/DependencyGraphModal.tsx`) opens from a single toolbar
button on `PlanningPage.tsx` and always fetches `GET /api/tasks/{team_id}/dependency-graph`
(`db.get_dependency_graph_for_team`, `db/__init__.py:865-884`), which returns **every** non-deleted task in the
team as a node plus every dependency edge among them. `layout()` feeds this straight into `dagre` with
`rankdir: 'LR'`, `nodesep: 24`, `ranksep: 80` and default `ranker` (network-simplex). The custom `TaskGraphNode`
renders a fixed `220x56` box with a 1px border, `CriticalityBadge` + `TaskStatusBadge` + an ellipsis-truncated
name; `Handle`s are `Position.Top`/`Position.Bottom` with `opacity: 0` (invisible, and oriented for a top-to-bottom
layout despite `rankdir: 'LR'` — a pre-existing mismatch). `nodesDraggable`/`nodesConnectable` are both `false`;
clicking a node calls `onNavigate` which closes the modal and jumps to that task via the existing
`depJumpTaskId`/`useTaskById` pattern (`PlanningPage.tsx`).

Dependencies themselves are stored as a plain edge list (`task_dependencies(task_id, depends_on_task_id)`) with no
per-edge metadata. The only existing write path is `set_task_dependencies(conn, task_id, dep_ids)`
(`db/__init__.py:834-841`), which **replaces the entire dependency list for one task** in one transaction, called
from `POST /api/task` (`support_planner.py:403-430`) alongside `has_dependency_cycle` — itself BFS-only, with no
same-team check (`db/__init__.py:844-862`; the original `dependency-visualization` design.md flagged this as a
known, unfixed risk).

Because every task in the team becomes a node whether or not it has any edges, teams with tens of tasks and only a
handful of real dependency chains end up with a `dagre` layout dominated by disconnected singleton nodes — this is
the concrete cause of the "паутина" (web) complaint, not a `dagre` tuning problem alone.

## Goals / Non-Goals

**Goals:**
- Let a user jump from one task's context menu straight to a graph scoped to *that task's own* connected
  component (ancestors + descendants), not the whole team.
- Make the team-wide graph itself less noisy by excluding tasks with no dependency edges at all.
- Redesign node content/styling to show description and segment, with correct text wrapping for long values.
- Make dependency edges directly editable on the canvas (add/reconnect/delete), backed by real endpoints instead
  of round-tripping through `TaskModal`'s full task-save flow.
- Fix the `Handle` orientation mismatch (`Top`/`Bottom` on an `LR` layout) as part of making handles visible and
  interactive.
- Produce a strictly leveled left-to-right layout (parent → level-1 → level-2 → …) so edges don't visually cross
  under node boxes.

**Non-Goals:**
- No change to `TaskModal`'s existing checkbox-based dependency picker — it remains a valid, equivalent way to
  edit dependencies; the graph becomes a second entry point onto the same underlying data, not a replacement.
- No per-edge metadata (labels, types) — `task_dependencies` stays a plain edge table; this change only adds two
  thin mutation endpoints over it.
- No change to cycle-detection algorithm (`has_dependency_cycle` BFS stays as-is) beyond adding a same-team check
  alongside it.
- No virtualization/pagination of the graph canvas — team-scoped task counts remain tens to low hundreds; explicit
  node-count guardrails are out of scope for this pass (see `openspec/changes/dependency-visualization/design.md`'s
  original non-goal, still true).
- No offline/optimistic canvas edits beyond what TanStack Query's mutation + invalidate cycle already gives every
  other mutation in this codebase.

## Decisions

### 1. Task-scoped graph via a query parameter on the existing endpoint, not a new route
`GET /api/tasks/{team_id}/dependency-graph?task_id=<id>` extends the existing endpoint rather than adding a
parallel `GET /api/tasks/{task_id}/related-dependency-graph`. The team_id path segment is still required (matches
every other `/api/tasks/{team_id}/...` route in the file) and is validated against the task's actual team; `task_id`
becomes an additional filter applied server-side. This keeps one endpoint, one DAO function
(`get_dependency_graph_for_team(conn, team_id, task_id=None)`), and one frontend hook
(`useDependencyGraph(teamId, enabled, taskId?)`) instead of maintaining two near-duplicate code paths — consistent
with Decision 1 in the original `dependency-visualization` design.md ("extend, don't add a parallel endpoint").

When `task_id` is provided, the DAO does two BFS walks over `task_dependencies` from that task — one following
`depends_on_task_id` edges outward (ancestors: what this task depends on, transitively) and one following
`task_id` edges outward (descendants: what depends on this task, transitively) — unions the visited id sets plus
the focal task itself, and filters both the node and edge queries to that id set. This is the same shape of
BFS already used by `has_dependency_cycle`, just walked in both directions and collecting visited nodes instead of
checking reachability.

### 2. Isolated-node exclusion only applies to the unscoped (team-wide) query
When `task_id` is `None`, the node query adds `AND id IN (SELECT task_id FROM task_dependencies UNION SELECT
depends_on_task_id FROM task_dependencies)` scoped to the team, dropping tasks with zero edges. When `task_id` is
provided, the focal task is always included even if it has no edges (so the graph never opens empty for a
just-created task with no dependencies yet) — the exclusion only fixes the "pautina" problem in the general
overview, it isn't relevant once a single task's component is the whole point of the view.

### 3. New context-menu group, reusing the existing `Dropdown`/`menuItems` construction
`PlanningPage.tsx`'s per-row `Dropdown` (`trigger={['contextMenu']}`, built in the `infoColumn.render` closure
around line 396-424) already assembles `menuItems` as groups (`status-group`, `priority-group`). A new
`graph-group` (label "Граф", single child `{ key: 'graph', label: 'Граф зависимостей по этой работе' }`) is added
unconditionally (no terminal-status gate — viewing a done/cancelled task's dependency graph is still meaningful),
and `handleMenuClick` gets a new `key === 'graph'` branch that opens `DependencyGraphModal` with `taskId: task.id`
instead of navigating. This reuses the exact menu-group pattern already established for `priority-group`/
`status-group` rather than introducing a second interaction mechanism (e.g. a toolbar button per row).

### 4. Single-edge mutation endpoints instead of round-tripping through `POST /api/task`
`POST /api/task` requires `name`/`criticality`/`segment_id` in every call (`support_planner.py:403-430`) because
it's a full upsert; reusing it for a single edge add/remove from the graph canvas would mean the graph node payload
must carry every editable task field just to resubmit them unchanged, and risks a lost-update race if another
tab/user edited the task's name/description between the graph loading and the edge edit being submitted. Instead:

- `POST /api/task-dependency` — body `{task_id, depends_on_task_id}` — validates both tasks exist, share a
  `team_id`, and are not soft-deleted; runs the existing `has_dependency_cycle(task_id, [depends_on_task_id])`
  check (400 on cycle, matching `POST /api/task`'s existing error message "Обнаружена циклическая зависимость");
  on success calls a new `db.add_task_dependency(conn, task_id, depends_on_task_id)` (`INSERT OR IGNORE`, single
  edge — same statement `set_task_dependencies` already uses per-row, factored out for reuse by both).
- `DELETE /api/task-dependency` — body `{task_id, depends_on_task_id}` — new `db.remove_task_dependency(conn,
  task_id, depends_on_task_id)` (`DELETE FROM task_dependencies WHERE task_id = ? AND depends_on_task_id = ?`).
- Both reuse the same terminal-task guard `POST /api/task` already applies (`task_status in ('done',
  'cancelled')` or `is_deleted` → 400 "Нельзя редактировать завершённую или отменённую задачу"), checked against
  `task_id` (the dependent task whose edge list is changing) — matching the existing rule that a terminal task
  blocks all task/assignment edits.
- Role requirement: same as `POST /api/task` today — logged in (`user`+), no additional restriction. This mirrors
  the fact that any `user` can already add/remove dependencies on a non-terminal task via `TaskModal`'s checkbox
  picker; the graph is an alternate UI onto the same permission surface, not a more/less privileged one.

**Alternative considered**: a single `PATCH /api/task/{task_id}/dependencies` with `{add: [...], remove: [...]}`
batch body. Rejected for v1 — the canvas only ever performs one edge operation per user gesture (one connect, one
delete, one reconnect = remove+add), so a batch endpoint would add request-shaping complexity (partial failure
semantics: what happens if `add` succeeds but `remove` hits a cycle?) without a real corresponding UI need. Two
single-purpose endpoints keep each request atomic and each error unambiguous.

### 5. Same-team enforcement lands here, not as a separate follow-up
The original `dependency-visualization` design.md flagged (Risk, item 1) that `has_dependency_cycle`/
`set_task_dependencies` never verified `task_id`/`depends_on_task_id` share a `team_id`, and deferred the fix as
out of scope for a read-only visualization change. This change *is* the first place new dependency edges get
created through a UI that doesn't already imply same-team by construction (`TaskModal`'s checkbox picker only ever
lists same-team candidates to begin with), so the new `POST /api/task-dependency` endpoint is the right, narrow
place to finally add the check — `SELECT team_id FROM tasks WHERE id IN (?, ?)` and comparing the two — rather than
retrofitting it onto the untouched `set_task_dependencies` bulk path.

### 6. `dagre` `ranker: 'longest-path'` + wider spacing + `smoothstep` edges, not a hand-rolled layered layout
Requirement 6 ("parent, level-1 children, level-2 children, … strictly left to right") is exactly what dagre's
`longest-path` ranker guarantees: every node's rank equals the length of the longest path from a source node to it,
so a node can never end up in an earlier rank than any of its predecessors demand — unlike the default
`network-simplex`/`tight-tree` rankers, which minimize total edge length/width and can compress two nodes at
different BFS depths into the same rank if that produces a more compact drawing. Switching the existing
`g.setGraph({ rankdir: 'LR', nodesep: 24, ranksep: 80 })` call (`DependencyGraphModal.tsx:50`) to add `ranker:
'longest-path'`, raise `ranksep` (e.g. 120) and `nodesep` (e.g. 40) to fit the wider redesigned node, and switching
edges from the default bezier `type` to `type: 'smoothstep'` (right-angle routing that steps around intervening
rank columns instead of arcing through them) directly addresses "edges shouldn't pass under blocks" without
introducing a second layout library or hand-rolled BFS-column algorithm. This stays proportionate to the
codebase's existing "one library, tune its options" approach (the same reasoning the original design.md used to
pick `dagre` over a custom implementation in the first place).

**Alternative considered**: computing BFS levels manually and only using `dagre`/a barycenter pass for in-rank
ordering. Rejected — `longest-path` already produces exactly the requested level structure for both the
team-wide and task-scoped graphs (a DAG, guaranteed acyclic by `has_dependency_cycle`), so a custom leveling pass
would duplicate what the existing dependency already provides for free, for graphs of this scale (tens of nodes).

### 7. Handles: visible "+" affordance, repositioned to `Left`/`Right`, `nodesConnectable: true`
The two invisible `Handle`s become visible small circular buttons (a "+" icon, using existing antd token colors)
at `Position.Left` (target — incoming "depends on") and `Position.Right` (source — outgoing "is depended on by"),
matching the `rankdir: 'LR'` flow direction and fixing the current `Top`/`Bottom` mismatch. `ReactFlow`'s
`onConnect` handler fires the new `POST /api/task-dependency` mutation (`source` node = `depends_on_task_id`,
`target` node = `task_id`, consistent with the existing edge convention `id: '${dep_id}-${task_id}'`,
`source: dep_id`, `target: task_id`). Dragging an existing edge's endpoint to a new node uses `onReconnect`
(implemented as remove-old + add-new, i.e. `DELETE` then `POST`, since there is no atomic "move edge" endpoint and
none is needed at this scale). A selected edge shows a small delete ("×") button at its midpoint (a custom edge
component using `EdgeLabelRenderer`), calling `DELETE /api/task-dependency` — matching requirement 4's "delete
directly on the graph" while keeping deletion an explicit, deliberate click (no accidental delete-on-select).
`onConnect`/`onReconnect` failures (cycle, cross-team, terminal-task) surface via the existing antd `message.error`
convention used elsewhere in `PlanningPage.tsx`'s mutations, and the canvas optimistically does nothing until the
mutation resolves (React Query invalidates `['dependency-graph', ...]` on success, which is what actually redraws
the new/removed edge — no local ReactFlow state mutation on `onConnect` itself, avoiding a client/server state
split).

### 8. Edge selection highlight via a custom edge component, not global CSS override
`@xyflow/react`'s built-in `.selected` class already darkens/dashes the path slightly, which requirement 5 calls
"есть, но слабое". Rather than fighting the library's default styling with a global `!important` CSS override
(fragile against library upgrades), a small custom edge component reads its own `selected` prop and sets
`stroke: token.colorPrimary` (or another suitably high-contrast token) at a visibly increased `strokeWidth` (e.g.
1.5px default → 3px selected) directly in its inline `style`, following this codebase's established convention of
inline-styling from live theme tokens rather than static CSS (the same reasoning `index.css`'s comments already
document for `.assignment-drag-over`/`.task-row-highlight-pulse`).

## Risks / Trade-offs

- **[Risk]** `onReconnect` implemented as remove+add is not atomic — if the `POST` (add) fails after the `DELETE`
  (remove) already succeeded (e.g. the new endpoint creates a cycle), the edge disappears entirely instead of
  reverting to its original position.
  **→ Mitigation**: order the calls as add-then-remove instead (create the new edge first; only remove the old one
  after the add succeeds) so a failed add leaves the original edge intact and simply surfaces the error — cheap,
  correct-by-construction fix, no rollback logic needed.
- **[Risk]** BFS-based connected-component queries for a large, densely-connected team graph could be slower than
  the current flat two-query approach, since it now runs iteratively (one round trip per BFS layer, same pattern
  `has_dependency_cycle` already uses in Python rather than a recursive SQL CTE).
  **→ Mitigation**: acceptable at this scale (tens to low hundreds of tasks per team, matching every other
  non-goal in this domain); revisit with a recursive CTE only if it becomes measurably slow in practice.
- **[Risk]** Excluding isolated nodes from the team-wide graph could surprise a user who expects to see literally
  every task (e.g. to confirm a specific task really has no dependencies).
  **→ Mitigation**: the task-scoped view (this change's primary new entry point) always shows the focal task even
  if isolated, so "does this task have any dependencies" is answerable there; the team-wide view's stated purpose
  is overview of *chains*, not a task inventory (that's what the planning table already is).
- **[Risk]** Making handles always-visible on every node adds visual noise to nodes that a viewer only wants to
  glance at (read-only viewing use case, e.g. opening the graph just to check status).
  **→ Mitigation**: acceptable trade-off per requirement 4's explicit ask; handles are small and low-contrast until
  hovered/focused, consistent with how the rest of this app treats hover-revealed affordances (e.g. row drag
  handles in the planning table).

## Migration Plan

No schema changes — additive query logic (`task_id` filter, isolated-node exclusion) and two new endpoints over
the existing `task_dependencies` table. Deployable and revertible independently per level, mirroring the original
change's level structure:
1. **Level 1** (backend: `task_id`-scoped query + isolated-node exclusion + `POST`/`DELETE /api/task-dependency` +
   same-team check): ships alone, purely additive API surface, no frontend dependency.
2. **Level 2** (node/edge visual redesign: description/segment content, thicker borders/strokes, `smoothstep` +
   `longest-path`, brighter edge-selection): depends only on the existing team-wide endpoint's current response
   shape plus the extra `description`/`segment_id`/`segment_name` node fields Level 1 adds.
3. **Level 3** (context-menu entry point + task-scoped modal + on-canvas connect/reconnect/delete): depends on
   Level 1's endpoints and Level 2's visual/layout groundwork; is the user-facing capstone of this change.

Rollback is reverting the relevant commit(s) per level — no data migration to undo.

## Open Questions

- Exact icon/visual treatment for the handle "+" affordance (antd icon vs. hand-drawn) — left to implementation,
  should stay visually consistent with existing small icon-buttons in `PlanningPage.tsx`'s row actions (e.g. the
  `HolderOutlined` drag handle).
- Whether the task-scoped graph should visually distinguish "ancestors" (left of focal task) from "descendants"
  (right of focal task) beyond the layout's natural left-to-right position (e.g. a subtle background tint per
  side) — nice-to-have, not required for the initial ship of Level 3.
