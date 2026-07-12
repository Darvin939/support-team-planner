## Why

`frontend/src/pages/PlanningPage.tsx` is 767 lines — the largest file in the frontend by a wide margin (next
largest: `AssignmentModal.tsx` at 519, `DependencyGraphModal.tsx` at 377). It already delegates drag/scroll/
cell-tint logic to `pages/planning/*` helper modules, but still owns team-selection/localStorage sync, 5+
`useMutation`s (status change, reorder, priority move, reschedule, assignment-status), two separate "resolve id →
open modal" effects (jump-to-task/jump-to-date), 6 filter `useState`s, and — the single largest chunk — a
~200-line `useMemo` building the antd `Table` columns (the task-name column with its nested context-menu/
dependency-badge/status-dropdown logic, plus per-date schedule-chip columns), all inline in one component. This
makes the file harder to navigate and review than it needs to be, following the same pattern already applied
successfully to `TaskModal.tsx`/`AssignmentModal.tsx`/`DependencyGraphModal.tsx` being split out of what was
presumably once a monolithic planning page.

## What Changes

- Extract the column-building logic (the task-name column + per-date schedule-chip columns, including their
  nested context-menu/badge/dropdown rendering) from `PlanningPage.tsx`'s inline `useMemo` into a new module under
  `frontend/src/pages/planning/` (e.g. `usePlanningColumns.ts` or `planningColumns.tsx`, exact name TBD based on
  whether it returns JSX-producing column definitions — likely `.tsx`).
- `PlanningPage.tsx` calls the extracted hook/function, passing whatever data/callbacks the column-building logic
  needs (task list, assignments, mutation triggers, filter state) — exact prop surface determined by reading the
  current inline implementation during design.

## Capabilities

### New Capabilities
- `planning-table-structure`: baseline behavior contract for the Planning page's task/schedule table (columns
  rendered, interactions available) that this code-relocation must preserve exactly.

### Modified Capabilities
- (none)

## Impact

- New file(s) under `frontend/src/pages/planning/` for column-building.
- `PlanningPage.tsx` shrinks significantly (column-building logic removed), following the same split pattern
  already used for modals/drag hooks in the same directory.
- No visual or behavioral change — same table, same columns, same interactions.
