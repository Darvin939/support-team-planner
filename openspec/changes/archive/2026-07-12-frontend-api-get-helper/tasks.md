## 1. Helper

- [x] 1.1 Added `apiGet<T>(url: string): Promise<T>` to `frontend/src/lib/apiMutate.ts`, mirroring `apiMutate`'s
      fetch/parse/error-throw logic.

## 2. Migration

- [x] 2.1 Grepped the frontend for hand-rolled `fetch(` + `if (!r.ok) throw` query blocks — found **19**
      occurrences across **8** files (more than the ~14 originally estimated): `hooks/usePlanningData.ts` (10,
      via a shared local `getJson<T>` helper), `hooks/useSettingsData.ts` (5, via its own identical local
      `getJson<T>` helper), `pages/StatisticsPage.tsx` (1), `pages/JournalPage.tsx` (2),
      `pages/planning/HistoryPanel.tsx` (1), `hooks/useMe.ts` (1), `hooks/useUserNames.ts` (1), `hooks/useTeams.ts`
      (1).
- [x] 2.2 Replaced every occurrence with `apiGet<T>(url)`, preserving each existing query key and URL-building
      logic exactly. Removed both local `getJson<T>` helpers (`usePlanningData.ts`, `useSettingsData.ts`) since
      they became dead code once their callers migrated.

## 3. Verification

**Caveat**: no browser automation tool was available in this session, so no interactive click-through was
performed. What was verified instead:

- [x] 3.1 `npm run build` succeeds with zero TypeScript errors across all 8 modified files (the generic
      `apiGet<T>` type-checks correctly against every call site's inferred/annotated return type). Confirmed via
      `starlette.testclient.TestClient` against the real running app that all 18 distinct migrated endpoint
      shapes (tasks, assignments, task-deps, active-assignments, team-blocks, team-templates, dependency-graph,
      active-tasks-list, users, blocks, block-templates, freeze-days, segments, me, teams, journal, task-history,
      assignment-history) return `200` with well-formed JSON bodies — the same responses `apiGet` would parse and
      return.
- [x] 3.2 Manual check: forced two error responses — `GET /api/teams/999999` (`404 {"error": "Team not found"}`)
      and an unauthenticated `GET /api/tasks/1` (`401 {"error": "Не авторизован"}`) — both carry the
      `{"error": "..."}` shape `apiGet` prefers over its generic fallback message, confirming the error contract
      specced in `frontend-api-error-format/spec.md` holds against the real server.
- [ ] **Not done — recommend a manual spot-check**: opening Planning/Settings/Statistics/Journal in a browser to
      confirm data renders and error toasts display as expected — a code/type-level check can't catch every
      possible rendering issue.
