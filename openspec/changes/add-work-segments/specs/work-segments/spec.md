## ADDED Requirements

### Requirement: Segment CRUD in Settings
The system SHALL provide a `segments` reference entity (id, unique name) manageable by an `editor`+ user from the Settings page, following the same list/create/edit/delete pattern as `blocks`/`teams`.

#### Scenario: Creating a segment
- **WHEN** an editor submits a new segment name in Settings
- **THEN** the system creates a `segments` row with that name and it becomes available for selection on tasks and block templates

#### Scenario: Duplicate segment name rejected
- **WHEN** an editor submits a segment name that already exists
- **THEN** the system returns a 400 error and does not create a duplicate row

#### Scenario: Deleting a segment still referenced by a task or block template
- **WHEN** an editor attempts to delete a segment that at least one task or block template still references
- **THEN** the system returns a 400 error and the segment is not deleted

#### Scenario: Deleting an unused segment
- **WHEN** an editor deletes a segment that no task or block template references
- **THEN** the segment is removed and no longer offered as an option

### Requirement: Default segment backfilled only for pre-existing data
On startup, the system SHALL create a default segment named "По умолчанию" and backfill it onto every pre-existing `tasks` and `block_templates` row that does not yet have a segment, so the required segment field is never left unset on upgrade. The default segment SHALL NOT be created when there is no pre-existing data to backfill — a fresh database, or one where this backfill has already run, starts with zero segments.

#### Scenario: Fresh database startup
- **WHEN** the application starts against a newly created, empty database
- **THEN** no segment is auto-created, and the segment list starts empty until a user creates one via Settings

#### Scenario: Upgrading an existing database
- **WHEN** the application starts against a pre-existing database whose `tasks`/`block_templates` rows predate the segment feature
- **THEN** a "По умолчанию" segment is created and every such row is assigned it, so no row is left with a missing segment

#### Scenario: Restarting after the upgrade backfill already ran
- **WHEN** the application restarts against a database that was already backfilled in a previous startup
- **THEN** no additional default segment is created, and any segments the user has since added or renamed are left untouched

### Requirement: Block template requires a segment
A block template SHALL have exactly one required segment, selected when the template is created or edited in Settings.

#### Scenario: Creating a block template without a segment
- **WHEN** an editor submits a new block template with no segment selected
- **THEN** the system returns a 400 error and does not create the template

#### Scenario: Creating a block template with a segment
- **WHEN** an editor submits a new block template with a segment selected
- **THEN** the template is created and tagged with that segment

### Requirement: Task requires a segment
A task SHALL have exactly one required segment, selected when the task is created, and editable afterward like any other task field.

#### Scenario: Creating a task without a segment
- **WHEN** a user submits a new task with no segment selected
- **THEN** the system returns a 400 error and does not create the task

#### Scenario: Creating a task with a segment
- **WHEN** a user submits a new task with a segment selected
- **THEN** the task is created and tagged with that segment

### Requirement: Segment narrows available block templates for assignment and auto-scheduling
When creating or editing an assignment for a task, and when auto-scheduling that task's assignments across blocks, the system SHALL offer only block templates that are both allowed for the task's team (existing team-template linkage) and tagged with the task's segment.

#### Scenario: Template matches task's segment
- **WHEN** a user opens the assignment/auto-schedule template picker for a task
- **THEN** only block templates allowed for the task's team and tagged with the task's segment are offered

#### Scenario: Template belongs to a different segment
- **WHEN** a block template is allowed for the task's team but tagged with a different segment than the task's
- **THEN** that template is not offered in the assignment/auto-schedule picker for that task

### Requirement: Segment filter on Planning task list
The Planning page task list SHALL support filtering by one or more segments, following the same UX pattern as the existing criticality and status filters.

#### Scenario: Filtering by a single segment
- **WHEN** a user selects a segment in the segment filter on the Planning page
- **THEN** only tasks tagged with that segment remain visible in the task list

#### Scenario: Clearing the segment filter
- **WHEN** a user clears the segment filter
- **THEN** tasks from all segments are shown again, subject to any other active filters
