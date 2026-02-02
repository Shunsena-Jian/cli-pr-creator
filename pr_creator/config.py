import json
import os
from pathlib import Path
from typing import Any, Dict

CONFIG_FILENAME = ".pr_creator_config.json"

def load_config() -> Dict[str, Any]:
    """
    Load configuration from:
    1. Check current directory
    2. Check user home directory
    3. Return defaults if nothing found
    """
    defaults = {
        "default_target_branch": "main",
        "jira_project_keys": [],
        "reviewer_groups": {},
        "jira_base_url": "https://qualitytrade.atlassian.net/browse/"
    }

    # Search paths: Current dir, Home dir
    search_paths = [
        Path.cwd() / CONFIG_FILENAME,
        Path.home() / CONFIG_FILENAME
    ]

    for path in search_paths:
        if path.exists():
            try:
                with open(path, "r") as f:
                    user_config = json.load(f)
                    defaults.update(user_config)
                    return defaults
            except json.JSONDecodeError:
                print(f"Warning: Failed to parse config file at {path}. Using defaults.")
    
    return defaults
