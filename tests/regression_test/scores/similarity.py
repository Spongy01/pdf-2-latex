"""
Comprehensive scoring for LaTeX regression testing

This module provides comprehensive analysis including mathematical content,
table preservation, citation handling, and overall document quality.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Union, Tuple
import difflib


def calculate_score(
    input_file_path: str, output_file_path: str
) -> Dict[str, Union[float, Dict]]:
    """
    Calculate comprehensive score between input and output LaTeX files.

    Returns detailed analysis including:
    - Mathematical content preservation
    - Table structure preservation
    - Citation and reference integrity
    - Environment handling
    - Overall document quality
    """

    try:
        # Read both files
        with open(input_file_path, "r", encoding="utf-8") as f:
            input_content = f.read()

        with open(output_file_path, "r", encoding="utf-8") as f:
            output_content = f.read()

        # Calculate comprehensive metrics
        math_score = _calculate_math_preservation(input_content, output_content)
        table_score = _calculate_table_preservation(input_content, output_content)
        citation_score = _calculate_citation_preservation(input_content, output_content)
        env_score = _calculate_environment_preservation(input_content, output_content)
        structure_score = _calculate_document_structure(input_content, output_content)
        quality_score = _calculate_quality_metrics(input_content, output_content)

        # Weighted comprehensive score
        overall_score = (
            math_score * 0.25  # Mathematical content is crucial
            + table_score * 0.20  # Tables are important structure
            + citation_score * 0.15  # Citations matter for academic docs
            + env_score * 0.15  # Environment handling
            + structure_score * 0.15  # Overall document structure
            + quality_score * 0.10  # General quality metrics
        )

        return {
            "score": round(overall_score, 2),
            "math_preservation": round(math_score, 2),
            "table_preservation": round(table_score, 2),
            "citation_preservation": round(citation_score, 2),
            "environment_preservation": round(env_score, 2),
            "structure_preservation": round(structure_score, 2),
            "quality_metrics": round(quality_score, 2),
            "details": {
                "input_analysis": _analyze_document(input_content),
                "output_analysis": _analyze_document(output_content),
                "differences": _calculate_differences(input_content, output_content),
            },
        }

    except Exception as e:
        return {
            "score": 0.0,
            "error": f"Error in comprehensive scoring: {e}",
            "math_preservation": 0.0,
            "table_preservation": 0.0,
            "citation_preservation": 0.0,
            "environment_preservation": 0.0,
            "structure_preservation": 0.0,
            "quality_metrics": 0.0,
        }


def _calculate_math_preservation(input_text: str, output_text: str) -> float:
    """Calculate how well mathematical content is preserved"""
    # Extract math environments and inline math
    input_math = _extract_math_content(input_text)
    output_math = _extract_math_content(output_text)

    if not input_math["equations"] and not input_math["inline"]:
        return 100.0  # No math to preserve

    # Calculate preservation ratios
    eq_preservation = _calculate_preservation_ratio(
        input_math["equations"], output_math["equations"]
    )
    inline_preservation = _calculate_preservation_ratio(
        input_math["inline"], output_math["inline"]
    )

    # Weight equations more heavily than inline math
    math_score = eq_preservation * 0.7 + inline_preservation * 0.3
    return math_score


def _calculate_table_preservation(input_text: str, output_text: str) -> float:
    """Calculate how well table structures are preserved"""
    input_tables = _extract_tables(input_text)
    output_tables = _extract_tables(output_text)

    if not input_tables:
        return 100.0  # No tables to preserve

    # Check table structure preservation
    structure_score = _calculate_preservation_ratio(
        [t["structure"] for t in input_tables], [t["structure"] for t in output_tables]
    )

    # Check table content preservation
    content_score = _calculate_preservation_ratio(
        [t["content"] for t in input_tables], [t["content"] for t in output_tables]
    )

    return structure_score * 0.6 + content_score * 0.4


def _calculate_citation_preservation(input_text: str, output_text: str) -> float:
    """Calculate citation and reference preservation"""
    input_citations = _extract_citations(input_text)
    output_citations = _extract_citations(output_text)

    if not input_citations["cite"] and not input_citations["ref"]:
        return 100.0  # No citations to preserve

    cite_preservation = _calculate_preservation_ratio(
        input_citations["cite"], output_citations["cite"]
    )
    ref_preservation = _calculate_preservation_ratio(
        input_citations["ref"], output_citations["ref"]
    )

    return (cite_preservation + ref_preservation) / 2


def _calculate_environment_preservation(input_text: str, output_text: str) -> float:
    """Calculate LaTeX environment preservation"""
    input_envs = _extract_environments(input_text)
    output_envs = _extract_environments(output_text)

    if not input_envs:
        return 100.0

    return _calculate_preservation_ratio(input_envs, output_envs)


def _calculate_document_structure(input_text: str, output_text: str) -> float:
    """Calculate overall document structure preservation"""
    input_structure = _extract_document_structure(input_text)
    output_structure = _extract_document_structure(output_text)

    # Use sequence matching for structure comparison
    matcher = difflib.SequenceMatcher(None, input_structure, output_structure)
    return matcher.ratio() * 100


def _calculate_quality_metrics(input_text: str, output_text: str) -> float:
    """Calculate general quality metrics"""
    # Length preservation (penalize excessive changes)
    length_ratio = min(len(output_text), len(input_text)) / max(
        len(output_text), len(input_text)
    )
    length_score = length_ratio * 100

    # Command density preservation
    input_commands = len(re.findall(r"\\[a-zA-Z]+", input_text))
    output_commands = len(re.findall(r"\\[a-zA-Z]+", output_text))

    if input_commands > 0:
        command_ratio = min(output_commands, input_commands) / max(
            output_commands, input_commands
        )
        command_score = command_ratio * 100
    else:
        command_score = 100.0

    return (length_score + command_score) / 2


# Helper functions
def _extract_math_content(text: str) -> Dict[str, List[str]]:
    """Extract mathematical content from LaTeX"""
    # Equation environments
    eq_patterns = [
        r"\\begin\{equation\}(.*?)\\end\{equation\}",
        r"\\begin\{align\}(.*?)\\end\{align\}",
        r"\\begin\{gather\}(.*?)\\end\{gather\}",
        r"\\\[(.*?)\\\]",
    ]

    equations = []
    for pattern in eq_patterns:
        equations.extend(re.findall(pattern, text, re.DOTALL))

    # Inline math
    inline_math = re.findall(r"\$(.*?)\$", text)

    return {"equations": equations, "inline": inline_math}


def _extract_tables(text: str) -> List[Dict[str, str]]:
    """Extract table information"""
    table_pattern = r"\\begin\{tabular\}(\{[^}]+\})(.*?)\\end\{tabular\}"
    tables = []

    for match in re.finditer(table_pattern, text, re.DOTALL):
        structure = match.group(1)  # Column specification
        content = match.group(2)  # Table content
        tables.append({"structure": structure, "content": content.strip()})

    return tables


def _extract_citations(text: str) -> Dict[str, List[str]]:
    """Extract citations and references"""
    # Citations
    cite_patterns = [r"\\cite\{([^}]+)\}", r"\\citep\{([^}]+)\}", r"\\citet\{([^}]+)\}"]

    citations = []
    for pattern in cite_patterns:
        citations.extend(re.findall(pattern, text))

    # References
    ref_patterns = [r"\\ref\{([^}]+)\}", r"\\eqref\{([^}]+)\}", r"\\pageref\{([^}]+)\}"]

    references = []
    for pattern in ref_patterns:
        references.extend(re.findall(pattern, text))

    return {"cite": citations, "ref": references}


def _extract_environments(text: str) -> List[str]:
    """Extract all LaTeX environments"""
    env_pattern = r"\\begin\{([^}]+)\}"
    return re.findall(env_pattern, text)


def _extract_document_structure(text: str) -> List[str]:
    """Extract document structure elements in order"""
    structure_patterns = [
        (r"\\part\{", "part"),
        (r"\\chapter\{", "chapter"),
        (r"\\section\{", "section"),
        (r"\\subsection\{", "subsection"),
        (r"\\subsubsection\{", "subsubsection"),
        (r"\\begin\{([^}]+)\}", "env_{}"),
    ]

    structure_elements = []

    for pattern, element_type in structure_patterns:
        for match in re.finditer(pattern, text):
            pos = match.start()
            if "env_{}" in element_type:
                env_name = match.group(1)
                element = f"env_{env_name}"
            else:
                element = element_type
            structure_elements.append((pos, element))

    # Sort by position to maintain document order
    structure_elements.sort(key=lambda x: x[0])
    return [elem[1] for elem in structure_elements]


def _calculate_preservation_ratio(input_items: List, output_items: List) -> float:
    """Calculate how well items are preserved between input and output"""
    if not input_items:
        return 100.0  # Nothing to preserve

    if not output_items:
        return 0.0  # Everything lost

    # Convert to sets for comparison
    input_set = set(str(item) for item in input_items)
    output_set = set(str(item) for item in output_items)

    # Calculate preservation ratio
    preserved = len(input_set.intersection(output_set))
    total = len(input_set)

    return (preserved / total) * 100 if total > 0 else 100.0


def _analyze_document(text: str) -> Dict:
    """Analyze a document and return statistics"""
    return {
        "total_length": len(text),
        "line_count": len(text.split("\n")),
        "word_count": len(text.split()),
        "command_count": len(re.findall(r"\\[a-zA-Z]+", text)),
        "math_equations": len(_extract_math_content(text)["equations"]),
        "inline_math": len(_extract_math_content(text)["inline"]),
        "tables": len(_extract_tables(text)),
        "citations": len(_extract_citations(text)["cite"]),
        "references": len(_extract_citations(text)["ref"]),
        "environments": len(set(_extract_environments(text))),
    }


def _calculate_differences(input_text: str, output_text: str) -> Dict:
    """Calculate specific differences between input and output"""
    input_analysis = _analyze_document(input_text)
    output_analysis = _analyze_document(output_text)

    differences = {}
    for key in input_analysis:
        input_val = input_analysis[key]
        output_val = output_analysis[key]

        if input_val != output_val:
            change_percent = (
                ((output_val - input_val) / input_val * 100) if input_val > 0 else 0
            )
            differences[key] = {
                "input": input_val,
                "output": output_val,
                "change": output_val - input_val,
                "change_percent": round(change_percent, 1),
            }

    return differences
