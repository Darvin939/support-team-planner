## Why

Team API остаётся крупной связной группой в entrypoint, хотя его request-модели и access-control уже выделены.
Перенос этой группы проверит router-границу для endpoints с entity authorization и composite transaction.

## What Changes

- Перенести list/detail/create/update/delete команд, team blocks и assignees в `APIRouter`.
- Сохранить фильтрацию команд по пользователю, editor/admin restrictions и team access checks.
- Сохранить атомарность create-team + grant-access.
- Зафиксировать OpenAPI, access и CRUD contracts тестами.
- Не менять frontend, payload, DAO или маршруты.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `backend-api-contract-stability`: router extraction сохраняет access helpers и composite transaction semantics.

## Impact

- Новый `routers/teams.py`, сокращение `support_planner.py`.
- Backend tests; frontend, БД и зависимости не изменяются.
