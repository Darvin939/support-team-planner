## Context

`git ls-files | grep -E '^(plugins|tests)/'` returns nothing — confirming both directories hold only untracked,
gitignored `__pycache__` content. `grep -rn "plugins" --include=*.py` across the project (excluding the
directories themselves) also returns nothing, confirming no live code imports from `plugins/`.

## Goals / Non-Goals

**Goals:** remove the confusing dead directories from the local working tree.

**Non-Goals:** any git operation — there's nothing tracked to remove, so this isn't a commit-worthy change in the
usual sense; it's a `rm -rf`/`Remove-Item` on the local filesystem only.

## Decisions

- **Straight deletion, no archival.** Considered keeping the `.pyc` files as a historical curiosity: rejected —
  they're compiled bytecode with no corresponding source, so they carry no information not already visible in
  git history (if the original `.py` files were ever committed, they're recoverable from `git log` on those
  paths regardless of whether the stale `__pycache__` sticks around locally).

## Risks / Trade-offs

- [Risk] Someone might have uncommitted, not-yet-tracked `.py` work-in-progress sitting in one of these
  directories that `git status`/`git ls-files` wouldn't distinguish from the stale `__pycache__` at a glance →
  Mitigation: tasks.md requires an explicit directory listing (not just a git check) immediately before deletion
  to confirm no `.py` files are present, not just no *tracked* files.
