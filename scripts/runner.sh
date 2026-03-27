#!/usr/bin/env bash
# Launch an agent runner.
# Usage: ./scripts/runner.sh <agent-name>
#   e.g. ./scripts/runner.sh claude
#        ./scripts/runner.sh gemini
#        ./scripts/runner.sh codex
set -euo pipefail

AGENT="${1:?Usage: $0 <agent-name> (e.g. claude, gemini, codex)}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

mkdir -p /tmp/swarm-share /tmp/swarm-logs /tmp/swarm-locks

exec python3 "$SCRIPT_DIR/runner.py" "$AGENT" --config "$REPO_DIR/swarm.toml"
