## Why

Backend сейчас возвращает ошибки в двух форматах: ручные ответы используют `{"error": "..."}`, а стандартные
`HTTPException` и ошибки валидации FastAPI — `{"detail": ...}`. Общие frontend helpers читают только `error`,
поэтому часть полезных сообщений теряется и заменяется техническим текстом с методом, URL и статусом.

## What Changes

- Установить единый публичный формат ошибок для всех `/api/*` ответов: `{"error": "<сообщение>"}`.
- Добавить FastAPI exception handlers для `HTTPException` и ошибок валидации запросов API.
- Сохранить HTTP status codes и существующие пользовательские сообщения маршрутов.
- Не преобразовывать redirect/HTML-ответы страниц входа и SPA.
- Объединить разбор ошибок `apiGet` и `apiMutate` в одну frontend-функцию, принимающую только публичное поле
  `error`.
- Обновить frontend и backend в одном change: приложение не поддерживает раздельное развёртывание их версий,
  поэтому переходный контракт `detail` не требуется.
- Добавить backend contract-тесты и frontend unit-тесты общего error parser.

## Capabilities

### New Capabilities

- `backend-api-error-format`: единый JSON-контракт контролируемых ошибок `/api/*`, включая HTTP и validation errors.

### Modified Capabilities

- `frontend-api-error-format`: GET и mutation helpers используют единый parser поля `error`, одинаково формируют
  fallback и меняются синхронно с backend API-контрактом.

## Impact

- `support_planner.py`: регистрация exception handlers и устранение расхождения стандартных FastAPI-ответов.
- `frontend/src/lib/apiMutate.ts`: общий разбор неуспешного ответа для GET и mutations.
- `tests/`: backend contract-тесты HTTPException/validation/auth ошибок.
- `frontend`: небольшой unit-test setup для чистой функции разбора ошибок, без UI/Playwright.
- Успешные ответы, маршруты и схема данных не изменяются; новые runtime-зависимости не требуются.
