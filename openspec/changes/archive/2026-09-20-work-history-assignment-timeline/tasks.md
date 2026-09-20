## 1. Backend timeline API

- [x] 1.1 Add SQL reader for non-deleted task assignments selecting only `date`, `block`, `status`, ordered by `date, id`.
- [x] 1.2 Add protected `GET /api/task/{task_id}/assignment-timeline` with access check and response model.
- [x] 1.3 Add backend tests for DTO, deleted-row filtering, ordering, and access denial.

## 2. Frontend data layer

- [x] 2.1 Add minimal timeline DTO type and task-scoped query key.
- [x] 2.2 Implement `useTaskAssignmentTimeline` with enabled flag and React Query caching.
- [x] 2.3 Implement pure date-range and comma-separated block helpers.

## 3. Shared assignment table

- [x] 3.1 Create read-only `AssignmentTimeline` with date columns and horizontal scrolling.
- [x] 3.2 Render separate block badges and localized colored statuses, including unknown-status fallback.
- [x] 3.3 Add loading, error, and empty states.
- [x] 3.4 Cover component and pure helpers with Vitest/RTL tests.

## 4. Card and archive integration

- [x] 4.1 Add timeline as a separate section in terminal `TaskModal`, hidden by default.
- [x] 4.2 Preserve history panel collapsed-by-default behavior.
- [x] 4.3 Add expandable archive rows with lazy timeline loading.
- [x] 4.4 Reset expanded keys when page, search, or period changes.
- [x] 4.5 Add component tests, including no requests for collapsed rows.

## 5. Shared grid and timeline layout revision

- [x] 5.1 Extract shared `PlanningDateGrid` layout primitive from auto-scheduling grid, preserving its existing interactive block rendering and drag/drop behavior.
- [x] 5.2 Reuse the shared primitive in `AssignmentTimeline` with bounded modal/container width, click-and-drag horizontal scroll, sticky opaque first column, and correct z-index layering.
- [x] 5.3 Change timeline rendering to one status group per date with comma-separated block names; use `Дата` and `Блок` first-column labels.
- [x] 5.4 Add unit/component coverage for grouping, labels, scroll hook wiring, and sticky layout styles without regressing auto-scheduling behavior.
- [x] 5.5 Constrain expanded archive timeline width, render status on a second line, and suppress text selection/context menu during grid drag.

## 6. Verification

- [x] 6.1 Run backend pytest for new and affected API scenarios.
- [x] 6.2 Run frontend Vitest, lint, and production build.
- [x] 6.3 Run production UI verification of archive expansion with the real backend; terminal-card integration is covered by component tests.
