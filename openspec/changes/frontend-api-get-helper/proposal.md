## Why

`frontend/src/lib/apiMutate.ts` is a single, consistent helper for POST/PUT/PATCH/DELETE, used throughout the
app's mutations. There is no equivalent for GET/read requests: every `useQuery`'s `queryFn` across
`hooks/usePlanningData.ts`, `hooks/useSettingsData.ts`, `hooks/useTeams.ts`, `hooks/useMe.ts`,
`hooks/useUserNames.ts`, plus inline query functions in `JournalPage.tsx` and `StatisticsPage.tsx`, hand-rolls its
own `fetch(url, {credentials: 'same-origin'}) + if (!r.ok) throw new Error(...)` block — roughly 14 occurrences
across 11 files (**corrected during implementation**: a full grep found 19 occurrences across 8 files —
`usePlanningData.ts` and `useSettingsData.ts` each route through their own local `getJson<T>` helper rather than
inlining `fetch` at every call site, so the initial estimate undercounted call sites inside those two files while
overcounting the file total; `pages/planning/HistoryPanel.tsx` was also missed initially). The error-message
format is also inconsistent: some throw `` `GET ${url} -> ${status}` ``
unconditionally (`JournalPage.tsx`, `StatisticsPage.tsx`), while `apiMutate` prefers the server's own `data.error`
message first, falling back to a status-code string only when the body has none.

## What Changes

- Add `apiGet<T>(url: string): Promise<T>` to `frontend/src/lib/apiMutate.ts` (or a sibling `apiGet.ts`),
  mirroring `apiMutate`'s error-message preference: server's `data.error` first, `` `GET ${url} -> ${status}` ``
  fallback.
- Replace the 19 hand-rolled `fetch`+error-check blocks in query functions with calls to `apiGet`, and delete the
  two now-dead-code local `getJson<T>` helpers they superseded.

## Capabilities

### New Capabilities
- `frontend-api-error-format`: consistent error-message contract for both reads and writes — prefer the server's
  `{"error": "..."}` body, fall back to a generic `METHOD url -> status` string.

### Modified Capabilities
- (none)

## Impact

- `frontend/src/lib/apiMutate.ts`: new exported `apiGet` helper.
- 8 files across `hooks/` and `pages/` updated to call it instead of inlining `fetch` (or a local `getJson`
  helper).
- Minor behavior change (intentional, not a regression): the handful of call sites that today always throw
  `` `GET ${url} -> ${status}` `` (ignoring any `error` field the server sent) will start preferring the server's
  message, same as `apiMutate` already does — this makes error toasts more informative, not less.
