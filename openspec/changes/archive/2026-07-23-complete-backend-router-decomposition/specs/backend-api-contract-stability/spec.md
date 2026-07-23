## ADDED Requirements

### Requirement: Завершающая router-декомпозиция сохраняет session и document контракты

Перенос login/logout/current-user и SPA document handlers SHALL сохранять session cookie semantics, redirects, response classes, payload и access middleware behavior.

#### Scenario: Успешный вход и получение текущего пользователя

- **WHEN** пользователь входит с валидными credentials и запрашивает `/api/me`
- **THEN** router создаёт прежнюю session и возвращает прежний профиль/роль

#### Scenario: Ошибка входа

- **WHEN** credentials невалидны
- **THEN** router возвращает прежние HTTP status и JSON error contract

#### Scenario: Выход

- **WHEN** пользователь вызывает logout
- **THEN** session очищается и клиент получает прежний redirect

#### Scenario: SPA document routes

- **WHEN** клиент открывает login, planning, settings, statistics или journal document route
- **THEN** shell router возвращает тот же React index response с прежней защитой middleware

### Requirement: Завершающая router-декомпозиция сохраняет полный task lifecycle

Перенос task handlers SHALL сохранять все пути, методы, request/response schemas, query parameters, role/entity checks, transition rules, error contracts и transaction boundaries.

#### Scenario: Чтение активных и архивных задач

- **WHEN** клиент запрашивает список, карточку или архив задач с фильтрами и пагинацией
- **THEN** router применяет прежний team/task access и возвращает прежний task response contract

#### Scenario: Составное сохранение задачи

- **WHEN** клиент создаёт или редактирует задачу вместе с зависимостями
- **THEN** router сохраняет задачу, историю и зависимости в прежней составной транзакции либо полностью откатывает их

#### Scenario: Lifecycle mutation

- **WHEN** клиент восстанавливает, удаляет, меняет статус, порядок или приоритет задачи
- **THEN** router сохраняет прежние role checks, task-lock rules, допустимые переходы и ошибки

#### Scenario: История задачи

- **WHEN** клиент запрашивает историю задачи
- **THEN** router проверяет доступ и сохраняет прежнюю пагинацию и response contract

#### Scenario: Task OpenAPI после переноса

- **WHEN** FastAPI генерирует OpenAPI
- **THEN** все task paths, methods, query/body parameters и schema references остаются прежними

### Requirement: Завершающая router-декомпозиция сохраняет journal контракт

Перенос journal API SHALL сохранить team access, нормализацию фильтров, пагинацию и response payload.

#### Scenario: Журнал с фильтрами

- **WHEN** клиент запрашивает журнал команды с search, периодом и автором изменения
- **THEN** router передаёт DAO прежние нормализованные параметры и возвращает `items` и `total`

#### Scenario: Недоступная команда

- **WHEN** пользователь запрашивает журнал команды вне разрешённого набора
- **THEN** router отклоняет запрос по прежнему access-control контракту
