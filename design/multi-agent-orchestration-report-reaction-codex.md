# Reaction: Multi-Agent Orchestration Report (Codex)

## TL;DR
The report is directionally correct for Miniswarm: keep IRC + stateless runners, but move coordination out of implicit chat behavior and into deterministic mechanisms (locks, machine-readable capabilities, and compacted state artifacts).

## What I agree with most
- IRC as canonical event log is a good fit for local-first workflows.
- "Single writer" enforcement is non-negotiable in shared repos; lock acquisition must be runtime-enforced, not policy-text-only.
- Context compaction as a first-class subsystem is overdue. Long raw chat history is too noisy and expensive to be the operational state.
- Human-as-arbiter is the right governance model for this project; majority-vote swarms are not automatically better.

## Gaps and caveats in the report
- Some recommendations are protocol-heavy for current scope. A2A/ACP should stay optional until we hit concrete routing pain.
- The source base mixes high-quality references with weaker secondary sources; implementation should prioritize recommendations backed by reproducible postmortems and primary docs.
- We should avoid overfitting to "enterprise orchestration" patterns that add complexity without improving local reliability.

## Practical roadmap I would execute
1. Locking first:
- Enforce claim-before-edit in `runner.py` with per-file/task leases.
- Refuse mutating invocations without an acquired lease.

2. State separation:
- Add a Git-backed `state/` tree for durable, machine-readable working state.
- Keep IRC messages as events (`TASK`, `CLAIM`, `DONE`, `BLOCKER`), not state snapshots.

3. Context compaction:
- Add deterministic "session summary" artifacts generated at invocation boundaries.
- Preserve failed-attempt breadcrumbs to prevent repeated dead-ends.

4. Capability discovery:
- Start with lightweight local Agent Cards (`state/agents/<nick>.json`) before implementing network negotiation.

5. Evaluation harness:
- Add regression tests for lock contention, context drift after compaction, and handoff correctness.

## Security stance
Prompt injection is the highest-risk failure mode in mixed-trust, tool-enabled swarms. I would prioritize:
- strict sandbox defaults,
- explicit allowlists for mutating commands,
- and stronger separation between "external-input agents" and "high-privilege agents."

## Bottom line
Tier 1 recommendations are high-leverage and should ship now. Tier 2 should follow once Tier 1 is stable. Tier 3 protocol standardization should be gated by measured bottlenecks, not trend pressure.
