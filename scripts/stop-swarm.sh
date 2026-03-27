#!/usr/bin/env bash
# Immediately shuts down all swarm agents and cleans up state.

echo "Stopping all miniswarm agent runners..."
pkill -f "runner.sh" || true
pkill -f "runner.py" || true

echo "Cleaning up state..."
rm -rf /tmp/swarm-locks/* /tmp/irc-log-*.txt /tmp/irc-fifo-* /tmp/swarm-share/* 2>/dev/null

echo "Swarm stopped."
