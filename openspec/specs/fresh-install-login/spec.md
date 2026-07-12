# fresh-install-login Specification

## Purpose
TBD - created by archiving change add-missing-python-deps. Update Purpose after archive.
## Requirements
### Requirement: A fresh install supports login without a manual extra step
Running `pip install -r requirements.txt` in a clean environment SHALL install every package required for
`POST /login` to succeed, with no separately-documented manual `pip install` step required.

#### Scenario: Clean install, then login
- **WHEN** a clean virtual environment runs `pip install -r requirements.txt` followed by starting
  `support_planner.py` and submitting `POST /login` with valid credentials
- **THEN** the login succeeds (`{"success": true}`) — no `AssertionError` about `python-multipart`, and the
  session cookie is signed correctly (no `itsdangerous`-related failure)

#### Scenario: Documentation matches reality
- **WHEN** README.md's setup instructions are followed exactly as written
- **THEN** they do not mention installing any package that isn't already in `requirements.txt`

