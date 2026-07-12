# task-management Specification

## Purpose
TBD - created by archiving change fix-task-edit-missing-id. Update Purpose after archive.
## Requirements
### Requirement: Editing a task requires it to exist
`POST /api/task` SHALL return a 404 error when `task_id` is provided but does not refer to an existing,
non-deleted task, instead of creating a new task under a different id.

#### Scenario: Editing a deleted task
- **WHEN** a client submits `POST /api/task` with a `task_id` belonging to a soft-deleted task
- **THEN** the API responds `404 {'error': 'Задача не найдена'}` and no new task is created

#### Scenario: Editing a nonexistent task
- **WHEN** a client submits `POST /api/task` with a `task_id` that has never existed
- **THEN** the API responds `404 {'error': 'Задача не найдена'}` and no new task is created

#### Scenario: Creating a task (unchanged)
- **WHEN** a client submits `POST /api/task` with no `task_id`
- **THEN** the API creates a new task as before

