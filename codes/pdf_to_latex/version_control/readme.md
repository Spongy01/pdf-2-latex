# Version Control System

A lightweight file version control system that tracks versions through JSON-based history.

## 📁 Project Structure

```
version_control/
├── version_history.py        # Core module (shared functions)
├── create_version.py          # Create new versions
├── delete_version.py          # Delete versions
├── change_current_version.py  # Switch active version
├── list_versions.py           # List all versions (utility)
└── version_history.json       # Auto-generated version database
```

## 🚀 Setup

1. Create the `version_control` directory if it doesn't exist
2. Place all Python files in the directory
3. The system will auto-create `version_history.json` with the root version "original" on first run

## 📖 Usage

### Create a New Version

```bash
# Create and set as current (default behavior)
python version_control/create_version.py --name "v1.0.0"

# Create with description
python version_control/create_version.py --name "v1.0.0" --description "Initial release"

# Create without setting as current
python version_control/create_version.py --name "v1.1.0" --no-set-current

# Create with description and set as current
python version_control/create_version.py --name "v2.0.0" --set-current --description "Major update"
```

### Delete a Version

```bash
# Delete a version (will auto-set latest undeleted as current if needed)
python version_control/delete_version.py --name "v1.0.0"
```

**Important Notes:**

- Root versions (like "original") cannot be deleted
- If deleting the current version, the latest undeleted version becomes current
- Deleted versions remain in history but are marked as deleted

### Change Current Version

```bash
# Switch to a different version
python version_control/change_current_version.py --name "v1.0.0"
```

**Important Notes:**

- Cannot set deleted versions as current
- Cannot set non-existent versions as current

### List All Versions

```bash
# List active versions only
python version_control/list_versions.py

# List all versions including deleted
python version_control/list_versions.py --all

# Show only current version
python version_control/list_versions.py --current-only
```

## 📊 Version History Structure

Each version in `version_history.json` has the following fields:

```json
{
  "name": "v1.0.0",
  "short_name": "v1.0.0",
  "created_at": "2025-10-07T14:30:00.123456",
  "is_current": true,
  "is_deleted": false,
  "description": "Initial release",
  "is_root": false
}
```

### Field Descriptions

- **name**: Full version name (required, unique)
- **short_name**: Optional short name (defaults to name)
- **created_at**: ISO format timestamp of creation
- **is_current**: Whether this is the active version
- **is_deleted**: Whether this version has been deleted
- **description**: Optional description of the version
- **is_root**: If true, cannot be deleted (e.g., "original")

## 🔒 Root Version

The system always maintains a root version called **"original"** (short name: "orig") that:

- Is created automatically on first run
- Cannot be deleted
- Has `is_root: true`
- Serves as the foundation version

## ✨ Features

- **Automatic Initialization**: Creates root version automatically
- **Safe Deletion**: Prevents deletion of root versions
- **Smart Current Switching**: Automatically handles current version transitions
- **Error Handling**: Comprehensive validation and error messages
- **History Preservation**: Deleted versions remain in history
- **Collision Detection**: Prevents duplicate version names
- **Clean CLI**: User-friendly command-line interface

## 🛡️ Error Handling

The system handles various edge cases:

- Missing or corrupted `version_history.json` → Auto-recreates with root version
- Duplicate version names → Error with clear message
- Deleting non-existent versions → Error message
- Deleting root versions → Protected, shows error
- Setting deleted versions as current → Prevented with error
- Invalid version names → Validation with helpful message

## 🎯 Best Practices

1. Use semantic versioning (e.g., v1.0.0, v1.1.0, v2.0.0)
2. Always include descriptions for major versions
3. Use the list command to review versions before deleting
4. Don't manually edit `version_history.json` (use the provided scripts)
5. Keep the root version "original" intact

## 🔧 Advanced Usage

### Programmatic Access

You can import and use the core functions in your own scripts:

```python
from version_control.version_history import (
    load_version_history,
    save_version_history,
    find_version_by_name,
    get_current_version
)

# Load all versions
versions = load_version_history()

# Find a specific version
version = find_version_by_name(versions, "v1.0.0")

# Get current version
current = get_current_version(versions)
```

## 📝 Example Workflow

```bash
# Initialize (automatic on first command)
python version_control/create_version.py --name "dev-branch" --description "Development version"

# Create release versions
python version_control/create_version.py --name "v1.0.0" --description "First stable release"
python version_control/create_version.py --name "v1.1.0" --description "Bug fixes"
python version_control/create_version.py --name "v2.0.0" --description "Major update"

# List all versions
python version_control/list_versions.py

# Switch to previous version
python version_control/change_current_version.py --name "v1.1.0"

# Delete old dev branch
python version_control/delete_version.py --name "dev-branch"

# View final state
python version_control/list_versions.py --all
```

## 🐛 Troubleshooting

**Issue**: `ModuleNotFoundError: No module named 'version_history'`

- **Solution**: Make sure you're running commands from the parent directory of `version_control/` or add the directory to your Python path

**Issue**: "Version already exists" error

- **Solution**: Use a different version name or delete the existing version first

**Issue**: Cannot delete a version

- **Solution**: Check if it's the root version ("original") which is protected

**Issue**: `version_history.json` is corrupted

- **Solution**: The system will auto-recreate it with the root version. You'll lose other versions, so keep backups!

## 📄 License

Free to use and modify for your projects.
