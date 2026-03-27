#!/usr/bin/env python3
"""
Miniswarm Status Dashboard

A simple CLI dashboard to monitor the status of the swarm.
Reads from swarm.toml and the runner logs in /tmp/swarm-logs/.
"""

import os
import re
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("/tmp/swarm-logs")
SHARE_DIR = Path("/tmp/swarm-share")

def get_agents():
    """Simple parser for swarm.toml to get agent names."""
    agents = []
    toml_path = Path("swarm.toml")
    if not toml_path.exists():
        return agents
    
    with open(toml_path) as f:
        for line in f:
            m = re.match(r'^\[agent\.(\w+)\]', line)
            if m:
                agents.append(m.group(1))
    return agents

def get_last_log_line(agent):
    log_file = LOG_DIR / f"runner-{agent}.log"
    if not log_file.exists():
        return "No log found"
    
    try:
        with open(log_file, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            # Read last 1024 bytes
            f.seek(max(0, size - 1024))
            lines = f.read().decode("utf-8", errors="replace").strip().split("\n")
            if lines:
                return lines[-1]
    except Exception as e:
        return f"Error reading log: {e}"
    return "Empty log"

def main():
    print(f"=== Miniswarm Status Dashboard ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    print(f"{'AGENT':<12} | {'STATUS / LAST ACTIVITY'}")
    print("-" * 60)
    
    agents = get_agents()
    if not agents:
        print("No agents found in swarm.toml")
        return

    for agent in agents:
        last_line = get_last_log_line(agent)
        # Extract timestamp and message
        # Format: [HH:MM:SS] Message
        m = re.match(r'^\[(\d{2}:\d{2}:\d{2})\]\s+(.*)$', last_line)
        if m:
            time_str, msg = m.group(1), m.group(2)
            # Shorten message if too long
            if len(msg) > 60:
                msg = msg[:57] + "..."
            print(f"{agent:<12} | [{time_str}] {msg}")
        else:
            print(f"{agent:<12} | {last_line}")

    print("-" * 60)
    # List shared artifacts
    if SHARE_DIR.exists():
        artifacts = list(SHARE_DIR.glob("*"))
        if artifacts:
            print(f"Shared artifacts ({len(artifacts)}):")
            # Sort by newest
            artifacts.sort(key=os.path.getmtime, reverse=True)
            for art in artifacts[:5]:
                mtime = datetime.fromtimestamp(os.path.getmtime(art)).strftime("%H:%M:%S")
                print(f"  [{mtime}] {art.name}")
            if len(artifacts) > 5:
                print(f"  ... and {len(artifacts) - 5} more")
    else:
        print("No shared artifacts found.")

if __name__ == "__main__":
    main()
