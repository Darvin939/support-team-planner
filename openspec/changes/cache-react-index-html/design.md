## Context

`_REACT_DIST`/`frontend/dist/index.html` is a build artifact produced once by `npm run build` and never touched
again while `python support_planner.py` is running — there is no dev-mode hot-reload path through this function
(Vite's own dev server handles that separately, proxying to the backend only for `/api`, `/login`, `/logout`).

## Goals / Non-Goals

**Goals:** avoid a redundant disk read on every page-route request.

**Non-Goals:** hot-reloading `index.html` if `frontend/dist/` changes while the server is running — that already
requires a process restart today (nothing watches the dist folder), so caching doesn't remove any capability that
existed before.

## Decisions

- **Cache at first access (lazy), guarded by a module-level `Optional[str]` variable**, rather than reading
  eagerly at import time — keeps the existing `os.path.isdir(_REACT_DIST)` startup check's semantics unchanged
  (a missing `dist/` still surfaces as a `FileNotFoundError` the first time a page is actually requested, exactly
  as it does today, rather than crashing at import time before `uvicorn.run` even starts).

## Risks / Trade-offs

- [Risk] None meaningful — this is a read-only, single-process, in-memory cache of an immutable-for-the-process-
  lifetime file.
