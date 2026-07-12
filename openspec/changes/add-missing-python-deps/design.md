## Context

`requirements.txt` is unpinned (no `==version` on any existing line), and both missing packages are transitive
runtime dependencies of `starlette`'s `SessionMiddleware` (`itsdangerous`) and `Form(...)` parsing
(`python-multipart`) — not imported directly anywhere in this project's own `.py` files, which is exactly why a
plain grep for their names across the codebase finds nothing and made them easy to overlook when
`requirements.txt` was last edited.

## Goals / Non-Goals

**Goals:** `pip install -r requirements.txt` alone is sufficient for `/login` to work on a clean machine.

**Non-Goals:** pinning versions for these or any other dependency — out of scope, matches existing file
convention.

## Decisions

- **Add both as plain unversioned lines**, matching every other entry in the file.
- **Also clean up README's "Важно" callout** in the same change, since leaving it in place after fixing
  `requirements.txt` would make the docs actively wrong (claiming a manual step is still needed when it no longer
  is).

## Risks / Trade-offs

- [Risk] None — this only adds packages already confirmed present and working in the project's own `.venv`.
