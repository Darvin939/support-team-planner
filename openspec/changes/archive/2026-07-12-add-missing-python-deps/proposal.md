## Why

`requirements.txt` lists `fastapi`, `uvicorn[standard]`, `pydantic`, `starlette`, `requests`, `python-dotenv`,
`urllib3` — but not `itsdangerous` or `python-multipart`, both of which the app needs at runtime for the login
feature: `itsdangerous` signs the session cookie inside `starlette.middleware.sessions.SessionMiddleware`, and
`python-multipart` is required by Starlette's form parser for `Form(...)` params (used by `POST /login`'s
`login`/`password` fields). Confirmed by reading the installed `starlette/formparsers.py`:
`assert multipart is not None, "The `python-multipart` library must be installed to use form parsing."` — this
`assert` lives inside `FormParser`, the class used for `application/x-www-form-urlencoded` bodies (not just
multipart file uploads), so it fires on the very first `/login` submission. Both packages are already present in
this project's `.venv` (confirmed via `pip show`: `itsdangerous 2.2.0`, `python-multipart 0.0.32`), which is why
local development works despite the gap — but a fresh `pip install -r requirements.txt` on a clean machine would
install neither. This gap is already documented as a known issue in both CLAUDE.md and README.md, but the fix
(updating `requirements.txt` itself) was never applied.

**Correction found during implementation, worse than originally described**: verified by actually uninstalling
both packages from the project's `.venv` and starting the app — the failure isn't a graceful `AssertionError` on
the first `/login` submission as this proposal originally claimed. It's a full startup crash at *import* time:
`starlette.middleware.sessions` itself does a top-level `import itsdangerous`, so `support_planner.py` fails
before `uvicorn.run()` is ever reached (`ModuleNotFoundError: No module named 'itsdangerous'`) — the app never
starts at all, not even for pages that don't touch login. `python-multipart`'s absence is the milder of the two
(that one genuinely only surfaces as an `AssertionError` on the first form submission, since Starlette's
`FormParser` only asserts at call time, not import time) — but `itsdangerous` alone is enough to make the app
entirely non-functional on a fresh install.

## What Changes

- Add `itsdangerous` and `python-multipart` to `requirements.txt`.
- Once added, the `pip install itsdangerous python-multipart` workaround note in README.md's "Быстрый старт"
  section becomes unnecessary and can be removed (the packages are now installed by the normal
  `pip install -r requirements.txt` step).

## Capabilities

### New Capabilities
- `fresh-install-login`: a clean `pip install -r requirements.txt` followed by `POST /login` succeeds without
  a manual extra-package install step.

### Modified Capabilities
- (none)

## Impact

- `requirements.txt`: two new lines.
- `README.md`: the "Важно" callout about manually installing these two packages can be removed once they're in
  `requirements.txt` (avoids the docs and the dependency list disagreeing with each other).
- No version pins specified beyond what's already the project's convention (`requirements.txt` currently pins
  nothing, e.g. `fastapi` with no version) — matching the existing unpinned style rather than introducing pins
  for just these two.
