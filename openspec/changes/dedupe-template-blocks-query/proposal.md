## Why

The query fetching a block template's blocks (`template_blocks JOIN blocks`, ordered by `schedule_offset ASC,
b.name ASC`) is duplicated three times in `db/__init__.py`: inside `get_all_templates`'s per-template loop, inside
`get_template_by_id`, and inside `get_team_allowed_templates`'s per-template loop. Same SQL, same result mapping
(`{'id', 'name', 'shift_days'}` per block), three copies.

## What Changes

- Add a private helper `_get_template_blocks(conn, template_id) -> list[dict]` in `db/__init__.py`, returning the
  already-mapped `[{'id', 'name', 'shift_days'}, ...]` list.
- Replace the duplicated query + mapping in all three functions with a call to this helper.

## Capabilities

### New Capabilities
- `block-template-composition`: shared contract for how a template's ordered list of blocks (with schedule
  offsets) is fetched, reused by all three read paths that expose it.

### Modified Capabilities
- (none)

## Impact

- `db/__init__.py`: new private helper; three functions' block-fetching logic replaced with calls to it.
- No behavior change — response shape for `/api/block-templates`, `/api/block-templates/{id}`, and
  `/api/teams/{id}` (whose `templates` field embeds this data) is unchanged.
