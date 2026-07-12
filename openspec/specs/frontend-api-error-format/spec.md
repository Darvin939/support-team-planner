# frontend-api-error-format Specification

## Purpose
TBD - created by archiving change frontend-api-get-helper. Update Purpose after archive.
## Requirements
### Requirement: GET requests use the shared apiGet error contract
Every frontend `useQuery`'s `queryFn` SHALL fetch via `apiGet`, which throws an `Error` whose message is the
server's `{"error": "..."}` body when present, falling back to `` `GET <url> -> <status>` `` otherwise — matching
`apiMutate`'s existing error contract for writes.

#### Scenario: Server returns a specific error
- **WHEN** a GET request receives a non-2xx response with a JSON body `{"error": "Team not found"}`
- **THEN** `apiGet` throws `Error("Team not found")`

#### Scenario: Server returns no JSON body or no error field
- **WHEN** a GET request receives a non-2xx response with an empty or non-JSON body
- **THEN** `apiGet` throws `Error("GET <url> -> <status>")`

#### Scenario: Successful GET
- **WHEN** a GET request receives a 2xx response
- **THEN** `apiGet` resolves with the parsed JSON body, typed per the caller's generic parameter

#### Scenario: Consistency with apiMutate
- **WHEN** comparing `apiGet`'s and `apiMutate`'s behavior for an equivalent non-2xx response
- **THEN** both produce the same error message given the same response body/status

