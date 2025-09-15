import json
import os
import re
import string
import fitz  # PyMuPDF
from dataclasses import dataclass, asdict
from tqdm import tqdm
from typing import List, Dict, Any, Optional, Tuple
from pdf_text_extractor import PDFTextExtractor


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
                # print(f"Node pos: {node.pos}, chars: '{node.chars}', offset: {offset}")
                # print(
                #     f"Adding positions: {node.pos + offset} to {node.pos + offset + len(node.chars)}"
                # )
                # write these to a file for debugging
                # with open(
                #     "files/data-science-book_book/outputs/latex_positions_debug.txt",
                #     "a",
                #     encoding="utf-8",
                # ) as f:
                #     f.write(
                #         f"Node pos: {node.pos}, chars: '{node.chars}', offset: {offset}\n"
                #     )
                #     f.write(
                #         f"Adding positions: {node.pos + offset} to {node.pos + offset + len(node.chars)}\n"
                #     )
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

            # # save document_content for debugging
            # with open(
            #     "files/algorithms_book/outputs/document_content.tex",
            #     "w",
            #     encoding="utf-8",
            # ) as f:
            #     f.write(document_content)

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
        OUTPUT_DIR: str = "",
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
        output_dir = OUTPUT_DIR if OUTPUT_DIR else "."
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

    def find_page_boundaries(self, OUTPUT_DIR) -> List[Dict]:
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
                        OUTPUT_DIR=OUTPUT_DIR,
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
        """Insert page end markers into the LaTeX document after the next natural break."""
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

            # Find the next natural break point after the position
            break_position = self._find_next_break_point(modified_content, position)

            # Insert page marker at the break position
            marker = "\n%---- Page End Break Here ---- Page : " + str(page_num) + "\n"

            if break_position < len(modified_content):
                modified_content = (
                    modified_content[:break_position]
                    + marker
                    + modified_content[break_position:]
                )

        return modified_content

    def _find_next_break_point(self, content: str, start_position: int) -> int:
        """Find the next \\\\ or \\n\\n after the given position."""
        if start_position >= len(content):
            return len(content)

        # Search for the next occurrence of either pattern
        search_start = start_position + 1

        # Find next \\\\
        double_backslash = content.find("\\\\", search_start)

        # Find next \\n\\n
        double_newline = content.find("\n\n", search_start)

        # Choose whichever comes first (ignore -1 results)
        candidates = []
        if double_backslash != -1:
            candidates.append(double_backslash + 2)  # Position after \\\\
        if double_newline != -1:
            candidates.append(double_newline + 2)  # Position after \\n\\n

        if candidates:
            return min(candidates)
        else:
            # No break found, insert at end of content
            return len(content)


def find_longest_increasing_subsequence(boundaries: List[Dict]) -> List[Dict]:
    """Find the longest increasing subsequence of LaTeX positions."""
    if not boundaries:
        return []

    # Sort by page number to maintain order
    sorted_boundaries = boundaries.copy()

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


def create_page_separators(BOOK_PATH, TEX_PATH, OUTPUT_TEX_PATH, OUTPUT_DIR):
    """Create page separators with v1 interface and v2 processing."""
    print("\n=== 🛠️ Step 1: Creating Page Separators ===")

    # Read files
    print(f"🔍 Reading book from: {BOOK_PATH}")
    print(f"🔍 Reading LaTeX from: {TEX_PATH}")

    try:
        book_pdf = fitz.open(BOOK_PATH)
        with open(TEX_PATH, "r", encoding="utf-8") as f:
            latex_content = f.read()
        print("✅ Successfully read PDF and LaTeX files.\n")
    except Exception as e:
        print(f"Error reading files: {e}")
        return None, None, None

    # Extract text from PDF pages with proper labeling (v1 approach)
    print("📄 Extracting text from PDF pages...\n")
    book_page_data = {}
    page_numbers = []

    for i in range(len(book_pdf)):
        page = book_pdf[i]
        label = page.get_label()
        # if label is None or not label.isdigit():
        #     label = i + 1
        label = i + 1
        page_numbers.append(label)
        text = page.get_text("text").replace("\n", " ")
        book_page_data[i] = text
        # print(f"📄 Page {i} (Label: {label}) text length: {len(text)}")

    # Initialize advanced extractor for more detailed processing
    print("\n🔧 Starting advanced pattern matcher...")
    extractor = PDFTextExtractor(skip_first_block=True)

    try:
        spans = extractor.extract_document_text(book_pdf)
        print(f"Extracted {len(spans)} text spans from PDF")
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return book_pdf, latex_content, page_numbers

    # Process LaTeX document
    print("Processing LaTeX document...")
    try:
        latex_processor = LatexProcessor()
        latex_processor.process_latex_document(latex_content)
        print(
            f"Processed LaTeX document: {len(latex_processor.plain_text)} plain text characters"
        )
    except Exception as e:
        print(f"Error processing LaTeX: {e}")
        return book_pdf, latex_content, page_numbers

    # Use the page labels from the extraction loop for alignment
    print("Adding PDF pages to processor...")
    for i in range(len(book_pdf)):
        page_content = book_page_data[i]
        page_label = page_numbers[i]

        if page_content.strip():  # Only add non-empty pages
            latex_processor.add_pdf_page(page_content, page_label)

    # Find page boundaries
    print("Finding page boundaries in LaTeX...")
    try:
        boundaries = latex_processor.find_page_boundaries(OUTPUT_DIR)
        print(f"Found {len(boundaries)} page boundaries")

        # Filter using longest increasing subsequence
        filtered_boundaries = find_longest_increasing_subsequence(boundaries)
        print(f"Using {len(filtered_boundaries)} consistent boundaries")
        # save boundaries to json for debugging
        with open(
            f"{OUTPUT_DIR}/page_boundaries.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(filtered_boundaries, f, indent=4)

    except Exception as e:
        print(f"Error finding page boundaries: {e}")
        return book_pdf, latex_content, page_numbers

    # Insert page markers
    print("Inserting page markers into LaTeX...")
    try:
        new_latex_content = latex_processor.insert_page_markers(filtered_boundaries)

        # Save to output file
        os.makedirs(os.path.dirname(OUTPUT_TEX_PATH), exist_ok=True)
        with open(OUTPUT_TEX_PATH, "w", encoding="utf-8") as file:
            file.write(new_latex_content)

        print(f"\n✅ Page Breaks inserted and written to:\n\t📁 {OUTPUT_TEX_PATH}")

    except Exception as e:
        print(f"Error inserting page markers: {e}")
        return book_pdf, latex_content, page_numbers

    return book_pdf, new_latex_content, page_numbers


if __name__ == "__main__":
    create_page_separators()
