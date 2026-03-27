#!/usr/bin/env python3
"""
Miniswarm Agent Runner

A lightweight daemon that bridges a request-response AI coding agent
(Claude, Gemini, Codex, etc.) into a persistent IRC-based swarm.

Usage:
    python3 scripts/runner.py claude
    python3 scripts/runner.py gemini
    python3 scripts/runner.py codex

The runner:
  - Maintains a persistent IRC connection
  - Watches for messages relevant to its agent
  - Invokes the agent CLI with gathered context
  - Posts responses back to IRC
  - Enforces guardrails (rate limits, loop detection, file locks, human overrides)
"""

import argparse
import hashlib
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import threading
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_config(config_path="swarm.toml"):
    """Load swarm.toml. We parse a minimal TOML subset to avoid dependencies."""
    config = {
        "server": {"host": "127.0.0.1", "port": 6667, "channel": "#swarm"},
        "defaults": {
            "max_invocations_per_hour": 30,
            "min_invoke_interval_seconds": 10,
            "max_messages_per_minute": 10,
            "loop_detection_threshold": 3,
            "heartbeat_interval_seconds": 300,
            "context_max_tokens": 4000,
            "file_lock_ttl_seconds": 600,
        },
        "agents": {},
        "humans": {"can_merge": True, "can_delete": True, "override_authority": True},
    }

    path = Path(config_path)
    if not path.exists():
        # Walk up to find it
        for parent in Path.cwd().parents:
            candidate = parent / config_path
            if candidate.exists():
                path = candidate
                break

    if path.exists():
        try:
            # Try tomllib (Python 3.11+)
            import tomllib
            with open(path, "rb") as f:
                raw = tomllib.load(f)
        except ImportError:
            try:
                import tomli as tomllib
                with open(path, "rb") as f:
                    raw = tomllib.load(f)
            except ImportError:
                # Fall back to manual parsing
                raw = _parse_toml_minimal(path)

        config["server"].update(raw.get("server", {}))
        config["defaults"].update(raw.get("defaults", {}))
        config["humans"].update(raw.get("humans", {}))
        # Flatten agent.X tables
        for key, val in raw.items():
            if key.startswith("agent."):
                agent_name = key.split(".", 1)[1]
                config["agents"][agent_name] = val
            elif key == "agent" and isinstance(val, dict):
                for agent_name, agent_conf in val.items():
                    config["agents"][agent_name] = agent_conf

    return config


def _parse_toml_minimal(path):
    """Bare-bones TOML parser for flat key-value sections. No nested tables."""
    result = {}
    current_section = None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^\[(.+)\]$', line)
            if m:
                current_section = m.group(1)
                # Handle dotted sections like [agent.claude]
                parts = current_section.split(".", 1)
                if len(parts) == 2:
                    result.setdefault(parts[0], {})[parts[1]] = {}
                else:
                    result[current_section] = {}
                continue
            m = re.match(r'^(\w+)\s*=\s*(.+)$', line)
            if m and current_section:
                key, val = m.group(1), m.group(2).strip()
                # Parse value
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                elif val.startswith('[') and val.endswith(']'):
                    val = [v.strip().strip('"') for v in val[1:-1].split(",")]
                elif val in ("true", "false"):
                    val = val == "true"
                elif '.' in val:
                    try:
                        val = float(val)
                    except ValueError:
                        pass
                else:
                    try:
                        val = int(val)
                    except ValueError:
                        pass
                # Store in correct nesting
                parts = current_section.split(".", 1)
                if len(parts) == 2:
                    result.setdefault(parts[0], {})[parts[1]][key] = val
                else:
                    result[current_section][key] = val
    return result


# ---------------------------------------------------------------------------
# IRC Connection
# ---------------------------------------------------------------------------

class IRCConnection:
    """Minimal IRC client over raw TCP."""

    def __init__(self, host, port, nick, channel):
        self.host = host
        self.port = port
        self.nick = nick
        self.channel = channel
        self.sock = None
        self.buffer = ""
        self.connected = False
        self.message_log = deque(maxlen=500)
        self._lock = threading.Lock()

    def connect(self):
        """Connect to the IRC server and join the channel."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(300)  # 5 min timeout for reads
        self.sock.connect((self.host, self.port))
        self._send(f"NICK {self.nick}")
        self._send(f"USER {self.nick} 0 * :{self.nick} agent (miniswarm runner)")
        time.sleep(1)
        self._send(f"JOIN {self.channel}")
        self.connected = True
        log(f"Connected to {self.host}:{self.port} as {self.nick}")

    def reconnect(self, max_retries=10):
        """Reconnect with exponential backoff."""
        self.connected = False
        for attempt in range(max_retries):
            delay = min(2 ** attempt, 60)
            log(f"Reconnecting in {delay}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(delay)
            try:
                if self.sock:
                    self.sock.close()
                self.connect()
                return True
            except (socket.error, OSError) as e:
                log(f"Reconnect failed: {e}")
        log("FATAL: Could not reconnect after max retries.")
        return False

    def _send(self, msg):
        """Send a raw IRC line."""
        with self._lock:
            self.sock.sendall(f"{msg}\r\n".encode("utf-8"))

    def send_message(self, text):
        """Send a PRIVMSG to the channel. Splits long messages."""
        # IRC max line is ~512 bytes; keep messages under 400 chars
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Split long lines
            while len(line) > 400:
                self._send(f"PRIVMSG {self.channel} :{line[:400]}")
                line = line[400:]
                time.sleep(0.3)
            self._send(f"PRIVMSG {self.channel} :{line}")
            time.sleep(0.3)

    def read_messages(self):
        """Read and parse pending IRC messages. Returns list of parsed messages."""
        messages = []
        try:
            data = self.sock.recv(4096).decode("utf-8", errors="replace")
            if not data:
                raise ConnectionError("Server closed connection")
            self.buffer += data
        except socket.timeout:
            return messages
        except (ConnectionError, OSError):
            self.connected = False
            return messages

        while "\r\n" in self.buffer:
            line, self.buffer = self.buffer.split("\r\n", 1)
            parsed = self._parse_line(line)
            if parsed:
                if parsed["type"] == "PING":
                    self._send(f"PONG {parsed['content']}")
                else:
                    self.message_log.append(parsed)
                    messages.append(parsed)
        return messages

    def _parse_line(self, line):
        """Parse a raw IRC line into a structured dict."""
        if line.startswith("PING"):
            return {"type": "PING", "content": line[5:]}

        m = re.match(r'^:(\S+) PRIVMSG (\S+) :(.+)$', line)
        if m:
            sender_full = m.group(1)
            sender = sender_full.split("!")[0]
            target = m.group(2)
            content = m.group(3)
            return {
                "type": "PRIVMSG",
                "sender": sender,
                "target": target,
                "content": content,
                "raw": line,
                "time": datetime.now().isoformat(),
            }

        # JOIN/PART/QUIT for presence tracking
        m = re.match(r'^:(\S+) (JOIN|PART|QUIT)', line)
        if m:
            sender = m.group(1).split("!")[0]
            action = m.group(2)
            return {
                "type": action,
                "sender": sender,
                "content": "",
                "raw": line,
                "time": datetime.now().isoformat(),
            }

        return None


# ---------------------------------------------------------------------------
# File Locking (TTL-based leases)
# ---------------------------------------------------------------------------

LOCK_DIR = Path("/tmp/swarm-locks")


def acquire_lock(filepath, owner, ttl_seconds=600):
    """Acquire a TTL-based file lease. Returns True if acquired."""
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_file = LOCK_DIR / hashlib.sha256(filepath.encode()).hexdigest()

    # Check existing lock
    if lock_file.exists():
        try:
            lock_data = json.loads(lock_file.read_text())
            expires = datetime.fromisoformat(lock_data["expires"])
            if expires > datetime.now() and lock_data["owner"] != owner:
                return False  # Locked by someone else
        except (json.JSONDecodeError, KeyError):
            pass  # Stale/corrupt lock, overwrite

    lock_data = {
        "path": filepath,
        "owner": owner,
        "acquired": datetime.now().isoformat(),
        "expires": (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat(),
    }
    lock_file.write_text(json.dumps(lock_data))
    return True


def release_lock(filepath, owner):
    """Release a file lease."""
    lock_file = LOCK_DIR / hashlib.sha256(filepath.encode()).hexdigest()
    if lock_file.exists():
        try:
            lock_data = json.loads(lock_file.read_text())
            if lock_data.get("owner") == owner:
                lock_file.unlink()
        except (json.JSONDecodeError, KeyError):
            lock_file.unlink()


def check_lock(filepath):
    """Check who holds a lock on a file. Returns owner or None."""
    lock_file = LOCK_DIR / hashlib.sha256(filepath.encode()).hexdigest()
    if lock_file.exists():
        try:
            lock_data = json.loads(lock_file.read_text())
            expires = datetime.fromisoformat(lock_data["expires"])
            if expires > datetime.now():
                return lock_data.get("owner")
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def release_all_locks(owner):
    """Release all locks held by an owner."""
    if LOCK_DIR.exists():
        for lock_file in LOCK_DIR.iterdir():
            try:
                lock_data = json.loads(lock_file.read_text())
                if lock_data.get("owner") == owner:
                    lock_file.unlink()
            except (json.JSONDecodeError, KeyError):
                pass


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------

class Guardrails:
    """Enforces rate limits, loop detection, and human overrides."""

    def __init__(self, config):
        self.config = config
        self.invocation_times = deque(maxlen=100)
        self.message_times = deque(maxlen=100)
        self.conversation_hashes = deque(maxlen=20)
        self.paused = False
        self.frozen = False  # FREEZE = no code pushes

    def check_rate_limit(self):
        """Returns (allowed, reason)."""
        now = time.time()
        defaults = self.config["defaults"]

        # Check min interval
        if self.invocation_times:
            elapsed = now - self.invocation_times[-1]
            min_interval = defaults["min_invoke_interval_seconds"]
            if elapsed < min_interval:
                return False, f"Rate limit: {min_interval - elapsed:.0f}s cooldown remaining"

        # Check hourly limit
        hour_ago = now - 3600
        recent = sum(1 for t in self.invocation_times if t > hour_ago)
        max_per_hour = defaults["max_invocations_per_hour"]
        if recent >= max_per_hour:
            return False, f"Rate limit: {recent}/{max_per_hour} invocations this hour"

        return True, ""

    def check_message_rate(self):
        """Check if we can send another IRC message."""
        now = time.time()
        minute_ago = now - 60
        recent = sum(1 for t in self.message_times if t > minute_ago)
        max_per_min = self.config["defaults"]["max_messages_per_minute"]
        return recent < max_per_min

    def record_invocation(self):
        self.invocation_times.append(time.time())

    def record_message(self):
        self.message_times.append(time.time())

    def check_loop(self, recent_messages, my_nick):
        """Detect ping-pong loops. Returns (is_loop, description)."""
        threshold = self.config["defaults"]["loop_detection_threshold"]
        # Look at last N*2 messages for back-and-forth patterns
        window = list(recent_messages)[-threshold * 2:]
        if len(window) < threshold * 2:
            return False, ""

        # Check for A->B->A->B pattern
        senders = [m["sender"] for m in window if m["type"] == "PRIVMSG"]
        if len(senders) >= threshold * 2:
            pairs = set()
            for i in range(len(senders) - 1):
                if senders[i] != senders[i + 1]:
                    pairs.add((senders[i], senders[i + 1]))
            # If only one pair is going back and forth
            if len(pairs) <= 2 and my_nick in {s for pair in pairs for s in pair}:
                other = None
                for pair in pairs:
                    for s in pair:
                        if s != my_nick:
                            other = s
                if other:
                    # Check content similarity (are they repeating?)
                    my_msgs = [m["content"] for m in window if m["sender"] == my_nick]
                    hashes = [hashlib.md5(m.encode()).hexdigest()[:8] for m in my_msgs]
                    if len(set(hashes)) < len(hashes):
                        return True, f"Ping-pong loop detected with @{other}"

        return False, ""

    def handle_override(self, message, my_nick):
        """Process human override commands. Returns True if handled."""
        content = message["content"].strip()

        # @agent STOP or @all STOP
        if re.match(rf'@({my_nick}|all)\s+STOP\b', content, re.IGNORECASE):
            self.paused = True
            return True

        if re.match(rf'@({my_nick}|all)\s+RESUME\b', content, re.IGNORECASE):
            self.paused = False
            return True

        if re.match(r'FREEZE\b', content, re.IGNORECASE):
            self.frozen = True
            return True

        if re.match(r'UNFREEZE\b', content, re.IGNORECASE):
            self.frozen = False
            return True

        return False


# ---------------------------------------------------------------------------
# Context Builder
# ---------------------------------------------------------------------------

def build_context(agent_config, recent_messages, trigger_message, project_root):
    """Build a structured context prompt for the agent invocation."""
    nick = agent_config["nick"]
    role = agent_config.get("role", "General-purpose coding agent")

    sections = []

    # 1. Identity and role
    sections.append(f"""## Your Identity
You are {nick}, an AI coding agent in a multi-agent swarm.
Role: {role}
Project: {project_root}
Time: {datetime.now().isoformat()}

You are being invoked by your runner because a message on IRC needs your attention.
After you complete your work, your response will be posted back to IRC #swarm.
Keep your response concise and actionable. Use the message prefixes from AGENTS.md.""")

    # 2. The triggering message (highest priority)
    sections.append(f"""## Message Requiring Your Attention
From @{trigger_message['sender']} at {trigger_message.get('time', 'unknown')}:
{trigger_message['content']}""")

    # 3. Recent conversation (for context)
    relevant = [m for m in recent_messages
                if m["type"] == "PRIVMSG"
                and m["raw"] != trigger_message.get("raw")][-15:]
    if relevant:
        lines = []
        for m in relevant:
            lines.append(f"  @{m['sender']}: {m['content']}")
        sections.append(f"""## Recent IRC Context (last {len(relevant)} messages)
{chr(10).join(lines)}""")

    # 4. Git state
    try:
        status = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, timeout=5, cwd=project_root
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5, cwd=project_root
        ).stdout.strip()
        if status or branch:
            sections.append(f"""## Git State
Branch: {branch}
{('Changes:' + chr(10) + status) if status else 'Working tree clean.'}""")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # 5. Instructions
    sections.append("""## Instructions
- Read AGENTS.md if you need protocol details.
- If you make code changes, summarize them in your response.
- If you need input from another agent or human, say so with QUESTION @nick.
- If you're handing off work, use HANDOFF @nick with commit hash and file paths.
- If you're done with a task, say DONE.
- Keep your IRC response under 5 messages. Use /tmp/swarm-share/ for long content.""")

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Agent Invocation
# ---------------------------------------------------------------------------

def invoke_agent(agent_config, context, project_root, timeout=300):
    """Invoke the agent CLI and return its response."""
    command = agent_config["command"]
    if isinstance(command, str):
        command = command.split()

    # Build the full command
    full_command = command + [context]

    log(f"Invoking: {command[0]} (context: {len(context)} chars)")

    try:
        result = subprocess.run(
            full_command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=project_root,
        )
        output = result.stdout.strip()
        if not output and result.stderr:
            output = result.stderr.strip()
        return output
    except subprocess.TimeoutExpired:
        return "BLOCKER — Agent invocation timed out."
    except FileNotFoundError:
        return f"BLOCKER — Agent CLI not found: {command[0]}"
    except Exception as e:
        return f"BLOCKER — Agent invocation failed: {e}"


def format_response_for_irc(raw_response, max_lines=8):
    """Clean up agent output for IRC posting."""
    lines = raw_response.strip().split("\n")

    # Filter out noise (blank lines, tool output, etc.)
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip common CLI noise and agent inner monologues
        if any(line.startswith(p) for p in ["$", ">>>", "---", "===", "```", "I will "]):
            continue
        cleaned.append(line)

    if not cleaned:
        return ["STATUS — Task completed (no output)."]

    if len(cleaned) <= max_lines:
        return cleaned

    # Too long — save to shared workspace and summarize
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    share_path = f"/tmp/swarm-share/response-{timestamp}.txt"
    Path(share_path).write_text(raw_response)
    return cleaned[:max_lines - 1] + [f"(full response: {share_path})"]


# ---------------------------------------------------------------------------
# Message Relevance
# ---------------------------------------------------------------------------

def is_relevant(message, my_nick, config):
    """Determine if a message needs this agent's attention."""
    if message["type"] != "PRIVMSG":
        return False
    if message["sender"] == my_nick:
        return False

    content = message["content"]

    # 1. Lifecycle guard (Early return to avoid noise)
    # Don't respond to lifecycle messages, even if they contain mentions.
    lifecycle_prefixes = ("ACK", "BYE", "HELLO", "HEARTBEAT", "DONE", "STATUS")
    if content.startswith(lifecycle_prefixes):
        return False

    # 2. Direct @mention or @all (Highest priority)
    if f"@{my_nick.lower()}" in content.lower() or "@all" in content.lower():
        return True

    # 3. Directed prefixes with my nick
    directed_prefixes = ["HANDOFF", "QUESTION", "REVIEW", "TASK"]
    for prefix in directed_prefixes:
        if content.startswith(prefix) and f"@{my_nick}" in content:
            return True

    # 4. Unaddressed human messages — treat as @all
    # If a human posts without any @mention, all agents should hear it
    if is_human_message(message, config):
        agent_nicks = {a.get("nick", name) for name, a in config["agents"].items()}
        mentions_any_agent = any(f"@{nick}" in content.lower() for nick in agent_nicks)
        if not mentions_any_agent:
            return True

    return False


def is_human_message(message, config):
    """Check if a message is from a human (not another agent)."""
    sender = message["sender"]
    agent_nicks = {a.get("nick", name) for name, a in config["agents"].items()}
    return sender not in agent_nicks


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = Path("/tmp/swarm-logs")


def log(msg):
    """Log to stderr and to the session log file."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, file=sys.stderr)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"runner-{os.getenv('SWARM_NICK', 'unknown')}.log"
    with open(log_file, "a") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------

def run(agent_name, config):
    """Main runner loop."""
    agent_config = config["agents"].get(agent_name)
    if not agent_config:
        log(f"FATAL: No config for agent '{agent_name}'. Check swarm.toml.")
        log(f"Available agents: {list(config['agents'].keys())}")
        sys.exit(1)

    nick = agent_config.get("nick", agent_name)
    os.environ["SWARM_NICK"] = nick

    server = config["server"]
    project_root = str(Path.cwd())

    # Set up IRC
    irc = IRCConnection(server["host"], server["port"], nick, server["channel"])
    guardrails = Guardrails(config)

    # Graceful shutdown
    running = True
    agent_process = None

    def shutdown(signum, frame):
        nonlocal running
        log(f"Received signal {signum}, shutting down...")
        running = False
        if agent_process:
            agent_process.terminate()
        irc.send_message(f"BYE — {nick} runner shutting down.")
        release_all_locks(nick)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Connect
    try:
        irc.connect()
    except (socket.error, OSError) as e:
        log(f"FATAL: Cannot connect to IRC at {server['host']}:{server['port']}: {e}")
        log("Is the IRC server running? Try: nix run .")
        sys.exit(1)

    time.sleep(1)
    irc.send_message(f"HELLO — {nick} runner is online. Role: {agent_config.get('role', 'general')}. Awaiting tasks.")
    log(f"Runner started for {nick}. Listening on {server['channel']}...")

    last_heartbeat = time.time()

    # Main loop
    while running:
        try:
            messages = irc.read_messages()
        except Exception as e:
            log(f"IRC read error: {e}")
            if not irc.reconnect():
                break
            continue

        if not irc.connected:
            if not irc.reconnect():
                break
            continue

        for msg in messages:
            # Log everything
            if msg["type"] == "PRIVMSG":
                log(f"<{msg['sender']}> {msg['content']}")

            # Check for human overrides first
            if is_human_message(msg, config):
                if guardrails.handle_override(msg, nick):
                    state = "PAUSED" if guardrails.paused else "RESUMED"
                    irc.send_message(f"ACK — {nick} is now {state}.")
                    log(f"Override: {state}")
                    continue

            # Skip if paused
            if guardrails.paused:
                if is_relevant(msg, nick, config):
                    irc.send_message(f"STATUS — {nick} is PAUSED. Use @{nick} RESUME to unpause.")
                continue

            # Check relevance
            if not is_relevant(msg, nick, config):
                continue

            log(f"Relevant message from {msg['sender']}: {msg['content']}")

            # Check rate limits
            allowed, reason = guardrails.check_rate_limit()
            if not allowed:
                log(f"Rate limited: {reason}")
                irc.send_message(f"STATUS — {reason}. Will respond shortly.")
                continue

            # Check for loops
            is_loop, loop_desc = guardrails.check_loop(irc.message_log, nick)
            if is_loop:
                log(f"Loop detected: {loop_desc}")
                irc.send_message(f"BLOCKER — {loop_desc}. Pausing for human input.")
                guardrails.paused = True
                continue

            # Build context and invoke agent
            irc.send_message(f"STATUS — Processing message from {msg['sender']}...")
            guardrails.record_invocation()

            context = build_context(
                agent_config,
                list(irc.message_log),
                msg,
                project_root,
            )

            response = invoke_agent(agent_config, context, project_root)

            if response:
                lines = format_response_for_irc(response)
                for line in lines:
                    if guardrails.check_message_rate():
                        irc.send_message(line)
                        guardrails.record_message()
                    else:
                        log("Message rate limit hit, saving remainder to file")
                        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                        share_path = f"/tmp/swarm-share/response-{timestamp}.txt"
                        remaining = lines[lines.index(line):]
                        Path(share_path).write_text("\n".join(remaining))
                        irc.send_message(f"(rate limited — full response: {share_path})")
                        break

        # Heartbeat
        now = time.time()
        heartbeat_interval = config["defaults"]["heartbeat_interval_seconds"]
        if now - last_heartbeat > heartbeat_interval:
            state = "paused" if guardrails.paused else "idle"
            invocations = len(guardrails.invocation_times)
            irc.send_message(f"HEARTBEAT — {nick}: {state} ({invocations} invocations this session)")
            last_heartbeat = now

    # Cleanup
    release_all_locks(nick)
    log("Runner stopped.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Miniswarm Agent Runner")
    parser.add_argument("agent", help="Agent name (must match a key in swarm.toml)")
    parser.add_argument("--config", default="swarm.toml", help="Path to swarm.toml")
    args = parser.parse_args()

    config = load_config(args.config)
    run(args.agent, config)


if __name__ == "__main__":
    main()
