# Miniswarm State

`state/` is the git-backed source of truth for structured swarm state.

- `claims.json`: TTL-based file/task leases used by `scripts/runner.py`
- `tasks.json`: optional structured task ledger
- `agents/`: per-agent state snapshots (optional)
- `summaries/`: session summaries/context compaction artifacts (optional)

`/tmp/swarm-share/` remains available for ephemeral scratch files and large
artifacts that do not need durable, reviewed history.
