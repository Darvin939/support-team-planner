# task-edit-locking Specification

## Purpose
TBD - created by archiving change dedupe-task-lock-check. Update Purpose after archive.
## Requirements
### Requirement: Terminal or deleted tasks block edits
A task whose `task_status` is `done` or `cancelled`, or whose `is_deleted` flag is set, SHALL block creation/edit
of its assignments and edit/delete of the task itself, via a single shared check used by every affected endpoint.

#### Scenario: Saving an assignment on a done task
- **WHEN** `POST /api/assignment` targets a task with `task_status = 'done'`
- **THEN** the API responds `400 {'error': 'Нельзя изменять назначения завершённой или отменённой задачи'}`

#### Scenario: Deleting an assignment on a cancelled task
- **WHEN** `DELETE /api/assignment/{id}` targets an assignment whose task has `task_status = 'cancelled'`
- **THEN** the API responds `400` with the same locking error

#### Scenario: Editing a soft-deleted task
- **WHEN** `POST /api/task` is called with a `task_id` whose `is_deleted = 1`
- **THEN** the API responds `400 {'error': 'Нельзя редактировать завершённую или отменённую задачу'}`

#### Scenario: Deleting an already-terminal task
- **WHEN** `DELETE /api/task/{id}` targets a task with `task_status` in `('done', 'cancelled')`
- **THEN** the API responds `400` with the same locking error

#### Scenario: Active tasks are unaffected
- **WHEN** any of the above endpoints target a task with `task_status = 'new'` and `is_deleted = 0`
- **THEN** the locking check passes and the request proceeds to its normal validation/logic

