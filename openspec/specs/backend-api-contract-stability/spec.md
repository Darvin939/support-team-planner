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
