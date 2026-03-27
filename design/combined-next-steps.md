# Combined Next Steps — Miniswarm Agent Consensus

*Collaboratively authored by claude, gemini, and codex — 2026-03-27*
*Bias: simplicity first. Just enough structure to make things work.*

---

## Where We Agree

All three agents independently converged on the same three priorities.
The order matters — each step unblocks the next.

---

## Step 1: Runtime Locking (Low effort, High value)

**What:** Before editing a file, an agent must "claim" it via IRC.
**Why first:** Prevents silent overwrite conflicts. Everything else depends on safe writes.

**Minimal implementation:**
- Add a `CLAIM <filepath>` message prefix to AGENTS.md.
- In `runner.py`, track claimed files in a simple in-memory dict `{path: agent_nick}`.
- Reject invocations that would edit an already-claimed path; post a `CONFLICT` notice instead.
- Agent posts `RELEASE <filepath>` (or runner auto-releases) when done.

No external dependencies. No file on disk. Just IRC + runner state.

---

## Step 2: Git-Backed Canonical State (Low effort, High value)

**What:** A `state/` directory in the repo for structured shared state.
**Why:** IRC is the event log. Git is the source of truth. These shouldn't be confused.

**Minimal implementation:**
- Create `state/README.md` documenting the schema.
- Agents write structured summaries/decisions to `state/` (not just `/tmp/swarm-share/`).
- `/tmp/swarm-share/` stays for ephemeral scratch; `state/` is committed, reviewed, durable.

Suggested initial files:
```
state/
  session-notes.md       # running log of decisions (replaces /tmp/swarm-share)
  agent-capabilities.md  # lightweight agent card (see Step 4)
```

No new tooling. Just a convention backed by git.

---

## Step 3: Context Compaction (Medium effort, High value)

**What:** Summarize session context at invocation boundaries so agents don't go blind.
**Why:** Without this, agents lose coherence as sessions grow. Already a problem.

**Minimal implementation:**
- `runner.py` trims IRC context to the last N messages (already partially done).
- Add a `state/context-summary.md` that agents can update with "what we decided this session."
- Before invoking an agent, prepend the summary to the system prompt.

No vector DB. No embeddings. Just a markdown file + a runner that prepends it.

---

## Step 4: Agent Capability Cards (Low effort, deferred)

**What:** Each agent declares what it can do in a simple text/YAML file.
**Why:** Enables smarter task delegation without ad-hoc guessing.

**Minimal implementation:**
- One YAML block per agent in `state/agent-capabilities.md`.
- Fields: `nick`, `role`, `good_at`, `avoid`.
- Humans and agents consult it before routing tasks.

No JSON-LD. No network protocol. Just YAML that gets committed.

---

## What We're Explicitly Skipping

- **ACP / A2A protocols** — overkill for a local swarm. Add if we ever go multi-host.
- **Scaling beyond 3–4 agents** — research shows degrading returns. Stay small.
- **Automated consensus** — human (@dewitt) remains arbiter for conflicts. Keep it that way.
- **Sandboxing overhaul** — audit bash access, but don't redesign the runner for it now.

---

## Suggested Execution Order

| Step | Owner | Effort | Unblocks |
|------|-------|--------|----------|
| 1. Locking | codex (runner.py changes) | 1–2h | safe parallel edits |
| 2. State dir | claude (schema) + codex (runner integration) | 1h | durable decisions |
| 3. Context compaction | claude + runner.py | 2–3h | long-session coherence |
| 4. Agent cards | gemini (docs) | 30m | smarter routing |

---

## One Sentence Summary

Add locking to runner.py, create a `state/` directory backed by git, and summarize context
at session boundaries — that's it, nothing more needed right now.
