"""
Create a new version in the version control system.

Usage:
    python create_version.py --name <version_name> [--set-current] [--description <desc>]

Arguments:
    --name: (Required) Name of the new version
    --set-current: (Optional) Set this version as current (default: True)
                   Use --no-set-current to create without setting as current
    --description: (Optional) Description of the version
"""
import argparse
import sys
from datetime import datetime
from version_history import (
    load_version_history,
    save_version_history,
    find_version_by_name,
    validate_version_name
)

def create_version(name: str, set_current: bool = True, description: str = "") -> None:
    """Create a new version."""
    
    # Validate version name
    if not validate_version_name(name):
        print(f"✗ Error: Invalid version name '{name}'")
        print("  Version names must be non-empty, max 100 chars, and contain only")
        print("  alphanumeric characters, hyphens, underscores, spaces, or periods.")
        sys.exit(1)
    
    # Load existing versions
    versions = load_version_history()
    
    # Check if version already exists
    existing = find_version_by_name(versions, name)
    if existing:
        if existing.get("is_deleted", False):
            print(f"✗ Error: Version '{name}' already exists (deleted)")
        else:
            print(f"✗ Error: Version '{name}' already exists")
        sys.exit(1)
    
    # Create new version
    new_version = {
        "name": name,
        "short_name": name,  # Default to same as name
        "created_at": datetime.now().isoformat(),
        "is_current": set_current,
        "is_deleted": False,
        "description": description,
        "is_root": False
    }
    
    # If setting as current, unset all other versions
    if set_current:
        for version in versions:
            version["is_current"] = False
    
    # Add new version to the end
    versions.append(new_version)
    
    # Save updated history
    save_version_history(versions)
    
    # Print success message
    status = "current" if set_current else "inactive"
    print(f"✓ Created version '{name}' ({status})")
    if description:
        print(f"  Description: {description}")

def main():
    parser = argparse.ArgumentParser(
        description="Create a new version in the version control system",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--name",
        required=True,
        help="Name of the new version (required)"
    )
    
    parser.add_argument(
        "--set-current",
        dest="set_current",
        action="store_true",
        default=True,
        help="Set this version as current (default: True)"
    )
    
    parser.add_argument(
        "--no-set-current",
        dest="set_current",
        action="store_false",
        help="Do not set this version as current"
    )
    
    parser.add_argument(
        "--description",
        default="",
        help="Description of the version (optional)"
    )
    
    args = parser.parse_args()
    
    try:
        create_version(args.name, args.set_current, args.description)
    except KeyboardInterrupt:
        print("\n✗ Operation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()