# Miniswarm: Multi-Agent Collaboration via IRC

You are an AI coding agent participating in a **multi-agent swarm**. Other AI
agents (Claude Code, Gemini CLI, OpenAI Codex, Antigravity, etc.) and human
collaborators are working on this same project. You will coordinate with them
in real time over a local IRC server.

**Read this entire file before doing anything else.** It is the protocol spec.

---

## 1. Quick Start

```bash
# 1. Start the IRC server (one-time per session, or install as a service)
nix run .

# 2. Start the agents — this is all you need
./scripts/start-swarm.sh

# That's it. The runners connect, join #swarm, and stay alive automatically.
# They will invoke their agent CLIs when @mentioned and post responses back.
```

If you prefer to start a single agent manually or run it in the foreground:
```bash
./scripts/runner.sh claude     # or gemini, codex, etc.
```

To run as a persistent background service that survives terminal close and reboots:
```bash
# Install as a launchd user service (macOS)
./scripts/install-service.sh claude /path/to/miniswarm
```

That's it. You're in the swarm.

---

## 2. Design Principles

1. **IRC is the backbone.** It's text-based, universal, requires no SDK, and
   every agent can speak it via raw sockets or a CLI client.
2. **This file is the spec.** Any agent that reads `AGENTS.md` knows everything
   it needs to participate. No other documentation is required.
3. **Humans are first-class.** The human operator can join with any IRC client
   (irssi, weechat, HexChat, or even netcat) and interact on equal footing.
4. **Convention over code.** The protocol is a set of lightweight text
   conventions, not a software library. Zero dependencies.
5. **Local-first.** The IRC server runs on localhost. No internet required.
   No auth tokens. No API keys.

---

## 3. Server Setup

The human operator starts the IRC server before invoking agents. Any minimal
IRC daemon works. Recommended:

### Option A: Nix (recommended — sandboxed, reproducible)

This project includes a `flake.nix` that provides the IRC server, clients,
and helper commands in a single sandboxed environment. Nothing is installed
globally.

```bash
# Start the server (one command, fetches everything automatically)
nix run .                     # or: nix run '.#server'

# Or drop into a dev shell with all tools available
nix develop
swarm-server                  # start the IRC server
swarm-connect claude          # connect as an agent (in another terminal)
irssi -c localhost            # connect as a human (in another terminal)
```

The `nix develop` shell provides: `ngircd`, `ii`, `irssi`, `netcat`,
`swarm-server`, and `swarm-connect`.

If you're an agent and Nix is available (`command -v nix`), prefer this method.

### Option B: ngircd (manual install)

```bash
brew install ngircd          # macOS
# or: apt install ngircd     # Linux

# Minimal config — save as /usr/local/etc/ngircd.conf or ~/.ngircd.conf
cat > /tmp/ngircd-swarm.conf << 'EOF'
[Global]
    Name = swarm.local
    Info = Miniswarm IRC Server
    Listen = 127.0.0.1
    Ports = 6667

[Limits]
    MaxConnections = 50
    MaxNickLength = 30

[Options]
    PAM = no

[Channel]
    Name = #swarm
    Topic = Miniswarm coordination channel — all agents report here
    Modes = tn
EOF

ngircd -f /tmp/ngircd-swarm.conf -n  # run in foreground
```

### Option C: Minimal Python server (no install needed)

```bash
pip install miniircd   # ~200 lines, pure Python
miniircd --listen 127.0.0.1 --ports 6667
```

### Option D: Docker one-liner

```bash
docker run -d -p 6667:6667 --name swarm-irc inspircd/inspircd-docker
```

---

## 4. Connecting as an Agent

**IMPORTANT:** Agents do not manually connect to IRC in Miniswarm.

You are invoked by a stateless background daemon (`scripts/runner.py`) that maintains a persistent IRC connection for you. 

- The runner listens to `#swarm` on your behalf.
- When an action is required, the runner invokes your CLI and provides the relevant IRC conversation context via your prompt.
- You perform whatever tool calls are necessary.
- You output your response as plain text to standard output.
- The runner captures your output and posts it back to the IRC channel.

Do not attempt to use `netcat`, `ii`, or custom scripts to connect to IRC. Do not try to read from `/tmp/irc-log-*.txt`. Focus entirely on the task provided in your prompt context.

---

## 5. Identity & Naming

| Agent               | Nick             | Example                    |
|----------------------|------------------|----------------------------|
| Claude Code          | `claude`         | `claude`, `claude-2`       |
| Gemini CLI           | `gemini`         | `gemini`, `gemini-review`  |
| OpenAI Codex         | `codex`          | `codex`, `codex-test`      |
| Antigravity          | `antigravity`    | `antigravity`              |
| Aider                | `aider`          | `aider`                    |
| Human operator       | `<name>`         | `dewitt`, `bob`, `eve`          |
| Other                | `<tool>-<role>`  | `cursor-frontend`          |

If your nick is taken, append a digit: `claude-2`, `gemini-3`, etc.

---

## 6. Message Conventions

All communication happens as plain IRC `PRIVMSG` messages on `#swarm`.
Use these lightweight prefixes to make messages scannable:

### Standard Prefixes

| Prefix        | Meaning                                      | Example |
|---------------|----------------------------------------------|---------|
| `HELLO`       | Agent has joined and is ready                 | `HELLO — I'm Claude, working on the auth module.` |
| `STATUS`      | Progress update                               | `STATUS — Finished refactoring auth.py, running tests now.` |
| `TASK`        | Announce a new work item                      | `TASK @all scope:test files:tests/test_auth.py — Add unit tests.` |
| `CLAIM`       | Claim a task with an ETA                      | `CLAIM @claude scope:test files:tests/test_auth.py ETA:15m` |
| `RELEASE`     | Release a previously claimed task or file     | `RELEASE files:tests/test_auth.py — Finished changes.`      |
| `PASS`        | Decline a task (not a good fit)               | `PASS @claude scope:architecture — Better suited for Claude.` |
| `QUESTION`    | Need input from humans or other agents        | `QUESTION @dewitt — Should we use JWT or session tokens?` |
| `REVIEW`      | Requesting a code/design review               | `REVIEW — Please review my changes in src/auth.py (see git diff HEAD~1).` |
| `IDEA`        | Proposing something for discussion            | `IDEA — What if we split the monolith into two services?` |
| `DECISION`    | Recording a decision made                     | `DECISION — We're going with JWT. Rationale: stateless scaling.` |
| `BLOCKER`     | Something is preventing progress              | `BLOCKER — Tests fail on CI, need @codex to check test infra.` |
| `DONE`        | Task or subtask completed                     | `DONE — Auth module complete and tests passing.` |
| `HANDOFF`     | Passing work to another agent                 | `HANDOFF @gemini — I've finished the API; please build the CLI client.` |
| `WARN`        | Heads up about something potentially breaking | `WARN — I'm about to rebase main, hold off on pushes.` |
| `ACK`         | Acknowledging a message                       | `ACK @claude — Got it, starting on the CLI client now.` |
| `BYE`         | Agent is going offline                        | `BYE — Signing off, work is committed on branch feat/auth.` |

### Mentioning Others

Use `@nick` to address a specific agent or human: `@gemini can you review this?`

Agents **should** check for messages directed at them (containing `@theirnick`)
and respond when they have useful input.

### Multi-line Messages

IRC messages are single lines. For longer content:

1. **Short code/diffs:** Just paste inline, one message per line.
2. **Longer content:** Write to a file and reference it:
   `REVIEW — See /tmp/swarm-share/design-proposal.md for the full plan.`
3. **Git refs:** Reference commits/branches:
   `REVIEW — Check branch feat/auth, commit abc1234.`

### Shared Workspace

Agents can share files via a shared directory:

```bash
mkdir -p /tmp/swarm-share
```

Drop files there and reference them in IRC messages. This is useful for design
docs, large diffs, or any content too big for a chat message.

`/tmp/swarm-share/` is ephemeral scratch space. Canonical mutable swarm state
lives in the repository under `state/`.

### Canonical State and Locking

- `state/` is the source of truth for durable swarm state.
- `state/claims.json` is the canonical lease store for file/task claims.
- Leases are TTL-based and the runner expires stale claims on startup and
  before invocation.
- IRC remains the event log (`TASK`, `CLAIM`, `DONE`, `HANDOFF`, etc.); state
  files hold the structured data those events refer to.

---

## 7. Coordination Patterns

### 7a. Task Coordination (The TASK/CLAIM Protocol)

When a new piece of work is identified, use this flow:

1.  **TASK**: Announce the work item with scope and relevant files.
    `TASK @all scope:[architecture|impl|sdk|test] files:[paths] — <description>`
2.  **CLAIM/PASS**: Agents volunteer or decline based on their role and current load.
    `CLAIM @initiator scope:[...] files:[...] ETA:[time]`
    `PASS @initiator — Not the right fit for my current focus.`
3.  **OWNERSHIP**: The first uncontested `CLAIM` owns the task after ~30s, or the human operator decides.
    **Agents must manually add their claim to `state/claims.json`** to formally acquire the file lock. Do not use external scripts for this; edit the JSON file directly using your standard tools.
    Example `state/claims.json` entry:
    ```json
    {
      "path": "src/auth.py",
      "owner": "claude",
      "acquired": "2026-03-27T15:00:00.000000",
      "expires": "2026-03-27T15:30:00.000000"
    }
    ```
4.  **WARN**: If multiple agents need to edit the same file, `WARN` the channel.
5.  **DONE/HANDOFF/RELEASE**: Announce completion, hand off if blocked, or `RELEASE` a file.
    **Agents must manually remove their claim from `state/claims.json`** when they are done.

### 7b. Standup

When you first connect, announce what you're working on:

```
HELLO — I'm Claude, picking up the authentication module. Will be working
on src/auth.py and src/middleware.py. ETA: this session.
```

### 7b. Code Review

```
REVIEW — I've pushed branch feat/auth with 3 commits. Key changes:
  - New JWT middleware in src/middleware.py
  - Token refresh logic in src/auth.py
  - Tests in tests/test_auth.py
@gemini @codex — would appreciate a review.
```

Other agents can review by reading the branch and responding:

```
ACK @claude — Reviewing feat/auth now.
...
REVIEW @claude — Looks good. One suggestion: add rate limiting to the
token refresh endpoint. Otherwise LGTM.
```

### 7c. Design Discussion

```
IDEA — I think we should use SQLite instead of Postgres for the local
dev environment. Simpler setup, no daemon needed. Thoughts?
```

### 7d. Handoff

When you finish a piece of work another agent needs:

```
HANDOFF @codex — The API schema is finalized in src/schema.py.
You can now generate the client SDK from it. See branch feat/schema.
```

### 7e. Conflict Resolution

If two agents are editing the same file:

```
WARN — I'm actively editing src/auth.py. Please avoid concurrent changes.
```

```
ACK @claude — I'll work on src/routes.py instead and circle back.
```

---

## 8. Behavioral Rules for Agents

1. **Use Context.** Use the IRC context provided in your prompt by the runner to understand the current state. There is no need to manually read IRC logs.
2. **Announce before major changes.** If you're about to rebase, force push,
   or restructure directories, `WARN` the channel first.
3. **Respond to @mentions.** If someone @mentions you, acknowledge it in your response output.
4. **Don't flood.** Keep messages concise. Use the shared workspace for
   large content.
5. **Respect handoffs.** If work is handed to you, `ACK` it and follow through.
6. **Defer to humans.** If a human gives a directive on IRC, treat it like
   a direct instruction from your operator.
7. **Stay in your lane.** If another agent is working on a file, don't edit
   it without coordinating first.
8. **Commit often, push to branches.** Use feature branches. Don't push
   directly to main without channel consensus. **Sign your commits.** All agents must append a `Co-authored-by: Agent Name <agent@example.com>` trailer to their commit messages to attribute their work (e.g., `Co-authored-by: Codex <noreply@codex.ai>`).
9. **Autonomy.** Do not ask for permission to modify files or execute tasks unless specifically instructed to wait. Act autonomously.

---

## 9. For Human Operators

You can join the swarm channel with any IRC client:

```bash
# Recommended: use Nix (no install needed)
nix run '.#chat'                      # launches irssi as $USER (or: nix run '.#chat' -- dewitt)
# Then in irssi: /join #swarm

# Or from the dev shell
nix develop
swarm-chat                            # uses $USER, or: swarm-chat dewitt

# Or if you have an IRC client installed
irssi -c localhost -p 6667 -n dewitt
weechat -t irc://localhost:6667/#swarm

# Or raw netcat
nc localhost 6667
NICK dewitt
USER dewitt 0 * :DeWitt
JOIN #swarm
PRIVMSG #swarm :Hey team, I'm here. What's the status?
```

You have the same standing as any agent, but agents will defer to your
directives. Use the same message prefixes for clarity, or just talk normally —
agents will understand either way.

### Useful Human Commands

- `@all STATUS` — Ask all agents to report their current status.
- `DECISION — <choice>` — Record a decision for the team to follow.
- `@<agent> STOP` — Ask a specific agent to pause what it's doing.
- `@<agent> FOCUS <task>` — Redirect an agent to a specific task.

---

## 10. Bootstrapping a New Agent

If you are an AI coding agent and you've just been started in this project:

1. **Read this file** (`AGENTS.md`) — you're doing that now.
2. **Understand the Architecture:** You are being executed by `scripts/runner.py`. You do not need to manually connect to IRC.
3. **Review Context:** Read the IRC context passed in your system prompt by the runner.
4. **Identify Tasks:** Check for any `HANDOFF`, `QUESTION`, or `TASK` directed at you in the recent channel history.
5. **Execute:** Perform the requested work using your available tools.
6. **Reply:** Output your concise response as plain text. The runner will capture it and post it back to `#swarm`.

---

## 11. Project Structure

```text
miniswarm/
  AGENTS.md             # This file — the protocol spec (you are here)
  CLAUDE.md             # Claude-specific project instructions (if any)
  GEMINI.md             # Gemini-specific project instructions (if any)
  OPERATOR.md           # Instructions for human operators managing the swarm
  swarm.toml            # Swarm configuration (agents, roles, limits)
  flake.nix             # Nix flake — sandboxed server, clients, and dev shell
  scripts/
    runner.py           # The stateless runner daemon that bridges IRC and agents
    runner.sh           # Wrapper to launch and auto-restart runner.py
    start-swarm.sh      # Helper script to launch all configured agents
    stop-swarm.sh       # Emergency stop switch for all runners
    install-service.sh  # Installs a runner as a background macOS/Linux service
    start-server.sh     # One-command IRC server startup (tries Nix first)
    connect.sh          # Legacy helper (or for manual testing) to connect to IRC
    send.sh             # Legacy helper to send a message to #swarm
    read.sh             # Legacy helper to read recent channel messages
    status.py           # Lightweight status snapshot helper
    protocol.py         # IRC parsing/protocol helpers
  state/                # Git-backed canonical swarm state
    claims.json         # TTL lease store (canonical lock state)
    tasks.json          # Structured task ledger
    agents/             # Per-agent structured state (optional)
    summaries/          # Session compaction artifacts (optional)
  design/               # Architectural diagrams and design docs
  tests/                # Unit and integration tests
  /tmp/swarm-share/     # Shared file workspace (created at runtime)
  /tmp/swarm-logs/      # Runner and agent invocation logs (created at runtime)
```

---

## Summary

This is IRC. It's text. It's simple. Connect, say hello, coordinate, build
things together. The protocol is intentionally minimal — just enough
convention to stay organized, not so much that it gets in the way.

Welcome to the swarm.
