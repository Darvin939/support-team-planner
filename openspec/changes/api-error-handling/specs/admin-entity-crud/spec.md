## ADDED Requirements

### Requirement: Constraint violations return 400 with a specific message
Create/update endpoints for teams, blocks, block templates, and segments SHALL respond `400 {'error': '<specific
message>'}` when the operation violates a uniqueness constraint (duplicate name). The segment delete endpoint
SHALL respond `400 {'error': '<specific message>'}` when the segment is still referenced by a task or block
template. All other, unexpected errors SHALL propagate as a 500 rather than being coerced into a 400.

#### Scenario: Duplicate team name on create
- **WHEN** `POST /api/teams` is called with a `name` that already exists
- **THEN** the API responds `400 {'error': 'Команда с таким названием уже существует'}`

#### Scenario: Duplicate name on update
- **WHEN** `PUT /api/teams/{id}`, `PUT /api/block-templates/{id}`, or `PUT /api/segments/{id}` is called with a
  `name` already used by a different row
- **THEN** the API responds `400` with a message naming the conflicting entity type

#### Scenario: Deleting a referenced segment
- **WHEN** `DELETE /api/segments/{id}` is called for a segment still referenced by a task or block template
- **THEN** the API responds `400 {'error': '...'}` instead of an unhandled 500

#### Scenario: Deleting a referenced team, block, or template is not a constraint violation
- **WHEN** `DELETE /api/teams/{id}`, `DELETE /api/blocks/{id}`, or `DELETE /api/block-templates/{id}` is called
  for an entity still referenced elsewhere (a team with tasks, a block used in a template, a template assigned to
  a team)
- **THEN** the delete succeeds (200) and the referencing rows are removed via cascade — this is existing,
  intentional schema behavior (`ON DELETE CASCADE`), not an error condition this change handles

#### Scenario: Unexpected error is not masked
- **WHEN** any of the create/update endpoints, or segment delete, hits an error that is not a constraint
  violation (a genuine bug)
- **THEN** the API responds with a 500 (FastAPI's default unhandled-exception behavior), not a 400
