## Why

После выделения request-моделей и access-control маршруты всё ещё зарегистрированы в монолитном entrypoint.
Справочники блоков, шаблонов и сегментов образуют независимую группу и подходят для первого безопасного router.

## What Changes

- Перенести `/api/blocks`, `/api/block-templates` и `/api/segments` в отдельный `APIRouter`.
- Подключить router в entrypoint без изменения путей, методов, payload, статусов и ошибок.
- Добавить contract/regression-тесты перенесённых маршрутов.
- Не менять frontend и DAO.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `backend-api-contract-stability`: перенос endpoints в router сохраняет публичный API и access-control.

## Impact

- Новый router-модуль справочников; сокращение `support_planner.py`.
- Backend tests; frontend, БД и зависимости не изменяются.
