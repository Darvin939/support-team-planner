## Why

Архитектурный backlog завершён: DAO разделён по доменам, bulk-операции назначений атомарны, Planning декомпозирован, assignment orchestration централизована, N+1 устранены, list/count-фильтры и frontend domain types унифицированы, SQLite infrastructure разделена, а DB-ошибки и основные response contracts типизированы. Расширение тестового покрытия оформляется отдельным change.

## What Changes

- Разделить `db/__init__.py` на доменные DAO-модули с сохранением транзакционной модели и временного совместимого фасада `db`; границы модулей проектировать без привязки к SQLite, чтобы в будущем можно было подключить PostgreSQL.
- Добавить атомарные bulk API для автоназначения и массового удаления назначений; frontend и backend изменять одновременно.
- Собрать assignment mutations/orchestration в domain hooks и разгрузить `PlanningPage` и `AssignmentModal`.
- Устранить N+1-загрузку пользовательских команд и блоков шаблонов, унифицировать доменные list/count-фильтры.
- Централизовать frontend domain types, labels и option factories.
- Отделить SQLite schema/migrations/functions от connection backend.
- Заменить скрытое подавление DB-ошибок доменными исключениями.
- Добавить типизированные response-модели основных API.
- Сохранить существующее наблюдаемое поведение, роли и API-контракты, кроме явно добавляемых bulk endpoints.

## Capabilities

### New Capabilities

- `codebase-maintainability`: Границы backend/frontend-слоёв, атомарные bulk-операции, отсутствие дублирования и обязательная регрессионная проверка архитектурных рефакторингов.

### Modified Capabilities

- `frontend-state-consistency`: Assignment orchestration переносится из page/modal components в domain hooks при одновременном обновлении frontend/backend bulk-контрактов.

## Impact

- Уже завершено: доменные `db/`-модули, bulk assignment endpoints, Planning/Assignment hooks, общие frontend DTO и доменные pagination filters.
- Следующий backend scope: разделение `db/sqlite.py`, migration registry, доменные DB-ошибки и Pydantic response contracts.
- Дополнительное frontend unit/UI-покрытие transformations, invalidation/reset и navigation/bulk semantics вынесено в отдельный будущий change.
- Текущие одиночные assignment endpoints сохраняются; bulk-удаление и bulk-upsert используют атомарный контракт.
- PostgreSQL backend, драйвер, конфигурация, миграции и тестовый стенд в это изменение не входят.
