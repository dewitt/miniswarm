# Claude Code — Miniswarm Instructions

## Current project state (as of 2026-03-27)

The swarm is built and running. Three autonomous agent runners (claude, gemini,
codex) are connected to #swarm on localhost:6667. The runner daemon
(scripts/runner.py) bridges IRC with the agent CLI. Key files:

- `design/SWARM-ARCHITECTURE.md` — read this first for the full picture
- `swarm.toml` — configuration (rate limits, agent commands, roles)
- `scripts/runner.py` — the runner daemon (the core piece)
- `/tmp/swarm-share/session-2026-03-27.md` — session notes

Next priorities: context summarization, consensus rules, end-to-end task test.

## What is this project?

Miniswarm is a multi-agent collaboration protocol. Multiple AI coding agents
(Claude, Gemini, Codex, etc.) and humans coordinate in real time over a local
IRC server. Read `AGENTS.md` for the full protocol spec.

## Your first action in any session

1. Read `AGENTS.md` fully.
2. Check if IRC is running: `nc -z localhost 6667`
3. If running, connect using `scripts/connect.sh claude` (in background).
4. Say HELLO on #swarm with what you plan to work on.
5. Check for messages directed at you before starting work.

## During your session

- After every ~5 tool calls, check IRC for new messages: `tail -20 /tmp/irc-log-claude.txt`
- Respond to @claude mentions promptly.
- Announce significant changes (new files, refactors, rebases) on IRC before doing them.
- When you finish a task, post DONE on IRC.
- If you need input from another agent or a human, post QUESTION on IRC and continue
  other work while waiting.

## Sending messages

```bash
# Use the helper
./scripts/send.sh claude "STATUS — Working on the auth module."

# Or write directly to the pipe
echo "PRIVMSG #swarm :STATUS — Tests passing." > /tmp/irc-fifo-claude
```

## Key rules

- Defer to human directives on IRC.
- Don't edit files another agent announced they're working on.
- Use feature branches, not main.
- Keep IRC messages concise. Use /tmp/swarm-share/ for large content.
