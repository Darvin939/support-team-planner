#!/bin/bash
set -euo pipefail

# Publishes a fresh frontend/dist build to a dedicated branch (default: "deploy")
# on the remote, so a deploy host can `git pull`/checkout that branch to get the
# built static assets. frontend/dist stays gitignored on develop/main — the tree
# is built via plumbing commands in a throwaway index, so the current branch's
# index/HEAD is never touched and dist never appears in `git status`.
#
# Usage: ./publish_dist.sh [deploy-branch] [remote]

DEPLOY_BRANCH="${1:-deploy}"
REMOTE="${2:-origin}"
DIST_DIR="frontend/dist"

# Anchor to the script's own location, not the caller's cwd — a fresh terminal
# window opened elsewhere (not "Git Bash Here" in the repo) would otherwise make
# `git rev-parse --show-toplevel` resolve against whatever repo (if any) happens
# to sit at the shell's start directory, silently picking up the wrong project's
# git config/remote/credentials instead of failing loudly.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$SCRIPT_DIR"
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "==> Building frontend..."
( cd frontend && npm run build )

if [ ! -d "$DIST_DIR" ] || [ -z "$(ls -A "$DIST_DIR")" ]; then
    echo "error: $DIST_DIR missing or empty after build" >&2
    exit 1
fi

echo "==> Checking current tip of $REMOTE/$DEPLOY_BRANCH..."
PARENT=""
if git fetch "$REMOTE" "$DEPLOY_BRANCH" 2>/dev/null; then
    PARENT="$(git rev-parse -q --verify FETCH_HEAD 2>/dev/null || true)"
fi

TMP_INDEX="$(mktemp -u)"
trap 'rm -f "$TMP_INDEX"' EXIT

echo "==> Building a git tree from $DIST_DIR (current branch index is untouched)..."
TREE="$(
    cd "$DIST_DIR"
    export GIT_DIR="$REPO_ROOT/.git"
    export GIT_INDEX_FILE="$TMP_INDEX"
    export GIT_WORK_TREE="$PWD"
    git add -A
    git write-tree
)"

MSG="Deploy frontend/dist from $(git rev-parse --short HEAD) ($(date -u '+%Y-%m-%d %H:%M:%SZ'))"

if [ -n "$PARENT" ]; then
    COMMIT="$(git commit-tree "$TREE" -p "$PARENT" -m "$MSG")"
else
    COMMIT="$(git commit-tree "$TREE" -m "$MSG")"
fi

echo "==> Pushing $COMMIT to $REMOTE/$DEPLOY_BRANCH..."
git push "$REMOTE" "$COMMIT:refs/heads/$DEPLOY_BRANCH"

echo "==> Done. Current branch's index/HEAD were never touched:"
git status --short -- "$DIST_DIR"
echo "    (no output above means $DIST_DIR is still untracked/ignored, as expected)"
