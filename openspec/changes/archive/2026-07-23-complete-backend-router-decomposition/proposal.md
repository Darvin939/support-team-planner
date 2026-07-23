## Why

После поэтапного выделения вспомогательных API в `support_planner.py` остаются три крупные связанные области: session/SPA shell, полный lifecycle задач и журнал команды. Их целесообразно перенести одним завершающим пакетом, чтобы не дробить рефакторинг и спецификации на отдельное изменение для каждого небольшого router.

## What Changes

- Выделить session endpoints (`login`, `logout`, `api/me`) и SPA document routes в отдельный router shell.
- Выделить полный task API: список, карточку, архив, создание/редактирование, восстановление, удаление, статусы, порядок, приоритет и историю.
- Выделить API журнала команды в отдельный router.
- Перенести загрузку общих task transition rules из entrypoint в переиспользуемый доменный модуль.
- Оставить в `support_planner.py` сборку FastAPI-приложения, middleware, exception handlers, static assets и production startup.
- Сохранить все публичные URL, методы, payload, ответы, ошибки, проверки ролей/доступа, транзакции и OpenAPI.
- Не изменять frontend, потому что публичный контракт остаётся прежним.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `backend-api-contract-stability`: единым набором требований закрепить сохранение session/document, task lifecycle и journal контрактов при завершении router-декомпозиции.

## Impact

- `support_planner.py` станет composition root приложения.
- Новые routers для shell/session, задач и журнала.
- Общий модуль task transition rules.
- Backend API, access-control, transaction и OpenAPI regression tests.
- Frontend, база данных и внешние зависимости не изменяются.
