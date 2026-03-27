#!/usr/bin/env bash
# Launch an agent runner with automatic restart on failure.
# Usage: ./scripts/runner.sh <agent-name>
#   e.g. ./scripts/runner.sh claude
#        ./scripts/runner.sh gemini
#        ./scripts/runner.sh codex
#
# To run in background (survives terminal close):
#   nohup ./scripts/runner.sh claude > /tmp/swarm-logs/runner-claude.out 2>&1 &
set -euo pipefail

AGENT="${1:?Usage: $0 <agent-name> (e.g. claude, gemini, codex)}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

mkdir -p /tmp/swarm-share /tmp/swarm-logs /tmp/swarm-locks

RESTART_DELAY=5
MAX_RESTART_DELAY=60

echo "[runner.sh] Starting runner for $AGENT (pid $$)" >&2

# Restart loop — keeps the runner alive if it crashes or disconnects
while true; do
    python3 "$SCRIPT_DIR/runner.py" "$AGENT" --config "$REPO_DIR/swarm.toml"
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "[runner.sh] Runner exited cleanly. Not restarting." >&2
        break
    fi

    echo "[runner.sh] Runner exited with code $EXIT_CODE. Restarting in ${RESTART_DELAY}s..." >&2
    sleep "$RESTART_DELAY"

    # Exponential backoff up to MAX_RESTART_DELAY
    RESTART_DELAY=$(( RESTART_DELAY * 2 ))
    if [ "$RESTART_DELAY" -gt "$MAX_RESTART_DELAY" ]; then
        RESTART_DELAY=$MAX_RESTART_DELAY
    fi
done
