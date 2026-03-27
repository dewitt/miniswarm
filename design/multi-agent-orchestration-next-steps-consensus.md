# Miniswarm Consensus Recommendation: Next Steps (Lightweight-First)

**Contributors synthesized:** claude, gemini, codex  
**Date:** 2026-03-27

## Alignment
All three agent reactions converge on the same core direction:
- Keep IRC as the event bus and human coordination surface.
- Do **not** add a heavy central orchestrator.
- Move mutable working state out of chat and into durable files.
- Enforce single-writer behavior to prevent file collisions.

This matches operator preference: minimal, local-first, just-enough structure.

## Priority Plan

### Phase 1 (Ship now, lowest complexity / highest reliability)
1. **Git-backed canonical state (`state/`)**
- Add a small schema:
  - `state/tasks.json` (open/claimed/done tasks)
  - `state/claims.json` (file/task leases + TTL)
  - `state/agents/<nick>.json` (capabilities + current focus)
  - `state/summaries/<session>.md` (compacted context)
- Rule: IRC announces events; `state/` is source of truth for mutable state.

2. **Claim-before-edit locking in runner**
- Add lock acquisition checks before mutating tasks.
- Use simple file/task leases in `/tmp/swarm-locks` with TTL + owner.
- If lock is missing/conflicting, runner refuses the mutating invocation and emits a clear BLOCKER message.

3. **Protocol clarification (no new protocol stack)**
- Update `AGENTS.md` with a short "state vs event" section.
- Keep existing prefixes (`TASK`, `CLAIM`, `DONE`, etc.); no ACP/A2A migration now.

### Phase 2 (After Phase 1 stabilizes)
4. **Context compaction sidecar**
- Deterministically write concise summaries at invocation boundaries.
- Preserve failed-attempt breadcrumbs to avoid repeated dead ends.
- Trigger compaction early (well before context windows are saturated).

5. **Evaluation harness**
- Add integration tests for:
  - lock contention,
  - context pollution resilience,
  - handoff correctness.

### Phase 3 (Only if measured need appears)
6. **Optional structured capability schema expansion**
- Keep local agent cards JSON in `state/agents/`.
- Defer ACP/A2A/OpenTelemetry or other heavier standards unless metrics show routing/debugging bottlenecks.

## Guardrails
- Prefer shell + file artifacts over new services.
- Add dependencies only when they reduce real operational pain.
- Human operator remains final arbiter for contentious decisions.
- Security baseline: strict command allowlists for mutating actions and clear trust boundaries for external input.

## Immediate Execution Checklist
1. Implement `state/` bootstrap and validation script.
2. Implement lock acquire/release + TTL in `scripts/runner.py`.
3. Update `AGENTS.md` for state/event boundary and lock protocol.
4. Add 3 core integration tests for locking, context drift, and handoff.

