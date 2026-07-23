## ADDED Requirements

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
