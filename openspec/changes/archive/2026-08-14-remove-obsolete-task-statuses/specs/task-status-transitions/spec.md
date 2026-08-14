## MODIFIED Requirements

### Requirement: One JSON file is the source of truth for task-status transitions
The current task-status vocabulary SHALL contain exactly `new`, `done`, and `cancelled`. The set of allowed task-status transitions SHALL be defined in exactly one file (`frontend/src/data/taskTransitions.json`), read directly by both the backend and the frontend — neither maintains its own independent transition map. Template-driven completion suggestions MUST execute the same standard transition and MUST NOT bypass this map. Legacy `ready` and `in_progress` values MUST NOT be created by штатные demo seed-скрипты and SHALL NOT require a frontend compatibility layer.

#### Scenario: Backend enforcement matches the shared file
- **WHEN** `PATCH /api/tasks/{id}/status` is called with a target status
- **THEN** it is accepted or rejected based on the transitions loaded from `taskTransitions.json`, not a hardcoded Python transition literal

#### Scenario: Frontend UI matches the shared file
- **WHEN** the Planning page renders the status-change menu for a task
- **THEN** the offered transitions come from importing `taskTransitions.json`, not a hardcoded TypeScript transition literal

#### Scenario: Editing the shared file changes both sides
- **WHEN** a transition between current statuses is added to `taskTransitions.json`
- **THEN** both backend validation and the frontend menu reflect it after their next restart/rebuild, with no independent transition map needing a change

#### Scenario: Existing rule is preserved
- **WHEN** the app is deployed with the current transition file
- **THEN** the only transitions allowed are `new → done` and `new → cancelled`, and no transition from `done` or `cancelled` is allowed

#### Scenario: Подтверждение предложения использует стандартный переход
- **WHEN** пользователь подтверждает предложение завершить работу после успешного выполнения шаблона
- **THEN** frontend запрашивает переход в `done` через стандартный маршрут, а backend применяет общую карту допустимых переходов

#### Scenario: Новые demo-данные используют актуальный словарь
- **WHEN** любой штатный demo seed создаёт набор работ
- **THEN** каждая новая работа имеет один из статусов `new`, `done`, `cancelled`

#### Scenario: Текущая seeded-БД очищена от legacy-статусов
- **WHEN** выполняется разовая обслуживающая операция над текущей тестовой БД
- **THEN** `ready` и `in_progress` заменяются на `new` в работах и значениях истории статуса без добавления application migration

## ADDED Requirements

### Requirement: API использует явные перечисления доменных значений
Pydantic-контракты SHALL ограничивать текущий статус работы значениями `new`, `done`, `cancelled`, статус назначения значениями `new`, `planned`, `rollback`, `success`, `cancelled`, критичность значениями `low`, `medium`, `high`, а роль значениями `user`, `editor`, `admin`. Общие значения аудита MAY оставаться строковыми.

#### Scenario: Допустимые значения принимаются
- **WHEN** API получает любое значение из соответствующего объявленного перечисления
- **THEN** enum-валидация принимает его, после чего применяются обычные бизнес-правила доступа и переходов

#### Scenario: Неизвестный статус назначения отклоняется
- **WHEN** API сохранения назначения получает статус вне `new`, `planned`, `rollback`, `success`, `cancelled`
- **THEN** запрос отклоняется до записи в БД в стандартном формате ошибки API

#### Scenario: Неизвестное значение другого enum отклоняется
- **WHEN** input-модель получает неизвестный статус работы, критичность или роль
- **THEN** запрос отклоняется до выполнения соответствующей операции
