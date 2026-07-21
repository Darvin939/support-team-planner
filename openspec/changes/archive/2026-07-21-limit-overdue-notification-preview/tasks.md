## 1. Ограниченный hook уведомлений

- [x] 1.1 Добавить `OVERDUE_PREVIEW_LIMIT = 30`, отдельный query key и параметры `offset=0&limit=30` в `useOverdueAssignments`.
- [x] 1.2 Изменить тип результата hook на API-response с `items` и `total`, сохранив период и пятиминутный refetch.

## 2. Представление popover

- [x] 2.1 Перевести список, badge, заголовок и обработчик навигации `OverdueNotifications` на `items`/`total`.
- [x] 2.2 Показывать сообщение «Показаны первые 30 из N», только когда `total` превышает длину preview.

## 3. Проверка

- [x] 3.1 Собрать production-frontend и устранить ошибки TypeScript/build.
- [x] 3.2 Перед UI-тестом создать WAL-безопасную резервную копию `database.db`; через Python + Playwright и реальную авторизацию проверить запрос с `limit=30`, badge полного количества, максимум 30 элементов и сообщение об ограничении.
- [x] 3.3 Остановить запущенный тестом backend; при изменении БД восстановить её через SQLite backup API, выполнить `PRAGMA wal_checkpoint(TRUNCATE)` и проверить целостность.
