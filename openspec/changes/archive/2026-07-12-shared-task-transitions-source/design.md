## Context

The transition map is small (`{'new': ['done', 'cancelled']}` today) and consumed differently on each side:
Python (`support_planner.py:531`) does `allowed = VALID_TASK_TRANSITIONS.get(current_status, set())` then
`data.status not in allowed`; TypeScript (`PlanningPage.tsx`) uses it to compute which status-change menu items to
show, and CLAUDE.md notes the UI "short-circuits to an empty transitions list when `isUser`" (role-gating is
separate from this map).

## Goals / Non-Goals

**Goals:** exactly one place defines the transition rules; both runtimes read it without manual re-typing.

**Non-Goals:** building a general-purpose shared-config system for other Python/TS duplication (this app has no
other cross-language constants today) — solving this one specific, already-identified drift risk is the full
scope.

## Decisions

- **Plain JSON file inside `frontend/src/`, not a generated file or a runtime API endpoint.** Considered
  alternatives:
  - *Runtime endpoint* (e.g. `GET /api/config` returning the map): rejected — adds a network round-trip and
    loading-state handling to the Planning page for a value that's static per-deploy, not per-user/per-request.
  - *Code generation* (a script emitting the TS file from the Python source, or vice versa, run at build time):
    rejected — adds build tooling complexity disproportionate to a 3-line map.
  - *JSON file at repo root* (e.g. `task_transitions.json` next to `support_planner.py`): considered, but Vite's
    dev server restricts filesystem access outside its project root (`frontend/`) by default
    (`server.fs.allow`), which would require a `vite.config.ts` change to permit importing a file from the parent
    directory. Placing the file inside `frontend/src/` avoids that entirely — Python can read any path on disk,
    so there's no symmetric constraint on that side.
- **Python loads it once at import time**, matching how `VALID_TASK_TRANSITIONS` is already a module-level
  constant today — no per-request file I/O.
- **JSON arrays, converted to Python `set`s at load time** (`{k: set(v) for k, v in json.load(f).items()}`) —
  preserves the existing `in`-check performance/semantics in `update_task_status_api` without changing that
  function's logic, only where the dict comes from.

## Risks / Trade-offs

- [Risk] A malformed/missing JSON file would now break app startup (Python) or the Planning page's build
  (TypeScript), where today a typo in either literal would just be a silent logic bug → Mitigation: this is an
  acceptable, arguably better trade-off — failing loudly and early (import-time `FileNotFoundError`/`JSONDecodeError`,
  or a TS build error for invalid JSON) beats silently drifting between two hand-maintained copies.
- [Risk] Frontend `frontend/src/` needs to be present in the backend's working directory at runtime (not just
  `frontend/dist/`) → Mitigation: already true — the repo checkout always includes `frontend/src/`; only
  `frontend/dist/` is gitignored/build-only. No new deployment requirement.
