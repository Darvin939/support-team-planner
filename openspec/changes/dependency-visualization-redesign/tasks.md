## 1. Backend — graph query scoping and node fields

- [x] 1.1 Extend `get_dependency_graph_for_team(conn, team_id, task_id=None)` in `db/__init__.py`: extend the
      node `SELECT` to also include `description`, `segment_id`, and `seg.name AS segment_name` (join `segments
      seg ON tasks.segment_id = seg.id`).
- [x] 1.2 When `task_id` is `None`, restrict the node query to tasks that appear in at least one
      `task_dependencies` row for the team (either side of the edge) — excludes isolated tasks from the
      team-wide graph.
- [x] 1.3 When `task_id` is provided, implement a bidirectional BFS over `task_dependencies` (ancestors via
      `depends_on_task_id`, descendants via `task_id`, same iterative style as `has_dependency_cycle`), union the
      visited ids with the focal task id, and filter both the node and edge queries to that id set. Always
      include the focal task even if it has no edges.
- [x] 1.4 Add `GET /api/tasks/{team_id}/dependency-graph`'s optional `task_id: Optional[int] = None` query param
      in `support_planner.py`, passed through to the DAO call; extend the response's node fields to include the
      new `description`/`segment_id`/`segment_name`.

## 2. Backend — single-edge mutation endpoints

- [x] 2.1 Add `add_task_dependency(conn, task_id, depends_on_task_id)` to `db/__init__.py` (single-row
      `INSERT OR IGNORE INTO task_dependencies ...`, factored so `set_task_dependencies` can reuse it per-row if
      convenient).
- [x] 2.2 Add `remove_task_dependency(conn, task_id, depends_on_task_id)` to `db/__init__.py`
      (`DELETE FROM task_dependencies WHERE task_id = ? AND depends_on_task_id = ?`).
- [x] 2.3 Add a same-team check usable by both new endpoints: fetch both tasks' `team_id`/`task_status`/
      `is_deleted` in one query and compare.
- [x] 2.4 Add `POST /api/task-dependency` in `support_planner.py`: body `{task_id, depends_on_task_id}`; validate
      both tasks exist and are not soft-deleted, reject if `task_id`'s task is `done`/`cancelled` (reuse the
      existing "Нельзя редактировать завершённую или отменённую задачу" message), reject cross-team pairs (400),
      run `has_dependency_cycle(task_id, [depends_on_task_id])` (400 "Обнаружена циклическая зависимость" on
      cycle), then call `add_task_dependency`.
- [x] 2.5 Add `DELETE /api/task-dependency` in `support_planner.py`: body `{task_id, depends_on_task_id}`; same
      terminal-task guard as 2.4, then call `remove_task_dependency`.
- [x] 2.6 Confirm role requirements: both new endpoints fall under the default `user`+ rank (no entry needed in
      `_ADMIN_ONLY_API_PREFIXES`/`_EDITOR_API_PREFIXES`), matching `POST /api/task`'s existing dependency-edit
      permission level.

## 3. Frontend — data layer

- [x] 3.1 Extend `useDependencyGraph` in `frontend/src/hooks/usePlanningData.ts` to accept an optional `taskId`
      param, included in both the query key (`['dependency-graph', teamId, taskId ?? null]`) and the request URL
      (`?task_id=` when present).
- [x] 3.2 Extend the graph node TypeScript shape with `description`, `segment_id`, `segment_name`.
- [x] 3.3 Add `useAddTaskDependency`/`useRemoveTaskDependency` mutation hooks (POST/DELETE `/api/task-dependency`
      via the shared `apiMutate.ts` wrapper), invalidating the `['dependency-graph', ...]` query key on success
      and surfacing errors via the existing antd `message.error` convention on failure.

## 4. Frontend — node/edge visual redesign

- [x] 4.1 Rework `TaskGraphNode` in `DependencyGraphModal.tsx`: render name, description (when present),
      `CriticalityBadge`, and segment name; apply `whiteSpace: 'pre-wrap'`, `overflowWrap: 'anywhere'` to the
      name/description text; widen the border from `1px` to a heavier stroke (e.g. `2px`); remove the fixed-height
      `NODE_HEIGHT` single-line assumption so the node can grow with wrapped text (switch to `minHeight` /
      `nodrag` content sizing as `@xyflow/react` requires for variable-height nodes).
- [x] 4.2 Reposition the two `Handle`s to `Position.Left` (target) and `Position.Right` (source), matching
      `rankdir: 'LR'`; make them visibly rendered (small circular "+" affordance using antd tokens) instead of
      `opacity: 0`.
- [x] 4.3 Add a custom edge component reading its own `selected` prop, setting a high-contrast
      `stroke: token.colorPrimary` (or equivalent) and increased `strokeWidth` when selected, versus a slightly
      heavier-than-1px default stroke when not selected; register it via `edgeTypes` and use `type: 'smoothstep'`
      routing.
- [x] 4.4 Add a delete ("×") affordance at the midpoint of a selected edge via `EdgeLabelRenderer`, wired to
      `useRemoveTaskDependency`.

## 5. Frontend — layout

- [x] 5.1 Update the `layout()` function's `dagre` `setGraph` call: add `ranker: 'longest-path'`, increase
      `ranksep`/`nodesep` to fit the redesigned node size from 4.1.
- [x] 5.2 Verify (manually, against the item-7 debug endpoint below) that a multi-level chain renders in strictly
      increasing left-to-right columns with no edge visually passing under an intervening node.

## 6. Frontend — on-canvas edge editing

- [x] 6.1 Set `nodesConnectable: true` on the `ReactFlow` element (currently `false`); implement `onConnect` to
      call `useAddTaskDependency` with `{depends_on_task_id: source, task_id: target}`.
- [x] 6.2 Implement `onReconnect` (add-new-edge first, then remove-old-edge only after the add succeeds — so a
      rejected add leaves the original edge intact rather than losing it, per the design's ordering decision).
- [x] 6.3 Wire the 4.4 delete affordance and any cycle/same-team/terminal-task error responses from 2.4/2.5 to
      antd `message.error`, with Russian copy consistent with existing error messages in this codebase.

## 7. Frontend — task-scoped entry point

- [x] 7.1 In `PlanningPage.tsx`'s per-row context-menu `menuItems` construction, add a new `graph-group` with a
      single "Граф зависимостей по этой работе" item, unconditional on task status.
- [x] 7.2 Extend `handleMenuClick` with a `key === 'graph'` branch that opens `DependencyGraphModal` with
      `taskId: task.id` (as opposed to the existing team-wide toolbar entry point, which continues to open it
      with no `taskId`).
- [x] 7.3 Thread the optional `taskId` prop through `DependencyGraphModal` to `useDependencyGraph`, and update the
      modal title to reflect scope (e.g. include the focal task's name when `taskId` is set).

## 8. Verification

- [x] 8.1 Use `GET http://localhost:5093/api/tasks/1/dependency-graph` (team 1's real data — the most complex
      graph available locally) as the manual test fixture for layout/styling verification throughout this change,
      per the request to debug against a non-trivial graph rather than seed data. Confirmed via curl: 22 nodes /
      35 edges team-wide (24 total tasks, 2 isolated), 19-node connected component for task 1.
- [x] 8.2 Manually verify the team-wide graph (no `task_id`) no longer shows isolated tasks, and that the
      remaining chains lay out left-to-right with `longest-path` ranking and no edges crossing under nodes.
      Verified live in a real browser (Playwright): tasks 21/23 (zero edges) confirmed excluded from the
      team-wide response; `longest-path` + wider spacing renders clean left-to-right columns with no crossing.
      Caught and fixed a real bug along the way: dagre's layout used a fixed `NODE_HEIGHT` estimate while the
      redesigned node rendered taller (auto-growing for wrapped description text), causing nodes in the same
      rank to visually overlap — fixed by making the node's actual height match the dagre estimate exactly
      (fixed height + internal scroll for outliers) and increasing `nodesep`.
- [x] 8.3 Manually verify the task-scoped context-menu entry: opening it for a task with both ancestors and
      descendants shows exactly its connected component; opening it for an isolated task shows just that one node.
      Verified: context-menu item opens the modal titled "Граф зависимостей — <task name>"; task 1's scoped graph
      matched its 19-node component exactly; isolated tasks 21/23 confirmed via API to return a single node with
      zero edges.
- [x] 8.4 Manually verify on-canvas editing: connecting two nodes creates a persisted edge (confirm via reload or
      the underlying `GET .../deps` data); attempting a cycle-creating connection is rejected with an error and no
      edge appears; deleting a selected edge removes it; reconnecting an edge's endpoint updates it correctly.
      Verified live: dragging from one node's right handle to another's left handle fired `POST
      /api/task-dependency` and the new edge was confirmed via the API (then cleaned up); cycle/terminal/
      cross-team rejections verified via direct endpoint calls (see 8.5/8.6); delete button (visible on a
      selected edge) wired to the same `DELETE` endpoint verified working via direct call. Reconnect
      (`onReconnect`) verified by code review (add-new-then-remove-old ordering, per the design decision) rather
      than a live drag gesture. Caught and fixed a real bug along the way: passing `nodes`/`edges` straight from
      the layout memo with no `onNodesChange`/`onEdgesChange` meant `@xyflow/react` could never apply its own
      "selected" state, so clicking an edge silently did nothing — fixed by switching to `useNodesState`/
      `useEdgesState` synced from the computed layout via an effect. That in turn surfaced a second bug: the
      delete callback closed over the mutation object directly, whose identity changes every render, which
      re-triggered the sync effect every render (infinite loop / React error #185) — fixed by reading the
      mutation through a ref so the callback stays referentially stable.
- [x] 8.5 Manually verify a cross-team connection attempt (if two teams are available in local data) is rejected.
      Verified via direct endpoint call: team 1 task depending on a team 2 task returns
      "Задачи принадлежат разным командам" (400) and no edge is created.
- [x] 8.6 Manually verify a terminal (`done`/`cancelled`) task's dependencies cannot be edited from the graph
      (connect/reconnect/delete all rejected with the existing terminal-task error message). Verified via direct
      endpoint calls in both directions (done task as the dependent side rejected; done task as the dependency
      side is allowed, matching the design's "only the dependent side's status gates the edit" rule).
- [x] 8.7 Manually verify the edge-selection highlight is clearly distinguishable from the unselected state at a
      glance, and that node borders/edge strokes read as visibly thicker than the previous 1px baseline. Verified
      live: selected edge renders at `stroke: colorPrimary`, `strokeWidth: 3.5` plus a drop-shadow glow, vs. a
      muted 2px default — clearly distinguishable in the screenshot; node borders render at a crisp 2px.
- [x] 8.8 Confirm no regressions in the existing team-wide toolbar entry point, node-click-to-navigate behavior,
      and `TaskModal`'s existing checkbox-based dependency picker (this change must not alter that flow). Verified
      live: toolbar "Граф зависимостей" button still opens the team-wide graph; clicking a node closes the graph
      and opens `TaskModal` for that task; the task's "Зависит от" checkbox picker rendered correctly and
      unaffected.
