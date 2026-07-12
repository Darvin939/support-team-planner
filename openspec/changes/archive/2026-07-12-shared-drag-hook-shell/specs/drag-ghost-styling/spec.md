## ADDED Requirements

### Requirement: Drag-ghost font styling is copied via one shared function
Both `useAssignmentDrag` and `useTaskRowDrag` SHALL copy `fontFamily`, `fontSize`, `fontWeight`, and `color` from
their drag source element onto their ghost element via one shared `copyFontStyle` function, and both SHALL use
the same drag-start distance threshold constant.

#### Scenario: Assignment drag ghost matches source chip styling
- **WHEN** a user starts dragging an assignment chip
- **THEN** the floating ghost's font family/size/weight/color match the source chip's computed style, identical
  to before this refactor

#### Scenario: Task row drag ghost matches source name cell styling
- **WHEN** a user starts dragging a task row via its handle
- **THEN** the floating ghost's font family/size/weight/color match the task-name cell's computed style,
  identical to before this refactor

#### Scenario: Drag-start threshold is shared and unchanged
- **WHEN** a user moves the mouse less than 5px after mousedown in either drag interaction
- **THEN** no drag starts (no ghost appears, no state changes) — same 5px threshold as before, now sourced from
  one shared constant
