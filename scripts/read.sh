#!/usr/bin/env bash
# Read recent messages from the swarm IRC channel.
# Usage: ./read.sh <nick> [num_lines]
set -euo pipefail

NICK="${1:?Usage: $0 <nick> [num_lines]}"
LINES="${2:-20}"
LOG="/tmp/irc-log-${NICK}.txt"

if [ ! -f "$LOG" ]; then
    echo "No log found for $NICK (expected at $LOG)"
    echo "Run connect.sh first."
    exit 1
fi

# Filter to show only channel messages (PRIVMSG), cleaned up
tail -"$LINES" "$LOG" | grep "PRIVMSG" | sed 's/^:\([^!]*\).*PRIVMSG [^ ]* :/\1: /'
