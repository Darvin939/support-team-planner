## Why

`frontend/src/pages/settings/TeamsTab.tsx`, `SegmentsTab.tsx`, `UsersTab.tsx`, `BlocksTab.tsx` (its templates
list), and `FreezeDaysTab.tsx` each hand-roll the same ~25-30 line pattern: local `modalX: X | 'new' | null`
state, an antd `useForm`, a `saveMutation` that branches POST (create) vs PUT (update) based on
`modalX === 'new'`, a `deleteMutation`, and identical `onSuccess` (invalidate query + `message.success` + close
modal) / `onError` (`message.error(e.message)`) handlers on both mutations, plus an `openModal` that seeds
`form.setFieldsValue`. Five near-identical copies of the same orchestration logic make each settings tab larger
than it needs to be and mean a shared behavior change (e.g. tweaking the success toast wording) requires five
edits.

## What Changes

- Add a shared hook, `useCrudMutations<T>(queryKey, { create, update, delete: del })`, in
  `frontend/src/hooks/` (or `frontend/src/lib/`), encapsulating the save/delete `useMutation`s + their
  `onSuccess`/`onError` handlers + query invalidation.
- Each of the five settings-tab components adopts the hook, keeping their own JSX/form-field layout (which
  genuinely differs per entity) but delegating the mutation orchestration to it.

## Capabilities

### New Capabilities
- `settings-entity-crud`: shared save/delete mutation contract (success toast + query invalidation + modal
  close; error toast on failure) for Settings-page entity management.

### Modified Capabilities
- (none)

## Impact

- New file: a `useCrudMutations` hook (exact location TBD in design.md).
- `TeamsTab.tsx`, `SegmentsTab.tsx`, `UsersTab.tsx`, `BlocksTab.tsx`, `FreezeDaysTab.tsx`: each adopts the shared
  hook, removing their local `saveMutation`/`deleteMutation` boilerplate.
- No API changes, no visible UI/UX change — same toasts, same modal behavior, same error messages.
