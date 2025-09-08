import json
import fitz  # PyMuPDF
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
from enum import IntFlag


class FontFlags(IntFlag):
    """Enum for font flags to make them more readable and maintainable."""

    SUPERSCRIPT = 2**0
    ITALIC = 2**1
    SERIFED = 2**2
    MONOSPACED = 2**3
    BOLD = 2**4


@dataclass
class SpanStyle:
    """Data class for span styling information."""

    is_italic: bool = False
    is_bold: bool = False
    is_superscript: bool = False
    is_serifed: bool = False
    is_monospaced: bool = False


@dataclass
class BoundingBox:
    """Data class for bounding box coordinates."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass
class SpanData:
    """Data class for text span information."""

    text: str
    font: str
    size: float
    flags: int
    bbox: BoundingBox
    page_number: int
    block_number: int
    line_number: int
    span_number: int
    span_number_overall: int
    style: SpanStyle
    color: Optional[int] = None

    @property
    def is_whitespace_only(self) -> bool:
        """Check if span contains only whitespace."""
        return self.text.strip() == ""

    @property
    def char_count(self) -> int:
        """Get character count of the span."""
        return len(self.text)


class PDFTextExtractor:
    """Enhanced PDF text extractor."""

    def __init__(self, skip_first_block: bool = True):
        self.skip_first_block = skip_first_block
        self.span_counter = 0

    def decompose_flags(self, flags: int) -> SpanStyle:
        """Convert PyMuPDF flags to readable style information."""
        return SpanStyle(
            is_superscript=bool(flags & FontFlags.SUPERSCRIPT),
            is_italic=bool(flags & FontFlags.ITALIC),
            is_bold=bool(flags & FontFlags.BOLD),
            is_serifed=bool(flags & FontFlags.SERIFED),
            is_monospaced=bool(flags & FontFlags.MONOSPACED),
        )

    def extract_span_data(
        self,
        span_dict: Dict[str, Any],
        page_number: int,
        block_number: int,
        line_number: int,
        span_number: int,
    ) -> SpanData:
        """Extract and structure span data from PyMuPDF span dictionary."""
        bbox = BoundingBox(*span_dict["bbox"])
        style = self.decompose_flags(span_dict["flags"])

        self.span_counter += 1

        return SpanData(
            text=span_dict["text"],
            font=span_dict["font"],
            size=span_dict["size"],
            flags=span_dict["flags"],
            bbox=bbox,
            page_number=page_number,
            block_number=block_number,
            line_number=line_number,
            span_number=span_number,
            span_number_overall=self.span_counter,
            style=style,
            color=span_dict.get("color"),
        )

    def extract_page_text(self, doc, page_number: int) -> List[SpanData]:
        """Extract structured text data from a single page."""
        page = doc[page_number]
        blocks = page.get_text("dict", flags=0)["blocks"]

        page_spans = []
        start_block = 1 if self.skip_first_block and len(blocks) > 1 else 0

        for block_number, block in enumerate(blocks[start_block:], start=start_block):
            if "lines" not in block:
                continue

            for line_number, line in enumerate(block["lines"]):
                for span_number, span in enumerate(line["spans"]):
                    span_data = self.extract_span_data(
                        span, page_number, block_number, line_number, span_number
                    )
                    page_spans.append(span_data)

        return page_spans

    def extract_document_text(self, doc) -> List[SpanData]:
        """Extract structured text data from entire document."""
        all_spans = []

        for page_number in range(len(doc)):
            page_spans = self.extract_page_text(doc, page_number)
            all_spans.extend(page_spans)

        return all_spans

    def get_page_text_content(self, spans: List[SpanData], page_number: int) -> str:
        """Get plain text content for a specific page."""
        page_spans = [span for span in spans if span.page_number == page_number]
        return "".join(span.text for span in page_spans)

    def get_page_statistics(
        self, spans: List[SpanData], page_number: int
    ) -> Dict[str, Any]:
        """Get statistics for a specific page."""
        page_spans = [span for span in spans if span.page_number == page_number]

        if not page_spans:
            return {}

        total_chars = sum(span.char_count for span in page_spans)
        total_words = sum(len(span.text.split()) for span in page_spans)

        return {
            "page_number": page_number,
            "total_spans": len(page_spans),
            "total_characters": total_chars,
            "total_words": total_words,
        }

    def save_to_file(self, spans: List[SpanData], filename: str) -> None:
        """Save spans to JSON file."""
        spans_dict = [asdict(span) for span in spans]
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(spans_dict, f, indent=2, default=str)
