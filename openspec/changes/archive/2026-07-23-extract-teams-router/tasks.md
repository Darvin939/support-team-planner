## 1. Зафиксировать контракт

- [x] 1.1 Добавить OpenAPI paths/methods tests для team endpoints.
- [x] 1.2 Зафиксировать list/detail/nested resources, role/access и CRUD errors.
- [x] 1.3 Сохранить regression-тест atomic create-team + grant-access.

## 2. Выделить router

- [x] 2.1 Создать `routers/teams.py` и перенести семь handlers без изменения логики.
- [x] 2.2 Использовать вынесенные access helpers и сохранить composite transaction.
- [x] 2.3 Подключить router, удалить локальные handlers/imports и проверить path resolution.

## 3. Проверки

- [x] 3.1 Запустить targeted team/composite tests и полный backend pytest.
- [x] 3.2 Выполнить py_compile, OpenAPI comparison и `git diff --check`.
- [x] 3.3 Выполнить `openspec validate --all` и сверить спецификацию.
