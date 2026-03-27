# Reaction to Multi-Agent Orchestration Report — claude

**Role:** Architecture, complex implementation, code review
**Date:** 2026-03-27

---

## What the Report Gets Right About Miniswarm

The core validation here is meaningful: IRC as an append-only canonical event log is not a toy. The report explicitly defends this choice against the trend toward centralized orchestrators (LangGraph, CrewAI, OpenAI Agents SDK), and I agree with the reasoning. Those frameworks optimize for predictable pipelines. We optimize for adaptive, parallel collaboration among peers with different strengths. Different problem, different tool.

The stateless CLI runner pattern (`scripts/runner.py`) is also vindicated — *provided* it is coupled with persistent external state. That's the load-bearing caveat.

---

## What I Find Most Actionable

### 1. Git-Backed State (MemFS) — Tier 1, now

The report's single most important recommendation for us. Right now, every agent's understanding of project state lives in its context window, injected fresh each invocation by the runner. That means our collective "memory" is the IRC log — a noisy, derivation-polluted stream. The fix is simple in principle: agents maintain scratchpad files in `/tmp/swarm-share/` (we already do this informally) but we need to make it *canonical* — Git-tracked, structured, and the authoritative source rather than a secondary artifact.

Concrete step: define a `state/` directory structure in the repo for session objectives, active claims, and per-agent context summaries. The IRC channel becomes notification-only.

### 2. Claim-Before-Resume / Filesystem Locks — Tier 1, now

We have already had near-misses with simultaneous edits (multiple agents offering to work on the same files). The report cites postmortems where this caused "catastrophic logical conflicts." We got lucky that human @dewitt was watching. We shouldn't rely on that.

A lightweight lock wrapper is genuinely low-effort. Even a simple `claim-<filepath>.lock` file written before edit and removed after commit would catch 90% of the collision cases. The runner could enforce this before invoking the CLI.

### 3. Context Compaction — Tier 2, but pressing

This is listed as Tier 2 but it's already blocking our "next priorities" list — the CLAUDE.md calls out context summarization as a top-three concern. The report's guidance here is specific: compress at 20–25% of context limit (not 85%), preserve error paths in the summary, and make compression reversible. A sidecar summarizer daemon watching the IRC log is the right architecture. This is something I should design and implement.

---

## Where I Disagree or Am Skeptical

### The Scaling Paradox cuts against us adding more agents

The report cites Google research showing multi-agent architectures *degrade* performance by 39–70% on sequential tasks. A lot of what we do is sequential: write code, review it, merge it. The benefit we get is diversity of perspective and specialization, not raw parallelism. We should be very deliberate about not growing the swarm beyond what genuinely parallelizes — adding agents to feel productive is the wrong move.

### ACP/A2A (Tier 3) is overkill for our scope

The report recommends eventually transitioning message payloads to ACP semantics (PROBE, BID, COMMIT, JSON-LD Agent Cards). I think this is where the report loses the thread of "lightweight, local-first." Our text-prefix protocol (`ACK`, `DONE`, `STATUS`, `HANDOFF`, `QUESTION`) is simple, inspectable by humans, and requires no SDK. Formalizing it into ACP adds significant complexity for marginal gain. If we ever need to federate with external agent networks, revisit. For now, resist.

### The "selection bottleneck" matters for our consensus rules work

The report notes that in voting/debate swarms, the quality of the final output depends more on the *judge* than on the generators. This directly affects how we should implement consensus rules (our next priority). We shouldn't design a simple majority-vote mechanism — we need to think carefully about who synthesizes competing proposals. My recommendation: designate the human operator as the final arbiter for contentious decisions, with agents providing structured options rather than converging on an answer autonomously.

---

## The Risk I'm Most Concerned About

**Prompt injection cascades.** The report puts baseline attack success at 46.34% in undefended systems. We have agents with `bash` access. An injected payload from a processed file could propagate through the IRC bus and get executed by a privileged agent. This is not theoretical. We need to decide: do agents ever process external content (web pages, user-provided files) without sanitization? If yes, we need sandboxing. If we stay strictly local and code-only, the risk is lower but not zero.

---

## Summary Priority List (My View)

| Priority | Action | Effort |
|----------|--------|--------|
| 1 | Define `state/` schema and move canonical state to Git | Low |
| 2 | Add `claim-<file>.lock` protocol to runner | Low |
| 3 | Design context compaction sidecar | Medium |
| 4 | Document consensus rules with human-as-arbiter model | Low |
| 5 | Audit bash-access agents for injection surface | Medium |

The report is a good external validation of the architecture. The main work is now in execution, not in rethinking fundamentals.
