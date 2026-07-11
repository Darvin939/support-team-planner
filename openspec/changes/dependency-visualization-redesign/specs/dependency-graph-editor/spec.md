## ADDED Requirements

### Requirement: Task-scoped dependency graph
The system SHALL allow opening the dependency graph scoped to a single task's connected dependency component
(its transitive ancestors and transitive descendants) instead of the whole team, via a context-menu action on
that task's row, and SHALL expose this scoping as an optional `task_id` query parameter on
`GET /api/tasks/{team_id}/dependency-graph`.

#### Scenario: Opening the graph from a task's context menu
- **WHEN** a user right-clicks a task row in the planning table and selects "Граф зависимостей по этой работе"
  from its own menu group
- **THEN** the dependency graph opens showing only that task plus every task reachable from it via dependency
  edges in either direction, not every task in the team

#### Scenario: Task-scoped API response excludes unrelated tasks
- **WHEN** `GET /api/tasks/{team_id}/dependency-graph?task_id=<id>` is requested for a task that has some
  dependencies and some dependents, in a team that also has other, unrelated tasks with their own separate
  dependency chains
- **THEN** the response's `nodes`/`edges` include only the focal task and its transitive ancestors/descendants,
  and exclude the unrelated tasks and their edges entirely

#### Scenario: Task-scoped graph always includes the focal task
- **WHEN** `GET /api/tasks/{team_id}/dependency-graph?task_id=<id>` is requested for a task with zero
  dependency edges (no ancestors, no descendants)
- **THEN** the response includes exactly one node (the focal task itself) and zero edges, rather than an empty
  response

### Requirement: Team-wide dependency graph excludes isolated tasks
The system SHALL exclude tasks with zero dependency edges from the unscoped (no `task_id`) team-wide dependency
graph response, so the overview highlights actual dependency chains rather than being dominated by unrelated,
edge-less tasks.

#### Scenario: Isolated tasks are omitted from the team-wide graph
- **WHEN** `GET /api/tasks/{team_id}/dependency-graph` is requested (no `task_id`) for a team where most tasks
  have no dependency relationships and a few tasks form one or more dependency chains
- **THEN** the response's `nodes` list contains only the tasks that are part of at least one dependency edge

### Requirement: Dependency graph node content and styling
Each node in the dependency graph SHALL display the task's name, description, criticality, and segment, with
long text wrapped (not truncated) so the full content remains readable, and SHALL render with a visibly thicker
border than a 1px hairline.

#### Scenario: Long name or description wraps instead of being cut off
- **WHEN** a task node's name or description exceeds the node's visible width
- **THEN** the text wraps onto additional lines within the node (`whiteSpace: 'pre-wrap'`,
  `overflowWrap: 'anywhere'`) instead of being ellipsis-truncated to one line

#### Scenario: Node shows criticality and segment
- **WHEN** the dependency graph renders a task node
- **THEN** the node displays that task's criticality badge and segment name alongside its name and description

### Requirement: Editable dependency edges on the graph canvas
The system SHALL allow adding, reconnecting, and deleting dependency edges directly on the dependency graph
canvas, backed by dedicated single-edge mutation endpoints, subject to the same cycle-detection, same-team, and
terminal-task rules that already govern dependency edits made via the task edit form.

#### Scenario: Connecting two nodes adds a dependency
- **WHEN** a user drags a connection from one node's outgoing handle to another node's incoming handle on the
  graph canvas
- **THEN** a new dependency edge is created between those two tasks and persists (visible on reload / for other
  users)

#### Scenario: Adding a dependency edge that would create a cycle is rejected
- **WHEN** a user attempts to connect two nodes on the canvas such that the resulting edge would create a
  dependency cycle
- **THEN** the edge is not created, and an error message is shown, consistent with the existing
  "Обнаружена циклическая зависимость" error already returned when creating a cyclic dependency via the task
  edit form

#### Scenario: Adding a dependency edge across two different teams' tasks is rejected
- **WHEN** a user attempts to connect two nodes that belong to tasks in different teams
- **THEN** the edge is not created, and an error is returned

#### Scenario: Deleting an edge on the canvas
- **WHEN** a user selects a dependency edge on the graph canvas and confirms deletion
- **THEN** the corresponding dependency relationship is removed and no longer appears in the graph

#### Scenario: Reconnecting an existing edge to a different node
- **WHEN** a user drags an existing edge's endpoint from one node to a different node on the canvas
- **THEN** the original dependency edge is removed and a new dependency edge reflecting the new endpoint is
  created, subject to the same cycle/same-team checks as creating a new edge

#### Scenario: Editing dependencies of a terminal task is rejected
- **WHEN** a user attempts to add, reconnect, or delete a dependency edge where the dependent task
  (`task_id` side of the edge) is in a `done` or `cancelled` status
- **THEN** the edit is rejected with the same "Нельзя редактировать завершённую или отменённую задачу" error
  already used when editing a terminal task's other fields

### Requirement: Dependency graph connection handles
Each node in the dependency graph SHALL expose a visible affordance at its incoming and outgoing connection
points that a user can use to start creating a new dependency edge, positioned consistently with the graph's
left-to-right layout direction (incoming/target on the left, outgoing/source on the right).

#### Scenario: Connection handle is visible and positioned for left-to-right flow
- **WHEN** the dependency graph renders a node in its left-to-right layout
- **THEN** the node shows a visible connection-point affordance on its left side (incoming/target) and its right
  side (outgoing/source), rather than invisible or top/bottom-positioned handles

### Requirement: Bright edge-selection highlight
Clicking a dependency edge on the graph canvas SHALL highlight it with a visibly high-contrast color and a
noticeably thicker stroke than its unselected state.

#### Scenario: Selected edge is visually distinct from unselected edges
- **WHEN** a user clicks a dependency edge on the canvas while other edges remain unselected
- **THEN** the clicked edge renders in a distinctly brighter/higher-contrast color and thicker stroke width than
  the other, unselected edges

### Requirement: Ranked left-to-right layout
The dependency graph SHALL lay out nodes left-to-right in strict rank order, such that no node's rank is earlier
than the rank required by any of its dependency edges, so that a task's ancestors, the task itself, and its
descendants form clearly separated columns, and dependency edges SHALL route around intervening node columns
rather than visually crossing beneath them.

#### Scenario: Multi-level dependency chain lays out in ordered columns
- **WHEN** the dependency graph renders a chain where task A depends on B, and B depends on C
- **THEN** C, B, and A render in three distinct, increasing left-to-right rank positions in that order (C
  leftmost, A rightmost), consistent with the "dependency before dependent" edge direction
