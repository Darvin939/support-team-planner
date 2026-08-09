## Context

Backend DAO разделены по доменным модулям за совместимым фасадом, bulk assignment operations реализованы атомарно, а Planning и assignment orchestration декомпозированы. Пакетная загрузка связей, доменные pagination filters, общие frontend DTO, SQLite infrastructure, доменные DB-ошибки и основные response contracts завершены. Дополнительное расширение frontend/unit/UI-покрытия не входит в этот change и будет планироваться отдельно.

Изменение является umbrella backlog: группы выполняются последовательно внутри одного OpenSpec change. Публичные контракты сохраняются, а новые bulk-контракты всегда реализуются одновременно во frontend и backend.

## Goals / Non-Goals

**Goals:**

- Разделить data-access по доменам без изменения транзакционных гарантий.
- Сформировать DB-neutral границы доменных DAO, пригодные для будущего подключения PostgreSQL.
- Перенести составные assignment operations на backend и выполнять их атомарно.
- Сократить orchestration и дублирование в крупных frontend-компонентах.
- Устранить N+1-запросы и расхождение page/count-фильтров.
- Сделать DB/API-ошибки и response contracts явными и тестируемыми.
- Сохранить нумерацию и порядок backlog для продолжения в следующих сессиях.

**Non-Goals:**

- Переход с SQLite на другую СУБД.
- Реализация PostgreSQL backend, драйвера, конфигурации, миграций или тестового стенда.
- WebSocket или изменение модели обновления UI.
- Полная генерация TypeScript-клиента из OpenAPI.
- Визуальный редизайн Planning.
- Удаление существующих одиночных assignment endpoints до отдельного решения.

## Decisions

### 1. DAO переносится доменными вертикалями

Целевые модули: connection, teams, users, reference data, tasks, dependencies, assignments, history и statistics. `db/__init__.py` временно остаётся фасадом реэкспортов. Это позволяет переносить одну связанную группу за раз и сохранять текущие импорты роутеров.

Альтернатива — одномоментно изменить все импорты — отклонена из-за большого diff и риска смешать структурный перенос с изменением поведения.

Публичные границы доменных DAO не должны принимать SQLite connection/cursor types и не должны требовать от вызывающего кода знания SQLite lifecycle. Диалектные операции, регистрация SQLite functions, получение insert ID, классификация ошибок и schema/migration logic остаются за backend abstraction. SQL, общий для поддерживаемых backend, допускается внутри доменных DAO; SQLite-специфичные конструкции должны быть локализованы и не становиться частью их публичного контракта.

Это архитектурная подготовка границ, а не реализация второго backend: PostgreSQL-модули, условные ветки, фиктивные адаптеры и неиспользуемые интерфейсы заранее не создаются.

### 2. Bulk assignment operations принадлежат backend

Автоназначение и массовое удаление получают отдельные request-модели и endpoints. Валидация всего набора, права и записи выполняются внутри одной `composite_transaction`. Frontend отправляет один запрос и обрабатывает один результат.

Для удаления до реализации требуется выбрать атомарную семантику либо структурированный partial-result. По умолчанию предпочтительна атомарность.

### 3. Assignment orchestration концентрируется в domain hooks

После появления bulk endpoints save/delete/status/reschedule/bulk/auto-assignment mutations размещаются в общем assignment application layer. Page/modal components сохраняют form, selection и presentation state.

### 4. Planning декомпозируется по ответственности

Из `PlanningPage` выносятся queries/lookups, navigation/jump state, assignment actions и крупные самостоятельные presentation-блоки. Мелкие JSX-фрагменты без собственной ответственности не выделяются только ради количества строк.

### 5. Оптимизация SQL остаётся доменной

Для пользователей, команд, задач, архива и истории применяются отдельные filter builders и page result helpers. Универсальный ORM-подобный SQL builder не вводится. Связи пользователей/команд и шаблонов/блоков загружаются пакетно.

### 6. Storage infrastructure меняется после DAO

После стабилизации доменных DAO `db/sqlite.py` делится на backend, schema, migrations и registered functions. Миграции получают явный последовательный registry.

### 7. Ожидаемые DB-ошибки типизированы

Ожидаемые constraint/not-found случаи преобразуются в доменные исключения. Неожиданные ошибки не маскируются `False`/`None` и остаются доступными логированию и общему API error handler.

### 8. Контракты укрепляются постепенно

Основные response shapes получают Pydantic-модели. Общие frontend DTO и enum-like labels переносятся в `domain/`. Генерация клиента не является обязательной частью изменения.

## Risks / Trade-offs

- [Большой umbrella scope] → выполнять только по нумерованным группам и проверять каждую группу отдельно.
- [Циклические импорты после деления DAO] → общий connection/backend слой не импортирует доменные DAO; фасад содержит только реэкспорты.
- [Преждевременная абстракция ради PostgreSQL] → выделять только границы, уже оправданные текущим SQLite-кодом; не создавать неиспользуемые PostgreSQL abstractions.
- [SQLite-специфичный SQL просачивается в доменные контракты] → локализовать dialect operations в backend abstraction и отмечать оставшиеся диалектные запросы внутри реализации.
- [Изменение транзакционного поведения] → сохранить тесты connection reuse/composite transactions и добавить rollback-тесты каждого bulk endpoint.
- [Частичная несовместимость frontend/backend] → любые изменения публичного payload выполняются в одной группе сразу на обеих сторонах.
- [Избыточная абстракция frontend] → выносить только server orchestration и блоки с самостоятельной ответственностью.
- [Оптимизированный SQL становится сложнее] → сравнивать результаты и query count с существующими сценариями до удаления старого кода.

## Migration Plan

1. Разделить DAO за совместимым фасадом.
2. Добавить bulk assignment contracts и backend tests.
3. Одновременно перевести frontend на новые endpoints и domain hooks.
4. Декомпозировать Planning presentation/orchestration.
5. Устранить N+1 и унифицировать list/count filters.
6. Централизовать frontend domain types.
7. Разделить SQLite schema/migrations/functions.
8. Ввести доменные DB-ошибки и response models.
9. Дополнительное системное расширение тестового покрытия оформить отдельным OpenSpec change.

Rollback каждой группы выполняется её отдельным коммитом; миграций пользовательских данных в первых группах нет.

## Open Questions

- Массовое удаление реализовано полностью атомарным.
- Старые одиночные endpoints сохраняются до отдельного решения о deprecation.
- Response-модели сначала введены для изменяемых bulk assignment endpoints; следующий этап расширяет их на основные Task/Assignment/paginated/history ответы.
