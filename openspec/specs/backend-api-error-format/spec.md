# backend-api-error-format Specification

## Purpose
Зафиксировать единый формат контролируемых ошибок backend API, пригодный для общего отображения во frontend.

## Requirements
### Requirement: Контролируемые API-ошибки используют единый JSON-контракт

Каждый контролируемый неуспешный ответ маршрута `/api/*` SHALL содержать JSON-объект с непустым строковым полем
`error`, пригодным для показа пользователю.

#### Scenario: Ручная ошибка маршрута

- **WHEN** API route возвращает контролируемую ошибку через ручной JSON response
- **THEN** тело ответа имеет форму `{"error": "<сообщение>"}` и сохраняет назначенный route status code

#### Scenario: HTTPException API-маршрута

- **WHEN** обработка `/api/*` возбуждает `HTTPException` со строковым `detail`
- **THEN** backend возвращает тот же status code и тело `{"error": "<detail>"}`

#### Scenario: Ошибка валидации API-запроса

- **WHEN** параметры, path или JSON body запроса `/api/*` не проходят FastAPI/Pydantic validation
- **THEN** backend возвращает status `422` и тело с непустым строковым полем `error`

### Requirement: Ошибки не-API маршрутов сохраняют прежнюю семантику

Обработчики единого API-контракта MUST NOT преобразовывать ответы страниц, login/logout и SPA-маршрутов в
API-формат.

#### Scenario: Ошибка или redirect маршрута страницы

- **WHEN** запрос к пути вне `/api/*` завершается стандартной HTTP-ошибкой или redirect
- **THEN** ответ сохраняет предусмотренный этим маршрутом формат и не преобразуется принудительно в
  `{"error": "..."}`
