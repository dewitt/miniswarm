# Miniswarm Architecture

## The Vision

N autonomous AI coding agents running in parallel, communicating and
coordinating like a team of engineers — but faster. They share a project,
divide work, review each other's output, resolve conflicts, and make
decisions. Humans drop in and out as peers. The protocol is IRC: simple,
text-based, human-readable.

This document describes the architecture that makes this work.

---

## The Core Problem

Every major coding agent today (Claude Code, Gemini CLI, Codex, Aider,
Cursor) is **request-response**. A human types something, the agent acts,
then waits. None of them are designed to be long-running daemons that
listen on a channel and react autonomously.

Miniswarm needs a thin **agent runner** layer that bridges this gap:
monitoring IRC, deciding when to invoke an agent, providing context, and
posting responses back to the channel.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   IRC Server (ngircd)                 │
│                     localhost:6667                    │
│                       #swarm                         │
└──────────┬───────────┬───────────┬───────────┬───────┘
           │           │           │           │
     ┌─────┴──┐  ┌─────┴──┐  ┌────┴───┐  ┌────┴───┐
     │ runner │  │ runner │  │ runner │  │ human  │
     │ claude │  │ gemini │  │ codex  │  │ (irssi)│
     └───┬────┘  └───┬────┘  └───┬────┘  └────────┘
         │           │           │
     ┌───┴────┐  ┌───┴────┐  ┌───┴────┐
     │ claude │  │ gemini │  │ codex  │
     │  cli   │  │  cli   │  │  cli   │
     └────────┘  └────────┘  └────────┘
```

### Components

1. **IRC Server** — ngircd on localhost. The shared bus. Stateless,
   dumb, reliable. All coordination flows through here.

2. **Agent Runner** — one per agent. A lightweight daemon (shell script
   or Python) that:
   - Maintains a persistent IRC connection
   - Monitors #swarm for messages relevant to its agent
   - Decides when the agent needs to be invoked
   - Invokes the agent with appropriate context
   - Posts the agent's response back to IRC
   - Handles protocol-level stuff (PING/PONG, ACK) without waking the agent

3. **Agent CLI** — the actual AI (claude, gemini, codex, etc.). Invoked
   by the runner in non-interactive mode when substantive work is needed.

4. **Human** — joins with any IRC client. First-class participant.

---

## The Agent Runner

This is the key new component. Each runner is an autonomous process that
makes its agent a persistent member of the swarm.

### Runner Responsibilities

```
ALWAYS (handled by runner, no agent invocation):
  - Maintain IRC connection (PING/PONG)
  - ACK simple protocol messages
  - Respond to STATUS requests with cached state
  - Log all channel activity

SOMETIMES (invoke agent with context):
  - @mention directed at this agent
  - QUESTION directed at this agent
  - HANDOFF directed at this agent
  - REVIEW request (agent reviews the code)
  - DECISION that affects this agent's current work

NEVER (ignore):
  - Messages between other agents that don't mention this agent
  - STATUS updates from others (log only)
  - HELLO/BYE from others (log only)
```

### Runner Invocation Model

When the runner decides the agent needs to act, it:

1. Gathers context:
   - Last N messages from IRC log (conversation context)
   - Current task/role description
   - Relevant file state (git status, recent diffs)

2. Invokes the agent in non-interactive mode:
   ```bash
   # Claude Code
   claude -p "$(cat context.txt)" --allowedTools bash,read,write,edit

   # Gemini CLI
   gemini -p "$(cat context.txt)"

   # Codex
   codex -p "$(cat context.txt)"
   ```

3. Parses the agent's output and posts relevant parts to IRC.

4. If the agent made code changes, announces them on IRC.

### Runner State Machine

```
                    ┌─────────┐
                    │  IDLE   │◄──────────────────────┐
                    └────┬────┘                       │
                         │ relevant message           │ done / timeout
                         ▼                            │
                    ┌─────────┐                       │
                    │ CONTEXT │ gather context         │
                    │ GATHER  │                        │
                    └────┬────┘                       │
                         │                            │
                         ▼                            │
                    ┌─────────┐                       │
                    │ WORKING │ agent invoked          │
                    │         │ (with timeout)         │
                    └────┬────┘                       │
                         │                            │
                         ▼                            │
                    ┌─────────┐                       │
                    │ RESPOND │ post to IRC ───────────┘
                    └─────────┘
```

---

## Guardrails

Autonomous agents communicating without a human in every loop is powerful
but dangerous. These guardrails prevent runaway behavior.

### G1: Rate Limiting

Each runner enforces rate limits on its agent:

| Limit                         | Default | Rationale                          |
|-------------------------------|---------|------------------------------------|
| Max agent invocations / hour  | 30      | Cost control                       |
| Min seconds between invokes   | 10      | Prevent rapid-fire loops           |
| Max IRC messages / minute     | 10      | Prevent channel flooding           |
| Max tokens per invocation     | 50,000  | Bound cost per action              |

Configurable per-agent in a `swarm.toml` or similar.

### G2: Loop Detection

The runner tracks conversation patterns. If it detects:
- Agent A responds to Agent B who responds to Agent A (ping-pong) for
  more than 3 rounds without human input or a DECISION
- The same question being asked more than twice
- An agent invoking itself (via IRC echo)

...it **pauses** and posts:
```
BLOCKER — Loop detected between @claude and @gemini. Pausing for human
input. Context: [summary of the loop]
```

### G3: Scope Constraints

Each agent's runner has a defined scope:

```toml
[agent.claude]
nick = "claude"
role = "Senior engineer — architecture, code review, complex implementation"
allowed_files = ["src/**", "tests/**"]    # glob patterns
allowed_branches = ["feat/*", "fix/*"]    # never push to main
can_merge = false                          # only humans merge to main
can_delete = false                         # no deleting files/branches without approval
max_files_per_session = 20                 # scope creep prevention
```

### G4: Human Override

Humans always have override authority on IRC:

| Command              | Effect                                      |
|----------------------|---------------------------------------------|
| `@<agent> STOP`      | Runner immediately pauses the agent         |
| `@<agent> RESUME`    | Runner unpauses                             |
| `@all STOP`          | All runners pause                           |
| `@all RESUME`        | All runners resume                          |
| `VETO <decision>`    | Overrides a DECISION made by agents         |
| `FREEZE`             | No agent may push code until `UNFREEZE`     |

The runner **must** respect these immediately, even mid-invocation.

### G5: Mandatory Human Checkpoints

Certain actions always require human approval, even in autonomous mode:

- Pushing to main/master
- Deleting files or branches
- Modifying CI/CD configuration
- Changing dependencies (package.json, Cargo.toml, etc.)
- Any action touching security-sensitive files (.env, auth, crypto)

When an agent wants to do one of these, the runner posts:
```
APPROVAL @dewitt — Claude wants to merge feat/auth into main.
Changes: 3 files, +200/-50. Tests passing. Approve? (reply APPROVE or DENY)
```

### G6: Cost Budget

Each runner tracks cumulative cost (tokens used, API calls made). When
the budget hits a threshold, the runner posts a warning and eventually
pauses:

```
WARN — Claude has used ~$2.50 of API budget this session ($5.00 limit).
```

```
BLOCKER — Claude has hit its session budget ($5.00). Pausing.
@dewitt — increase budget or end session?
```

### G7: Conflict Prevention

Before an agent starts editing a file:

1. Runner checks if any other agent has announced work on that file
2. If so, runner posts a coordination message instead of invoking
3. Git branch isolation: each agent works on its own branch

```
WARN @gemini — Claude is about to edit src/auth.py which you're also
working on. Coordinating...
```

### G8: Audit Trail

Everything is logged:
- All IRC messages (the IRC server logs, plus per-runner logs)
- Every agent invocation (prompt, response, tokens used, duration)
- Every file change (git handles this)
- Every guardrail trigger (rate limit hit, loop detected, etc.)

Logs live in `/tmp/swarm-logs/` with one file per runner per session.

---

## Protocol Additions

Building on the conventions in AGENTS.md, the runner layer adds:

### Task Assignment

```
TASK @claude — Implement JWT authentication in src/auth.py.
  Requirements: RS256, 1hr expiry, refresh tokens.
  Branch: feat/auth
  Priority: high
```

### Task Claiming

```
CLAIM — I'm taking the JWT auth task. Starting on branch feat/auth.
```

### Progress (structured)

```
PROGRESS — JWT auth: [███████░░░] 70%
  Done: token generation, validation, middleware
  Remaining: refresh logic, tests
```

### Consensus

For decisions that affect multiple agents:

```
PROPOSE — Use SQLite for local dev. Votes needed from active agents.
```
```
VOTE +1 — Agreed, simpler setup. (@claude)
VOTE +1 — LGTM. (@codex)
VOTE -1 — Prefer Postgres for parity with prod. (@gemini)
```
```
RESULT — SQLite approved 2-1. Dissent noted. Proceeding.
```

### Heartbeat

Runners send periodic heartbeats so others know who's alive:

```
HEARTBEAT — claude: idle (last active 2m ago)
HEARTBEAT — gemini: working on feat/cli (5m elapsed)
```

---

## Configuration

Each swarm session is configured by a `swarm.toml` in the project root:

```toml
[server]
host = "127.0.0.1"
port = 6667
channel = "#swarm"

[defaults]
max_invocations_per_hour = 30
min_invoke_interval_seconds = 10
max_messages_per_minute = 10
session_budget_usd = 5.00
loop_detection_threshold = 3

[agent.claude]
nick = "claude"
command = "claude -p"
role = "Architecture, complex implementation, code review"
allowed_files = ["**"]
can_merge = false

[agent.gemini]
nick = "gemini"
command = "gemini -p"
role = "Frontend, testing, documentation"
allowed_files = ["**"]
can_merge = false

[agent.codex]
nick = "codex"
command = "codex -p"
role = "Code generation, SDK clients, boilerplate"
allowed_files = ["**"]
can_merge = false

[humans]
can_merge = true
can_delete = true
override_authority = true
```

---

## Bootstrapping a Swarm Session

```bash
# Terminal 1: Start the server
nix run .

# Terminal 2: Start all agents
./scripts/start-swarm.sh

# Terminal 3: Join as human
nix run '.#chat'

# On IRC:
dewitt> Hey team. Today we're building a REST API for the todo app.
dewitt> @claude — design the API schema and implement the routes.
dewitt> @gemini — write integration tests once claude has the routes up.
dewitt> @codex — generate the OpenAPI spec from claude's implementation.

# Agents autonomously:
claude> ACK @dewitt — Starting on API schema. Branch: feat/api
claude> STATUS — Schema designed. 5 endpoints. See /tmp/swarm-share/api-schema.md
claude> HANDOFF @gemini — Routes implemented in src/routes.py. Ready for tests.
gemini> ACK @claude — Writing integration tests on branch feat/api-tests.
codex>  ACK @dewitt — Waiting for @claude to finish routes, then generating OpenAPI spec.
...
```

---

## What We're NOT Building

- **A framework.** This is conventions + scripts, not a library.
- **A scheduler.** Humans assign work. Agents can hand off to each other.
  There's no central orchestrator.
- **A permissions system.** Guardrails are enforced by each runner locally,
  not by the IRC server. This is a trust-based system for local dev.
- **A distributed system.** This runs on one machine. localhost only.
  Scaling to multiple machines is a non-goal for v1.

---

## Implementation Plan

### Phase 1: Protocol (done)
- [x] AGENTS.md — conventions and message formats
- [x] IRC server setup (nix flake)
- [x] Connection helpers (connect.sh, send.sh, read.sh)
- [x] Human chat client (swarm-chat via nix)

### Phase 2: Agent Runner (done)
- [x] runner.sh / runner.py — generic agent runner daemon
- [x] IRC message parser (extract prefix, mentions, content)
- [x] Invocation logic (when to wake the agent)
- [x] Context builder (gather relevant info for the agent)
- [x] Response handler (post agent output to IRC)
- [x] PING/PONG and heartbeat

### Phase 3: Guardrails (mostly done)
- [x] Rate limiting
- [x] Loop detection
- [x] Human override commands (STOP, RESUME, FREEZE)
- [ ] Cost tracking
- [x] File conflict detection (TTL locks)

### Phase 4: Agent-Specific Adapters (done)
- [x] Claude Code adapter (via `swarm.toml` command)
- [x] Gemini CLI adapter (via `swarm.toml` command)
- [x] Codex adapter (via `swarm.toml` command)
- [x] Generic adapter (any CLI tool)

### Phase 5: Polish
- [x] swarm.toml configuration
- [x] Session logging and audit trail
- [ ] Desktop notifications for humans
- [ ] Status dashboard (optional, maybe a simple web UI)

---

## Open Questions

1. **How much context to give agents?** Too little and they're confused.
   Too much and it's expensive/slow. Should we summarize or send raw logs?

2. **Agent identity across invocations.** Each `claude -p` call is stateless.
   How do we maintain continuity? Feed back previous decisions? Use
   CLAUDE.md/session files?

3. **Conflict resolution without humans.** If two agents disagree, what's
   the tiebreaker? Voting? Designated lead? Always escalate to human?

4. **Testing this.** How do we test a multi-agent system? Record and replay
   IRC sessions? Mock agents?

5. **What's the right granularity for tasks?** Too coarse and agents
   thrash. Too fine and the overhead of IRC coordination exceeds the work.
