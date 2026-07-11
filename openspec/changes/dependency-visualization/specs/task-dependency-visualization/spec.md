## ADDED Requirements

### Requirement: Satisfied dependencies are visible
The system SHALL display a distinct badge for dependencies whose status is `done` and which are not soft-deleted,
in addition to the existing `deleted` / `cancelled` / `pending` badges.

#### Scenario: Task has only satisfied dependencies
- **WHEN** a task's dependencies all have `dep_status = 'done'` and `dep_is_deleted = false`
- **THEN** the planning table shows a "done" dependency badge with the count of satisfied dependencies, where
  previously no dependency badge would have been shown for this task

### Requirement: Clicking a dependency navigates to it when its row is loaded
The system SHALL, when a user clicks a dependency reference and that dependency's task row is currently rendered
in the planning table, scroll the table to that row and visually highlight it.

#### Scenario: Dependency row is on the current page
- **WHEN** a user clicks a dependency name/entry for a task whose row is currently rendered in the planning table
  (matched via the row's task id)
- **THEN** the table scrolls the matching row into view and applies a temporary visual highlight to it

#### Scenario: Dependency row is not currently rendered
- **WHEN** a user clicks a dependency entry for a task whose row is not currently rendered in the planning table
  (different page, filtered out by search, or otherwise not loaded)
- **THEN** the system does not silently fail; it SHALL fall back to the dependency-detail navigation behavior
  described below

### Requirement: Dependency mini-card preview
The system SHALL present a clickable preview of a dependency's status, criticality, and segment before the user
navigates to it.

#### Scenario: Opening a dependency preview
- **WHEN** a user clicks a dependency badge on a task with one or more dependencies
- **THEN** a panel opens showing, for each dependency: its status, its criticality, its segment, and an action to
  navigate to that dependency's task

#### Scenario: Preview for a soft-deleted dependency
- **WHEN** a dependency referenced by a task has been soft-deleted
- **THEN** the preview clearly indicates the dependency no longer exists (e.g. "задача удалена") and does not
  offer a navigate action that would open a non-existent task

### Requirement: Navigating to a dependency not currently loaded opens its detail view
The system SHALL open the dependency task's detail view directly when the user requests navigation to a
dependency whose row is not part of the currently rendered/loaded table state, provided the dependency task
exists and is not soft-deleted.

#### Scenario: Navigate action for an off-screen, non-deleted dependency
- **WHEN** a user triggers the navigate action for a dependency task that is not currently rendered in the table
  and is not soft-deleted
- **THEN** the system opens that dependency task's detail/edit view directly, without requiring the user to
  manually locate it via search or pagination

#### Scenario: Navigate action for a soft-deleted dependency
- **WHEN** a user triggers the navigate action for a dependency task that has been soft-deleted
- **THEN** the system informs the user the task has been deleted instead of attempting to open a detail view for
  it

### Requirement: Team-wide dependency graph view
The system SHALL provide a view that visualizes all tasks in a team and the dependency edges between them as a
directed graph, with each node indicating the task's status and criticality.

#### Scenario: Opening the dependency graph
- **WHEN** a user opens the dependency graph view for a team
- **THEN** the system displays every non-deleted task in that team as a node and every dependency relationship
  between two non-deleted tasks in that team as a directed edge, laid out automatically

#### Scenario: Navigating from a graph node
- **WHEN** a user clicks a task node in the dependency graph view
- **THEN** the system opens that task's detail/edit view, using the same navigation behavior as clicking a
  dependency's navigate action elsewhere in the planning UI

#### Scenario: Task with no dependency relationships
- **WHEN** a team's dependency graph is opened and a task has no incoming or outgoing dependency edges
- **THEN** that task still appears as a node in the graph view

### Requirement: Dependency graph access is not role-restricted
The system SHALL make the dependency graph view available to any authenticated user regardless of role, since it
is a read-only view of existing data.

#### Scenario: Non-editor role opens the graph
- **WHEN** a user with the base `user` role (not `editor` or `admin`) opens the dependency graph view for a team
  they can access
- **THEN** the view loads successfully without a permission error
