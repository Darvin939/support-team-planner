## ADDED Requirements

### Requirement: Settings entity save/delete follows a shared mutation contract
Saving (create or update) or deleting an entity on a Settings tab that adopts the shared hook SHALL: invalidate
the entity's list query and close the modal on success with a success toast; show an error toast with the
server's error message on failure; and leave the modal open on failure so the user can correct and retry.

#### Scenario: Successful create
- **WHEN** a user submits the "new entity" form and the API call succeeds
- **THEN** the entity list refreshes, the modal closes, and a success toast appears

#### Scenario: Successful update
- **WHEN** a user submits an edit to an existing entity and the API call succeeds
- **THEN** the entity list refreshes, the modal closes, and a success toast appears

#### Scenario: Failed save
- **WHEN** the API rejects a save (e.g. duplicate name → 400)
- **THEN** an error toast shows the server's message and the modal stays open with the user's input preserved

#### Scenario: Successful delete
- **WHEN** a user confirms deletion of an entity and the API call succeeds
- **THEN** the entity list refreshes and a success toast appears

#### Scenario: Behavior is unchanged from before this refactor
- **WHEN** any of the above scenarios occurs on a tab migrated to the shared hook
- **THEN** the observed toast text, timing, and modal behavior are identical to that tab's behavior before the
  refactor
