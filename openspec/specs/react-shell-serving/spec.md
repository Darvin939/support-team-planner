# react-shell-serving Specification

## Purpose
TBD - created by archiving change cache-react-index-html. Update Purpose after archive.
## Requirements
### Requirement: index.html is served from an in-memory cache
The application SHALL read `frontend/dist/index.html` from disk at most once per process lifetime, serving every
subsequent page-route request from an in-memory copy with identical content.

#### Scenario: First request reads from disk
- **WHEN** the first page-route request (e.g. `GET /planning`) is handled after process startup
- **THEN** `frontend/dist/index.html` is read from disk and its contents cached in memory

#### Scenario: Subsequent requests use the cache
- **WHEN** any further page-route request is handled in the same process
- **THEN** the response body is served from the in-memory cache without another disk read, and is byte-identical
  to the first response

#### Scenario: Missing dist/ still fails the same way
- **WHEN** `frontend/dist/index.html` does not exist
- **THEN** the first page-route request still fails (no behavior regression versus before this change) — the app
  does not crash at import/startup time

