## MODIFIED Requirements

### Requirement: GET requests use the shared apiGet error contract

Every frontend `useQuery`'s `queryFn` SHALL fetch via `apiGet`. Both `apiGet` and `apiMutate` SHALL use the same
error-response parser, which accepts a non-empty string `error` and otherwise throws an `Error` with
`` `<METHOD> <url> -> <status>` ``.

#### Scenario: Server returns a specific error

- **WHEN** a GET or mutation request receives a non-2xx response with a JSON body
  `{"error": "Team not found"}`
- **THEN** the helper throws `Error("Team not found")`

#### Scenario: Server returns no usable JSON error

- **WHEN** a request receives a non-2xx response with an empty or non-JSON body, or without a non-empty string
  `error`
- **THEN** the helper throws `Error("<METHOD> <url> -> <status>")`

#### Scenario: Successful GET

- **WHEN** a GET request receives a 2xx response
- **THEN** `apiGet` resolves with the parsed JSON body, typed per the caller's generic parameter

#### Scenario: Consistency with apiMutate

- **WHEN** comparing `apiGet` and `apiMutate` for equivalent non-2xx responses
- **THEN** both select the same server message or fallback according to the shared parser rules

### Requirement: Frontend and backend API contracts change together

Changes to a public API response contract SHALL update its frontend consumer and backend producer in the same
OpenSpec change. The application SHALL NOT add compatibility handling for an older counterpart unless separate
deployment or an external producer is an explicit requirement.

#### Scenario: Public API response contract changes

- **WHEN** an OpenSpec change modifies a public backend response payload
- **THEN** the same change specifies and implements the corresponding frontend consumer update
- **AND** no legacy payload fallback is added without an explicit compatibility requirement
