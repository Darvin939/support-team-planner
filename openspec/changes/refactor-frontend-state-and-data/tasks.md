## 1. Общие primitives

- [ ] 1.1 Добавить `useDebouncedValue` и перевести Planning, Journal, Users и TaskModal, сохранив delay и trim каждого экрана.
- [ ] 1.2 Вынести общие `UserRole`, `Criticality`, `TaskStatus`, `AssignmentStatus`, labels и terminal-status helpers.
- [ ] 1.3 Добавить безопасный типизированный helper для localStorage и перевести простые сохраняемые значения без изменения ключей.

## 2. TanStack Query и API

- [ ] 2.1 Создать типизированные factories query keys с прежней структурой ключей.
- [ ] 2.2 Перевести queries Planning, Settings, Journal и Statistics на factories.
- [ ] 2.3 Добавить доменные invalidation helpers для задач, назначений и зависимостей и заменить повторяющиеся группы вызовов.
- [ ] 2.4 Унифицировать построение query parameters через общий API URL helper.

## 3. Назначения

- [ ] 3.1 Добавить типизированный API payload назначения и чистую функцию `assignmentToPayload(existing, patch)`.
- [ ] 3.2 Вынести повторяемые save/delete assignment mutations и сообщения в hooks, сохранив различия сценариев.
- [ ] 3.3 Перевести PlanningPage и AssignmentModal на общие payload/mutations; bulk и autoassign оставить отдельными workflow.

## 4. Навигация и пагинация

- [ ] 4.1 Добавить `useStoredTeamRoute` и перевести Planning/Journal с сохранением текущих redirect-правил.
- [ ] 4.2 Добавить `usePaginationState` с page/offset/pageSize/reset и перевести Users, Journal, History и Statistics там, где контракт совпадает.
- [ ] 4.3 Вынести повторяемую offset-pagination разметку без объединения разных visual variants.

## 5. История и крупные компоненты

- [ ] 5.1 Вынести общий query hook и renderer записей истории для HistoryPanel и TaskHistoryModal.
- [ ] 5.2 Вынести state/mutations/filter-navigation части PlanningPage в domain hooks и сохранить локальный JSX экрана.
- [ ] 5.3 Вынести assignment form/mutations и auto-assignment state из AssignmentModal, сохранив AutoScheduleGrid и поведение формы.
- [ ] 5.4 Проверить отсутствие лишних универсальных abstractions и удалить ставший неиспользуемым код/imports.

## 6. Проверка

- [ ] 6.1 После каждого логического блока запускать `npm run build` и устранять TypeScript/React regressions.
- [ ] 6.2 Запустить существующие backend-тесты для контроля общего рабочего дерева.
- [ ] 6.3 Выполнить production UI-тесты Python + Playwright для поиска, командной навигации, пагинации, CRUD задач/назначений, истории и настроек; остановить процессы и восстановить БД.
