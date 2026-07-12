## 1. Confirm nothing of value is present

- [x] 1.1 Listed the full contents of `plugins/` and `tests/` — confirmed every file was a `.pyc` under a
      `__pycache__` directory (`plugins/__pycache__/{__init__,base,registry}.cpython-314.pyc`,
      `plugins/confluence/__pycache__/{__init__,plugin}.cpython-314.pyc`,
      `tests/__pycache__/test_{confluence_plugin,db_task_by_id,plugin_rank,plugins,plugins_api}.cpython-314-pytest-9.1.1.pyc`)
      — no stray `.py`/other files (`find ./plugins ./tests -type f ! -name "*.pyc"` returned empty).
- [x] 1.2 Confirmed `git ls-files | grep -E '^(plugins|tests)/'` and `git status --short plugins tests` both show
      nothing tracked/changed under either path.

## 2. Delete

- [x] 2.1 Removed `plugins/` and `tests/` from the local working tree.

## 3. Verification

- [x] 3.1 Confirmed `import support_planner` succeeds with no error after removal, and started the real app
      (`python support_planner.py`) — clean startup log, no error, then stopped the process.
- [x] 3.2 Confirmed `git status` shows no change for `plugins`/`tests` — expected, since both were gitignored
      and untracked to begin with.
