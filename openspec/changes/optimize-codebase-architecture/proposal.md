## Why

После декомпозиции backend-роутеров и консолидации frontend server-state основными источниками сложности остаются монолитный DAO, распределённая orchestration назначений и повторяющиеся модели, SQL-фильтры и запросы связей. Нужен сохранённый единый backlog, чтобы выполнять улучшения последовательно, не теряя зависимости и не создавая отдельную спецификацию на каждый небольшой рефакторинг.

## What Changes

- Разделить `db/__init__.py` на доменные DAO-модули с сохранением транзакционной модели и временного совместимого фасада `db`; границы модулей проектировать без привязки к SQLite, чтобы в будущем можно было подключить PostgreSQL.
- Добавить атомарные bulk API для автоназначения и массового удаления назначений; frontend и backend изменять одновременно.
- Собрать assignment mutations/orchestration в domain hooks и разгрузить `PlanningPage` и `AssignmentModal`.
- Устранить N+1-загрузку пользовательских команд и блоков шаблонов, унифицировать доменные list/count-фильтры.
- Централизовать frontend domain types, labels и option factories.
- Отделить SQLite schema/migrations/functions от connection backend.
- Заменить скрытое подавление DB-ошибок доменными исключениями.
- Добавить типизированные response-модели и усилить frontend unit/UI-покрытие критических сценариев.
- Сохранить существующее наблюдаемое поведение, роли и API-контракты, кроме явно добавляемых bulk endpoints.

## Capabilities

### New Capabilities

- `codebase-maintainability`: Границы backend/frontend-слоёв, атомарные bulk-операции, отсутствие дублирования и обязательная регрессионная проверка архитектурных рефакторингов.

### Modified Capabilities

- `frontend-state-consistency`: Assignment orchestration переносится из page/modal components в domain hooks при одновременном обновлении frontend/backend bulk-контрактов.

## Impact

- Backend: `db/`, `routers/assignments.py`, `api_models.py`, тесты транзакций и API.
- Frontend: Planning/Assignment components, assignment hooks, domain types и тесты.
- API: добавляются bulk assignment endpoints без удаления текущих одиночных операций.
- Порядок реализации важен: сначала безопасная декомпозиция DAO, затем bulk-контракты, frontend orchestration и последующая инфраструктурная очистка.
- PostgreSQL backend, драйвер, конфигурация, миграции и тестовый стенд в это изменение не входят.
