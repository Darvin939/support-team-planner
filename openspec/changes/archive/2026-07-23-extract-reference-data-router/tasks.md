## 1. Зафиксировать контракт

- [x] 1.1 Добавить tests для paths/methods OpenAPI справочных endpoints.
- [x] 1.2 Зафиксировать success, validation, duplicate/not-found и role-access сценарии.

## 2. Выделить router

- [x] 2.1 Создать пакет `routers` и `reference_data.py` с `APIRouter`.
- [x] 2.2 Перенести handlers blocks, block-templates и segments без изменения логики.
- [x] 2.3 Подключить router в entrypoint и удалить исходные handlers.

## 3. Проверки

- [x] 3.1 Запустить targeted и полный backend pytest.
- [x] 3.2 Выполнить py_compile, сравнить OpenAPI paths и выполнить `git diff --check`.
- [x] 3.3 Выполнить `openspec validate --all` и сверить спецификацию.
