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

    # Fast-forward only; never rebuild code that did not actually update
    if ! git merge --ff-only "origin/$BRANCH"; then
      echo "[Auto-Updater] ❌ Could not fast-forward to origin/$BRANCH (local changes or diverged history)."
      echo "[Auto-Updater]    Run 'git status' in the repository and resolve it. Services were not rebuilt."
      continue
    fi

    # Rebuild every service except this updater: recreating its own container kills this
    # script mid-run and leaves the other containers created but never started.
    SERVICES=$(docker compose config --services | grep -vx "auto_updater")
    echo "[Auto-Updater] Rebuilding and applying Docker services: $(echo $SERVICES)"
    if ! docker compose up -d --build $SERVICES; then
      echo "[Auto-Updater] ❌ Rebuild failed. Fix it and run 'docker compose up -d --build' in the repository."
      continue
    fi

    echo "[Auto-Updater] ✅ Update complete! Services reloaded to commit $REMOTE_HASH"
  fi
done
