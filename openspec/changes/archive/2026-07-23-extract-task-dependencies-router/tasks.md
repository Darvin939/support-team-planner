## 1. Доменные правила зависимостей

- [x] 1.1 Вынести cycle exception и общую проверку пары задач в модуль правил зависимостей без привязки результата проверки к HTTP
- [x] 1.2 Перевести атомарное сохранение основной задачи на импорт вынесенного cycle exception
- [x] 1.3 Добавить unit-тесты правил для отсутствующих, удалённых, межкомандных и терминальных задач

## 2. Router зависимостей задач

- [x] 2.1 Создать `routers/task_dependencies.py` и перенести endpoints `deps`, `dependency-graph`, `task-dependency` и `active-list`
- [x] 2.2 Переиспользовать общие request model, access-control helpers и CSV parser, сохранив точные ответы и фильтры
- [x] 2.3 Подключить router в прежней логической позиции и удалить перенесённые handlers/helper из entrypoint

## 3. Регрессионная проверка

- [x] 3.1 Добавить API-тесты успешного чтения, query-фильтров и проверок доступа к команде/обеим задачам
- [x] 3.2 Добавить API-тесты ошибок mutation и обнаружения циклической зависимости
- [x] 3.3 Проверить сохранение OpenAPI paths, methods, parameters и `TaskDependencyIn`
- [x] 3.4 Запустить целевые тесты, полный backend test suite и `openspec validate --all`
