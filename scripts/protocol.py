import re
from typing import Dict, Any, List, Optional

def parse_message(line: str) -> Dict[str, Any]:
    """
    Parses a swarm message into its components.
    Expected format: PREFIX [@mentions...] [scope:...] [files:...] — <body>
    """
    result = {
        "prefix": "",
        "mentions": [],
        "scope": "",
        "files": [],
        "body": ""
    }
    
    # Check for prefix
    # Matches words like TASK, CLAIM, PASS, STATUS, etc.
    prefix_match = re.match(r'^([A-Z]+)(?:\s+|$)', line)
    if not prefix_match:
        return result
        
    result["prefix"] = prefix_match.group(1)
    
    # Extract body if there's a dash separator
    parts = line.split("—", 1)
    metadata_part = parts[0].strip()
    if len(parts) > 1:
        result["body"] = parts[1].strip()
        
    # Extract mentions
    mentions = re.findall(r'@([a-zA-Z0-9_-]+)', metadata_part)
    result["mentions"] = mentions
    
    # Extract scope
    scope_match = re.search(r'scope:\[?([^\s\]]+)\]?', metadata_part)
    if scope_match:
        result["scope"] = scope_match.group(1)
        
    # Extract files
    # Match files: followed by either [file1, file2] or file1,file2
    files_match = re.search(r'files:(?:\[([^\]]+)\]|([^\s]+))', metadata_part)
    if files_match:
        files_str = files_match.group(1) if files_match.group(1) else files_match.group(2)
        # Split by comma and strip spaces
        result["files"] = [f.strip() for f in files_str.split(",") if f.strip()]
        
    return result

def format_task(scope: str, files: List[str], body: str) -> str:
    """
    Formats a TASK message.
    """
    files_str = ",".join(files)
    return f"TASK @all scope:{scope} files:{files_str} — {body}"
