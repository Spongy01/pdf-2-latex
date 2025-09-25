"""
Similarity-based scoring for LaTeX regression testing

This module provides text similarity scoring between input and output LaTeX files.
"""

import re
import difflib
from pathlib import Path
from typing import Dict, Union


def calculate_score(
    input_file_path: str, output_file_path: str
) -> Dict[str, Union[float, Dict]]:
    """
    Calculate similarity score between input and output LaTeX files.

    Args:
        input_file_path: Path to the input LaTeX file (e.g., files/ai/inputs/ai.tex)
        output_file_path: Path to the output LaTeX file (e.g., files/ai/outputs/ai_cleaned_final.tex)

    Returns:
        Dictionary containing:
        - score: Overall similarity score (0-100)
        - text_similarity: Raw text similarity
        - command_similarity: LaTeX command preservation
        - structure_similarity: Document structure preservation
    """

    try:
        # Read both files
        with open(input_file_path, "r", encoding="utf-8") as f:
            input_content = f.read()

        with open(output_file_path, "r", encoding="utf-8") as f:
            output_content = f.read()

        # Calculate different similarity metrics
        text_sim = _calculate_text_similarity(input_content, output_content)
        command_sim = _calculate_command_similarity(input_content, output_content)
        structure_sim = _calculate_structure_similarity(input_content, output_content)

        # Weighted overall score
        overall_score = text_sim * 0.5 + command_sim * 0.3 + structure_sim * 0.2

        return {
            "score": round(overall_score, 2),
            "text_similarity": round(text_sim, 2),
            "command_similarity": round(command_sim, 2),
            "structure_similarity": round(structure_sim, 2),
            "details": {
                "input_length": len(input_content),
                "output_length": len(output_content),
                "input_commands": len(_extract_latex_commands(input_content)),
                "output_commands": len(_extract_latex_commands(output_content)),
            },
        }

    except FileNotFoundError as e:
        return {
            "score": 0.0,
            "error": f"File not found: {e}",
            "text_similarity": 0.0,
            "command_similarity": 0.0,
            "structure_similarity": 0.0,
        }
    except Exception as e:
        return {
            "score": 0.0,
            "error": f"Error calculating score: {e}",
            "text_similarity": 0.0,
            "command_similarity": 0.0,
            "structure_similarity": 0.0,
        }


def _calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate text similarity using sequence matching"""
    # Clean text (remove extra whitespace, normalize)
    clean1 = re.sub(r"\s+", " ", text1.strip())
    clean2 = re.sub(r"\s+", " ", text2.strip())

    # Calculate similarity using difflib
    matcher = difflib.SequenceMatcher(None, clean1, clean2)
    similarity = matcher.ratio() * 100

    return similarity


def _calculate_command_similarity(text1: str, text2: str) -> float:
    """Calculate LaTeX command preservation similarity"""
    commands1 = _extract_latex_commands(text1)
    commands2 = _extract_latex_commands(text2)

    if not commands1 and not commands2:
        return 100.0
    if not commands1 or not commands2:
        return 0.0

    # Calculate Jaccard similarity for commands
    set1 = set(commands1)
    set2 = set(commands2)

    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))

    if union == 0:
        return 100.0

    jaccard_sim = (intersection / union) * 100
    return jaccard_sim


def _calculate_structure_similarity(text1: str, text2: str) -> float:
    """Calculate document structure similarity"""
    # Extract structural elements
    structure1 = _extract_structure(text1)
    structure2 = _extract_structure(text2)

    if not structure1 and not structure2:
        return 100.0

    # Compare structure sequences
    matcher = difflib.SequenceMatcher(None, structure1, structure2)
    similarity = matcher.ratio() * 100

    return similarity


def _extract_latex_commands(text: str) -> list:
    """Extract all LaTeX commands from text"""
    # Pattern to match LaTeX commands like \command{} or \command
    command_pattern = r"\\[a-zA-Z*]+(?:\[[^\]]*\])?(?:\{[^}]*\})*"
    commands = re.findall(command_pattern, text)

    # Normalize commands (remove arguments for comparison)
    normalized_commands = []
    for cmd in commands:
        # Extract just the command name
        cmd_name = re.match(r"\\[a-zA-Z*]+", cmd)
        if cmd_name:
            normalized_commands.append(cmd_name.group())

    return normalized_commands


def _extract_structure(text: str) -> list:
    """Extract document structure elements (sections, environments, etc.)"""
    structure_elements = []

    # Section commands
    section_pattern = (
        r"\\(part|chapter|section|subsection|subsubsection|paragraph|subparagraph)"
    )
    sections = re.findall(section_pattern, text)
    structure_elements.extend([f"\\{s}" for s in sections])

    # Environment starts
    env_pattern = r"\\begin\{([^}]+)\}"
    environments = re.findall(env_pattern, text)
    structure_elements.extend([f"\\begin{{{e}}}" for e in environments])

    return structure_elements


# Alternative simple scoring function that just returns a float
def simple_calculate_score(input_file_path: str, output_file_path: str) -> float:
    """
    Simple scoring function that returns just a float score.
    This is an alternative interface that some users might prefer.
    """
    result = calculate_score(input_file_path, output_file_path)
    return result.get("score", 0.0)
