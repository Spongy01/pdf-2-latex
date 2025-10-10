"""
Core module for version control system.
Handles version history JSON operations and validation.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

VERSION_HISTORY_FILE = "version_control/version_history.json"


def get_root_version() -> Dict:
    """Return the root version that cannot be deleted."""
    return {
        "name": "original",
        "short_name": "orig",
        "created_at": datetime.now().isoformat(),
        "is_current": True,
        "is_deleted": False,
        "description": "Root version - cannot be deleted",
        "is_root": True,
    }


def ensure_version_history() -> None:
    """Ensure version_history.json exists with root version."""
    os.makedirs(os.path.dirname(VERSION_HISTORY_FILE), exist_ok=True)

    if not os.path.exists(VERSION_HISTORY_FILE):
        root_version = get_root_version()
        save_version_history([root_version])
        print(f"✓ Created version_history.json with root version 'original'")


def load_version_history() -> List[Dict]:
    """Load version history from JSON file."""
    ensure_version_history()

    try:
        with open(VERSION_HISTORY_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠ Corrupted version_history.json, recreating with root version")
        root_version = get_root_version()
        save_version_history([root_version])
        return [root_version]


def save_version_history(versions: List[Dict]) -> None:
    """Save version history to JSON file."""
    with open(VERSION_HISTORY_FILE, "w") as f:
        json.dump(versions, f, indent=2)


def find_version_by_name(versions: List[Dict], name: str) -> Optional[Dict]:
    """Find a version by name."""
    for version in versions:
        if version["name"] == name:
            return version
    return None


def get_current_version(versions: List[Dict]) -> Optional[Dict]:
    """Get the currently active version."""
    for version in versions:
        if version.get("is_current", False) and not version.get("is_deleted", False):
            return version
    return None


def get_latest_undeleted_version(versions: List[Dict]) -> Optional[Dict]:
    """Get the latest undeleted version."""
    for version in reversed(versions):
        if not version.get("is_deleted", False):
            return version
    return None


def validate_version_name(name: str) -> bool:
    """Validate version name format."""
    if not name or not name.strip():
        return False
    if len(name) > 100:
        return False
    # Allow alphanumeric, hyphens, underscores, and spaces
    return all(c.isalnum() or c in ["-", "_", " ", "."] for c in name)
