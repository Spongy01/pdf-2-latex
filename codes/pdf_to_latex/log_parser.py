"""
LaTeX Log Parser

This script parses LaTeX compilation log files to extract detailed error and warning information.
It collects all LaTeX Error: and LaTeX Warning: messages with their descriptions and counts.

Usage:
    python log_parser.py <log_file_path> [output_json_path]
    
Or import and use:
    from log_parser import parse_latex_log
    results = parse_latex_log("path/to/file.log")
"""

import re
import json
import argparse
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_latex_log(log_file_path: str) -> Dict:
    """
    Parse a LaTeX log file and extract detailed error and warning information.
    
    Args:
        log_file_path: Path to the LaTeX log file
        
    Returns:
        Dictionary containing:
        - errors: List of error details with counts
        - warnings: List of warning details with counts
        - summary: Summary statistics
        - compilation_info: General compilation information
    """
    
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            log_content = f.read()
    except FileNotFoundError:
        logger.error(f"Log file not found: {log_file_path}")
        return {"error": f"Log file not found: {log_file_path}"}
    except Exception as e:
        logger.error(f"Error reading log file: {e}")
        return {"error": f"Error reading log file: {e}"}
    
    # Initialize result structure
    result = {
        "log_file": log_file_path,
        "errors": [],
        "warnings": [],
        "summary": {
            "total_errors": 0,
            "total_warnings": 0,
            "unique_errors": 0,
            "unique_warnings": 0,
            "compilation_successful": False
        },
        "compilation_info": {
            "pages_compiled": 0,
            "total_pages": 0,
            "compilation_time": None,
            "latex_version": None,
            "output_file": None
        }
    }
    
    # Parse errors
    errors = _parse_errors(log_content)
    result["errors"] = errors
    result["summary"]["total_errors"] = sum(error["count"] for error in errors)
    result["summary"]["unique_errors"] = len(errors)
    
    # Parse warnings
    warnings = _parse_warnings(log_content)
    result["warnings"] = warnings
    result["summary"]["total_warnings"] = sum(warning["count"] for warning in warnings)
    result["summary"]["unique_warnings"] = len(warnings)
    
    # Parse compilation info
    compilation_info = _parse_compilation_info(log_content)
    result["compilation_info"].update(compilation_info)
    
    # Determine if compilation was successful
    result["summary"]["compilation_successful"] = (
        result["summary"]["total_errors"] == 0 and 
        "Output written" in log_content
    )
    
    return result


def _parse_errors(log_content: str) -> List[Dict]:
    """Parse LaTeX errors from log content."""
    
    # Single pattern to match: <source> Error: <description>.
    error_pattern = r'(\w+)\s+Error:\s+([^.\n]+)\.'
    
    errors = []
    error_counter = Counter()
    error_details = defaultdict(list)
    
    matches = re.finditer(error_pattern, log_content, re.IGNORECASE | re.MULTILINE)
    for match in matches:
        source = match.group(1).strip()
        error_desc = match.group(2).strip()
        
        # Clean up the error description
        error_desc = re.sub(r'\s+', ' ', error_desc)  # Normalize whitespace
        
        # Create a unique key combining source and description
        error_key = f"{source}: {error_desc}"
        
        error_counter[error_key] += 1
        error_details[error_key].append(source)
    
    # Convert to list format
    for error_key, count in error_counter.items():
        error_info = {
            "source": error_details[error_key][0],  # Get the source
            "description": error_key.split(': ', 1)[1],  # Get description part
            "count": count,
            "sources": list(set(error_details[error_key]))  # Unique sources
        }
        errors.append(error_info)
    
    # Sort by count (most frequent first)
    errors.sort(key=lambda x: x["count"], reverse=True)
    
    return errors


def _parse_warnings(log_content: str) -> List[Dict]:
    """Parse LaTeX warnings from log content."""
    
    # Single pattern to match: <source> Warning: <description>.
    warning_pattern = r'(\w+)\s+Warning:\s+([^.\n]+)\.'
    
    warnings = []
    warning_counter = Counter()
    warning_details = defaultdict(list)
    
    matches = re.finditer(warning_pattern, log_content, re.IGNORECASE | re.MULTILINE)
    for match in matches:
        source = match.group(1).strip()
        warning_desc = match.group(2).strip()
        
        # Clean up the warning description
        warning_desc = re.sub(r'\s+', ' ', warning_desc)  # Normalize whitespace
        
        # Create a unique key combining source and description
        warning_key = f"{source}: {warning_desc}"
        
        warning_counter[warning_key] += 1
        warning_details[warning_key].append(source)
    
    # Convert to list format
    for warning_key, count in warning_counter.items():
        warning_info = {
            "source": warning_details[warning_key][0],  # Get the source
            "description": warning_key.split(': ', 1)[1],  # Get description part
            "count": count,
            "sources": list(set(warning_details[warning_key]))  # Unique sources
        }
        warnings.append(warning_info)
    
    # Sort by count (most frequent first)
    warnings.sort(key=lambda x: x["count"], reverse=True)
    
    return warnings


def _parse_compilation_info(log_content: str) -> Dict:
    """Parse general compilation information from log content."""
    
    info = {
        "pages_compiled": 0,
        "total_pages": 0,
        "compilation_time": None,
        "latex_version": None,
        "output_file": None
    }
    
    # Extract page information
    page_matches = re.findall(r'\[(\d+)\]', log_content)
    if page_matches:
        info["pages_compiled"] = max(int(p) for p in page_matches)
    
    # Extract LaTeX version
    version_match = re.search(r'This is (?:pdf|xe|lua)TeX, Version ([^\s]+)', log_content)
    if version_match:
        info["latex_version"] = version_match.group(1)
    
    # Extract output file
    output_match = re.search(r'Output written on ([^(]+)', log_content)
    if output_match:
        info["output_file"] = output_match.group(1).strip()
    
    # Extract compilation time (if available)
    time_match = re.search(r'Time used: ([^\s]+)', log_content)
    if time_match:
        info["compilation_time"] = time_match.group(1)
    
    return info


def save_log_analysis(log_file_path: str, output_path: Optional[str] = None) -> str:
    """
    Parse a LaTeX log file and save the analysis to JSON.
    
    Args:
        log_file_path: Path to the LaTeX log file
        output_path: Optional output path for JSON file
        
    Returns:
        Path to the saved JSON file
    """
    
    # Parse the log file
    analysis = parse_latex_log(log_file_path)
    
    # Determine output path
    if output_path is None:
        log_path = Path(log_file_path)
        output_path = log_path.parent / f"{log_path.stem}_log_analysis.json"
    
    # Save to JSON
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Log analysis saved to: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Error saving log analysis: {e}")
        raise


def main():
    """Command-line interface for the log parser."""
    
    parser = argparse.ArgumentParser(description="Parse LaTeX compilation log files")
    parser.add_argument("log_file", help="Path to the LaTeX log file")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Parse and save the log analysis
    try:
        output_path = save_log_analysis(args.log_file, args.output)
        
        # Print summary
        analysis = parse_latex_log(args.log_file)
        summary = analysis["summary"]
        
        print(f"\n{'='*50}")
        print(f"LATEX LOG ANALYSIS SUMMARY")
        print(f"{'='*50}")
        print(f"Log file: {args.log_file}")
        print(f"Output: {output_path}")
        print(f"Total Errors: {summary['total_errors']}")
        print(f"Unique Errors: {summary['unique_errors']}")
        print(f"Total Warnings: {summary['total_warnings']}")
        print(f"Unique Warnings: {summary['unique_warnings']}")
        print(f"Compilation Successful: {summary['compilation_successful']}")
        
        if summary['total_errors'] > 0:
            print(f"\nTop Errors:")
            for i, error in enumerate(analysis['errors'][:5], 1):
                print(f"  {i}. [{error['source']}] {error['description']} (x{error['count']})")
        
        if summary['total_warnings'] > 0:
            print(f"\nTop Warnings:")
            for i, warning in enumerate(analysis['warnings'][:5], 1):
                print(f"  {i}. [{warning['source']}] {warning['description']} (x{warning['count']})")
        
        print(f"{'='*50}")
        
    except Exception as e:
        logger.error(f"Error processing log file: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
