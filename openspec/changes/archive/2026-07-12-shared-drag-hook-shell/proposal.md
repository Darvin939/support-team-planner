## Why

`useAssignmentDrag.ts` (221 lines) and `useTaskRowDrag.ts` (183 lines) are both hand-rolled
mousedown/mousemove/mouseup drag implementations sharing a family resemblance: an `optionsRef` pattern, a
button-0-only gate, a 5px-movement drag-start threshold (`Math.sqrt(dx*dx+dy*dy) > 5`, identical in both), a
cloned/created ghost element appended to `document.body` with font styles copied from `getComputedStyle(source)`
(`fontFamily`/`fontSize`/`fontWeight`/`color`, duplicated near-verbatim in both files), and identical
`document.addEventListener`/`removeEventListener` wiring + cleanup in `useEffect`. Having now read both files in
full: the two `DragState` interfaces are entirely different shapes (one tracks cell/date/occupancy for horizontal
movement, the other tracks row midpoints/insertion-index for vertical reordering), and the mousemove logic
(auto-scroll + `elementFromPoint` cell hit-testing vs. midpoint-based insertion-index computation) is genuinely
distinct, not superficially different names for the same algorithm. Forcing both into one generic parametrized
hook would need a state-machine abstraction flexible enough to cover both axes/algorithms, which is very likely
to add more indirection than the ~15-20 lines of true duplication it would remove.

## What Changes

- Extract the two genuinely identical, low-risk pieces of duplication into small shared utilities in
  `frontend/src/pages/planning/` (alongside the existing `scrollUtils.ts`/`cellTint.ts` pure helpers):
  - `copyFontStyle(target: HTMLElement, source: HTMLElement)` — copies `fontFamily`/`fontSize`/`fontWeight`/
    `color` from `getComputedStyle(source)` onto `target`, replacing the duplicated 4-line block in both files'
    ghost-creation code.
  - `DRAG_START_THRESHOLD_PX = 5` constant (+ optionally a tiny `exceedsDragThreshold(dx, dy)` helper), replacing
    the duplicated magic-number threshold check in both files.
- **Not extracting** the full mousedown/mousemove/mouseup shell, the `optionsRef` pattern, or event-listener
  wiring into a shared base hook — see design.md for why this is a deliberate scope limit, not an oversight.

## Capabilities

### New Capabilities
- `drag-ghost-styling`: shared contract for how a drag-ghost element's font styling is copied from its source
  element, used identically by both drag interactions.

### Modified Capabilities
- (none)

## Impact

- New file (or addition to `scrollUtils.ts`): `copyFontStyle` utility, `DRAG_START_THRESHOLD_PX` constant.
- `useAssignmentDrag.ts` and `useTaskRowDrag.ts`: their duplicated font-copy and threshold-check code replaced
  with calls to the shared utility/constant; everything else (the genuinely distinct drag algorithms) untouched.
- No behavior change — both drag interactions (assignment cell drag, task row reorder) work identically.
