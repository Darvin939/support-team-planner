## 1. Декомпозиция `db/__init__.py`

- [ ] 1.1 Выделить DB-neutral connection/transaction boundaries без изменения request connection reuse
- [ ] 1.2 Перенести teams, users и reference-data DAO в доменные модули
- [ ] 1.3 Перенести tasks, dependencies, assignments, statistics и history DAO
- [ ] 1.4 Сохранить совместимый фасад `db` и выполнить backend regression suite
- [ ] 1.5 Проверить, что публичные доменные DAO не зависят от SQLite-specific connection/cursor API, не создавая PostgreSQL-заготовок

## 2. Bulk API автоназначения

- [ ] 2.1 Зафиксировать request/response-модели и атомарную семантику автоназначения
- [ ] 2.2 Реализовать backend bulk upsert в `composite_transaction` с проверкой прав и конфликтов
- [ ] 2.3 Одновременно перевести `AssignmentModal` на один bulk-запрос
- [ ] 2.4 Добавить rollback/API/unit и production UI-тесты автоназначения

## 3. Bulk API удаления назначений

- [ ] 3.1 Выбрать и зафиксировать атомарный либо partial-result контракт удаления
- [ ] 3.2 Реализовать backend bulk delete с проверкой каждого назначения
- [ ] 3.3 Одновременно заменить HTTP-цикл в `PlanningPage` bulk mutation hook
- [ ] 3.4 Добавить тесты успешного удаления, запрета роли и rollback/partial-result

## 4. Декомпозиция `PlanningPage`

- [ ] 4.1 Вынести Planning queries и lookup maps в специализированные hooks
- [ ] 4.2 Вынести jump/dependency navigation state
- [ ] 4.3 Вынести assignment actions и selection orchestration
- [ ] 4.4 Выделить самостоятельные filters/toolbar/stats presentation-блоки
- [ ] 4.5 Проверить Planning production UI-сценарии без визуальных изменений

## 5. Assignment domain hooks

- [ ] 5.1 Объединить save/delete/status/reschedule mutations в assignment application layer
- [ ] 5.2 Добавить bulk reschedule/delete/auto-assignment hooks поверх backend-контрактов
- [ ] 5.3 Централизовать invalidation policies, callbacks и сообщения
- [ ] 5.4 Удалить локальные query/mutation chains из Planning и Assignment modal

## 6. Устранение N+1

- [ ] 6.1 Пакетно загружать team IDs для полной и paginated выборки пользователей
- [ ] 6.2 Пакетно загружать blocks для всех разрешённых шаблонов команды
- [ ] 6.3 Выделить общий grouping helper для teams и templates
- [ ] 6.4 Добавить query-count и result-equivalence тесты

## 7. Доменные list/count filters

- [ ] 7.1 Унифицировать page result shape без универсального SQL builder
- [ ] 7.2 Выделить общие фильтры list/count для задач и архива
- [ ] 7.3 Выделить общие фильтры list/count для пользователей, команд и истории
- [ ] 7.4 Проверить empty-page, total и search/filter regression cases

## 8. Frontend domain types

- [ ] 8.1 Собрать общие Task/Assignment/User/Team/reference DTO в `domain/`
- [ ] 8.2 Удалить дубли `User`, `BlockTemplateEntry` и response interfaces
- [ ] 8.3 Централизовать status/criticality/role labels и option factories
- [ ] 8.4 Оставить form-only types рядом с компонентами и выполнить typecheck/build

## 9. SQLite schema и migrations

- [ ] 9.1 Разделить connection backend, schema, migrations и registered functions
- [ ] 9.2 Ввести последовательный migration registry с явными версиями
- [ ] 9.3 Проверить fresh install и upgrade существующей БД
- [ ] 9.4 Проверить SQLite connection lifecycle и WAL regression suite

## 10. Доменные DB-ошибки

- [ ] 10.1 Инвентаризировать `raise_on_error=False` и ожидаемые constraint cases
- [ ] 10.2 Ввести типизированные duplicate/not-found/integrity исключения
- [ ] 10.3 Перевести роутеры на явное отображение доменных ошибок в API contract
- [ ] 10.4 Убедиться, что неожиданные ошибки не маскируются и логируются

## 11. Типизированные response-модели

- [ ] 11.1 Добавить response-модели изменяемых bulk assignment endpoints
- [ ] 11.2 Добавить модели основных Task/Assignment/paginated/history responses
- [ ] 11.3 Подключить `response_model` и устранить ручное расхождение shapes
- [ ] 11.4 Проверить OpenAPI и совместимость frontend DTO

## 12. Расширение frontend-тестов

- [ ] 12.1 Покрыть чистые assignment payload/grouping transformations
- [ ] 12.2 Покрыть mutation invalidation и pagination/filter resets
- [ ] 12.3 Покрыть jump navigation, selection и bulk error semantics
- [ ] 12.4 Добавить только критические production Python+Playwright сценарии
- [ ] 12.5 Выполнить полный frontend/backend/OpenSpec validation
