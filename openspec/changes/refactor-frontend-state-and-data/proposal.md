## Why

Frontend накопил повторяющиеся реализации debounce, URL/localStorage-синхронизации, пагинации, query keys и mutation invalidation. Это повышает стоимость изменений и создаёт риск, что одинаковые сценарии начнут вести себя по-разному на Planning, Journal, Statistics и в модальных окнах.

## What Changes

- Добавляются общие hooks для debounce и сохраняемого состояния.
- Унифицируется синхронизация выбранной команды между URL, localStorage и доступным списком команд.
- React Query keys и группы invalidation переносятся в единый типизированный слой.
- Формирование payload и mutations назначений перестают дублироваться между PlanningPage и AssignmentModal.
- Общие доменные типы ролей, статусов и критичности выносятся из отдельных страниц.
- Повторяющиеся history/pagination primitives переиспользуются без унификации различающейся компоновки.
- PlanningPage и AssignmentModal декомпозируются по зонам ответственности.
- Пользовательское поведение, API-контракты и визуальное представление остаются без изменений.

## Capabilities

### New Capabilities

- `frontend-state-consistency`: Единые правила debounce, query cache invalidation, сохраняемой командной навигации и пагинационного состояния без изменения наблюдаемого поведения.

### Modified Capabilities

Нет.

## Impact

- `frontend/src/hooks`, новый слой query keys/domain types и API helpers.
- PlanningPage, JournalPage, StatisticsPage, UsersTab, TaskModal, AssignmentModal и HistoryPanel.
- Backend и форматы API не изменяются.
- Production UI-тесты должны подтвердить отсутствие регрессий основных сценариев.
