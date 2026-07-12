## Why

`VALID_TASK_TRANSITIONS` — the map of allowed task-status transitions (`{'new': {'done', 'cancelled'}}`) — is
defined twice: `support_planner.py:193-195` (Python, enforced server-side in `update_task_status_api`) and
`frontend/src/pages/PlanningPage.tsx:62-64` (TypeScript, used to decide which transitions to offer in the UI).
CLAUDE.md itself already flags this as a manually-synced pair that "must stay in sync." The values currently
match, but there's no mechanism preventing drift — a future change to one side (e.g. adding a `done → cancelled`
transition) is easy to make in one file and forget in the other, silently degrading the UI (offering/hiding
transitions that don't match what the server actually allows) rather than failing loudly.

## What Changes

- Move the transition map into one canonical JSON file, `frontend/src/data/taskTransitions.json`, living inside
  the frontend source tree so Vite/TypeScript import it natively with no build-config changes
  (`import taskTransitions from '../data/taskTransitions.json'`).
- `support_planner.py` reads the same file at import time (`json.load` from a path relative to the repo root,
  e.g. `frontend/src/data/taskTransitions.json`) instead of defining `VALID_TASK_TRANSITIONS` as a Python literal.
- `PlanningPage.tsx` imports the JSON file directly instead of its local literal.

## Capabilities

### New Capabilities
- `task-status-transitions`: single canonical source of truth for allowed task-status transitions, read
  identically by the backend enforcement and the frontend UI.

### Modified Capabilities
- (none)

## Impact

- New file: `frontend/src/data/taskTransitions.json`.
- `support_planner.py`: `VALID_TASK_TRANSITIONS` becomes a `json.load()` of the shared file instead of a literal
  (set values need converting from JSON arrays to Python `set`s at load time, since the code checks
  `data.status not in allowed` against a `set`).
- `PlanningPage.tsx`: local `VALID_TASK_TRANSITIONS` literal replaced with an import.
- Deployment note: `frontend/src/` must exist at runtime for the backend to read this file — already true today
  (the whole `frontend/` source tree is part of the deployed repo checkout; only `frontend/dist/` is a build
  artifact). No new deployment step.
