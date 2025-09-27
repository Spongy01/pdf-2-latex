"""
Version Control Module for PDF to LaTeX Conversion Pipeline

This module handles versioning of conversion outputs by:
1. Tracking versions in a version.json file
2. Creating versioned output folders
3. Maintaining conversion history
"""

import os
import json
from datetime import datetime


def get_next_version(book_folder, output_folder):
    """
    Get the next version number for the given book folder.

    Args:
        book_folder (str): Path to the book's main folder

    Returns:
        tuple: (version_number, version_folder_path, is_new_book)
    """
    version_file = os.path.join(book_folder, "version.json")
    if output_folder is None:
        output_folder = os.path.join(book_folder, "outputs")

    # Check if version.json exists
    if os.path.exists(version_file):
        try:
            with open(version_file, "r") as f:
                version_data = json.load(f)

            latest_version = version_data.get("latest_version", 0)
            next_version = latest_version + 1
            is_new_book = False

        except (json.JSONDecodeError, KeyError):
            # If file is corrupted or invalid, start fresh
            next_version = 1
            is_new_book = True

    else:
        # New book, start with version 1
        next_version = 1
        is_new_book = True

    version_folder = os.path.join(output_folder, f"version_{next_version}")

    return next_version, version_folder, is_new_book


def update_version_file(book_folder, version_number, output_folder, file_name):
    """
    Update the version.json file with new version information.

    Args:
        book_folder (str): Path to the book's main folder
        version_number (int): Current version number
        output_folder (str): Path to the version's output folder
        file_name (str): Base filename
    """
    version_file = os.path.join(book_folder, "version.json")
    current_time = datetime.now().isoformat()

    # Load existing data or create new
    if os.path.exists(version_file):
        try:
            with open(version_file, "r") as f:
                version_data = json.load(f)
        except (json.JSONDecodeError, KeyError):
            version_data = {"versions": {}}
    else:
        version_data = {"versions": {}}

    # Update version data
    version_data["latest_version"] = version_number
    version_data["last_updated"] = current_time
    version_data["book_name"] = file_name

    # Add version entry
    version_data["versions"][f"version_{version_number}"] = {
        "created_at": current_time,
        "output_folder": output_folder,
        "version_number": version_number,
    }

    # Save updated data
    with open(version_file, "w") as f:
        json.dump(version_data, f, indent=2)

    print(f"Updated version file: {version_file}")
    print(f"Created version {version_number} at {current_time}")


def get_version_history(book_folder):
    """
    Get the version history for a book.

    Args:
        book_folder (str): Path to the book's main folder

    Returns:
        dict: Version history data
    """
    version_file = os.path.join(book_folder, "version.json")

    if os.path.exists(version_file):
        try:
            with open(version_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError):
            return None

    return None
