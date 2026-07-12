## Context

Per an architecture review, `PlanningPage.tsx`'s column-building `useMemo` (roughly lines 364-567 as of this
writing — verify exact bounds during implementation, since the file will have shifted by the time this change is
applied) constructs both the task-name column (with nested context-menu, dependency badges, and a
priority/status dropdown) and the per-date schedule-chip columns. This is the single largest contiguous chunk of
the file and the main reason it's ~250 lines longer than the next-largest frontend file.

## Goals / Non-Goals

**Goals:** move the column-building logic to its own module, following the existing precedent of
`TaskModal.tsx`/`AssignmentModal.tsx`/`DependencyGraphModal.tsx`/`HistoryPanel.tsx` already being split out of
`pages/planning/`; zero behavior/visual change.

**Non-Goals:** touching the drag hooks (`useAssignmentDrag.ts`, `useTaskRowDrag.ts`), the 5+ `useMutation`s, the
jump-to-task/jump-to-date effects, or the filter state — those are separate concerns from column-building and are
explicitly out of scope for this change (they could each be their own future extraction, but bundling them here
would make this change harder to review and verify).

## Decisions

- **Extract as a hook (`usePlanningColumns(...)`) returning the `ColumnsType` array, not a plain function
  module**, since the column-building logic already depends on component state/callbacks (mutation triggers,
  filter values) that change across renders — a hook keeps the `useMemo`/dependency-array semantics intact rather
  than needing `PlanningPage.tsx` to manually memoize a plain function's output itself.
- **Exact prop/argument surface is an implementation-time decision**, not fixed here — the column-building code
  needs to be read in full first to enumerate what it actually closes over (task list? assignments? mutation
  callbacks? filter state? all of the above are plausible candidates per the proposal's description) rather than
  guessing the hook's signature in advance and having it not match reality.

## Risks / Trade-offs

- [Risk] The column logic likely closes over several pieces of `PlanningPage.tsx` state/callbacks (context menu
  open/close, mutation triggers for status/priority/reorder) — extracting it may require passing a wider prop
  surface than expected, partially offsetting the file-size win with more prop-drilling → Mitigation: if the
  argument list balloons past what's reasonable, group related callbacks into one object parameter (e.g.
  `{ onStatusChange, onPriorityMove, onReorder }`) rather than passing 10+ individual props — a judgment call to
  make during implementation, not pre-specified here.
- [Risk] Since this is a large, mechanical extraction with no test suite to catch a subtle behavior slip (see
  CLAUDE.md: no runnable tests exist), verification is manual-only → Mitigation: tasks.md's verification section
  requires exercising every interactive element the column logic renders (context menu, badges, status dropdown,
  schedule chips) before considering this change done.
