import copy
import json
import os
import re
import string
import fitz  # PyMuPDF
from dataclasses import dataclass, asdict
from tqdm import tqdm
from typing import List, Dict, Any, Optional, Tuple
from codes.pdf_to_latex.pdf_text_extractor import PDFTextExtractor


class LatexProcessor:
    """Process LaTeX documents and track character positions."""

    def __init__(self):
        self.latex_content = ""
        self.plain_text = ""
        self.positions = []
        self.pdf_pages = []

    def detex_with_positions(
        self, content: str, offset: int = 0
    ) -> Tuple[str, List[int]]:
        """Convert LaTeX to plain text paragraph by paragraph while tracking character positions."""

        # Split content into paragraphs
        paragraphs = content.split("\n\n")

        all_plain_text = ""
        all_positions = []
        current_offset = offset

        for para_idx, paragraph in enumerate(paragraphs):
            if not paragraph.strip():  # Skip empty paragraphs
                # Still track the position of the newlines
                current_offset += len(paragraph) + 2  # +2 for \n\n
                continue

            # print(f"Processing paragraph {para_idx + 1}/{len(paragraphs)}...")

            # Process this paragraph
            para_plain_text, para_positions = self._process_single_paragraph(
                paragraph, current_offset
            )

            # Append to overall results
            all_plain_text += para_plain_text
            all_positions.extend(para_positions)

            # Update offset for next paragraph
            current_offset += len(paragraph) + 2  # +2 for \n\n separator

        return all_plain_text, all_positions

    def _process_single_paragraph(
        self, paragraph: str, offset: int
    ) -> Tuple[str, List[int]]:
        """Process a single paragraph with pylatexenc."""
        from pylatexenc.latexwalker import (
            LatexWalker,
            LatexCharsNode,
            LatexGroupNode,
            LatexMacroNode,
            LatexEnvironmentNode,
        )

        lw = LatexWalker(paragraph)
        try:
            nodes, _, _ = lw.get_latex_nodes()
        except Exception as e:
            print(f"Warning: LaTeX parsing error in paragraph: {e}")
            return paragraph, list(range(offset, offset + len(paragraph)))

        plain_text = ""
        positions = []

        def process_node(node):
            nonlocal plain_text, positions

            if isinstance(node, LatexCharsNode):
                print(f"Node pos: {node.pos}, chars: '{node.chars}', offset: {offset}")
                print(
                    f"Adding positions: {node.pos + offset} to {node.pos + offset + len(node.chars)}"
                )
                # write these to a file for debugging
                with open(
                    "files/data-science-book_book/outputs/latex_positions_debug.txt",
                    "a",
                    encoding="utf-8",
                ) as f:
                    f.write(
                        f"Node pos: {node.pos}, chars: '{node.chars}', offset: {offset}\n"
                    )
                    f.write(
                        f"Adding positions: {node.pos + offset} to {node.pos + offset + len(node.chars)}\n"
                    )
                plain_text += node.chars
                positions.extend(
                    range(node.pos + offset, node.pos + offset + len(node.chars))
                )

            elif isinstance(node, LatexGroupNode):
                for sub_node in node.nodelist:
                    process_node(sub_node)

            elif isinstance(node, LatexMacroNode):
                # Skip certain macros
                if node.macroname in ["includegraphics", "label", "vspace", "newpage"]:
                    return

                # Handle captions
                elif node.macroname == "caption" and node.nodeargd:
                    for arg in node.nodeargd.argnlist:
                        if isinstance(arg, LatexGroupNode):
                            for sub_node in arg.nodelist:
                                process_node(sub_node)
                    return

                # Process macro arguments
                if node.nodeargd:
                    for arg in node.nodeargd.argnlist:
                        if isinstance(arg, LatexGroupNode):
                            for sub_node in arg.nodelist:
                                process_node(sub_node)

            elif isinstance(node, LatexEnvironmentNode):
                # Handle environments
                for sub_node in node.nodelist:
                    process_node(sub_node)

        for node in nodes:
            process_node(node)

        return plain_text, positions

    def clean_text_with_mapping(self, text: str) -> Tuple[str, List[int]]:
        """Clean text and maintain mapping from cleaned positions to original positions."""
        cleaned = ""
        position_mapping = []

        for i, char in enumerate(text):
            if char.isalpha():
                cleaned += char.lower()
                position_mapping.append(i)

        return cleaned, position_mapping

    def find_text_in_positions(
        self,
        target_text: str,
        search_text: str,
        positions: List[int],
        min_match_length: int = 50,
    ) -> Optional[int]:
        """Find target text within search text and return the LaTeX position."""
        clean_target, _ = self.clean_text_with_mapping(target_text)
        clean_search, search_position_mapping = self.clean_text_with_mapping(
            search_text
        )
        if len(clean_target) < min_match_length:
            return None

        # Find match in cleaned text
        pos = clean_search.find(clean_target)
        if pos != -1:
            end_pos_cleaned = pos + len(clean_target) - 1
            # Map back to original search_text position
            if end_pos_cleaned < len(search_position_mapping):
                original_pos = search_position_mapping[end_pos_cleaned]
                # Then map to LaTeX position
                if original_pos < len(positions):
                    return positions[original_pos]

        # Try fuzzy matching with suffixes
        for suffix_len in range(
            min(len(clean_target) // 2, 200), min_match_length - 1, -10
        ):
            suffix = clean_target[-suffix_len:]
            # Find match in cleaned text
            pos = clean_search.find(suffix)
            if pos != -1:
                end_pos_cleaned = pos + len(suffix) - 1
                # Map back to original search_text position
                if end_pos_cleaned < len(search_position_mapping):
                    original_pos = search_position_mapping[end_pos_cleaned]
                    # Then map to LaTeX position
                    if original_pos < len(positions):
                        return positions[original_pos]

        return None

    def process_latex_document(self, latex_content: str) -> None:
        """Process the entire LaTeX document and extract plain text with positions."""
        self.latex_content = latex_content

        # Extract content between \begin{document} and \end{document}
        document_match = re.search(
            r"\\begin\{document\}(.*?)\\end\{document\}", latex_content, re.DOTALL
        )

        if document_match:
            document_content = document_match.group(1)
            document_start = document_match.start(1)

            # save document_content for debugging
            with open(
                "files/algorithms_book/outputs/document_content.tex",
                "w",
                encoding="utf-8",
            ) as f:
                f.write(document_content)

            self.plain_text, self.positions = self.detex_with_positions(
                document_content, document_start
            )
        else:
            self.plain_text, self.positions = self.detex_with_positions(
                latex_content, 0
            )

    def add_pdf_page(self, page_content: str, page_number: int) -> None:
        """Add a PDF page's text content."""
        self.pdf_pages.append(
            {"page_number": page_number, "content": page_content.strip()}
        )

    def fuzzy_find_text_in_positions(
        self,
        target_text: str,
        search_text: str,
        positions: List[int],
        min_match_length: int = 35,
        similarity_threshold: int = 80,
    ) -> Optional[int]:
        """Find target text using fuzzy string matching library."""
        try:
            from fuzzywuzzy import fuzz, process
        except ImportError:
            print(
                "Warning: fuzzywuzzy not installed. Install with: pip install fuzzywuzzy python-Levenshtein"
            )
            return self.find_text_in_positions(
                target_text, search_text, positions, min_match_length
            )

        clean_target, _ = self.clean_text_with_mapping(target_text)
        clean_search, search_position_mapping = self.clean_text_with_mapping(
            search_text
        )

        # Save in output directory
        output_dir = "/home/sysaba1/pdf-2-latex/files/algorithms_book/outputs/"
        clean_search_path = os.path.join(output_dir, "cleaned_latex_text.txt")

        with open(clean_search_path, "w", encoding="utf-8") as f:
            f.write(clean_search)

        clean_target = clean_target[-200:]  # Use only the last 200 chars for matching

        # Strategy 1: Try exact match first (fastest)
        pos = clean_search.find(clean_target)
        if pos != -1:
            end_pos_cleaned = pos + len(clean_target) - 1
            # Map back to original search_text position
            if end_pos_cleaned < len(search_position_mapping):
                original_search_pos = search_position_mapping[end_pos_cleaned]
                # Map to LaTeX position
                if original_search_pos < len(positions):
                    return positions[original_search_pos]

        # Strategy 2: Sliding window fuzzy matching
        target_len = len(clean_target)
        best_match_pos = None
        best_ratio = 0

        # Use a sliding window approach
        step_size = max(1, target_len // 10)  # Adjust step size based on target length

        for i in range(0, len(clean_search) - target_len + 1, step_size):
            window = clean_search[i : i + target_len]

            # Use ratio for partial string matching
            ratio = fuzz.ratio(clean_target, window)

            if ratio > best_ratio and ratio >= similarity_threshold:
                best_ratio = ratio
                best_match_pos = i + target_len - 1

        if best_match_pos is not None:
            # Map fuzzy match position back through the position chain
            if best_match_pos < len(search_position_mapping):
                original_search_pos = search_position_mapping[best_match_pos]
                if original_search_pos < len(positions):
                    return positions[original_search_pos]

        # # Strategy 3: Try with partial ratio (subsequence matching)
        # for i in range(0, len(clean_search) - target_len + 1, step_size):
        #     window = clean_search[i : i + target_len]

        #     # Use partial_ratio for subsequence matching
        #     ratio = fuzz.partial_ratio(clean_target, window)

        #     if (
        #         ratio > best_ratio and ratio >= similarity_threshold - 10
        #     ):  # Lower threshold for partial
        #         best_ratio = ratio
        #         best_match_pos = i + target_len - 1

        # if best_match_pos is not None and best_match_pos < len(positions):
        #     print(f"Partial fuzzy match found with {best_ratio}% similarity")
        #     return positions[best_match_pos]

        return None

    def find_page_boundaries(self) -> List[Dict]:
        """Find LaTeX positions where each PDF page ends."""
        if not self.plain_text or not self.pdf_pages:
            raise ValueError("Must process LaTeX document and add PDF pages first")

        boundaries = []

        for page_info in tqdm(self.pdf_pages):
            page_num = page_info["page_number"]
            page_content = page_info["content"]

            # Find where this cumulative content ends in the LaTeX
            latex_position = self.find_text_in_positions(
                page_content,
                self.plain_text,
                self.positions,
                min_match_length=50,
            )

            if latex_position is not None:
                boundaries.append(
                    {
                        "page_number": page_num,
                        "latex_position": latex_position,
                        "content_length": len(page_content),
                        "page_last_content": page_content[-50:],
                        "last_location": self.positions[-1],
                        "method": "exact_match",
                    }
                )
                # print(f"Page {page_num} ends at LaTeX position {latex_position}")
            else:
                # print(f"Warning: Could not find boundary for page {page_num}")
                # Try with just the current page content
                latex_position = self.find_text_in_positions(
                    page_content, self.plain_text, self.positions, min_match_length=35
                )
                if latex_position is not None:
                    boundaries.append(
                        {
                            "page_number": page_num,
                            "latex_position": latex_position,
                            "content_length": len(page_content),
                            "page_last_content": page_content[-50:],
                            "method": "exact_match_fallback",
                        }
                    )
                    # print(
                    #     f"Page {page_num} ends at LaTeX position {latex_position} (fallback)"
                    # )
                else:
                    # print(
                    #     f"Error: Still could not find boundary for page {page_num}, going for fuzzy matching  ..."
                    # )
                    latex_position = self.fuzzy_find_text_in_positions(
                        page_content,
                        self.plain_text,
                        self.positions,
                        min_match_length=50,
                        similarity_threshold=80,
                    )
                    if latex_position is not None:
                        boundaries.append(
                            {
                                "page_number": page_num,
                                "latex_position": latex_position,
                                "content_length": len(page_content),
                                "page_last_content": page_content[-50:],
                                "method": "fuzzy_matching",
                            }
                        )
                        # print(
                        #     f"Page {page_num} ends at LaTeX position {latex_position} (fuzzy match)"
                        # )
                    # else:
                    # print(
                    #     f"Error: Could not find boundary for page {page_num} even with fuzzy matching."
                    # )
        return boundaries

    def insert_page_markers(self, boundaries: List[Dict]) -> str:
        """Insert page end markers into the LaTeX document."""
        if not boundaries:
            return self.latex_content

        # Sort boundaries by position (reverse order for insertion)
        sorted_boundaries = sorted(
            boundaries, key=lambda x: x["latex_position"], reverse=True
        )

        modified_content = self.latex_content

        for boundary in sorted_boundaries:
            page_num = boundary["page_number"]
            position = boundary["latex_position"]

            # Insert page marker at the position
            marker = f"\n% END OF PAGE {page_num}\n"

            # Insert the marker at the calculated position
            if position < len(modified_content):
                modified_content = (
                    modified_content[: position + 1]
                    + marker
                    + modified_content[position + 1 :]
                )

        return modified_content


def find_longest_increasing_subsequence(boundaries: List[Dict]) -> List[Dict]:
    """Find the longest increasing subsequence of LaTeX positions."""
    if not boundaries:
        return []

    # Sort by page number to maintain order
    sorted_boundaries = sorted(boundaries, key=lambda x: x["page_number"])

    n = len(sorted_boundaries)
    if n == 0:
        return []

    # dp[i] stores the length of LIS ending at index i
    dp = [1] * n
    # parent[i] stores the previous index in the LIS ending at i
    parent = [-1] * n

    # Fill dp array
    for i in range(1, n):
        for j in range(i):
            # Check if latex_position is increasing
            if (
                sorted_boundaries[j]["latex_position"]
                < sorted_boundaries[i]["latex_position"]
                and dp[j] + 1 > dp[i]
            ):
                dp[i] = dp[j] + 1
                parent[i] = j

    # Find the index with maximum LIS length
    max_length = max(dp)
    max_index = dp.index(max_length)

    # Reconstruct the LIS
    lis_boundaries = []
    current = max_index

    while current != -1:
        lis_boundaries.append(sorted_boundaries[current])
        current = parent[current]

    # Reverse to get correct order
    lis_boundaries.reverse()

    print(f"Original boundaries: {len(boundaries)}")
    print(f"LIS boundaries: {len(lis_boundaries)}")
    print(
        f"Filtered out: {len(boundaries) - len(lis_boundaries)} inconsistent boundaries"
    )

    return lis_boundaries


def main():
    """Main function to run the PDF-LaTeX alignment process."""
    book_name = "data-science-book"
    # book_name = "algorithms"
    # book_name = "assembly"
    # File paths
    pdf_path = (
        f"/home/sysaba1/pdf-2-latex/files/{book_name}_book/inputs/{book_name}.pdf"
    )
    latex_path = (
        f"/home/sysaba1/pdf-2-latex/files/{book_name}_book/inputs/{book_name}.tex"
    )
    output_path = f"/home/sysaba1/pdf-2-latex/files/{book_name}_book/outputs/"

    # Create output directory
    os.makedirs(output_path, exist_ok=True)

    print("Starting PDF-LaTeX alignment process...")
    print(f"PDF file: {pdf_path}")
    print(f"LaTeX file: {latex_path}")

    # Verify files exist
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return

    if not os.path.exists(latex_path):
        print(f"Error: LaTeX file not found at {latex_path}")
        return

    # Open PDF document
    try:
        doc = fitz.open(pdf_path)
        print(f"Successfully opened PDF with {len(doc)} pages")
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return

    # Read LaTeX content
    try:
        with open(latex_path, "r", encoding="utf-8") as f:
            latex_content = f.read()
        print(f"Successfully read LaTeX file ({len(latex_content)} characters)")
    except Exception as e:
        print(f"Error reading LaTeX file: {e}")
        return

    # Initialize extractor
    print("\nExtracting PDF text data...")
    extractor = PDFTextExtractor(skip_first_block=True)

    try:
        spans = extractor.extract_document_text(doc)
        print(f"Extracted {len(spans)} text spans from PDF")

        # Save extracted spans
        spans_output_path = os.path.join(output_path, "extracted_spans.json")
        extractor.save_to_file(spans, spans_output_path)
        print(f"Saved extracted spans to: {spans_output_path}")

    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return

    # Get page contents
    print("Preparing page contents for alignment...")
    page_contents = []

    MAX_PAGES = 3000  # Limit to first 30 pages for testing

    for page_num in range(min(len(doc), MAX_PAGES)):
        try:
            page_text = extractor.get_page_text_content(spans, page_num)
            page_stats = extractor.get_page_statistics(spans, page_num)

            page_contents.append(
                {
                    "page_number": page_num + 1,  # 1-indexed for display
                    "content": page_text,
                    "character_count": page_stats.get("total_characters", 0),
                    "word_count": page_stats.get("total_words", 0),
                }
            )

            print(
                f"Page {page_num + 1}: {page_stats.get('total_characters', 0)} chars, "
                f"{page_stats.get('total_words', 0)} words"
            )

        except Exception as e:
            print(f"Error processing page {page_num + 1}: {e}")
            continue

    # Process LaTeX document
    print("\nProcessing LaTeX document...")
    try:
        latex_processor = LatexProcessor()
        latex_processor.process_latex_document(latex_content)
        print(
            f"Processed LaTeX document: {len(latex_processor.plain_text)} plain text characters"
        )

        # print(f"Sample of processed LaTeX text:")
        # print(
        #     latex_processor.plain_text[:1000]
        # )  # Print the first 500 characters as a sample

        # Save processed LaTeX for debugging
        latex_debug_path = os.path.join(output_path, "processed_latex.txt")
        with open(latex_debug_path, "w", encoding="utf-8") as f:
            f.write(latex_processor.plain_text)
        print(f"Saved processed LaTeX text to: {latex_debug_path}")

    except Exception as e:
        print(f"Error processing LaTeX: {e}")
        import traceback

        traceback.print_exc()
        return

    # Add PDF pages to processor
    print("\nAdding PDF pages to processor...")
    for page_info in page_contents:
        if page_info["content"].strip():  # Only add non-empty pages
            latex_processor.add_pdf_page(page_info["content"], page_info["page_number"])
            # print(
            #     f"Added page {page_info['page_number']} "
            #     f"({page_info['character_count']} chars)"
            # )

    # Find page boundaries
    print("\nFinding page boundaries in LaTeX...")
    try:
        boundaries = latex_processor.find_page_boundaries()
        print(f"Found {len(boundaries)} page boundaries")

        # Save original boundary information
        boundaries_path = os.path.join(output_path, "page_boundaries_raw.json")
        with open(boundaries_path, "w", encoding="utf-8") as f:
            json.dump(boundaries, f, indent=2)
        print(f"Saved raw boundary information to: {boundaries_path}")

        # Find longest increasing subsequence
        print("\nFiltering boundaries using longest increasing subsequence...")
        filtered_boundaries = find_longest_increasing_subsequence(boundaries)

        # Save filtered boundaries
        filtered_boundaries_path = os.path.join(output_path, "page_boundaries.json")
        with open(filtered_boundaries_path, "w", encoding="utf-8") as f:
            json.dump(filtered_boundaries, f, indent=2)
        print(f"Saved filtered boundary information to: {filtered_boundaries_path}")

        # Use filtered boundaries for page markers
        boundaries = filtered_boundaries

    except Exception as e:
        print(f"Error finding page boundaries: {e}")
        import traceback

        traceback.print_exc()
        return

    # Insert page markers
    print("\nInserting page markers into LaTeX...")
    try:
        marked_latex = latex_processor.insert_page_markers(boundaries)

        # Save marked LaTeX
        output_latex_path = os.path.join(
            output_path, f"{book_name}_with_page_markers.tex"
        )
        with open(output_latex_path, "w", encoding="utf-8") as f:
            f.write(marked_latex)
        print(f"Saved LaTeX with page markers to: {output_latex_path}")

    except Exception as e:
        print(f"Error inserting page markers: {e}")
        import traceback

        traceback.print_exc()
        return

    # Generate summary
    print("\nGenerating summary report...")
    try:
        summary = {
            "pdf_file": pdf_path,
            "latex_file": latex_path,
            "total_pages": len(doc),
            "total_spans": len(spans),
            "total_boundaries_found": len(boundaries),
            "output_files": {
                "marked_latex": output_latex_path,
                "extracted_spans": spans_output_path,
                "page_boundaries": boundaries_path,
                "processed_latex": latex_debug_path,
            },
            "page_statistics": page_contents,
        }

        summary_path = os.path.join(output_path, "alignment_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"Saved alignment summary to: {summary_path}")

    except Exception as e:
        print(f"Error generating summary: {e}")

    # Close PDF document
    doc.close()

    print("\n" + "=" * 60)
    print("PDF-LaTeX ALIGNMENT COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print(f"✓ Processed {len(doc)} PDF pages")
    print(f"✓ Found {len(boundaries)} page boundaries")
    print(f"✓ Generated LaTeX with page markers")
    print(f"✓ All output files saved to: {output_path}")
    print("\nCheck the output directory for:")
    print("  - data-science-book_with_page_markers.tex (main output)")
    print("  - alignment_summary.json (process summary)")
    print("  - extracted_spans.json (PDF text data)")
    print("  - page_boundaries.json (boundary information)")


if __name__ == "__main__":
    main()
