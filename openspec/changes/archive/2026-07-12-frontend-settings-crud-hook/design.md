## Context

Per an architecture review of `frontend/src/pages/settings/`, `TeamsTab.tsx`, `SegmentsTab.tsx`, `UsersTab.tsx`,
and `BlocksTab.tsx` (its template list) share this shape: `modalX: X | 'new' | null` state, a `useForm`, a
`saveMutation` using `apiMutate` that POSTs when `modalX === 'new'` and PUTs otherwise, a `deleteMutation`, both
mutations sharing the same `onSuccess` (invalidate the relevant query key, `message.success(...)`, close the
modal) and `onError` (`message.error(e.message)`) shape, and an `openModal(record)` that seeds
`form.setFieldsValue(record)`. `FreezeDaysTab.tsx` was also flagged as structurally similar by an initial
read-only survey, but freeze days are managed via three distinct operations (single date, date range, whole-month
replacement — see `db.add_freeze_day`/`add_freeze_range`/`set_freeze_days_for_month`) rather than a single
entity-with-id create/update/delete triple, so it may not fit this hook's shape as cleanly as the other four.

## Goals / Non-Goals

**Goals:** one hook covering the create/update/delete mutation orchestration for the tabs where it genuinely
fits (at minimum Teams, Segments, Blocks; Users if its bootstrap-admin special-casing doesn't conflict — see Open
Questions), with zero change to toasts, modal behavior, or error messages.

**Non-Goals:** unifying the *form JSX* (fields differ per entity) or the *modal component* itself — only the
mutation/query-invalidation plumbing is shared. Not forcing `FreezeDaysTab` into the same hook if its
add-day/add-range/replace-month operations don't map onto a single entity's create/update/delete.

## Decisions

- **Generic hook signature**: `useCrudMutations<TEntity>({ queryKey, createFn, updateFn, deleteFn, entityLabel })`
  returning `{ saveMutation, deleteMutation }`, where `createFn`/`updateFn`/`deleteFn` are thin wrappers around
  `apiMutate` (matching each tab's existing endpoint calls) and `entityLabel` (e.g. `'Команда'`) parameterizes the
  success-toast text if it currently varies per tab (verify at implementation time — the exact current wording
  needs to be read from each tab file, not assumed).
- **Location**: `frontend/src/hooks/useCrudMutations.ts`, alongside the other domain hooks (`usePlanningData.ts`,
  `useSettingsData.ts`), since it's a data-layer concern, not a UI component.
- **Scope decision deferred per-tab**: implementation should read each of the five tab files first and only
  adopt the hook where the create/update/delete-with-id shape genuinely matches (see Open Questions) — this
  avoids forcing an awkward abstraction onto `UsersTab.tsx` (bootstrap-admin edit restrictions) or
  `FreezeDaysTab.tsx` (non-CRUD operations) if their real shape turns out not to fit.

## Risks / Trade-offs

- [Risk] `UsersTab.tsx` may have bootstrap-admin-specific validation/UI branching that doesn't cleanly separate
  from its mutation logic → Mitigation: read the file before starting; if the branching is only in the *form*
  (which fields are editable), the hook still fits (mutations stay generic); if it's in the *mutation success/
  error handling itself*, exclude `UsersTab` from this change and note it as a follow-up.
- [Risk] Toast/error message wording could subtly differ per tab today in ways worth preserving (e.g. one tab
  might say "Пользователь создан" vs a generic "Сохранено") → Mitigation: pass `entityLabel`/explicit message
  strings into the hook rather than hardcoding one message for all five.

## Open Questions

- Does `FreezeDaysTab.tsx` have *any* single-entity modal CRUD sub-flow (vs. being entirely
  day/range/month-shaped), and if so, is it worth partially adopting the hook there? Resolve by reading the file
  during implementation (task 1.1 in tasks.md).
- Exact current toast/message text per tab, to preserve verbatim — resolve by reading each file before writing
  the hook calls (not by guessing).
