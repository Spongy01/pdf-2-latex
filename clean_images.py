#!/usr/bin/env python3
"""
Image Name Cleaner and LaTeX Updater

This script:
1. Cleans up complex image names in a directory (removes prefixes, keeps page numbers)
2. Updates references in a LaTeX file to use the new clean image names

Usage:
    python clean_images.py <images_directory> <tex_file> [--dry-run]
"""

import os
import re
import shutil
import argparse
from pathlib import Path


def clean_image_name(filename):
    """
    Clean up image filename by extracting page number and creating simple name.
    
    Examples:
        '2025_03_17_ca60ec0bfd96dcf8e028g-401.jpg' -> 'image_401.jpg'
        '2025_03_17_ca60ec0bfd96dcf8e028g-401(1).jpg' -> 'image_401_1.jpg'
        '2025_03_17_ca60ec0bfd96dcf8e028g-401(2).jpg' -> 'image_401_2.jpg'
    """
    # Pattern to match the complex filename and extract page number
    pattern = r'.*?-(\d+)(?:\((\d+)\))?\.jpg$'
    match = re.match(pattern, filename)
    
    if match:
        page_num = match.group(1)
        # Check if there's a duplicate number in parentheses
        duplicate_num = match.group(2) if match.group(2) else None
        if duplicate_num:
            return f"image_{page_num}_{duplicate_num}.jpg"
        else:
            return f"image_{page_num}.jpg"
    else:
        # If pattern doesn't match, return original name
        return filename


def find_image_references_in_tex(tex_content):
    """
    Find all image references in LaTeX content.
    Returns a list of tuples: (original_reference, page_number, duplicate_suffix)
    """
    references = []
    
    # Pattern 1: LaTeX \includegraphics commands
    pattern1 = r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}'
    matches1 = re.finditer(pattern1, tex_content)
    
    for match in matches1:
        # Extract the full \includegraphics command
        full_command = match.group(0)
        image_path = match.group(1)
        
        # Extract page number and duplicate suffix from the image path
        page_match = re.search(r'(\d+)(?:\((\d+)\))?(?:\.jpg)?$', image_path)
        if page_match:
            page_num = page_match.group(1)
            duplicate_suffix = page_match.group(2) if page_match.group(2) else ""
            references.append((full_command, page_num, duplicate_suffix))
    
    # Pattern 2: Markdown-style image links with CDN URLs
    pattern2 = r'!\[.*?\]\((https://cdn\.mathpix\.com/cropped/[^)]*?(\d+)(?:\((\d+)\))?\.jpg[^)]*?)\)'
    matches2 = re.findall(pattern2, tex_content)
    
    for full_url, page_num, duplicate_suffix in matches2:
        duplicate_suffix = duplicate_suffix if duplicate_suffix else ""
        references.append((full_url, page_num, duplicate_suffix))
    
    # Pattern 3: Direct image references (just filename without includegraphics)
    pattern3 = r'(\d{4}_\d{2}_\d{2}_[a-f0-9]+-(\d+)(?:\((\d+)\))?\.jpg)'
    matches3 = re.findall(pattern3, tex_content)
    
    for full_name, page_num, duplicate_suffix in matches3:
        duplicate_suffix = duplicate_suffix if duplicate_suffix else ""
        references.append((full_name, page_num, duplicate_suffix))
    
    return references


def update_tex_file(tex_file_path, image_mapping, dry_run=False):
    """
    Update LaTeX file to use new image names.
    
    Args:
        tex_file_path: Path to the LaTeX file
        image_mapping: Dictionary mapping (page_num, duplicate_suffix) to new names
        dry_run: If True, only show what would be changed without making changes
    """
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Updating LaTeX file: {tex_file_path}")
    
    # Read the LaTeX file
    with open(tex_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes_made = 0
    
    # Find and replace image references
    for old_ref, page_num, duplicate_suffix in find_image_references_in_tex(content):
        key = (page_num, duplicate_suffix)
        if key in image_mapping:
            new_name = image_mapping[key]
            # Remove .jpg extension for \includegraphics commands
            new_name_no_ext = new_name.replace('.jpg', '')
            
            # Handle different types of references
            if old_ref.startswith('https://cdn.mathpix.com'):
                # CDN URL - replace with local image reference (no .jpg extension)
                new_ref = f"\\includegraphics[max width=\\textwidth]{{{new_name_no_ext}}}"
            elif old_ref.startswith('\\includegraphics'):
                # Already a LaTeX command - replace the filename (no .jpg extension)
                # Find the old filename in the command and replace it
                old_filename_match = re.search(r'\{([^}]+)\}', old_ref)
                if old_filename_match:
                    old_filename = old_filename_match.group(1)
                    new_ref = old_ref.replace(old_filename, new_name_no_ext)
                else:
                    new_ref = old_ref
            else:
                # Direct filename reference - keep .jpg extension
                new_ref = new_name
            
            if old_ref != new_ref:
                print(f"  Replacing: {old_ref[:80]}{'...' if len(old_ref) > 80 else ''}")
                print(f"  With:      {new_ref}")
                content = content.replace(old_ref, new_ref)
                changes_made += 1
    
    if changes_made > 0:
        if not dry_run:
            # Create backup
            backup_path = f"{tex_file_path}.backup"
            shutil.copy2(tex_file_path, backup_path)
            print(f"  Created backup: {backup_path}")
            
            # Write updated content
            with open(tex_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✅ Updated {changes_made} image references")
        else:
            print(f"  [DRY RUN] Would update {changes_made} image references")
    else:
        print("  No image references found to update")


def clean_images_in_directory(images_dir, dry_run=False):
    """
    Clean up image names in the directory.
    
    Args:
        images_dir: Path to the images directory
        dry_run: If True, only show what would be changed without making changes
    
    Returns:
        Dictionary mapping (page_num, duplicate_suffix) to new clean names
    """
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Cleaning images in: {images_dir}")
    
    image_mapping = {}
    jpg_files = [f for f in os.listdir(images_dir) if f.lower().endswith('.jpg')]
    
    if not jpg_files:
        print("  No JPG files found in directory")
        return image_mapping
    
    print(f"  Found {len(jpg_files)} JPG files")
    
    for filename in sorted(jpg_files):
        # Extract page number and duplicate suffix
        page_match = re.search(r'(\d+)(?:\((\d+)\))?\.jpg$', filename)
        if page_match:
            page_num = page_match.group(1)
            duplicate_suffix = page_match.group(2) if page_match.group(2) else ""
            
            clean_name = clean_image_name(filename)
            key = (page_num, duplicate_suffix)
            image_mapping[key] = clean_name
            
            old_path = os.path.join(images_dir, filename)
            new_path = os.path.join(images_dir, clean_name)
            
            if filename != clean_name:
                print(f"  {filename} -> {clean_name}")
                
                if not dry_run:
                    if os.path.exists(new_path):
                        print(f"    Warning: {clean_name} already exists, skipping")
                    else:
                        shutil.move(old_path, new_path)
                        print(f"    ✅ Renamed")
            else:
                print(f"  {filename} (no change needed)")
    
    return image_mapping


def main():
    parser = argparse.ArgumentParser(
        description="Clean image names and update LaTeX file references"
    )
    parser.add_argument("images_dir", help="Directory containing the images")
    parser.add_argument("tex_file", help="Path to the LaTeX file to update")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Show what would be changed without making changes")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.isdir(args.images_dir):
        print(f"Error: Images directory does not exist: {args.images_dir}")
        return 1
    
    if not os.path.isfile(args.tex_file):
        print(f"Error: LaTeX file does not exist: {args.tex_file}")
        return 1
    
    print("=" * 60)
    print("IMAGE NAME CLEANER AND LATEX UPDATER")
    print("=" * 60)
    
    # Step 1: Clean image names
    image_mapping = clean_images_in_directory(args.images_dir, args.dry_run)
    
    if not image_mapping:
        print("\nNo images to process.")
        return 0
    
    # Step 2: Update LaTeX file
    update_tex_file(args.tex_file, image_mapping, args.dry_run)
    
    print("\n" + "=" * 60)
    if args.dry_run:
        print("DRY RUN COMPLETE - No files were actually changed")
    else:
        print("CLEANUP COMPLETE")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    exit(main())