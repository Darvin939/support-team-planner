## Context

Read in full: `useAssignmentDrag.ts:36-221` and `useTaskRowDrag.ts:37-183`. Concretely identical fragments:

1. **Font-copy on ghost creation** — `useAssignmentDrag.ts:117-122` and `useTaskRowDrag.ts:118-123` both do:
   ```ts
   const cs = getComputedStyle(sourceEl);
   ghost.style.fontFamily = cs.fontFamily;
   ghost.style.fontSize = cs.fontSize;
   ghost.style.fontWeight = cs.fontWeight;
   ghost.style.color = cs.color;
   ```
2. **Drag-start threshold** — `useAssignmentDrag.ts:105` and `useTaskRowDrag.ts:88` both do
   `!state.dragStarted && Math.sqrt(dx * dx + dy * dy) > 5`.

Everything else that looks superficially similar (the `DragState` shape, the mousemove branch logic, ghost
positioning math, cleanup specifics) is algorithmically different between horizontal cell-drag and vertical
row-reorder — not restatable as one shared function without a parametrized abstraction layer.

## Goals / Non-Goals

**Goals:** remove the two concretely-duplicated fragments above; zero behavior change.

**Non-Goals:** unifying the two hooks into one generic/parametrized "drag hook" — evaluated and rejected (see
Decisions). Not touching `useAutoScheduleDragScroll.ts`/`useTableDragScroll.ts` (the edge-auto-scroll helpers) —
out of scope for this change, which is specifically about the two identified fragments.

## Decisions

- **Extract only the font-copy helper and the threshold constant, not a shared base hook.** Considered building
  a generic `useDocumentDrag<TState>({ onMouseDown, onMouseMove, onMouseUp })` wrapping the
  addEventListener/removeEventListener boilerplate and threshold check: rejected. The two hooks' `handleMouseMove`
  bodies are the bulk of each file (dozens of lines of genuinely distinct logic — auto-scroll math and
  `elementFromPoint` hit-testing vs. midpoint/insertion-index math) and don't share a callback shape a generic
  wrapper could usefully abstract over without becoming a thin, leaky pass-through that adds a layer of
  indirection for a reader tracing through the code, while saving only the ~10 lines of
  `document.addEventListener`/`removeEventListener` calls that are already trivial to read inline.
- **`copyFontStyle` as a pure function**, not a hook — it has no React state/lifecycle, just DOM style copying,
  so it belongs with `scrollUtils.ts`'s existing pure helpers (`findScrollableAncestor`) rather than being
  wrapped in a hook itself.

## Risks / Trade-offs

- [Risk] This change is deliberately smaller in scope than "deduplicate the two drag hooks" might imply —
  someone expecting a unified drag hook after reading only the proposal title might be surprised by how narrow
  the actual diff is → Mitigation: this design.md explicitly documents why full unification was evaluated and
  rejected, so the scope limit is a recorded decision, not an oversight.
