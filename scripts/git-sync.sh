#!/bin/bash
# git-sync: polls for changes and restarts bot on update
set -euo pipefail

INTERVAL="${SYNC_INTERVAL:-5}"
REPO_DIR="/repo"
BOT_CONTAINER="${BOT_CONTAINER:-pydantic-pydantic-bot-1}"

cd "$REPO_DIR"
git config --global --add safe.directory "$REPO_DIR"

echo "$(date) git-sync started (every ${INTERVAL}s, watching ${BOT_CONTAINER})"

while true; do
    sleep "$INTERVAL"

    git fetch origin main --quiet 2>/dev/null || continue
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/main)

    if [ "$LOCAL" != "$REMOTE" ]; then
        echo "$(date) Changes detected (${LOCAL:0:7} -> ${REMOTE:0:7}), pulling..."
        git pull origin main --quiet
        echo "$(date) Restarting bot..."
        docker restart "$BOT_CONTAINER" 2>/dev/null || true
        echo "$(date) Done"
    fi
done
