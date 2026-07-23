## Why

User CRUD и pagination остаются отдельной связной группой в entrypoint. Их перенос завершит декомпозицию
settings API и проверит router-границу с admin-only mutations и bootstrap-admin protection.

## What Changes

- Перенести list/create/update/delete `/api/users` в отдельный `APIRouter`.
- Сохранить full-list и paginated режимы GET.
- Сохранить admin-only mutations, duplicate handling, password semantics и запрет удаления текущего пользователя.
- Добавить OpenAPI, pagination, role и CRUD regression-тесты.
- Не менять frontend, payload или DAO.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `backend-api-contract-stability`: router extraction сохраняет method-dependent role restrictions и request user.

## Impact

- Новый `routers/users.py`, сокращение `support_planner.py`.
- Backend tests; frontend, БД и зависимости не изменяются.
