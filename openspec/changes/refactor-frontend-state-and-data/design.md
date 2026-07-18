## Context

Frontend использует React, Ant Design и TanStack Query. Повторение появилось не в отдельных визуальных атомах, а в управлении состоянием: debounce-effects, query keys, группы invalidation, page/offset, localStorage и payload назначений. PlanningPage и AssignmentModal стали крупными координаторами нескольких независимых процессов.

Рефакторинг должен быть поведенчески нейтральным и выполняться небольшими проверяемыми шагами. Backend и API-контракты не меняются.

## Goals / Non-Goals

**Goals:**

- Убрать безопасно обобщаемое дублирование состояния и data-access.
- Сделать query keys и invalidation единообразными и типизированными.
- Снизить размер и связанность PlanningPage и AssignmentModal.
- Сохранить текущие UX, задержки, сообщения и API payload.

**Non-Goals:**

- Редизайн экранов.
- Изменение backend API.
- Универсальный CRUD-компонент для всех settings-вкладок.
- Унификация всех видов Ant Design Pagination одним визуальным компонентом.
- Переписывание drag-and-drop hooks, графа зависимостей или автопланирования без наличия дублирования.

## Decisions

### Небольшие hooks вместо общего state framework

Добавляются `useDebouncedValue`, типизированный localStorage helper, `useStoredTeamRoute` и `usePaginationState`. Каждый hook имеет узкий контракт. Новая state-библиотека не вводится: текущих React state и TanStack Query достаточно.

### Query key factory как единый источник истины

Все ключи описываются в `queryKeys.ts` с `as const`. Группы invalidation оформляются функциями уровня домена (`invalidateAssignmentData`, `invalidateTaskDependencies`), а не скрываются в универсальном mutation wrapper. Это оставляет зависимости cache явно читаемыми.

### Общий payload и mutations назначений

Преобразование существующего Assignment в API payload выносится в чистую функцию с patch-параметром. Повторяемые save/delete mutations и invalidation переносятся в hooks, но сложные bulk/autoassign workflows остаются рядом со своими координаторами.

### Доменные типы без массового перемещения интерфейсов

Общие строковые union-типы и labels переносятся в `domain/`, но экранные response-интерфейсы остаются рядом с потребителями. Это уменьшает дублирование без создания монолитного файла типов.

### Декомпозиция по ответственности

Из PlanningPage сначала выносятся navigation/filter/pagination и mutations, а из AssignmentModal — form payload/mutations и auto-assignment state. JSX-компоненты выделяются только если имеют самостоятельный контракт. Ограничение по числу строк не является целью само по себе.

### История: переиспользование содержимого, не контейнера

Общими становятся query hook, список записей и offset pagination. Боковая панель и modal сохраняют разную компоновку.

## Risks / Trade-offs

- [Изменятся query keys и перестанет работать invalidation] → Сначала добавить factories с идентичной структурой массивов, затем мигрировать потребителей и проверить сценарии мутаций.
- [Общий debounce изменит trim или задержку] → Передавать уже нормализованное значение и явный delay на каждом экране.
- [Hook навигации создаст redirect loop] → Тестировать состояния teams undefined, пустой список, доступный и недоступный URL ID.
- [Декомпозиция ухудшит читаемость из-за чрезмерного количества файлов] → Выделять только stateful domain hooks и повторяемые primitives; локальный однократный JSX оставлять на месте.
- [Большой refactor усложнит поиск регрессии] → Делать этапы последовательно, запускать build после каждого логического блока и production UI в конце.

## Migration Plan

1. Добавить общие domain types, debounce и query key factories без миграции потребителей.
2. Перевести debounce и query keys, проверить сборку.
3. Вынести assignment payload/mutations и navigation storage hook.
4. Вынести pagination/history primitives.
5. Декомпозировать PlanningPage и AssignmentModal только после стабилизации primitives.
6. Выполнить production build и UI regression suite.

Rollback выполняется по этапам: каждый новый hook можно заменить прежней локальной реализацией без backend-миграций.

## Open Questions

Нет.
