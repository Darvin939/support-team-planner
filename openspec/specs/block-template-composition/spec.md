# block-template-composition Specification

## Purpose
TBD - created by archiving change dedupe-template-blocks-query. Update Purpose after archive.
## Requirements
### Requirement: A template's blocks are fetched via one shared function
`get_all_templates`, `get_template_by_id`, and `get_team_allowed_templates` SHALL fetch a template's blocks
(id, name, `shift_days`) via one shared function, ordered by schedule offset then block name.

#### Scenario: Blocks are ordered by offset then name
- **WHEN** a template has blocks with schedule offsets `[2, 0, 0]` and names `['Б1', 'ГФ', 'АБВ']` respectively
- **THEN** the returned list orders the two offset-0 blocks alphabetically (`АБВ`, `ГФ`) before the offset-2 block
  (`Б1`)

#### Scenario: Consistent shape across all three callers
- **WHEN** the same `template_id` is fetched via `GET /api/block-templates`, `GET /api/block-templates/{id}`, and
  (embedded) `GET /api/teams/{id}`
- **THEN** the `blocks` array for that template is identical across all three responses

