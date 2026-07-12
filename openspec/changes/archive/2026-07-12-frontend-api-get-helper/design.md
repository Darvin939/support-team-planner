## Context

`apiMutate` (`frontend/src/lib/apiMutate.ts:9-19`) already establishes the pattern: `fetch` with
`credentials: 'same-origin'`, parse JSON body defensively (`.catch(() => ({}))`), and on non-2xx throw
`new Error(data.error || fallback)`. GET requests need the identical shape minus the `method`/`body` params.

## Goals / Non-Goals

**Goals:** one `apiGet` helper with byte-identical error-handling semantics to `apiMutate`; every existing
query-function call site migrated to it.

**Non-Goals:** introducing a request-caching or retry layer beyond what TanStack Query's `useQuery` already
provides — `apiGet` is purely the `fetch` + error-normalization primitive underneath it, same role `apiMutate`
plays for mutations.

## Decisions

- **Generic `apiGet<T>(url): Promise<T>`** rather than returning `unknown`/`any` — callers currently type their
  `queryFn` return value via the `useQuery<T>` generic already; `apiGet<T>` lets that same annotation flow through
  instead of an extra cast at each call site.
- **Same file, `apiMutate.ts`**, not a new file — the two helpers share the same JSON-parsing/error-throwing
  logic (arguably `apiMutate` could call `apiGet`-style shared logic internally, but keeping both as separate
  small exported functions in one file is simpler than factoring out a third internal-only helper for two call
  sites).
- **Query-key/queryFn wiring is untouched** — this change only replaces the `fetch(...)` body of each `queryFn`
  with `() => apiGet<T>(url)`; TanStack Query configuration (staleTime, retry, etc.) per hook is out of scope.

## Risks / Trade-offs

- [Risk] The message-format change (server error preferred over generic status string) is user-visible in error
  toasts for the ~2-3 call sites that previously always showed the generic message → Mitigation: this is a
  strict improvement (more specific error text) and matches `apiMutate`'s existing, already-shipped behavior —
  not a new risk pattern, just extending it to reads.
