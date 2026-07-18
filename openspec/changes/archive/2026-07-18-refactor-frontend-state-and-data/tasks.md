## 1. Общие primitives

- [x] 1.1 Добавить `useDebouncedValue` и перевести Planning, Journal, Users и TaskModal, сохранив delay и trim каждого экрана.
- [x] 1.2 Вынести реально используемые общие `Criticality`, `TaskStatus`, `AssignmentStatus` и labels, не добавляя неиспользуемые доменные экспорты.
- [x] 1.3 Добавить безопасный типизированный helper для localStorage и перевести простые сохраняемые значения без изменения ключей.

## 2. TanStack Query и API

- [x] 2.1 Создать типизированные factories query keys с прежней структурой ключей.
- [x] 2.2 Перевести queries Planning, Settings, Journal и Statistics на factories.
- [x] 2.3 Добавить доменные invalidation helpers для задач, назначений и зависимостей и заменить повторяющиеся группы вызовов.
- [x] 2.4 Унифицировать построение query parameters через общий API URL helper.

## 3. Назначения

- [x] 3.1 Добавить типизированный API payload назначения и чистую функцию `assignmentToPayload(existing, patch)`.
- [x] 3.2 Вынести повторяемые save/delete assignment mutations и сообщения в hooks, сохранив различия сценариев.
- [x] 3.3 Перевести PlanningPage и AssignmentModal на общие payload/mutations; bulk и autoassign оставить отдельными workflow.

## 4. Навигация и пагинация

- [x] 4.1 Добавить `useStoredTeamRoute` и перевести Planning/Journal с сохранением текущих redirect-правил.
- [x] 4.2 Добавить `usePaginationState` с page/offset/pageSize/reset и перевести Users, Journal, History и Statistics там, где контракт совпадает.
- [x] 4.3 Вынести повторяемую offset-pagination разметку без объединения разных visual variants.

## 5. История и крупные компоненты

- [x] 5.1 Вынести общий query hook и renderer записей истории для HistoryPanel и TaskHistoryModal.
- [x] 5.2 Вынести state/mutations/filter-navigation части PlanningPage в domain hooks и сохранить локальный JSX экрана.
- [x] 5.3 Вынести assignment form/mutations и auto-assignment state из AssignmentModal, сохранив AutoScheduleGrid и поведение формы.
- [x] 5.4 Проверить отсутствие лишних универсальных abstractions и удалить ставший неиспользуемым код/imports.

## 6. Проверка

- [x] 6.1 После каждого логического блока запускать `npm run build` и устранять TypeScript/React regressions.
- [x] 6.2 Запустить существующие backend-тесты для контроля общего рабочего дерева.
- [x] 6.3 Выполнить production UI-тесты Python + Playwright для поиска, командной навигации, пагинации, CRUD задач/назначений, истории и настроек; остановить процессы и восстановить БД.
