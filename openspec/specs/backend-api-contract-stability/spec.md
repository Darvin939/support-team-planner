# backend-api-contract-stability Specification

## Purpose
Зафиксировать сохранение публичных API-контрактов при внутренней декомпозиции backend и правила синхронного
изменения frontend при реальном изменении контракта.

## Requirements
### Requirement: Внутренняя декомпозиция сохраняет request-контракты API

Перемещение request-моделей между backend-модулями SHALL сохранять публичные имена OpenAPI schemas, поля, типы,
обязательность, значения по умолчанию и validation-поведение соответствующих маршрутов.

#### Scenario: Валидный запрос после переноса модели

- **WHEN** клиент отправляет payload, который был валиден до внутренней декомпозиции backend
- **THEN** маршрут принимает его с прежней семантикой

#### Scenario: Невалидный запрос после переноса модели

- **WHEN** клиент отправляет payload, который нарушает существующий request-контракт
- **THEN** маршрут отклоняет его с тем же публичным API error contract

#### Scenario: OpenAPI после переноса модели

- **WHEN** FastAPI генерирует OpenAPI schema после внутреннего переноса request-моделей
- **THEN** публичные schema names и свойства перенесённых моделей остаются прежними

### Requirement: Behavior-preserving backend refactor не требует фиктивного frontend-изменения

Внутренняя декомпозиция backend SHALL NOT изменять frontend, если публичные request и response контракты
сохраняются. Если публичный контракт необходимо изменить, тот же OpenSpec change MUST включать соответствующее
изменение frontend.

#### Scenario: Публичный контракт не меняется

- **WHEN** backend-класс перемещается между модулями без изменения генерируемой API schema
- **THEN** frontend остаётся без изменений

#### Scenario: Требуется изменение публичного контракта

- **WHEN** реализация требует изменить поле, тип, обязательность или форму API payload
- **THEN** план изменения пересматривается и включает синхронное обновление frontend consumer

### Requirement: Декомпозиция access-control сохраняет защиту маршрутов

Перемещение authentication middleware и authorization helpers между backend-модулями SHALL сохранять публичное
поведение для неавторизованных пользователей и всех поддерживаемых ролей.

#### Scenario: Неавторизованный запрос страницы
- **WHEN** неавторизованный клиент запрашивает защищённую HTML-страницу
- **THEN** он получает прежний redirect на login

#### Scenario: Неавторизованный API-запрос
- **WHEN** неавторизованный клиент запрашивает защищённый `/api/*` маршрут
- **THEN** он получает прежний HTTP status и JSON error contract

#### Scenario: Недостаточная роль
- **WHEN** авторизованный пользователь вызывает маршрут, требующий более высокой роли
- **THEN** запрос отклоняется с прежним HTTP status и сообщением

#### Scenario: Доступ к сущности команды
- **WHEN** пользователь обращается к team/task/assignment вне разрешённых ему команд
- **THEN** entity access helper отклоняет запрос по прежним правилам

### Requirement: Перенос endpoints в router сохраняет API-контракт

Перемещение route handlers из entrypoint в `APIRouter` SHALL сохранять пути, HTTP-методы, request/response payload,
status codes, error contract и применяемые access-control правила.

#### Scenario: Успешный запрос перенесённого endpoint
- **WHEN** клиент вызывает перенесённый endpoint с валидными данными
- **THEN** ответ совпадает с поведением до декомпозиции

#### Scenario: Ошибка перенесённого endpoint
- **WHEN** перенесённый endpoint отклоняет запрос
- **THEN** status и JSON error contract остаются прежними

#### Scenario: OpenAPI после подключения router
- **WHEN** приложение генерирует OpenAPI
- **THEN** перенесённые paths, methods и schemas остаются доступны под прежними именами

### Requirement: Router сохраняет приоритет специфичных путей над catch-all

При переносе route-группы в `APIRouter` backend SHALL сохранять порядок разрешения специфичных paths и
перекрывающего их catch-all path.

#### Scenario: Запрос month route
- **WHEN** клиент вызывает `/api/freeze-days/month` или вложенный month path
- **THEN** запрос обрабатывает month handler, а не date catch-all handler

#### Scenario: Запрос date route
- **WHEN** клиент вызывает `/api/freeze-days/<date>` вне month paths
- **THEN** запрос обрабатывает date handler с прежним контрактом

### Requirement: Router сохраняет entity access и составную транзакцию

Перемещение entity handlers в `APIRouter` SHALL сохранять request-derived authorization checks и границы
существующих composite transactions.

#### Scenario: Доступ к команде после переноса
- **WHEN** пользователь запрашивает команду или вложенный team resource
- **THEN** router применяет прежние user/role и team-access правила

#### Scenario: Создание команды после переноса
- **WHEN** создание команды или выдача доступа завершается ошибкой
- **THEN** обе записи откатываются в прежней composite transaction

#### Scenario: Вложенные team paths
- **WHEN** клиент вызывает blocks или assignees path команды
- **THEN** запрос попадает в прежний handler и сохраняет контракт

### Requirement: Router сохраняет method-dependent role policy

Явные зависимости FastAPI на route-группе или конкретном endpoint SHALL сохранять различающиеся по операциям требования к роли и предоставлять handler проверенного текущего session user без зависимости политики от строкового сопоставления HTTP-метода и URL-пути в общем middleware.

#### Scenario: Чтение пользователей
- **WHEN** не-admin авторизованный пользователь вызывает GET `/api/users`
- **THEN** запрос остаётся доступен в прежнем full-list или paginated режиме

#### Scenario: Изменение пользователей
- **WHEN** роль ниже admin вызывает mutation `/api/users`
- **THEN** явно назначенная endpoint-зависимость отклоняет запрос по прежнему контракту

#### Scenario: Удаление пользователя
- **WHEN** admin удаляет пользователя
- **THEN** handler передаёт id проверенного текущего пользователя в доменную операцию

### Requirement: Router сохраняет общие domain rules

Если handlers разных route-групп используют одно доменное правило, декомпозиция SHALL оставлять единый helper и
сохранять результаты правила во всех потребителях.

#### Scenario: Заблокированная задача в assignment handler
- **WHEN** assignment mutation относится к завершённой, отменённой или удалённой задаче
- **THEN** router отклоняет операцию по прежнему task-lock правилу

#### Scenario: Та же задача в task handler
- **WHEN** task handler проверяет ту же задачу
- **THEN** он использует тот же domain helper и получает тот же результат

#### Scenario: CSV query filter после переноса
- **WHEN** task или assignment endpoint разбирает список id из CSV query parameter
- **THEN** оба endpoint используют один parser и сохраняют прежнее поведение пустых и заполненных значений

#### Scenario: Request context после переноса
- **WHEN** assignment mutation записывает историю
- **THEN** router передаёт прежний session user и сохраняет access checks

### Requirement: Router зависимостей сохраняет правила графа и доступа

Перенос endpoints зависимостей задач в `APIRouter` SHALL сохранять проверки доступа к команде и обеим сторонам связи, правила допустимости редактирования и обнаружения циклов.

#### Scenario: Чтение зависимостей команды

- **WHEN** пользователь запрашивает список зависимостей, граф или список активных задач команды
- **THEN** router применяет прежнюю проверку доступа к команде и сохраняет response contract

#### Scenario: Доступ к компоненте графа

- **WHEN** запрос графа содержит `task_id`
- **THEN** router дополнительно проверяет доступ к указанной задаче до возврата связанной компоненты

#### Scenario: Изменение одной связи

- **WHEN** пользователь добавляет или удаляет зависимость между двумя задачами
- **THEN** router проверяет доступ к обеим задачам и сохраняет запреты для отсутствующих, удалённых, межкомандных и терминальных задач

#### Scenario: Создание цикла

- **WHEN** добавляемая зависимость создаёт цикл
- **THEN** router отклоняет операцию с прежними HTTP status и JSON error contract

### Requirement: Router зависимостей сохраняет query-фильтры

Перенос read endpoints зависимостей SHALL сохранить parsing и семантику существующих query parameters.

#### Scenario: Ограничение списка зависимостей

- **WHEN** клиент передаёт CSV `task_ids` в endpoint списка зависимостей
- **THEN** router передаёт DAO тот же разобранный набор идентификаторов

#### Scenario: Поиск активных задач с обязательными идентификаторами

- **WHEN** клиент передаёт `search`, `limit` и CSV `include_ids`
- **THEN** router сохраняет нормализацию поиска, лимит и включение указанных задач

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
