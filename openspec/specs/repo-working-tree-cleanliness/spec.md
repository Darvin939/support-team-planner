# repo-working-tree-cleanliness Specification

## Purpose
TBD - created by archiving change remove-stale-plugin-test-cache. Update Purpose after archive.
## Requirements
### Requirement: No orphaned bytecode directories in the working tree
The working tree SHALL NOT contain a directory whose only contents are `__pycache__`/compiled bytecode with no
corresponding tracked `.py` source file anywhere in that directory tree.

#### Scenario: plugins/ and tests/ are removed
- **WHEN** the working tree is inspected after this change
- **THEN** neither `plugins/` nor `tests/` exists on disk

#### Scenario: No tracked history is affected
- **WHEN** `git status`/`git log` is checked before and after this change
- **THEN** there is no difference — neither directory was tracked, so nothing to commit or lose

#### Scenario: Application behavior is unaffected
- **WHEN** the app is started (`python support_planner.py`) after this change
- **THEN** it starts identically to before — no code path imports from `plugins/` or `tests/`

