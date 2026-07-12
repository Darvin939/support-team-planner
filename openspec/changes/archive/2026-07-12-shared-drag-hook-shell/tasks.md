## 1. Shared utilities

- [x] 1.1 Added `copyFontStyle(target: HTMLElement, source: HTMLElement): void` to
      `frontend/src/pages/planning/scrollUtils.ts`, copying `fontFamily`/`fontSize`/`fontWeight`/`color` from
      `getComputedStyle(source)` onto `target.style`.
- [x] 1.2 Added `export const DRAG_START_THRESHOLD_PX = 5;` to the same file.

## 2. Migration

- [x] 2.1 In `useAssignmentDrag.ts`, replaced the 4-line font-copy block with `copyFontStyle(ghost,
      state.sourceChip)` (kept the separate `ghost.style.width = ...` line, which uses
      `getBoundingClientRect()`, not `getComputedStyle()` — unrelated to the font-copy), and the inline `5` in the
      threshold check with `DRAG_START_THRESHOLD_PX`.
- [x] 2.2 In `useTaskRowDrag.ts`, replaced the equivalent font-copy block with `copyFontStyle(ghost,
      sourceForStyle)` inside the existing `if (sourceForStyle)` guard (`copyFontStyle` requires a non-null
      `HTMLElement`, matching the guard's purpose), and the inline `5` with `DRAG_START_THRESHOLD_PX`.

## 3. Verification

- [x] 3.1 **Real browser check via Playwright**: dragged a throwaway assignment chip from `2026-07-20` to the
      adjacent empty `2026-07-21` cell — ghost appeared once the 5px threshold was exceeded (confirming
      `copyFontStyle`'s styling didn't break ghost creation), the source cell gained `.assignment-drag-source`,
      and the drop fired `POST /api/assignment` with `date: "2026-07-21"` — identical behavior to before the
      change.
- [x] 3.2 **Real browser check**: dragged a task row's handle ~400px down — ghost appeared once the threshold was
      exceeded, and the drop fired `PATCH /api/tasks/1/reorder` with a new `task_ids` order — confirming
      `useTaskRowDrag`'s ghost/threshold logic still works through the shared helper.
- [x] 3.3 **Real browser check**: a 3px mouse movement after mousedown created **no** ghost for either drag
      interaction (assignment chip or task row) — confirms the shared `DRAG_START_THRESHOLD_PX` constant
      preserves the exact same 5px threshold as the original inline `5`.

**Debugging note**: the first test attempts against a real assignment chip failed because the chip's `x`
coordinate (an assignment ~40 days out in a date-range table with ~37 date columns) was outside the browser
viewport — `scrollIntoViewIfNeeded()` before computing the bounding box fixed it. Not a refactor issue, purely a
test-script gap.

**Cleanup**: the throwaway task/assignment created for 3.1/3.2 was deleted afterward via the API. The task-row
drag in 3.2 reordered 3 *real* seeded tasks (team 1, low-criticality tier) as a side effect of actually exercising
the drop — restored their original order (`[1, 4, 7, 10, 13, 16, 19, 22]`) via `PATCH /api/tasks/1/reorder`
immediately after, confirmed via a follow-up `GET /api/tasks/1`.
