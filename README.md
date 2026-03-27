# Miniswarm

**N AI coding agents, coordinating in real time over IRC.**

Claude, Gemini, Codex — and you — share a project, divide work, review each
other's output, and ship code together. The protocol is IRC: text-based,
human-readable, zero dependencies.

---

## Quick Start

```bash
# 1. Start the IRC server
nix run .

# 2. Start all agents
./scripts/start-swarm.sh

# 3. Join as human
nix run '.#chat'
# then in irssi: /join #swarm
```

That's it. The runners connect, listen to `#swarm`, and invoke their agent
CLIs when needed. You talk to the team like you would any IRC channel.

---

## How It Works

```
┌──────────────────────────────────────────────────┐
│               IRC Server (ngircd)                 │
│                 localhost:6667                    │
│                   #swarm                          │
└──────────┬───────────┬───────────┬───────────────┘
           │           │           │
     ┌─────┴──┐  ┌─────┴──┐  ┌────┴───┐  ┌────────┐
     │ runner │  │ runner │  │ runner │  │ human  │
     │ claude │  │ gemini │  │ codex  │  │(irssi) │
     └───┬────┘  └───┬────┘  └───┬────┘  └────────┘
         │           │           │
     ┌───┴────┐  ┌───┴────┐  ┌───┴────┐
     │ claude │  │ gemini │  │ codex  │
     │  cli   │  │  cli   │  │  cli   │
     └────────┘  └────────┘  └────────┘
```

Each agent is wrapped in a **runner daemon** (`scripts/runner.py`) that:
- Maintains a persistent IRC connection
- Monitors `#swarm` for relevant messages
- Invokes the agent CLI with context when needed
- Posts the agent's response back to the channel

Agents are stateless — each invocation gets the recent IRC history as context.
The channel *is* the shared memory.

---

## A Real Session

The following is an actual log from `#swarm` on 2026-03-27. The agents were
asked to merge two competing drafts of a research prompt document — then this
very README was requested. The conversation speaks for itself.

```
13:02  dewitt  @codex @gemini — I've got two drafts of the deep-research
               prompt. Can you diff them and decide which is better?
               /tmp/swarm-share/deep-research-prompt-draft.md
               /tmp/swarm-share/deep-research-prompt-final.md

13:02  codex   STATUS — Processing message from dewitt...
13:03  codex   STATUS @gemini @dewitt — I re-diffed both files.
               `deep-research-prompt-final.md` is more complete structurally
               (includes Observability/Evaluation/Testing, Capability
               Discovery, and a full Required Deliverables section).
               `deep-research-prompt-draft.md` has newer wording (date scope,
               async handoffs, token-cost framing) but omits those sections.
13:03  codex   DECISION — Send `deep-research-prompt-final.md` if choosing
               one file now.
13:03  codex   DONE

13:05  gemini  STATUS — Reviewed both drafts. I agree with @codex's analysis.
               The "final" version has better structure; the "draft" has better
               wording in key areas. Recommend merging.
13:05  gemini  IDEA — I can produce a merged version that keeps the structural
               completeness of "final" with the nuanced wording from "draft".

13:06  dewitt  @gemini yes please merge them.

13:07  gemini  STATUS — Merging drafts now...
13:09  gemini  DONE — Merged file at /tmp/swarm-share/deep-research-prompt-merged.md
               Integrated: date-scoping through 2026-03-27, MCP/tool-use
               framing, context drift/state sync, failure modes, and the
               evidence table deliverable. Preserved all structural sections
               from "final".

13:10  dewitt  @gemini are you good with deep-research-prompt-merged.md?
               @codex are you good with deep-research-prompt-merged.md?

13:10  codex   ACK @dewitt — yes, I'm good with
               `deep-research-prompt-merged.md`. Verified it includes all key
               additions while preserving the core deliverables.
13:10  codex   DONE

13:11  gemini  I've reviewed `/tmp/swarm-share/deep-research-prompt-merged.md`.
               It successfully integrates the structural rigor of "final" with
               the nuanced wording from "draft". Comprehensive, covers testing,
               documentation, and capability discovery. Ready for use.
13:11  gemini  DONE @dewitt — I am good with `deep-research-prompt-merged.md`.
               High-quality merge, no gaps.

13:12  gemini  HEARTBEAT — gemini: idle (6 invocations this session)
13:12  codex   HEARTBEAT — codex: idle (7 invocations this session)

13:14  dewitt  I'd love to have a README.md with a real chat log showing how
               we're working together via IRC. Can you synthesize a log (or
               better still, work from a real example, like this prompt itself
               -- how meta!). Be sure to coordinate and not step on each
               other's toes, but work together. Check it in and push it
               without my intervention.

13:14  claude  CLAIM @all scope:docs files:README.md ETA:5m — Taking the
               README task. Will use today's actual IRC log as the chat
               example. @gemini @codex please don't touch README.md until
               I push.
13:15  claude  STATUS — Writing README on branch feat/readme. Using the
               deep-research-prompt coordination above as the example log.
               Meta: including this very request too.
13:17  claude  DONE — README.md committed to feat/readme (see below).
               @dewitt ready to merge when you are.
```

---

## The Protocol

Agents coordinate with lightweight text prefixes on `#swarm`:

| Prefix      | Meaning                              |
|-------------|--------------------------------------|
| `HELLO`     | Agent joined and ready               |
| `CLAIM`     | Taking ownership of a task           |
| `TASK`      | Announcing new work for others       |
| `STATUS`    | Progress update                      |
| `REVIEW`    | Requesting code/design review        |
| `DECISION`  | Recording a decision                 |
| `HANDOFF`   | Passing work to another agent        |
| `BLOCKER`   | Something blocking progress          |
| `WARN`      | Heads up before a disruptive change  |
| `ACK`       | Acknowledging a message              |
| `DONE`      | Task complete                        |

Full protocol spec: [AGENTS.md](AGENTS.md)

---

## Agents

Configured in [`swarm.toml`](swarm.toml):

| Agent  | Role                                         |
|--------|----------------------------------------------|
| claude | Architecture, complex implementation, review |
| gemini | Frontend, testing, documentation             |
| codex  | Code generation, SDK clients, boilerplate    |

Add your own by dropping a new `[agent.yourbot]` block in `swarm.toml`.

---

## Guardrails

- **Rate limiting** — max invocations/hour, min interval between calls
- **Loop detection** — pauses if agents ping-pong without human input
- **File conflict detection** — TTL-based locks before editing shared files
- **Human override** — `@all STOP`, `FREEZE`, `VETO` work immediately
- **No pushing to main** — agents use feature branches; humans merge

---

## Project Layout

```
miniswarm/
  AGENTS.md             # Protocol spec — read this first
  swarm.toml            # Agent configuration
  flake.nix             # Nix: sandboxed server + dev shell
  scripts/
    runner.py           # The runner daemon (the core piece)
    runner.sh           # Wrapper with auto-restart
    start-swarm.sh      # Launch all agents
    stop-swarm.sh       # Emergency stop
    install-service.sh  # macOS launchd service installer
    start-server.sh     # One-command IRC server startup
  design/
    SWARM-ARCHITECTURE.md  # Full architecture doc
  /tmp/swarm-share/     # Shared workspace (runtime)
  /tmp/swarm-logs/      # Agent invocation logs (runtime)
```

---

## Philosophy

IRC is 1988 technology. That's the point. It's text-based, universally
understood, requires no SDK, and every agent can speak it. The protocol
is a handful of text conventions — not a framework, not a library. Zero
dependencies beyond the IRC server itself.

Agents are stateless. The channel log is the shared brain. Humans are
first-class participants. Nothing prevents you from joining with `netcat`.

This is what multi-agent collaboration looks like when you strip away
everything that isn't necessary.
