#!/bin/sh
set -e

WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
POLL_INTERVAL="${UPDATE_INTERVAL_SECONDS:-60}"
BRANCH="${UPDATE_BRANCH:-main}"

echo "=========================================================="
echo " [Remote Desktop Support] Automated Git Self-Updater Active"
echo " Monitoring Branch: $BRANCH"
echo " Poll Interval: ${POLL_INTERVAL}s"
echo " Repository Path: $WORKSPACE_DIR"
echo "=========================================================="

cd "$WORKSPACE_DIR"
git config --global --add safe.directory "$WORKSPACE_DIR" || true

while true; do
  sleep "$POLL_INTERVAL"

  # Check if remote repository is reachable
  if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
    echo "[Auto-Updater] Warning: Could not connect to remote git repository. Will retry in ${POLL_INTERVAL}s..."
    continue
  fi

  LOCAL_HASH=$(git rev-parse HEAD 2>/dev/null || echo "")
  REMOTE_HASH=$(git rev-parse "origin/$BRANCH" 2>/dev/null || echo "")

  BEHIND_COUNT=$(git rev-list HEAD..origin/"$BRANCH" --count 2>/dev/null || echo "0")

  if [ -n "$REMOTE_HASH" ] && [ "$BEHIND_COUNT" -gt 0 ]; then
    echo "[Auto-Updater] 🚀 New updates detected on origin/$BRANCH ($BEHIND_COUNT commits ahead)!"
    echo "  Current commit: $LOCAL_HASH"
    echo "  Target commit:  $REMOTE_HASH"
    echo "[Auto-Updater] Pulling latest changes..."

    # Reset or pull changes
    git pull --rebase origin "$BRANCH" || {
      echo "[Auto-Updater] Rebase failed, attempting fast-forward merge..."
      git merge --ff-only "origin/$BRANCH" || true
    }

    echo "[Auto-Updater] Rebuilding and applying Docker services..."
    docker compose up -d --build

    echo "[Auto-Updater] ✅ Update complete! Services reloaded to commit $REMOTE_HASH"
  fi
done
