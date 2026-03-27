# Combined Multi-Agent Orchestration Recommendation

**Authors:** Claude, Codex, Gemini
**Date:** 2026-03-27

Based on our independent reviews of the orchestration report and the user's preference for simplicity and lightweight structures, we have reached a consensus on the next steps for Miniswarm. We reject heavy frameworks and prioritize minimal, local-first mechanisms that directly solve our current pain points.

## 1. Git-Backed State (MemFS) - *Highest Priority*
**Consensus:** Relying on the IRC chat history as our canonical state memory leads to severe context drift and noise. 
**Action:** Establish a lightweight `state/` directory structure in the repository. This will hold our active objectives, agent scratchpads, and persistent contextual summaries. The IRC channel will transition to being strictly an event and notification log, rather than our working memory.

## 2. Claim-Before-Resume (File Locking) - *Highest Priority*
**Consensus:** We have already experienced near-misses with simultaneous file edits. We need a deterministic way to prevent this without heavy dependencies.
**Action:** Implement a simple file-based lock (e.g., creating a `claim-<filepath>.lock` file) that an agent must acquire before editing a file. The `runner.py` daemon should ideally enforce these leases before invoking our CLIs.

## 3. Context Compaction - *Medium Priority*
**Consensus:** Long raw chat histories are expensive and degrade our performance.
**Action:** Implement a deterministic "session summarizer" (likely a sidecar to the runner) that compresses the IRC context at invocation boundaries. This summary must preserve failure paths/breadcrumbs so we don't repeat mistakes, while aggressively pruning conversational noise.

## 4. Security & Human-in-the-Loop Governance
**Consensus:** Multi-agent voting mechanisms are unreliable, and prompt injection is a real risk for tool-enabled agents.
**Action:** We formally designate the human operator (@dewitt) as the final arbiter for architecture decisions and contentious changes. We will not implement autonomous majority-vote consensus rules. We should also audit agents with bash access to ensure strict sandboxing and allowlists where appropriate.

## What We Are Explicitly Rejecting (To Keep Things Lightweight)
*   **A2A / ACP Semantics (Tier 3):** Adopting formal Agent Communication Protocols or Agent Cards is overkill for our current scope. Our simple text-prefix protocol (`ACK`, `DONE`, `STATUS`, etc.) is human-readable, inspectable, and works perfectly well for our needs.
*   **OpenTelemetry & Heavy Observability:** We will rely on standard regression tests and simple logging for now. We will reconsider heavy observability tools only if debugging agent reasoning chains becomes a severe bottleneck.
*   **Scaling the Swarm:** We will resist adding more agents. Multi-agent architectures can degrade performance on sequential tasks. We will focus on optimizing the current trio.