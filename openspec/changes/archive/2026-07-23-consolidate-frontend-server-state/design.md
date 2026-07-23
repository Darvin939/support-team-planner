## Context

Frontend использует React Query, `queryKeys`, `buildApiUrl`, `usePaginationState` и несколько domain hooks, но миграция осталась частичной. Raw query-key literals встречаются в Planning и Settings, invalidation policy определяется как общими helpers, так и непосредственно в компонентах, URL filters собираются разными способами, а Journal/Statistics содержат собственные `useQuery`. Это не меняет текущий UI, но повышает вероятность расхождения cache и повторения boilerplate.

## Goals / Non-Goals

**Goals:**

- Сделать `queryKeys` единственным источником cache identities.
- Сделать `buildApiUrl` единственным способом собирать query parameters.
- Централизовать invalidation по доменным наборам данных.
- Перенести task mutations и page-level server queries в hooks.
- Использовать общий pagination hook во всех offset/page сценариях.
- Сохранить запросы, debounce, роли, toasts и визуальное поведение.

**Non-Goals:**

- Изменение backend/API.
- Изменение структуры экранов или UX.
- Замена React Query либо Ant Design.
- Объединение всего локального UI state в глобальное хранилище.
- Отдельные OpenSpec/specs для Planning, Journal, Statistics и Settings.

## Decisions

### 1. `queryKeys` становится иерархическим каноническим registry

Все queries и invalidations используют функции/roots из `queryKeys`; raw arrays вроде `['tasks']` и `['users']` удаляются. Массивы идентификаторов нормализуются до стабильного порядка до формирования key и URL.

### 2. Invalidation выражается доменными policies

`queryInvalidation.ts` получает helpers для task data, assignment data, dependencies и settings entities. Mutation hooks вызывают policy, а не перечисляют cache keys. Helpers возвращают/ожидают promises там, где последующее UI-действие зависит от завершения invalidation.

Альтернатива — универсальный invalidate-all — проще, но создаёт лишние запросы и скрывает зависимости.

### 3. HTTP query строится только через `buildApiUrl`

Paginated teams/users, Journal, Statistics, task dependencies и active lists используют один builder. Он сохраняет существующее правило пропуска `null`, `undefined` и пустой строки, но не пропускает `false` и `0`.

### 4. Domain hooks владеют server state

Создаются/расширяются hooks:

- task query/mutation hooks для status, reorder, priority, save, delete и restore;
- journal data hook;
- statistics active-assignments hook;
- settings hooks остаются владельцами settings queries.

Page/modal components сохраняют form, selection и presentation state, но не определяют query functions/cache policy.

### 5. Pagination reset остаётся явным поведением экрана

`usePaginationState` используется и в архиве задач. Сбросы при team/search/date/filter изменениях сохраняются в компонентах или специализированном hook; не вводится автоматический reset на любое изменение, чтобы не изменить UX.

### 6. Проверка сочетает unit tests и production UI smoke

Unit tests покрывают URL builder, key factories, invalidation calls и pagination. После production build Python+Playwright проверяет реальные Planning, Journal, Statistics и Settings с настоящей авторизацией, следуя правилам backup/restore БД.

## Risks / Trade-offs

- [Risk] Неполная invalidation оставит stale UI → зафиксировать матрицу mutation → query roots и протестировать каждый policy.
- [Risk] Изменение query key вызовет лишнюю первоначальную загрузку → допустимо после deploy, но внутри сессии все consumers должны перейти атомарно.
- [Risk] Сортировка id изменит порядок, значимый для API → нормализовать только параметры, где порядок семантически не важен (`team_ids`, filter task ids, include ids).
- [Risk] Перенос hooks изменит toast/callback timing → сохранить существующие `onSuccess/onError` callbacks и await semantics.
- [Risk] Общий URL builder иначе обработает пустые значения → добавить unit cases для `0`, `false`, `''`, `null`, массивов как предварительно сериализованных строк.
- [Trade-off] Domain hooks увеличат число файлов/exports, но уберут server-state orchestration из крупных page components.
