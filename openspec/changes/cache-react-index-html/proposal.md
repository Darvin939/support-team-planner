## Why

`_serve_react_index()` (`support_planner.py:27-30`) opens and reads `frontend/dist/index.html` from disk on
every single request to any of the app's page routes (`/login`, `/planning`, `/planning/{team_id}`, `/settings`,
`/statistics`, `/journal`, `/journal/{team_id}`) — seven routes, each hitting the filesystem for a file that never
changes while the process is running (it's a build artifact, regenerated only by `npm run build`, which requires
restarting the Python process to pick up anyway since nothing watches `frontend/dist/` for changes). This is a
small, easy, risk-free win.

## What Changes

- `_serve_react_index()` reads `frontend/dist/index.html` once (at first call, or eagerly at startup alongside
  the existing `os.path.isdir(_REACT_DIST)` check) and returns the cached string on every subsequent call.

## Capabilities

### New Capabilities
- `react-shell-serving`: serving the built React SPA shell (`index.html`) for every page route, from an
  in-memory cache rather than re-reading disk per request.

### Modified Capabilities
- (none)

## Impact

- `support_planner.py`: `_serve_react_index()` gains a module-level cache variable.
- No behavior change: response bytes for every page route are identical to today, just served from memory
  instead of re-read from disk each time.
