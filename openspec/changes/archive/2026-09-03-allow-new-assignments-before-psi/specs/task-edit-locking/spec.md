## MODIFIED Requirements

### Requirement: Terminal or deleted tasks block edits
A task whose `task_status` is `done` or `cancelled`, or whose `is_deleted` flag is set, SHALL block creation/edit of its assignments and edit/delete of the task itself, via a single shared check used by every affected endpoint. An active task whose `psi_status` is `required` SHALL permit assignment planning operations only when the assignment's resulting status is `new`; an existing assignment of another status SHALL permit updates only to non-planning fields while remaining subject to role authorization.

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
- **WHEN** any task-edit endpoint targets a task with `task_status = 'new'` and `is_deleted = 0`
- **THEN** the terminal locking check passes and the request proceeds to its normal validation/logic

#### Scenario: Required PSI permits new assignment planning
- **WHEN** an assignment planning operation leaves an assignment of an active task with `psi_status = 'required'` in status `new`
- **THEN** the PSI locking check passes and the request proceeds to its normal validation/logic

#### Scenario: Required PSI blocks activation
- **WHEN** an assignment operation would leave an assignment of an active task with `psi_status = 'required'` in a status other than `new`
- **THEN** the operation is rejected without treating the task as terminal
