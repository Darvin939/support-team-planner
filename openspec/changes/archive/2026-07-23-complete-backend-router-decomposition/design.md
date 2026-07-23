## Context

`support_planner.py` всё ещё совмещает composition root и 22 route handlers. Оставшиеся обработчики естественно делятся на три крупных модуля, но входят в один завершающий архитектурный шаг: после их переноса entrypoint будет отвечать только за создание приложения, middleware, обработчики ошибок, static assets и production startup. Публичное поведение менять нельзя; frontend и backend обновляются вместе только при реальном изменении контракта, которого здесь нет.

## Goals / Non-Goals

**Goals:**

- Завершить router-декомпозицию одним OpenSpec change.
- Выделить `shell`, `tasks` и `journal` routers без дробления на отдельные capabilities/specs.
- Сохранить session, document, task lifecycle, journal, access-control, transaction и OpenAPI контракты.
- Убрать из composition root доменную загрузку task transition rules.
- Расширить regression coverage на весь перенесённый набор.

**Non-Goals:**

- Изменение frontend или публичного API.
- Изменение структуры БД, DAO или middleware ordering.
- Добавление новых endpoint’ов, WebSocket или фоновых процессов.
- Дальнейшее дробление каждого router на отдельное OpenSpec-изменение.

## Decisions

### 1. Один change, три router-модуля, одна delta-spec

Будут созданы `routers/shell.py`, `routers/tasks.py` и `routers/journal.py`. Все они реализуются и проверяются в одном change, а контрактные уточнения записываются в единственную delta-spec существующей capability `backend-api-contract-stability`.

Альтернатива — отдельное изменение/spec на каждую группу — добавляет процессный шум без самостоятельных продуктовых возможностей.

### 2. Shell router владеет полным SPA-serving контуром

В `routers/shell.py` вместе находятся document handlers, путь production build, static mount, кеш React index и функция его чтения. Composition root вызывает только `register_shell(app)`, не зная деталей расположения и раздачи frontend-артефактов.

Альтернатива — передавать `_serve_react_index` в router через factory — оставляет детали одной ответственности разделёнными между двумя модулями и создаёт избыточную dependency injection для стабильного локального пути.

### 3. Task transitions становятся общим доменным ресурсом

Загрузка `frontend/src/data/taskTransitions.json` будет вынесена в отдельный модуль task rules рядом с `task_is_locked`. Tasks router импортирует готовую карту переходов. JSON остаётся единым источником истины для frontend и backend.

Альтернатива — передавать карту через factory — усложняет router без необходимости изменять правила во время исполнения.

### 4. Полный task lifecycle переносится атомарно

Все task handlers и `_task_json` переносятся вместе. Это сохраняет общий формат task response, транзакцию `create_or_update_task + dependencies`, role checks и порядок специфичных `/archive`, `/restore`, `/history`, `/priority` путей относительно параметризованных routes.

### 5. Journal остаётся отдельным router, но не отдельной спецификацией

Journal имеет собственный DAO query и фильтры, поэтому заслуживает отдельного кода-модуля. При этом его перенос является частью общей декомпозиции и покрывается той же contract-stability delta-spec.

## Risks / Trade-offs

- [Risk] Router factory shell может изменить document response class или redirect → проверить root/login и все SPA paths через API tests.
- [Risk] Порядок task paths может изменить route resolution → подключить tasks router единым блоком и проверить каждый path/method в OpenAPI и запросами.
- [Risk] Перенос transition map может разойтись с frontend source → сохранить чтение того же JSON-файла и тесты допустимых/недопустимых переходов.
- [Risk] Перенос task save может нарушить составную транзакцию → оставить тело транзакции неизменным и повторно запустить rollback tests.
- [Risk] Session handlers могут потерять middleware state/cookie semantics → использовать тот же `Request.session` и реальные login/logout tests.
- [Trade-off] Один change крупнее предыдущих, зато соответствует общей архитектурной цели и сокращает количество искусственных спецификаций.
