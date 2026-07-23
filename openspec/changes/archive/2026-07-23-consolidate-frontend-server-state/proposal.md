## Why

Frontend уже использует React Query и несколько общих hooks, но server-state инфраструктура применяется непоследовательно: рядом с централизованными query keys и URL builder остаются строковые cache keys, ручные query strings, локальные invalidation chains и server hooks внутри страниц. Это создаёт риск устаревшего cache и дублирует код при каждом новом mutation/filter.

## What Changes

- Завершить переход всех queries и invalidations на централизованные типизированные `queryKeys`.
- Использовать один `buildApiUrl` для query parameters вместо ручной конкатенации и локальных `URLSearchParams`.
- Сгруппировать invalidation policies для tasks, dependencies, assignments, teams/users и reference data.
- Вынести task mutations из `PlanningPage` и `TaskModal` в общие domain hooks по аналогии с assignment mutations.
- Вынести journal/statistics server queries из page-компонентов в data hooks.
- Перевести оставшуюся ручную offset pagination архива задач на `usePaginationState`.
- Добавить unit/component coverage query keys, URL generation, invalidation policies и pagination reset.
- Сохранить существующие HTTP-запросы, задержки debounce, сообщения, роли и видимое UI-поведение.
- Не изменять backend: публичный API-контракт не меняется.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `frontend-state-consistency`: одним набором требований уточнить канонические query keys/URL, согласованную invalidation, размещение server-state hooks и общий pagination state.

## Impact

- `frontend/src/lib/queryKeys.ts`, `queryInvalidation.ts`, `apiMutate.ts`.
- Data и mutation hooks Planning, Settings, Journal и Statistics.
- Page/modal components, из которых уйдёт server-state boilerplate.
- Frontend unit tests и production build.
- Backend, API payload и база данных не затрагиваются.
