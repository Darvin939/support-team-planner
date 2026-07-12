## ADDED Requirements

### Requirement: Planning table columns behave identically after extraction
The Planning page's table (task-name column with context menu/dependency badges/status dropdown, plus per-date
schedule-chip columns) SHALL render and behave identically whether its column definitions live inline in
`PlanningPage.tsx` or in an extracted module.

#### Scenario: Task-name column context menu unchanged
- **WHEN** a user right-clicks a task row's name cell
- **THEN** the same context menu (priority move to start/end of tier, etc.) appears, offering the same items as
  before the extraction

#### Scenario: Dependency badges unchanged
- **WHEN** a task has dependencies
- **THEN** the same dependency badge(s) render in the name column, identical to pre-extraction behavior

#### Scenario: Status/priority dropdown unchanged
- **WHEN** a user interacts with the status or priority control in the name column
- **THEN** the same options are offered and the same mutations fire as before extraction

#### Scenario: Schedule-chip columns unchanged
- **WHEN** the table renders per-date columns for the selected date range
- **THEN** each date column shows the same assignment chips, with the same drag-and-drop and click behavior as
  before extraction
