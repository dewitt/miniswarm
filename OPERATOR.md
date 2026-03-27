# Miniswarm Operator Guide

This guide is for the human operator managing the Miniswarm. It covers the step-by-step process to bootstrap a session, manage agents, recover from failures, and best practices for leading the swarm.

## 1. Bootstrapping a Session

Follow these steps to start a new swarm session from scratch:

### Step 1: Start the IRC Server
The IRC server is the coordination backbone. It must be running before any agents connect.
```bash
# Using Nix (recommended)
nix run .

# Or drop into a dev shell and start it manually
nix develop
swarm-server
```

### Step 2: Start the Agents
Launch the AI agent runners. These run as background daemons that connect to the IRC server and wait for messages. You can run as many agents as you have configured in `swarm.toml`.

```bash
# Start the core agents in the background
nohup ./scripts/runner.sh claude > /tmp/swarm-logs/runner-claude.out 2>&1 &
nohup ./scripts/runner.sh gemini > /tmp/swarm-logs/runner-gemini.out 2>&1 &
nohup ./scripts/runner.sh codex > /tmp/swarm-logs/runner-codex.out 2>&1 &
```
*Note: The `runner.sh` script automatically restarts the runner if it crashes or disconnects.*

### Step 3: Join the Swarm
Connect to the `#swarm` channel as the human operator to direct the agents.

```bash
# Using the built-in irssi client (if using Nix)
nix run '.#chat'

# Or using any standard IRC client
irssi -c localhost -p 6667 -n <your-name>
# Then in the client: /join #swarm
```

### Step 4: Initial Briefing
Once connected, give the swarm an initial directive or let them know you are present.
```text
Hey team, I'm here. Let's start by reviewing the open issues in the issue tracker.
```

---

## 2. Emergency Procedures: When Things Go Haywire

If agents get stuck in a loop, start hallucinating, or if you just need to abort the current operations, use the emergency stop script.

### The Kill Switch
Run the following command from the project root. It will instantly kill all agent runner processes and wipe all temporary state (locks, IRC logs, and shared files from `/tmp`).

```bash
./scripts/stop-swarm.sh
```

### Investigating Failures
If an agent is failing silently or acting erratically, check its runner log:
```bash
tail -f /tmp/swarm-logs/runner-<agent-name>.log
```
*These logs contain detailed invocation history, context sizes, and any exceptions thrown by the runner daemon.*

### Common Invocation Issues
If an agent is connected to IRC but not responding to mentions, check the `command` in `swarm.toml`:
*   **Missing Context Flag:** Most agents require a specific flag (like `-p` or `--prompt`) to accept context from the runner. Without it, the agent might wait for interactive input and time out.
*   **Non-Interactive Mode:** Ensure the agent is running with non-interactive flags (e.g., `-y` or `--yes`) to prevent it from hanging on confirmation prompts.
*   **Path Issues:** The runner executes from the project root. Ensure the agent CLI is in the system PATH or provide an absolute path in `swarm.toml`.

### Partial Recovery
If only one agent is stuck, you can restart just that agent:
```bash
pkill -f "runner.py <agent-name>"
# runner.sh will automatically restart it within a few seconds
```

---

## 3. Best Practices for Operators

*   **Be Explicit:** Agents are stateless between invocations (beyond their IRC history). When giving complex instructions, clearly state who should do what.
    *   *Bad:* `Someone fix the tests.`
    *   *Good:* `@claude please investigate the failing tests in src/auth.py. @gemini review Claude's PR when it's ready.`
*   **Use Overrides Judiciously:** The runner supports human override commands.
    *   `@<agent> STOP` — Immediately pause an agent from processing messages.
    *   `@<agent> RESUME` — Unpause the agent.
    *   `FREEZE` — Tell all agents to stop pushing code changes (they can still discuss).
*   **Encourage Shared Files:** For large diffs, architecture plans, or error logs, tell agents to use the shared workspace (`/tmp/swarm-share/`) instead of pasting hundreds of lines into IRC.
*   **Watch the Heartbeats:** Agents periodically emit a `HEARTBEAT` message. If you haven't seen one from an agent in a while, check its logs; it might have crashed or hung during an LLM invocation.
*   **Force Handoffs:** If an agent is struggling with a task outside its primary skillset (e.g., Codex struggling with design), explicitly direct them to hand it off: `@codex HANDOFF this task to @claude, provide your current diff in a shared file.`

---

## 4. Monitoring and Observability

Maintaining visibility into the swarm's activity is crucial for a smooth coordination experience. Use these tools and techniques to monitor the health and progress of your agents.

### IRC Heartbeats
Every agent is configured to send a `STATUS — HEARTBEAT` message periodically (default: 5 minutes, see `swarm.toml`). If an agent stops sending heartbeats, it may have crashed or is stuck in a long-running task.

### Per-Agent Logs
The runner daemon maintains a separate log file for each agent in the `/tmp/swarm-logs/` directory. These logs capture the exact command issued to the agent, the context provided, and its full response before it's posted to IRC.
```bash
# Example: Follow Gemini's activity
tail -f /tmp/swarm-logs/runner-gemini.log
```

### Shared Artifacts
Monitor the `/tmp/swarm-share/` directory for any large artifacts, design documents, or logs that agents have shared. This is the "brain" of the swarm where persistent cross-agent context lives.
```bash
ls -lrt /tmp/swarm-share/
```

### IRC History
If you join a session late, you can read the per-agent IRC receive logs to catch up on what they've seen:
```bash
# Read the last 100 messages seen by Claude
tail -n 100 /tmp/irc-log-claude.txt
```

### Resource Usage
While the runner manages agent processes, keep an eye on your system's overall resource usage. Many agents running in parallel can be CPU and memory intensive, especially if they are running local models or complex test suites.

---

## 5. Quick Reference Cheat Sheet

| Task | Command |
| :--- | :--- |
| **Start Server** | `nix run .` (or `scripts/start-server.sh`) |
| **Start Agent** | `./scripts/runner.sh <nick>` |
| **Join as Human** | `nix run .#chat` (or `irssi -c localhost -n <name>`) |
| **Stop All** | `./scripts/stop-swarm.sh` |
| **Agent Logs** | `tail -f /tmp/swarm-logs/runner-<nick>.log` |
| **IRC History** | `tail -f /tmp/irc-log-<nick>.txt` |
| **Pause Agent** | `@<nick> STOP` (on IRC) |
| **Resume Agent** | `@<nick> RESUME` (on IRC) |
| **Freeze Code** | `FREEZE` (on IRC) |
| **Unfreeze Code** | `UNFREEZE` (on IRC) |
| **Shared Files** | `/tmp/swarm-share/` |
