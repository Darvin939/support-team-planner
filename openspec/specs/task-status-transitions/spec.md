# task-status-transitions Specification

## Purpose
TBD - created by archiving change shared-task-transitions-source. Update Purpose after archive.
## Requirements
### Requirement: One JSON file is the source of truth for task-status transitions
The set of allowed task-status transitions SHALL be defined in exactly one file
(`frontend/src/data/taskTransitions.json`), read directly by both the backend (`support_planner.py`) and the
frontend (`PlanningPage.tsx`) — neither maintains its own independent copy of the transition map.

#### Scenario: Backend enforcement matches the shared file
- **WHEN** `PATCH /api/tasks/{id}/status` is called with a target status
- **THEN** it is accepted or rejected based on the transitions loaded from `taskTransitions.json`, not a
  hardcoded Python literal

#### Scenario: Frontend UI matches the shared file
- **WHEN** the Planning page renders the status-change menu for a task
- **THEN** the offered transitions come from importing `taskTransitions.json`, not a hardcoded TypeScript literal

#### Scenario: Editing the shared file changes both sides
- **WHEN** a new transition is added to `taskTransitions.json` (e.g. `"done": ["new"]`)
- **THEN** both the backend's validation and the frontend's offered menu items reflect it after their next
  restart/rebuild, with no other file needing to change

#### Scenario: Existing rule is preserved
- **WHEN** the app is deployed with the migrated file
- **THEN** the only transition allowed is `new → done` and `new → cancelled` (unchanged from today), and no
  transition from `done`/`cancelled` is allowed

