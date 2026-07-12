## 1. Implementation

- [x] 1.1 Added `_get_template_blocks(conn, template_id)` to `db/__init__.py`, running the shared query and
      returning `[{'id', 'name', 'shift_days'}, ...]`.
- [x] 1.2 Updated `get_all_templates`'s per-template loop to call `_get_template_blocks(conn, t['id'])`.
- [x] 1.3 Updated `get_template_by_id` to call `_get_template_blocks(conn, template_id)`.
- [x] 1.4 Updated `get_team_allowed_templates`'s per-template loop to call `_get_template_blocks(conn, t['id'])`.

## 2. Verification

- [x] 2.1 Manual check (via `starlette.testclient.TestClient`/direct `db` calls against the real app):
      `GET /api/block-templates` (`get_all_templates`) returned all 3 seeded templates with unchanged block
      lists/order — "Корпоративный релиз": ГФ(-3), Б1(-1), ГИС(0), ПРОД(2); "Стандартный релиз": ГФ(-2), Б1(0),
      Б2(1), ПРОД(3); "Ускоренный релиз": ГФ(-1), ПРОД(1). `get_template_by_id` has no dedicated HTTP route (it's
      internal-only, used by `update_template_api`) — called directly via `db.get_template_by_id(1)`, returned
      the same "Стандартный релиз" data.
- [x] 2.2 Manual check: `GET /api/teams/1` (backed by `get_team_allowed_templates`) returned "Стандартный релиз"
      with the same unchanged block list — matches 2.1's `get_template_by_id(1)` result exactly, as expected
      since they're the same template.
- [x] 2.3 AssignmentModal's block-template dropdown reads its data from the same `GET /api/teams/{id}` endpoint
      exercised in 2.2 (per `useTeams`/`AssignmentModal.tsx`), so this scenario is covered by the same test — no
      separate check needed since it's the identical DAO call and response shape.
