## Context

`get_all_templates` (`db/__init__.py:219-239`), `get_template_by_id` (`242-261`), and
`get_team_allowed_templates` (`77-107`) each run:
```sql
SELECT b.id, b.name, tb.schedule_offset AS shift_days
FROM template_blocks tb JOIN blocks b ON tb.block_id = b.id
WHERE tb.template_id = ?
ORDER BY tb.schedule_offset ASC, b.name ASC
```
and map the result to `[{'id': b['id'], 'name': b['name'], 'shift_days': b['shift_days']}, ...]` identically in
all three places.

## Goals / Non-Goals

**Goals:** one function, called from all three places, returning the identical list-of-dicts shape.

**Non-Goals:** batching the N+1 query pattern in `get_all_templates`/`get_team_allowed_templates` (one query per
template in a loop) into a single joined query — that's a separate, larger optimization with its own trade-offs
(more complex result-grouping code) and isn't what was asked for here; this change only removes the *duplicated
source code*, not the *duplicated query execution*.

## Decisions

- **Helper takes `conn` explicitly** (not `@with_db_connection`-wrapped itself) since it's always called from
  inside an already-connected function — matches the existing convention for internal helpers like
  `_set_team_templates`, `_set_template_blocks`, `_priority_at_tier_end` in the same file.

## Risks / Trade-offs

- [Risk] None — extraction is behavior-preserving; same SQL text, same ORDER BY, same result mapping.
