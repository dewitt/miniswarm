#!/usr/bin/env bash
# Start a local IRC server for miniswarm.
# Tries ngircd first, falls back to miniircd (Python), falls back to instructions.
set -euo pipefail

PORT="${SWARM_PORT:-6667}"
HOST="127.0.0.1"

# Check if something is already listening
if nc -z "$HOST" "$PORT" 2>/dev/null; then
    echo "IRC server already running on $HOST:$PORT"
    exit 0
fi

# Option 1: Nix flake (preferred — sandboxed, reproducible)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
if command -v nix &>/dev/null && [ -f "$REPO_DIR/flake.nix" ]; then
    echo "Starting swarm server via Nix on $HOST:$PORT ..."
    exec nix run "$REPO_DIR"
fi

# Option 2: ngircd (manual install)
if command -v ngircd &>/dev/null; then
    CONF=$(mktemp /tmp/ngircd-swarm-XXXXXX.conf)
    cat > "$CONF" << EOF
[Global]
    Name = swarm.local
    Info = Miniswarm IRC Server
    Listen = $HOST
    Ports = $PORT
    MaxConnections = 50
    MaxNickLength = 30

[Channel]
    Name = #swarm
    Topic = Miniswarm coordination channel
    Modes = tn
EOF
    echo "Starting ngircd on $HOST:$PORT ..."
    exec ngircd -f "$CONF" -n
fi

# Option 3: miniircd (Python)
if command -v miniircd &>/dev/null; then
    echo "Starting miniircd on $HOST:$PORT ..."
    exec miniircd --listen "$HOST" --ports "$PORT"
fi

# Option 4: Try Python package directly
if command -v python3 &>/dev/null; then
    if python3 -c "import miniircd" 2>/dev/null || pip install miniircd 2>/dev/null; then
        echo "Starting miniircd (via Python) on $HOST:$PORT ..."
        exec miniircd --listen "$HOST" --ports "$PORT"
    fi
fi

echo "ERROR: No IRC server found. Install one:"
echo "  nix run .                 # Nix (recommended, from project root)"
echo "  nix develop               # Nix dev shell with all tools"
echo "  brew install ngircd       # macOS"
echo "  apt install ngircd        # Linux"
echo "  pip install miniircd      # Python (any platform)"
exit 1
