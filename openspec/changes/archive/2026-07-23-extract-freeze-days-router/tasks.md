## 1. Зафиксировать контракт

- [x] 1.1 Добавить OpenAPI tests для collection, month и date paths/methods.
- [x] 1.2 Добавить regression-сценарии add/range/month/delete и editor restriction.

## 2. Выделить router

- [x] 2.1 Создать `routers/freeze_days.py` и перенести handlers в исходном порядке.
- [x] 2.2 Подключить router в entrypoint и удалить локальные handlers/imports.
- [x] 2.3 Проверить, что month routes не перехватываются date catch-all.

## 3. Проверки

- [x] 3.1 Запустить targeted и полный backend pytest.
- [x] 3.2 Выполнить py_compile, OpenAPI comparison и `git diff --check`.
- [x] 3.3 Выполнить `openspec validate --all` и сверить спецификацию.
