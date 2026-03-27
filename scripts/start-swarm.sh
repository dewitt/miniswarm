#!/usr/bin/env bash
# Starts the agent runners configured in swarm.toml.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="/tmp/swarm-logs"

mkdir -p "$LOG_DIR"

echo "Starting miniswarm agent runners..."

# Extract agent names from swarm.toml (e.g. [agent.claude] -> claude)
AGENTS=$(grep -oE '^\[agent\.[a-zA-Z0-9_-]+\]' "$REPO_DIR/swarm.toml" | sed 's/^\[agent\.//' | sed 's/\]$//')

for AGENT in $AGENTS; do
    echo "Starting runner for $AGENT in background..."
    nohup "$SCRIPT_DIR/runner.sh" "$AGENT" > "$LOG_DIR/runner-${AGENT}.out" 2>&1 &
done

echo "Swarm started. Logs are in $LOG_DIR"
