## 1. Зафиксировать контракт

- [x] 1.1 Добавить OpenAPI paths/methods tests для user endpoints.
- [x] 1.2 Зафиксировать full-list/pagination и non-admin GET/admin mutation policy.
- [x] 1.3 Сохранить duplicate, password и acting-user delete regression.

## 2. Выделить router

- [x] 2.1 Создать `routers/users.py` и перенести четыре handlers без изменения логики.
- [x] 2.2 Сохранить Request/session context и существующие auth/db вызовы.
- [x] 2.3 Подключить router, удалить локальные handlers/imports и проверить path resolution.

## 3. Проверки

- [x] 3.1 Запустить targeted users/access tests и полный backend pytest.
- [x] 3.2 Выполнить pycompile, OpenAPI comparison и `git diff --check`.
- [x] 3.3 Выполнить `openspec validate --all` и сверить спецификацию.
