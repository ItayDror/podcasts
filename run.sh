#!/usr/bin/env bash
# Auto-restart wrapper for the Telegram bot.
# Restarts the bot if it crashes, with a short backoff to avoid tight loops.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
MAX_BACKOFF=60
backoff=1

cd "$SCRIPT_DIR"

while true; do
    echo "[$(date)] Starting bot..."
    "$VENV_PYTHON" -m bot.main && exit_code=$? || exit_code=$?

    if [ "$exit_code" -eq 0 ]; then
        echo "[$(date)] Bot exited cleanly (code 0). Stopping."
        break
    fi

    echo "[$(date)] Bot crashed with exit code $exit_code. Restarting in ${backoff}s..."
    sleep "$backoff"

    # Exponential backoff capped at MAX_BACKOFF
    backoff=$((backoff * 2))
    if [ "$backoff" -gt "$MAX_BACKOFF" ]; then
        backoff=$MAX_BACKOFF
    fi
done
