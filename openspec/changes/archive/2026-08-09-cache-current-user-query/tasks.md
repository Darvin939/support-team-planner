## 1. Настроить query текущего пользователя

- [x] 1.1 Добавить `staleTime` 60 секунд только в конфигурацию `useMe`
- [x] 1.2 Сохранить существующие query key, retry и контракт данных текущего пользователя

## 2. Проверить поведение

- [x] 2.1 Добавить frontend-тест последовательного монтирования двух потребителей `useMe` с единственным вызовом query function
- [x] 2.2 Выполнить frontend unit-тесты и production build
- [x] 2.3 Выполнить Python + Playwright проверку числа `/api/me` при реальной загрузке планировщика с WAL-безопасным backup БД
- [x] 2.4 Выполнить `openspec validate cache-current-user-query --strict`
