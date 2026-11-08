#!/usr/bin/env bash
# Download this project from GitHub and prepare it for local IDE development.
# Usage: bash install-local.sh [target-directory] [branch]
# The default branch contains PR #1; change it to main after that PR is merged.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/tamatimo32/Business-2-Interface.git}"
TARGET_DIR="${1:-Business-2-Interface}"
BRANCH="${2:-arena/70600f6a-business-2-interface}"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"

if ! command -v git >/dev/null 2>&1; then
  echo "Git is required. Install Git, then run this script again." >&2
  exit 1
fi
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.11+ is required. Install it or set PYTHON_BIN to its executable." >&2
  exit 1
fi

if [ -e "$TARGET_DIR" ]; then
  if [ ! -d "$TARGET_DIR/.git" ]; then
    echo "Target exists but is not a Git checkout: $TARGET_DIR" >&2
    exit 1
  fi
  if [ -n "$(git -C "$TARGET_DIR" status --porcelain)" ]; then
    echo "Target has local changes. Commit or stash them before updating." >&2
    exit 1
  fi
  git -C "$TARGET_DIR" fetch origin "$BRANCH"
  git -C "$TARGET_DIR" checkout "$BRANCH"
  git -C "$TARGET_DIR" merge --ff-only FETCH_HEAD
else
  git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$TARGET_DIR"
fi

cd "$TARGET_DIR"
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
.venv/bin/python -m pip install -e backend --no-deps
if [ ! -f .env ]; then
  cp .env.example .env
fi
(cd backend && ../.venv/bin/alembic upgrade head)

if command -v code >/dev/null 2>&1; then
  code .
else
  echo "Open this folder in your IDE: $(pwd)"
  echo "Select the .venv Python interpreter."
fi

printf '\nReady. Start the backend with:\n'
printf '  cd %s/backend\n' "$(pwd)"
printf '  ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log --reload\n'
