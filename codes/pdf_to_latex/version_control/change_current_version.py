#!/usr/bin/env python3
"""
Change the current active version in the version control system.

Usage:
    python change_current_version.py --name <version_name>

Arguments:
    --name: (Required) Name of the version to set as current

Note: Cannot set deleted versions as current.
"""
import argparse
import sys
from version_history import (
    load_version_history,
    save_version_history,
    find_version_by_name,
    get_current_version
)

def change_current_version(name: str) -> None:
    """Change the current version to the specified version."""
    
    # Load existing versions
    versions = load_version_history()
    
    # Find the target version
    target_version = find_version_by_name(versions, name)
    
    if not target_version:
        print(f"✗ Error: Version '{name}' not found")
        print("  Cannot change to a non-existent version")
        sys.exit(1)
    
    # Check if the version is deleted
    if target_version.get("is_deleted", False):
        print(f"✗ Error: Version '{name}' is deleted")
        print("  Cannot set a deleted version as current")
        sys.exit(1)
    
    # Check if already current
    if target_version.get("is_current", False):
        print(f"⚠ Version '{name}' is already the current version")
        sys.exit(0)
    
    # Get the previously current version for reporting
    previous_current = get_current_version(versions)
    
    # Unset all current flags
    for version in versions:
        version["is_current"] = False
    
    # Set the target version as current
    target_version["is_current"] = True
    
    # Save updated history
    save_version_history(versions)
    
    # Print success message
    print(f"✓ Changed current version to '{name}'")
    if previous_current:
        print(f"  Previous version: '{previous_current['name']}'")

def main():
    parser = argparse.ArgumentParser(
        description="Change the current active version",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--name",
        required=True,
        help="Name of the version to set as current (required)"
    )
    
    args = parser.parse_args()
    
    try:
        change_current_version(args.name)
    except KeyboardInterrupt:
        print("\n✗ Operation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()