## 1. Investigation

- [x] 1.1 Read `TeamsTab.tsx`, `SegmentsTab.tsx`, `UsersTab.tsx`, `BlocksTab.tsx`, and `FreezeDaysTab.tsx` in full.
- [x] 1.2 Decision:
      - **Migrate**: `TeamsTab`, `SegmentsTab`, `UsersTab`, and `BlocksTab`'s `TemplatesList` sub-component —
        all four share the exact `T | 'new' | null` modal state + `useMutation` save (POST/PUT by id) +
        `useMutation` delete + matching `onSuccess`/`onError` shape. `UsersTab`'s `isEditingProtected` branching
        turned out to be entirely in the form JSX (which fields render), not in the mutation logic — confirms it
        fits cleanly, as anticipated.
      - **Exclude `BlocksTab`'s `BlocksList` sub-component**: a simpler inline create+delete pattern with no
        modal and no update — was never in the proposal's stated scope ("BlocksTab.tsx (its templates list)").
      - **Exclude `FreezeDaysTab`**: confirmed non-fit — always `PUT`s a whole month's day-set (no
        create/update split), keyed by `(year, month)` not a numeric `id`, and its modal state
        (`modalMonth: number | null` + a `Set<number>`) doesn't match the `T | 'new' | null` shape at all.
      - **Extra finding not in the original plan**: delete-success toasts differ per tab — Teams/Segments/Users
        show one (`message.success('...')`), `BlocksTab`'s `TemplatesList` shows none. The hook needs an
        *optional* delete-success message, not a hardcoded one.

## 2. Hook implementation

- [x] 2.1 Created `frontend/src/hooks/useCrudMutations.ts` implementing
      `useCrudMutations<TEntity extends {id: number}, TValues>({ queryKey, baseUrl, modalEntity, onSaveSuccess,
      deleteSuccessMessage? })` returning `{ saveMutation, deleteMutation }`. Per-tab value transformation
      (`UsersTab`'s `password: values.password || null`) stays at the call site (`saveMutation.mutate(...)`),
      not inside the hook, since it's genuinely entity-specific.

## 3. Migration

- [x] 3.1 Migrated `TeamsTab.tsx`.
- [x] 3.2 Migrated `SegmentsTab.tsx`.
- [x] 3.3 Migrated `BlocksTab.tsx`'s `TemplatesList` (not `BlocksList` — out of scope, see 1.2).
- [x] 3.4 Migrated `UsersTab.tsx`.
- [x] 3.5 `FreezeDaysTab.tsx` left untouched — documented in 1.2 why it's excluded.

## 4. Verification

- [x] 4.1 `npx tsc -b --noEmit` and `npm run build` (the project's real build command) both succeed with zero
      errors after all four migrations — confirms type-correctness of the generic `useCrudMutations<TEntity,
      TValues>` usage across four different entity/value-type pairs. Each migrated tab's `saveMutation`/
      `deleteMutation` was compared line-by-line against the pre-migration original (still visible in git diff)
      to confirm identical `mutationFn`/`onSuccess`/`onError` behavior — same URL construction
      (POST-when-new/PUT-when-editing), same query-key invalidation, same modal-close-on-save-success, same
      per-tab delete-toast text (or absence of one for `BlocksTab`'s `TemplatesList`).
- [x] 4.2 **Real browser verification via Playwright** (`chromium`, headless, driving the actual built app on
      `localhost:5093`) — 18/18 assertions passed across all four migrated tabs:
      - **Teams**: create → success toast + appears in list without reload; edit → success toast + list updates;
        delete → success toast ("Команда удалена") + removed from list; duplicate name on create → `400` error
        toast with the server's exact message ("Команда с таким названием уже существует") + modal stays open.
      - **Segments**: create/edit/delete → success toasts ("Сохранено" / "Сегмент удалён") + list updates each
        time.
      - **Users**: create/edit (including the `password: v.password || null` transform)/delete → success toasts
        ("Сохранено" / "Пользователь удалён") + list updates each time.
      - **Blocks (`TemplatesList`)**: create/edit → success toasts ("Сохранено") + list updates; delete → item
        removed from list **and confirmed no new success toast appears** (compared toast text sets before/after,
        not raw counts, since older toasts from the same run can still be in the DOM or mid-fade-out) — matches
        this tab's deliberate no-toast-on-delete behavior found in 1.2.
      - All test data (teams/segments/users/templates created during the run, including two left over from
        earlier failed script iterations before locator selectors were fixed) was cleaned up afterward via direct
        API calls; confirmed zero residue in the database.
      - Playwright was available in this environment via `npx playwright` (Chromium already installed at
        `C:\Users\Darvin\AppData\Local\ms-playwright\chromium-1228`) — an earlier verification pass in this same
        change incorrectly stated no browser tool was available; corrected after the user pointed this out.
