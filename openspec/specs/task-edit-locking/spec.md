# task-edit-locking Specification

## Purpose
TBD - created by archiving change dedupe-task-lock-check. Update Purpose after archive.
## Requirements
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

### Requirement: Назначения блокируют изменение сегмента и шаблона работы
При наличии хотя бы одного неудалённого назначения любого статуса система SHALL блокировать изменение сегмента и уже выбранного шаблона работы в форме и API. Повторная отправка прежних значений SHALL допускаться. После удаления всех назначений эти поля SHALL разблокироваться с учётом существующих ограничений терминальных и удалённых работ. Первоначальное заполнение отсутствующего шаблона старой работы SHALL оставаться доступным при неизменном сегменте. Проверка и запись MUST быть атомарными относительно создания назначений.

#### Scenario: Назначение в статусе Новый
- **WHEN** у работы есть неудалённое назначение в статусе `new`
- **THEN** форма запрещает менять сегмент и выбранный шаблон без отдельного поясняющего блока, а API отклоняет попытку изменения без частичного сохранения других полей

#### Scenario: Отменённое или неуспешное назначение
- **WHEN** единственное неудалённое назначение имеет статус `cancelled` или `unsuccessful`
- **THEN** сегмент и выбранный шаблон остаются заблокированными

#### Scenario: Изменение других полей
- **WHEN** работа с назначениями сохраняется с прежним сегментом и шаблоном и допустимыми изменениями других полей
- **THEN** новая блокировка не препятствует сохранению

#### Scenario: Все назначения удалены
- **WHEN** у нетерминальной работы удалены все назначения
- **THEN** сегмент и шаблон снова можно изменить, даже если история содержит удалённые назначения

#### Scenario: Осталось одно назначение
- **WHEN** удалена часть назначений, но хотя бы одно неудалённое назначение остаётся
- **THEN** блокировка сохраняется

#### Scenario: Терминальная работа без назначений
- **WHEN** у завершённой или отменённой работы нет неудалённых назначений
- **THEN** существующий запрет редактирования терминальной работы продолжает действовать

#### Scenario: Первое назначение и редактирование выполняются параллельно
- **WHEN** создание первого назначения конкурирует с изменением сегмента или шаблона
- **THEN** операции выполняются в согласованном порядке и изменение конфигурации после появления назначения отклоняется
