## Why

Assignment API остаётся одной из крупнейших предметных групп entrypoint. Его модели и access-control уже
выделены, но общий task-lock rule пока локален и должен получить независимую границу перед подключением router.

## What Changes

- Вынести task-lock predicate и CSV query parser в небольшие общие helpers для task и assignment handlers.
- Перенести list/save/bulk-reschedule/delete/history и active-assignments endpoints в `APIRouter`.
- Сохранить team/task/assignment access, lock checks, history acting-user и pagination/filter contracts.
- Добавить OpenAPI и regression-тесты.
- Не менять frontend, payload или DAO.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `backend-api-contract-stability`: router extraction сохраняет общие domain rules и request context.

## Impact

- Новые `task_rules.py`, `query_parsing.py` и `routers/assignments.py`, сокращение `support_planner.py`.
- Backend tests; frontend, БД и зависимости не изменяются.
