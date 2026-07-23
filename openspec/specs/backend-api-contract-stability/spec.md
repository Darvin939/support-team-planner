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

Перемещение route-группы в `APIRouter` SHALL сохранять различающиеся по HTTP-методу требования к роли и
использование текущего session user в handler.

#### Scenario: Чтение пользователей
- **WHEN** не-admin авторизованный пользователь вызывает GET `/api/users`
- **THEN** запрос остаётся доступен в прежнем full-list или paginated режиме

#### Scenario: Изменение пользователей
- **WHEN** роль ниже admin вызывает mutation `/api/users`
- **THEN** middleware отклоняет запрос по прежнему контракту

#### Scenario: Удаление пользователя
- **WHEN** admin удаляет пользователя
- **THEN** handler передаёт id текущего session user в доменную операцию

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
