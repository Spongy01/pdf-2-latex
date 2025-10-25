"""
Cleaning functions without GPT processing

This module contains utility functions for cleaning and fixing LaTeX files
without using GPT or AI processing.
"""

import re
import logging

# Setup logging
logger = logging.getLogger(__name__)


def fix_figure_table_positioning(tex_file_path):
    """
    Fix figure and table positioning by replacing [h] with [htbp].
    
    Args:
        tex_file_path: Path to the LaTeX file to process
        
    Returns:
        Path to the processed file (same as input)
    """
    try:
        # Read the file
        with open(tex_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match \begin{figure}[h] and \begin{table}[h]
        # This will match any single character positioning option and replace with [htbp]
        pattern = r'(\\begin\{(?:figure|table)\})\[([htbp])\](?!\s*\[)'
        
        # Find all matches first to report what we're changing
        matches = list(re.finditer(pattern, content))
        
        if matches:
            print(f"Found {len(matches)} figure/table positioning options to fix:")
            for match in matches:
                old_pos = match.group(2)
                print(f"  {match.group(1)}[{old_pos}] -> {match.group(1)}[htbp]")
            
            # Replace all [h], [t], [b], [p] with [htbp]
            new_content = re.sub(pattern, r'\1[htbp]', content)
            
            # Write back to file
            with open(tex_file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"✅ Fixed {len(matches)} figure/table positioning options")
        else:
            print("No figure/table positioning options found to fix")
        
        return tex_file_path
        
    except Exception as e:
        logger.error(f"Error fixing figure/table positioning: {e}")
        return tex_file_path
