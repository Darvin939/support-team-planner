## 1. Декомпозиция `db/__init__.py`

- [x] 1.1 Выделить DB-neutral connection/transaction boundaries без изменения request connection reuse
- [x] 1.2 Перенести teams, users и reference-data DAO в доменные модули
- [x] 1.3 Перенести tasks, dependencies, assignments, statistics и history DAO
- [x] 1.4 Сохранить совместимый фасад `db` и выполнить backend regression suite
- [x] 1.5 Проверить, что публичные доменные DAO не зависят от SQLite-specific connection/cursor API, не создавая PostgreSQL-заготовок

## 2. Bulk API автоназначения

- [x] 2.1 Зафиксировать request/response-модели и атомарную семантику автоназначения
- [x] 2.2 Реализовать backend bulk upsert в `composite_transaction` с проверкой прав и конфликтов
- [x] 2.3 Одновременно перевести `AssignmentModal` на один bulk-запрос
- [x] 2.4 Добавить rollback/API/unit и production UI-тесты автоназначения

## 3. Bulk API удаления назначений

- [x] 3.1 Выбрать и зафиксировать атомарный либо partial-result контракт удаления
- [x] 3.2 Реализовать backend bulk delete с проверкой каждого назначения
- [x] 3.3 Одновременно заменить HTTP-цикл в `PlanningPage` bulk mutation hook
- [x] 3.4 Добавить тесты успешного удаления, запрета роли и rollback/partial-result

## 4. Декомпозиция `PlanningPage`

- [x] 4.1 Вынести Planning queries и lookup maps в специализированные hooks
- [x] 4.2 Вынести jump/dependency navigation state
- [x] 4.3 Вынести assignment actions и selection orchestration
- [x] 4.4 Выделить самостоятельные filters/toolbar/stats presentation-блоки
- [x] 4.5 Проверить Planning production UI-сценарии без визуальных изменений

## 5. Assignment domain hooks

- [x] 5.1 Объединить save/delete/status/reschedule mutations в assignment application layer
- [x] 5.2 Добавить bulk reschedule/delete/auto-assignment hooks поверх backend-контрактов
- [x] 5.3 Централизовать invalidation policies, callbacks и сообщения
- [x] 5.4 Удалить локальные query/mutation chains из Planning и Assignment modal

## 6. Устранение N+1

- [x] 6.1 Пакетно загружать team IDs для полной и paginated выборки пользователей
- [x] 6.2 Пакетно загружать blocks для всех разрешённых шаблонов команды
- [x] 6.3 Выделить общий grouping helper для teams и templates
- [x] 6.4 Добавить query-count и result-equivalence тесты

## 7. Доменные list/count filters

- [x] 7.1 Унифицировать page result shape без универсального SQL builder
- [x] 7.2 Выделить общие фильтры list/count для задач и архива
- [x] 7.3 Выделить общие фильтры list/count для пользователей, команд и истории
- [x] 7.4 Проверить empty-page, total и search/filter regression cases

## 8. Frontend domain types

- [x] 8.1 Собрать общие Task/Assignment/User/Team/reference DTO в `domain/`
- [x] 8.2 Удалить дубли `User`, `BlockTemplateEntry` и response interfaces
- [x] 8.3 Централизовать status/criticality/role labels и option factories
- [x] 8.4 Оставить form-only types рядом с компонентами и выполнить typecheck/build

## 9. SQLite schema и migrations

- [x] 9.1 Разделить connection backend, schema, migrations и registered functions
- [x] 9.2 Ввести последовательный migration registry с явными версиями
- [x] 9.3 Проверить fresh install и upgrade существующей БД
- [x] 9.4 Проверить SQLite connection lifecycle и WAL regression suite

## 10. Доменные DB-ошибки

- [x] 10.1 Инвентаризировать `raise_on_error=False` и ожидаемые constraint cases
- [x] 10.2 Ввести типизированные duplicate/not-found/integrity исключения
- [x] 10.3 Перевести роутеры на явное отображение доменных ошибок в API contract
- [x] 10.4 Убедиться, что неожиданные ошибки не маскируются и логируются

## 11. Типизированные response-модели

- [x] 11.1 Добавить response-модели изменяемых bulk assignment endpoints
- [x] 11.2 Добавить модели основных Task/Assignment/paginated/history responses
- [x] 11.3 Подключить `response_model` и устранить ручное расхождение shapes
- [x] 11.4 Проверить OpenAPI и совместимость frontend DTO
