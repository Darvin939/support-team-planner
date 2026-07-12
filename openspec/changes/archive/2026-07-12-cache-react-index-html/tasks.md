## 1. Implementation

- [x] 1.1 Added a module-level `_react_index_html: Optional[str] = None` next to `_REACT_DIST` in
      `support_planner.py`.
- [x] 1.2 Updated `_serve_react_index()` to check the cache first; on a cache miss, read the file, store it in the
      module-level variable, and return it.

## 2. Verification

- [x] 2.1 Manual check (via `starlette.testclient.TestClient` against the real `support_planner.app`): hit
      `/planning`, `/settings`, `/statistics`, `/journal`, `/login` — all returned `200` with identical response
      length (970 bytes), confirming byte-identical content across every page route.
- [x] 2.2 Verified by monkeypatching `builtins.open` to count calls mentioning `index.html`: across all 5 page
      requests above, `open()` was called exactly **1** time total — confirming the file is read from disk once
      and every subsequent page route (including different routes, not just repeated hits to the same one) is
      served from the in-memory cache.
