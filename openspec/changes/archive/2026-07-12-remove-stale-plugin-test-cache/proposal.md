## Why

`plugins/` and `tests/` contain only stale `__pycache__` bytecode — `plugins/__pycache__/{__init__,base,registry}.cpython-314.pyc`,
`plugins/confluence/__pycache__/{__init__,plugin}.cpython-314.pyc`, and
`tests/__pycache__/test_{confluence_plugin,db_task_by_id,plugin_rank,plugins,plugins_api}.cpython-314-pytest-9.1.1.pyc`
— with **zero** tracked `.py` source files in either directory (`git ls-files` confirms nothing under `plugins/`
or `tests/` is tracked) and no reference to `plugins` anywhere in the project's `.py` files (confirmed by grep).
This is confirmed leftover residue from a previously-removed Confluence-integration plugin and its tests — pure
local clutter, not functionality. CLAUDE.md already flags both directories as "stale, untracked `__pycache__`
with no matching `.py` source on disk."

## What Changes

- Delete the `plugins/` and `tests/` directories from the local working tree.

## Capabilities

### New Capabilities
- `repo-working-tree-cleanliness`: no stale/orphaned build artifacts (bytecode with no corresponding tracked
  source) sit in the working tree.

### Modified Capabilities
- (none)

## Impact

- Local filesystem only: `plugins/` and `tests/` removed. No git history change (nothing tracked to remove), no
  `.py` source touched, no application behavior change (nothing imports `plugins`, and
  `python -m pytest tests/ -v` already collects 0 items today per CLAUDE.md).
- Note for whoever applies this: since both directories are gitignored, `git status`/`git diff` won't show
  anything for this change — it's a plain filesystem cleanup, not a commit.
