## 1. Канонические keys и URL

- [x] 1.1 Привести `queryKeys` к полному иерархическому registry для Planning, Settings, Journal и Statistics
- [x] 1.2 Заменить raw query-key arrays во frontend на канонические roots/factories
- [x] 1.3 Перевести ручные `URLSearchParams` и query-string concatenation на `buildApiUrl`
- [x] 1.4 Добавить unit-тесты key factories и URL builder для пустых, zero, false и encoded значений

## 2. Invalidation policies

- [x] 2.1 Расширить `queryInvalidation.ts` policies для tasks, assignments, dependencies и settings entities
- [x] 2.2 Перевести task/assignment/settings mutations на policies без локального перечисления cache keys
- [x] 2.3 Добавить unit-тесты матрицы mutation → invalidated query roots

## 3. Domain server-state hooks

- [x] 3.1 Вынести save/delete/restore/status/reorder/priority task mutations в общие hooks с прежними callbacks и messages
- [x] 3.2 Перевести `PlanningPage`, `TaskModal` и `TaskArchiveModal` на task mutation hooks
- [x] 3.3 Вынести Journal query из страницы в data hook
- [x] 3.4 Вынести Statistics active-assignments query из страницы в data hook
- [x] 3.5 Проверить, что page/modal components не содержат дублирующих query functions и invalidation chains

## 4. Pagination и filter state

- [x] 4.1 Перевести task archive offset на `usePaginationState`
- [x] 4.2 Сохранить reset rules Journal, Statistics, Settings, archive и history при изменении фильтров/page size
- [x] 4.3 Добавить hook/component tests вычисления offset и reset behavior

## 5. Проверка frontend

- [x] 5.1 Запустить frontend unit tests, lint/typecheck и production build
- [x] 5.2 Создать WAL-safe backup БД и выполнить Python+Playwright smoke Planning, Journal, Statistics и Settings на production backend
- [x] 5.3 Остановить запущенный backend и при изменении тестовых данных восстановить БД через SQLite backup API с checkpoint
- [x] 5.4 Запустить backend regression suite, `git diff --check` и `openspec validate --all`
