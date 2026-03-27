#!/usr/bin/env bash
# Send a message to the swarm IRC channel.
# Usage: ./send.sh <nick> <message>
#
# Convenience wrapper — just writes a PRIVMSG to the agent's FIFO.
set -euo pipefail

NICK="${1:?Usage: $0 <nick> <message>}"
shift
MESSAGE="$*"
CHANNEL="${SWARM_CHANNEL:-#swarm}"
FIFO="/tmp/irc-fifo-${NICK}"

if [ ! -p "$FIFO" ]; then
    echo "ERROR: No connection for $NICK (FIFO not found at $FIFO)"
    echo "Run connect.sh first."
    exit 1
fi

echo -e "PRIVMSG $CHANNEL :${MESSAGE}\r" > "$FIFO"
