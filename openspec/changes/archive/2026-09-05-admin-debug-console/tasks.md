## 1. Access and logging

- [x] 1.1 Добавить dependency точного bootstrap-admin (`role=admin`, `login=admin`) и покрыть 401/403 тестами.
- [x] 1.2 Настроить общий относительный rotating UTF-8 `application.log`, Uvicorn/application loggers и redaction.
- [x] 1.3 Добавить admin-only endpoint структурированных log records с ограничением, level/search фильтрами и без параметра пути.

## 2. Frontend

- [x] 2.1 Добавить lazy route и bug-пункт меню только для bootstrap-admin.
- [x] 2.2 Реализовать единственную панель Application log с фильтрами и периодическим обновлением.
- [x] 2.3 Реализовать follow-mode, начальный scroll вниз, сохранение ручной позиции и кнопку «К последним».

## 3. Scope reduction

- [x] 3.1 Удалить SQLite/Audit UI, DB endpoints/DAO и `DEBUG_TABLES`.
- [x] 3.2 Удалить `debug_audit_log` из schema/migrations и связанные backend/frontend тесты.
- [x] 3.3 Обновить verification и проверить отсутствие SQLite/Audit на странице и в API.

## 4. Verification

- [x] 4.1 Выполнить backend и frontend test suites.
- [x] 4.2 Собрать production frontend.
- [x] 4.3 Провести production Playwright smoke под реальным `admin` с проверкой единственной панели Application log.

## 5. Log noise and search refinements

- [x] 5.1 Исключить Uvicorn access-записи `/api/debug/logs`, сохранив ошибки endpoint и остальные логи.
- [x] 5.2 Подключить существующий `useDebouncedValue` к текстовому поиску Application log.
- [x] 5.3 Добавить regression-тесты и повторить backend/frontend/build проверки.
