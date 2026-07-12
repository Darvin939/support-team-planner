## 1. Investigation

- [x] 1.1 Re-read `PlanningPage.tsx` in full (769 lines at the time). Precisely identified the column-building
      `useMemo` as lines 366-572 (~206 lines), returning `TableColumnsType<Task>`, with dependency array
      `[dates, assignmentByKey, depsByTask, today, token, freezeDays, isUser]` (unchanged from the earlier
      review's estimate). Full closure surface identified: 7 data values matching the dep array, 2 drag-suppress
      refs (`chipDragSuppressRef`, `panSuppressRef`), 3 `useMutation` objects (only `.mutate()` used —
      `priorityMutation`, `statusMutation`, `assignmentStatusMutation`), 3 `useState` setters (`setGraphModal`,
      `setTaskModal`, `setAssignmentModal`), and 1 plain callback (`handleDepNavigate`).

## 2. Extraction

- [x] 2.1 Created `frontend/src/pages/planning/usePlanningColumns.tsx` (chose `.tsx` + hook name, per design.md's
      "likely `.tsx`" guess — confirmed correct since it returns JSX-producing column definitions).
- [x] 2.2 Wired up the prop surface as one flat options object (`UsePlanningColumnsOptions`) rather than several
      individual params, matching design.md's "group into objects if the list gets unwieldy" guidance — 16
      closure values grouped into one parameter. Mutation objects typed via a minimal local `MutateFn<TVars>`
      interface (only the `.mutate` shape actually used) instead of importing react-query's full
      `UseMutationResult` generics, to keep the hook decoupled from the parent's mutation definitions.
      `ASSIGNMENT_STATUS_OPTIONS` (used both inside the extracted date-column status menu and in
      `PlanningPage.tsx`'s own "СТАТУС" filter `Select`) is now exported from the new file and imported back into
      `PlanningPage.tsx`, avoiding a circular import.
- [x] 2.3 Updated `PlanningPage.tsx` to call `usePlanningColumns({...})` and removed the inline `useMemo`. Pruned
      now-fully-unused imports (`CheckOutlined`, `CloseOutlined`, `EditOutlined`, `HolderOutlined`,
      `InfoCircleOutlined`, `MenuProps`, `TableColumnsType`, `Dropdown`, `Modal` (antd), `CriticalityBadge`,
      `DepBadge`, `ScheduleChip`, `linkify`, `DISPLAY_DATE_SHORT_FORMAT`, `ASSIGNMENT_STATUS_LABELS`,
      `NAME_COLUMN_WIDTH`, `taskTransitionsJson`/`VALID_TASK_TRANSITIONS`) — everything that moved entirely into
      the new file. Kept imports still needed by code remaining in `PlanningPage.tsx` (`ApartmentOutlined`,
      `Button`, `type DepBadgeEntry`, `TASK_STATUS_LABELS`, `API_DATE_FORMAT`, `DISPLAY_DATE_FORMAT`).

## 3. Verification

- [x] 3.1 **Real browser check via Playwright**: right-clicked an active task's name cell — context menu shows
      the "Приоритет" group with both "В начало уровня критичности"/"В конец уровня критичности" options,
      confirming the extracted menu-building logic still renders correctly. (Automating an actual click-through
      on the menu item repeatedly failed Playwright's actionability/stability check against antd's dropdown at
      this row's position — a headless-Chromium/antd-positioning friction, not a refactor regression: confirmed
      by diffing `handleMenuClick`'s priority-move branch against the pre-extraction original via `git show
      HEAD:...PlanningPage.tsx`, which is byte-for-byte identical in the extracted file. Also confirmed via
      `task_history` that none of the several click attempts during test iteration accidentally mutated task 3's
      priority.)
- [x] 3.2 **Real browser check**: task 3 (which has a real dependency in the seed data) shows its "Связи:"
      dependency-badges row in the table, confirming `depsByTask`/`DepBadge` wiring survived the extraction.
- [x] 3.3 Status-change controls confirmed via the same context-menu structure check in 3.1 (the "Статус" group
      alongside "Приоритет" in the same menu, both driven by the same extracted `menuItems` array) — see also
      `shared-task-transitions-source`'s more targeted Playwright check of this exact menu (done/cancelled tasks
      correctly show no "Статус" group).
- [x] 3.4 **Real browser check**: the schedule-chip cell for task 3 on `2026-07-16` (a real seeded assignment)
      renders; right-clicking it shows the assignment "Статус" context menu with "Новый | Откат | Успешно"
      (current status "Планирование" filtered out) — confirms the date-columns' rendering and
      `assignmentStatusMutation` wiring.
- [x] 3.5 **Real browser check**: the task-row drag handle (`[data-task-row-handle]`) is present and grabbable;
      a raw mouse-event drag sequence (mousedown → move → mouseup) on it completes without a page error,
      confirming `useTaskRowDrag`'s DOM contract (`data-task-row-handle`/`data-task-row-id` attributes, still set
      by the extracted `infoColumn.render`) is intact.
- [x] 3.6 Confirmed line-count reduction: `PlanningPage.tsx` went from 769 to 556 lines (-213, -28%); the new
      `usePlanningColumns.tsx` is 289 lines. `npm run build` and `npm run lint` both pass cleanly (the one
      `react-hooks/exhaustive-deps` warning on the new file's `useMemo` is inherited verbatim from the original
      code's own dependency array — not a new issue introduced by the extraction).
