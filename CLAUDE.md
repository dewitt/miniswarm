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

## IMPORTANT: Runner Environment

**DO NOT** manually connect to IRC or use `scripts/connect.sh`.
**DO NOT** run `tail` or `read.sh` to check for messages.

You are being invoked by a stateless runner daemon (`scripts/runner.py`). The runner manages the persistent IRC connection for you.

When you are invoked:
1. The runner provides the latest IRC context via your system prompt.
2. You perform whatever tool calls are necessary to complete your task (editing files, reading code, etc.).
3. You output a concise, actionable text response using the prefixes from `AGENTS.md`.
4. You finish and exit. The runner will capture your text response and post it back to the IRC channel on your behalf.

## Key rules

- Defer to human directives on IRC.
- Don't edit files another agent announced they're working on.
- Use feature branches, not main.
- Keep your final text response concise. Use `/tmp/swarm-share/` for large content if needed.
- Act autonomously to solve the problem without explicitly asking permission for every command.
