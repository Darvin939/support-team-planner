## 1. Зафиксировать текущие API-контракты

- [x] 1.1 Собрать полный список Pydantic request-моделей в `support_planner.py` и проверить, какие из них входят
  в OpenAPI components.
- [x] 1.2 Добавить regression-тест ожидаемых schema names и ключевых properties/required/default для перенесённых
  моделей.
- [x] 1.3 Добавить или уточнить validation-тест, подтверждающий единый `{"error": "..."}` ответ на невалидный
  payload после декомпозиции.

## 2. Выделить модуль API-моделей

- [x] 2.1 Создать `api_models.py` и перенести в него все Pydantic request-модели без изменения объявлений.
- [x] 2.2 Заменить локальные модели в `support_planner.py` явными импортами, оставив
  `TaskDependencyCycleError` и route handlers на месте.
- [x] 2.3 Проверить отсутствие циклических импортов и локальных наследников `BaseModel` в entrypoint.

## 3. Проверки

- [x] 3.1 Запустить contract-тесты OpenAPI/validation и полный backend `python -m pytest`.
- [x] 3.2 Выполнить `python -m py_compile` для затронутых backend-модулей и `git diff --check`.
- [x] 3.3 Сверить реализацию с `backend-api-contract-stability` и выполнить `openspec validate --all`.
