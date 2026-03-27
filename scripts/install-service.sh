#!/usr/bin/env bash
# Install a miniswarm agent runner as a launchd user service (macOS).
# The service starts automatically on login and restarts on failure.
#
# Usage:
#   ./scripts/install-service.sh claude /path/to/miniswarm
#   ./scripts/install-service.sh gemini /path/to/miniswarm
#   ./scripts/install-service.sh codex  /path/to/miniswarm
#
# Manage:
#   launchctl bootout  gui/$UID com.miniswarm.runner.claude
#   launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.miniswarm.runner.claude.plist
set -euo pipefail

AGENT="${1:?Usage: $0 <agent-name> <repo-path>}"
REPO="${2:?Usage: $0 <agent-name> <repo-path>}"
REPO="$(cd "$REPO" && pwd)"

LABEL="com.miniswarm.runner.${AGENT}"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="/tmp/swarm-logs"

mkdir -p "$LOG_DIR"

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${REPO}/scripts/runner.sh</string>
        <string>${AGENT}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${REPO}</string>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/runner-${AGENT}.out</string>

    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/runner-${AGENT}.err</string>

    <!-- Restart automatically if the process exits -->
    <key>KeepAlive</key>
    <true/>

    <!-- Start immediately on load -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Throttle restarts — wait 10s before restarting -->
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

echo "Wrote $PLIST"

# Load it
launchctl bootout "gui/$UID/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"

echo "Service $LABEL installed and started."
echo ""
echo "Manage:"
echo "  launchctl bootout  gui/$UID $LABEL   # stop"
echo "  launchctl bootstrap gui/$UID $PLIST  # start"
echo "  launchctl list | grep miniswarm      # status"
echo "  tail -f $LOG_DIR/runner-${AGENT}.err # logs"
