## 1. Backend-логика готовности

- [x] 1.1 Добавить регрессионные backend-тесты: отменённый дубль не блокирует готовность, но отменённое единственное покрытие блока не считается успешным.
- [x] 1.2 Изменить `get_task_completion_suggestion`, чтобы исключать `cancelled`-назначения из покрытия и проверки статусов, сохранив блокировку для неотменённых `new`, `planned` и `rollback`.
- [x] 1.3 Запустить backend-тесты матрицы готовности и API-ответа `task_completion_suggestion`.

## 2. Frontend и production-проверка

- [x] 2.1 Проверить Vitest + React Testing Library покрытие открытия, подтверждения и отмены `TaskCompletionSuggestionModal`; дополнить его только при обнаруженном пробеле.
- [x] 2.2 Добавить в `AssignmentModal` callback для `task_completion_suggestion`, передать его из `PlanningPage` и покрыть Vitest + React Testing Library сценарием успешного ответа с предложением.
- [x] 2.3 Создать WAL-безопасную копию текущей БД, собрать production-frontend и Playwright-тестом подтвердить появление модалки при завершении через форму для работы с отменённым дублем уже успешно покрытого блока.
- [x] 2.4 Остановить запущенный backend, восстановить БД через SQLite backup API, выполнить `PRAGMA wal_checkpoint(TRUNCATE)` и проверить целостность восстановленной БД.
