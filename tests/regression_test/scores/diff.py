"""
Simple diff-based scoring for LaTeX regression testing

This module provides a basic similarity score based on character-level differences
between input and output LaTeX files using Python's difflib.
"""

import difflib
import hashlib
from pathlib import Path


def calculate_score(input_file_path: str, output_file_path: str) -> float:
    """
    Calculate similarity score based on fast line-level diff between two LaTeX files.

    Args:
        input_file_path: Path to the input LaTeX file (e.g., files/ai/inputs/ai.tex)
        output_file_path: Path to the output LaTeX file (e.g., files/ai/outputs/ai_cleaned_final.tex)

    Returns:
        Float score from 0.0 to 100.0, where 100.0 means identical files
    """

    try:
        # Read both files
        with open(input_file_path, "r", encoding="utf-8") as f:
            input_content = f.read()

        with open(output_file_path, "r", encoding="utf-8") as f:
            output_content = f.read()

        # Quick check: if files are identical, return 100
        if input_content == output_content:
            return 100.0

        # Option 1: Fast line-based comparison (recommended)
        return _fast_line_similarity(input_content, output_content)

        # Option 2: Ultra-fast hash-based similarity (uncomment to use)
        # return _hash_similarity(input_content, output_content)

        # Option 3: Length-based similarity (fastest, least accurate)
        # return _length_similarity(input_content, output_content)

    except FileNotFoundError as e:
        print(f"File not found: {e}")
        return 0.0
    except Exception as e:
        print(f"Error calculating diff score: {e}")
        return 0.0


def _fast_line_similarity(content1: str, content2: str) -> float:
    """Fast line-based similarity using difflib on lines, not characters"""
    lines1 = content1.splitlines()
    lines2 = content2.splitlines()

    # Use quick_ratio for much faster approximation
    matcher = difflib.SequenceMatcher(None, lines1, lines2)
    similarity_ratio = matcher.quick_ratio()  # Much faster than .ratio()

    return round(similarity_ratio * 100, 2)
