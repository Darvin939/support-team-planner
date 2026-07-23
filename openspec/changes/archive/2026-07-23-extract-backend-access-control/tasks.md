## 1. Зафиксировать access-control поведение

- [x] 1.1 Добавить parametrized regression-тесты публичных, authentication-required и role-restricted путей.
- [x] 1.2 Зафиксировать redirect для HTML, JSON error для API и запрет доступа к чужой команде.

## 2. Выделить access-control модуль

- [x] 2.1 Создать `access_control.py` и перенести path/rank matrix, login middleware и entity access helpers.
- [x] 2.2 Импортировать и зарегистрировать middleware в `support_planner.py` в прежнем порядке.
- [x] 2.3 Перевести routes на импортированные helpers и проверить отсутствие циклических импортов.

## 3. Проверки

- [x] 3.1 Запустить targeted access-control tests и полный `python -m pytest`.
- [x] 3.2 Выполнить `python -m py_compile`, `git diff --check` и проверить отсутствие публичных API изменений.
- [x] 3.3 Сверить реализацию со спецификацией и выполнить `openspec validate --all`.
