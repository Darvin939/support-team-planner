## Why

Маршруты календаря нерабочих дней являются самостоятельной CRUD-группой и всё ещё увеличивают монолитный
`support_planner.py`. После появления первого router их можно перенести по уже проверенному шаблону.

## What Changes

- Перенести все `/api/freeze-days` handlers в отдельный `APIRouter`.
- Сохранить path-порядок для `/month/...` и catch-all `/{date_str:path}`.
- Сохранить payload, статусы, errors, role restrictions и DAO-вызовы.
- Добавить OpenAPI и endpoint regression-тесты.
- Не менять frontend.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `backend-api-contract-stability`: router extraction сохраняет в том числе порядок специфичных и catch-all paths.

## Impact

- Новый `routers/freeze_days.py`, подключение в entrypoint и удаление локальных handlers.
- Backend tests; frontend, БД и зависимости не изменяются.
