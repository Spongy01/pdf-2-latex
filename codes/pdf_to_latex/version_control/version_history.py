"""
Core module for version control system.
Handles version history JSON operations and validation.
"""

import json
import os
import sys
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
        "description": "Root version - cannot be deleted hello",
        "is_root": True,
    }


def ensure_version_history() -> None:
    """Ensure version_history.json exists with root version."""
    sys.path.append(os.path.dirname(__file__))
    os.makedirs(os.path.dirname(VERSION_HISTORY_FILE), exist_ok=True)

    print("version history file path:", Path(VERSION_HISTORY_FILE).resolve())

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
    sys.path.append(os.path.dirname(__file__))
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


def update_version_usage(current_folder, book_name, version_number):
    """
    Update the version_usage.json file with the last usage information.
    Only keeps the last entry for each book-version combination.

    Args:
        current_folder (str): Path to the book's main folder
        book_name (str): Name of the book
        version_number (int): Version number that was used
    """
    usage_file = os.path.join(current_folder, "version_usage.json")
    current_time = datetime.now().isoformat()

    # Load existing usage data or create new
    if os.path.exists(usage_file):
        try:
            with open(usage_file, "r") as f:
                usage_data = json.load(f)
        except (json.JSONDecodeError, KeyError):
            usage_data = {}
    else:
        usage_data = {}

    # Create unique key for book-version combination
    usage_key = f"{book_name}___{version_number}"

    # Update or create entry (overwrites previous entry for same book-version)
    usage_data[usage_key] = {
        "book_name": book_name,
        "version": version_number,
        "last_used": current_time,
    }

    # Save updated data
    with open(usage_file, "w") as f:
        json.dump(usage_data, f, indent=2)

    print(
        f"Updated version usage: {book_name} version {version_number} at {current_time}"
    )
