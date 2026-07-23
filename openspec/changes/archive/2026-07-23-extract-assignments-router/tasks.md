## 1. Зафиксировать контракт

- [x] 1.1 Добавить OpenAPI paths/methods tests для assignment endpoints.
- [x] 1.2 Зафиксировать list/save/bulk/delete/history/active filters и response shapes.
- [x] 1.3 Зафиксировать access, acting-user history и task-lock regression.

## 2. Выделить общую domain rule

- [x] 2.1 Создать `task_rules.py` и перенести task-lock predicate без изменения условия.
- [x] 2.2 Перевести текущие task handlers на общий helper и проверить оба потребителя.
- [x] 2.3 Создать `query_parsing.py`, перенести CSV int parser и перевести оба потребителя.

## 3. Выделить router

- [x] 3.1 Создать `routers/assignments.py` и перенести шесть endpoints без изменения логики.
- [x] 3.2 Подключить router, удалить локальные handlers/imports и проверить path resolution.

## 4. Проверки

- [x] 4.1 Запустить targeted assignment/task-lock tests и полный backend pytest.
- [x] 4.2 Выполнить pycompile, OpenAPI comparison и `git diff --check`.
- [x] 4.3 Выполнить `openspec validate --all` и сверить спецификацию.
