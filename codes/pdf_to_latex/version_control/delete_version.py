#!/usr/bin/env python3
"""
Delete a version from the version control system.

Usage:
    python delete_version.py --name <version_name>

Arguments:
    --name: (Required) Name of the version to delete

Note: Root versions (is_root=True) cannot be deleted.
If the deleted version is current, the latest undeleted version becomes current.
"""
import argparse
import sys
from version_history import (
    load_version_history,
    save_version_history,
    find_version_by_name,
    get_latest_undeleted_version
)

def delete_version(name: str) -> None:
    """Delete a version by name."""
    
    # Load existing versions
    versions = load_version_history()
    
    # Find the version to delete
    version_to_delete = find_version_by_name(versions, name)
    
    if not version_to_delete:
        print(f"✗ Error: Version '{name}' not found")
        sys.exit(1)
    
    # Check if already deleted
    if version_to_delete.get("is_deleted", False):
        print(f"⚠ Warning: Version '{name}' is already deleted")
        sys.exit(0)
    
    # Check if it's a root version
    if version_to_delete.get("is_root", False):
        print(f"✗ Error: Cannot delete root version '{name}'")
        print("  Root versions are protected and cannot be deleted")
        sys.exit(1)
    
    # Mark as deleted
    was_current = version_to_delete.get("is_current", False)
    version_to_delete["is_deleted"] = True
    version_to_delete["is_current"] = False
    
    # If this was the current version, set the latest undeleted as current
    if was_current:
        # Temporarily save to exclude the newly deleted version
        save_version_history(versions)
        
        latest_undeleted = get_latest_undeleted_version(versions)
        if latest_undeleted:
            # Unset all current flags first
            for v in versions:
                v["is_current"] = False
            # Set the latest undeleted as current
            latest_undeleted["is_current"] = True
            print(f"✓ Deleted version '{name}' (was current)")
            print(f"  New current version: '{latest_undeleted['name']}'")
        else:
            print(f"✓ Deleted version '{name}' (was current)")
            print(f"  ⚠ Warning: No undeleted versions available to set as current")
    else:
        print(f"✓ Deleted version '{name}'")
    
    # Save updated history
    save_version_history(versions)

def main():
    parser = argparse.ArgumentParser(
        description="Delete a version from the version control system",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--name",
        required=True,
        help="Name of the version to delete (required)"
    )
    
    args = parser.parse_args()
    
    try:
        delete_version(args.name)
    except KeyboardInterrupt:
        print("\n✗ Operation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()