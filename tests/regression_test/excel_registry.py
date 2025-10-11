"""Master Excel registry for regression test results.

Layout (sheet 'AllVersions'):
- Column A: Metric labels (one per row)
- For each version, a contiguous block of columns is added to the right:
  - Row 1: merged cells across the block containing the version name
  - Row 2: book names (one per column inside the block, order comes from files/ discovery)
  - Rows 3+: metric values (each row corresponds to a metric in column A)

This module uses openpyxl. Install with: pip install openpyxl
"""
from __future__ import annotations
import os
import json
from pathlib import Path
from typing import List, Dict, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment


MASTER_FILENAME = "master_results.xlsx"
SHEET_NAME = "AllVersions"

# Metrics header list mirrored from regression runner
METRIC_ROWS = [
    "book_name",
    "scoring_method",
    "timestamp",
    "Score",
    "Latex Errors",
    "Latex Warnings",
    "Bibtex (metadata)",
    "Bibtex extracted (json)",
    "Entries Cited",
    "Chapters (metadata)",
    "Chapters (output)",
    "Sections (metadata)",
    "Sections (output)",
    "Subsections (metadata)",
    "Subsections (output)",
    "Figures (metadata)",
    "Figures (output)",
    "Tables (metadata)",
    "Tables (output)",
    "Index Entries (metadata)",
    "Index Entries (output)",
]


def _master_path(results_dir: Path) -> Path:
    return results_dir / MASTER_FILENAME


def _ensure_workbook(path: Path, books: List[str]) -> None:
    """Create workbook with metric rows in column A if not exists."""
    if path.exists():
        return

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    # Column A - metric labels start at row 3 (we reserve rows 1-2 for version/book headers)
    ws.cell(row=2, column=1, value="Metric")
    for idx, metric in enumerate(METRIC_ROWS, start=3):
        ws.cell(row=idx, column=1, value=metric)

    wb.save(path)


def _load_or_create(results_dir: Path) -> Workbook:
    path = _master_path(results_dir)
    # Determine repository root relative to this module file (tests/regression_test/../..)
    repo_root = Path(__file__).resolve().parents[2]
    books = _discover_books(repo_root / "files")
    _ensure_workbook(path, books)
    return load_workbook(path)


def _discover_books(files_dir: Path) -> List[str]:
    """Discover books by scanning files/ directory (same logic as regression tester)."""
    if not files_dir.exists():
        return []
    books = []
    for item in sorted(files_dir.iterdir()):
        if item.is_dir():
            input_file = item / "inputs" / f"{item.name}.tex"
            output_file = item / "outputs" / f"{item.name}_final.tex"
            # include books even if output not present; keep consistent order
            books.append(item.name)
    return books


def _find_version_block(ws, version_name: str) -> Optional[tuple]:
    """Return (start_col_index, end_col_index) if a block for version exists."""
    # scan row 1 for merged cells or values
    max_col = ws.max_column
    for col in range(2, max_col + 1):
        val = ws.cell(row=1, column=col).value
        if val == version_name:
            # walk left to find start of this block
            start = col
            while start > 2 and ws.cell(row=2, column=start - 1).value is not None:
                start -= 1
            # walk right to find block end
            end = col
            while end + 1 <= max_col and ws.cell(row=2, column=end + 1).value is not None:
                end += 1
            return start, end
    return None


def _add_version_block(ws, version_name: str, books: List[str]) -> int:
    """Append a block of columns for the version. Returns starting column index."""
    # Determine start column (append to the right)
    # Reserve column A for metrics; first block should start at column 2.
    # Leave a single empty separator column between existing content and the new block
    last_used = ws.max_column
    if last_used < 2:
        start_col = 2
    else:
        # place start two columns after last used to leave one empty column as separator
        start_col = last_used + 2

    # Add book columns and write book names in row 2
    for i, book in enumerate(books):
        col = start_col + i
        ws.cell(row=2, column=col, value=book)

    # Merge top row across block and set version name
    end_col = start_col + len(books) - 1 if books else start_col
    merge_range = f"{get_column_letter(start_col)}1:{get_column_letter(end_col)}1"
    ws.merge_cells(merge_range)
    ws.cell(row=1, column=start_col, value=version_name)
    ws.cell(row=1, column=start_col).alignment = Alignment(horizontal="center", vertical="center")

    return start_col


def update_master_excel(results_dir: Path, book_name: str, result: Dict) -> None:
    """Update (or create) the master Excel file with metrics for a single book and the current version."""
    wb = _load_or_create(results_dir)
    ws = wb[SHEET_NAME]

    # Discover files/ books using the repository root relative to this module
    repo_root = Path(__file__).resolve().parents[2]
    files_dir = repo_root / "files"
    books = _discover_books(files_dir)

    # Determine current version by reading version_control json (if available)
    version_file = repo_root / "codes" / "pdf_to_latex" / "version_control" / "version_history.json"
    version_name = "unknown"
    try:
        if version_file.exists():
            with open(version_file, "r") as f:
                versions = json.load(f)
            for v in versions:
                if v.get("is_current") and not v.get("is_deleted", False):
                    version_name = v.get("name")
                    break
    except Exception:
        version_name = "unknown"

    # Ensure metric rows exist in column A starting at row 3
    for idx, metric in enumerate(METRIC_ROWS, start=3):
        if ws.cell(row=idx, column=1).value is None:
            ws.cell(row=idx, column=1, value=metric)

    # Find or create version block
    block = _find_version_block(ws, version_name)
    if not block:
        start_col = _add_version_block(ws, version_name, books)
    else:
        start_col, end_col = block

    # Locate the column for the requested book within the version block
    # Recompute block boundaries for new workbook if needed
    if not block:
        end_col = start_col + len(books) - 1

    try:
        book_index = books.index(book_name)
    except ValueError:
        # Book not found in discovered list: append it at the end of the current block
        book_index = len(books)
        books.append(book_name)
        # expand the merged area and write the book name
        col = start_col + book_index
        ws.cell(row=2, column=col, value=book_name)
        # update merge to include new column
        new_end = start_col + len(books) - 1
        ws.merge_cells(f"{get_column_letter(start_col)}1:{get_column_letter(new_end)}1")

    target_col = start_col + book_index

    # Fill metric rows
    # map result details/dict to metric names; prefer result['details'] when available
    details = result.get("details", {}) if isinstance(result.get("details", {}), dict) else {}

    # base fields
    mapping = {
        "book_name": result.get("book_name", book_name),
        "scoring_method": result.get("scoring_method", ""),
        "timestamp": result.get("timestamp", ""),
        "Score": result.get("score", 0.0),
    }

    # Merge details into mapping where key matches metric names
    for key in METRIC_ROWS:
        if key in details:
            mapping[key] = details.get(key)

    # Also allow keys from details to be written to any metric row with exact key match
    for row_idx, metric in enumerate(METRIC_ROWS, start=3):
        value = mapping.get(metric, "")
        ws.cell(row=row_idx, column=target_col, value=value)

    # Save workbook
    wb.save(_master_path(results_dir))
