"""
Simple diff-based scoring for LaTeX regression testing

This module provides a basic similarity score based on character-level differences
between input and output LaTeX files using Python's difflib.
"""

import difflib
from pathlib import Path


def calculate_score(input_file_path: str, output_file_path: str) -> float:
    """
    Calculate similarity score based on character-level diff between two LaTeX files.

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

        # Calculate similarity using difflib's SequenceMatcher
        matcher = difflib.SequenceMatcher(None, input_content, output_content)
        similarity_ratio = matcher.ratio()

        # Convert to percentage (0-100 scale)
        score = similarity_ratio * 100

        return round(score, 2)

    except FileNotFoundError as e:
        print(f"File not found: {e}")
        return 0.0
    except Exception as e:
        print(f"Error calculating diff score: {e}")
        return 0.0
