# repo-working-tree-cleanliness Specification

## Purpose
TBD - created by archiving change remove-stale-plugin-test-cache. Update Purpose after archive.
## Requirements
### Requirement: No orphaned generated artifacts in the working tree
The working tree SHALL NOT track orphaned `__pycache__` directories, compiled bytecode or stale plugin caches;
source and test directories that contain current tracked `.py` files SHALL remain intact.

#### Scenario: Test sources are preserved
- **WHEN** the working tree is inspected
- **THEN** the tracked `tests/` directory remains available while generated `__pycache__` contents stay ignored

#### Scenario: Orphaned caches are absent
- **WHEN** an obsolete source or plugin directory has been removed
- **THEN** no standalone bytecode/cache-only directory for that removed source remains tracked

#### Scenario: Application behavior is unaffected
- **WHEN** the app is started (`python support_planner.py`) after this change
- **THEN** it starts without importing removed plugin/cache artifacts

