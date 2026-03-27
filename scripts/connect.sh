#!/usr/bin/env bash
# Connect an agent to the miniswarm IRC server.
# Usage: ./connect.sh <nick> [channel] [host] [port]
#
# Creates a named pipe for sending and a log file for receiving.
# The agent sends messages by writing to the pipe and reads by tailing the log.
set -euo pipefail

NICK="${1:?Usage: $0 <nick> [channel] [host] [port]}"
CHANNEL="${2:-#swarm}"
HOST="${3:-127.0.0.1}"
PORT="${4:-6667}"

FIFO="/tmp/irc-fifo-${NICK}"
LOG="/tmp/irc-log-${NICK}.txt"

# Clean up on exit
cleanup() {
    rm -f "$FIFO"
    [ -n "${IRC_PID:-}" ] && kill "$IRC_PID" 2>/dev/null || true
    echo "Disconnected $NICK from $HOST:$PORT"
}
trap cleanup EXIT

# Create the send pipe
rm -f "$FIFO"
mkfifo "$FIFO"

# Connect: pipe input from FIFO, log output to file
tail -f "$FIFO" | nc "$HOST" "$PORT" > "$LOG" 2>&1 &
IRC_PID=$!

# Give the connection a moment
sleep 0.5

# Register and join
echo -e "NICK $NICK\r" > "$FIFO"
echo -e "USER $NICK 0 * :$NICK agent\r" > "$FIFO"
sleep 0.5
echo -e "JOIN $CHANNEL\r" > "$FIFO"
sleep 0.3
echo -e "PRIVMSG $CHANNEL :HELLO — $NICK is online and ready.\r" > "$FIFO"

echo "Connected as $NICK to $CHANNEL on $HOST:$PORT"
echo "Send:    echo 'PRIVMSG $CHANNEL :your message' > $FIFO"
echo "Receive: tail -f $LOG"
echo ""
echo "Keeping connection alive (Ctrl-C to disconnect)..."

# Keep alive: respond to PINGs
tail -f "$LOG" | while IFS= read -r line; do
    if [[ "$line" == PING* ]]; then
        PONG="${line/PING/PONG}"
        echo -e "${PONG}\r" > "$FIFO"
    fi
done
