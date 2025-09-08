import pymupdf
import json
from tqdm import tqdm
from openai import OpenAI
import copy
import re
import io
import os
import sys
import time
import fitz
from pdf2image import convert_from_path
from PIL import Image
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

def flags_decomposer(flags):
    """Make font flags human readable."""
    l = []
    if flags & 2 ** 0:
        l.append("superscript")
    if flags & 2 ** 1:
        l.append("italic")
    if flags & 2 ** 2:
        l.append("serifed")
    else:
        l.append("sans")
    if flags & 2 ** 3:
        l.append("monospaced")
    else:
        l.append("proportional")
    if flags & 2 ** 4:
        l.append("bold")
    return ", ".join(l)

def get_page_text_data(page_number, span_counter, text_data, doc):
    """Extract text data from a PDF page with formatting information."""
    page = doc[page_number]
    blocks = page.get_text("dict", flags=0)["blocks"]
    line_number_in_page = 0
    span_number_in_page = 0
    
    for block_number, b in enumerate(blocks):
        span_number_in_block = 0
        
        for l in b["lines"]:
            line_number_in_page += 1
            span_number_in_line = 0
            
            for s in l["spans"]:
                span_data = copy.deepcopy(s)
                
                # Remove unnecessary properties
                del span_data["size"]
                del span_data["bidi"]
                del span_data["char_flags"]
                del span_data["ascender"]
                del span_data["descender"]
                del span_data['origin']
                del span_data['bbox']
                del span_data['color']
                del span_data['font']
                
                # Add formatting information
                decomposed_flags = flags_decomposer(span_data["flags"])
                span_data["is_italic"] = "italic" in decomposed_flags
                span_data["is_bold"] = "bold" in decomposed_flags
                span_data["is_superscript"] = "superscript" in decomposed_flags
                
                del span_data["flags"]
                
                # Append the data
                text_data.append(span_data)
                
                # Update counters
                span_counter += 1
                span_number_in_line += 1
                span_number_in_block += 1
                span_number_in_page += 1
                
    return text_data, span_counter

def get_pages_data(start_idx, end_idx, doc):
    """Get text data for a range of pages."""
    text_data = []
    span_counter = 0
    for i in range(start_idx, end_idx+1):
        text_data, span_counter = get_page_text_data(i, span_counter, text_data, doc)
    return text_data

def generate_response(data, command, prev_response="", temperature=1):
    """Generate response from OpenAI API."""
    first_page_prompt = f"{data} \n {command}"
    default_page_prompt = f"{data} \n {command}"
    prompt_content = first_page_prompt if prev_response == "" else default_page_prompt
    
    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. You convert PDF documents to LaTeX."},
            {"role": "user", "content": f"{prompt_content}"}
        ],
        temperature=temperature
    )
    return response.choices[0].message.content

def remove_latex_and_ticks(text):
    """Remove LaTeX code block markers."""
    return re.sub(r'```latex|```', '', text)

def process_part(index, start_idx, end_idx, tex_start_pos, tex_end_pos, counter, first_part, parts, page, doc, tex_file_contents, first_page_command, next_pages_prompt):
    """Process a part of the book and generate LaTeX for it."""
    text_data = get_pages_data(start_idx, end_idx, doc)
    tex_contents = tex_file_contents[tex_start_pos:tex_end_pos]

    # Construct the combined data for API call
    combined_data = (
        "Below is pre-generated TeX code without proper formatting.\n\n"
        f"{tex_contents}\n\n"
        "Below is the JSON data which contains formatting:\n\n"
        f"{text_data}"
    )
    
    if counter == parts-1:
        combined_data += "\n\nThis was the last part, close the LaTeX document with end document. Before that, make an index using \\makeindex command and similarly make a bibliography."
    else:
        combined_data += f"\n\nThis is the {counter} part of the book, do not close the LaTeX document with end document"

    command = first_page_command if first_part == 1 else next_pages_prompt
    try:
        response = generate_response(combined_data, command, "")
    except Exception as e:
        print(f"[ERROR] Error generating response for part {index}, page {page}: {e}")
        response = ""
    response = remove_latex_and_ticks(response)

    return index, response, page

def format_with_gpt(book_path=None, tex_path=None, output_tex_file=None, batch_size=5, max_parts=None, use_parallel=True):
    """Main function to process the book and convert it to properly formatted LaTeX."""
    # Set default paths if not provided
    print("\n=== Step 3: Formatting with GPT ===")
    # Load environment variables for API key
    load_dotenv()
    api_key = os.getenv("API_KEY")
    
    global client
    client = OpenAI(api_key=api_key)
    
    # Clear the output file if it exists
    with open(output_tex_file, 'w') as f:
        pass
    
    # Open the PDF document
    doc = pymupdf.open(book_path)
    toc = pymupdf.open(book_path)
    table_of_contents = toc.get_toc()
    
    # Read the LaTeX file
    with open(tex_path, 'r') as file:
        tex_file_contents = file.read()
    
    # Get page breaks and their positions
    page_breaks = re.findall(r'%---- Page End Break Here ---- Page : (\d+)', tex_file_contents)
    page_positions = {int(page): pos.start() for page, pos in zip(page_breaks, re.finditer(r'%---- Page End Break Here ---- Page : \d+', tex_file_contents))}
    
    # Get all page numbers in the book
    book_page_data = {}
    page_numbers = []
    for i in range(len(doc)):
        page = doc[i]
        page_numbers.append(page.get_label())
        if page.get_label() is None or not page.get_label().isdigit():
            page_numbers[i] = i + 1
        book_page_data[i] = page.get_text("text").replace("\n", " ")
    print("Total Pages in Book: ", len(book_page_data))
    print("Total Pages in LaTeX: ", len(page_breaks))
    # print(book_page_data)
    # If max_parts is specified, limit the number of parts to process
    if max_parts:
        parts = min(max_parts, len(page_breaks))
    else:
        parts = len(page_breaks)
    
    # Define prompt templates from the document
    first_page_command = r"""
You will receive an unformatted LaTeX (.tex) segment from the beginning of a book, along with a JSON array containing formatting metadata for that segment.

Each JSON object represents a span of text with:
- `text`: the content
- `is_italic`, `is_bold`, `is_superscript`: formatting flags

Your task is to apply the formatting **strictly as specified in the JSON**, and restructure the LaTeX file into a **compilable, clean, book-style format**.

### Formatting Instructions:

1. **Apply JSON Formatting**
   - Only apply formatting (`\textit`, `\textbf`, etc.) when the JSON flags require it.
   - Do NOT guess or infer formatting.

2. **Document Setup**
   - Treat the document as a book, not an article.
   - Add `\documentclass{book}` and appropriate `\usepackage` lines (e.g., `makeidx`).
   - Include `\makeindex`, `\tableofcontents`, and `\begin{document}` at the start.

3. **Structure**
   - Use `\chapter`, `\section`, `\subsection` only if already indicated in the `.tex` input.
   - Remove hardcoded numbers like "Chapter 1", "Section 1.1" — let LaTeX number them.
   - Do NOT create chapters based on repeated headers in the JSON.

4. **Images**
   - Replace all `\includegraphics{...}` calls with a full `figure` environment.
   - Add `\caption{}` if an image caption is present near it.

5. **Tables**
   - Reformat any visible tables into LaTeX `tabular` environments with clean alignment.

6. **Math & Escaping**
   - Use math mode (`$...$`) for anything with subscripts like `PK_A`, `SK_B`, etc.
   - Escape characters like `_`, `#`, `%`, `&`, `\`.

7. **Output Format**
   - Output must be **pure LaTeX only**.
   - **DO NOT include markdown, explanations, triple backticks, or comments.**
   - Your output will be directly compiled. It must be clean, valid LaTeX.

8. **Accuracy & Completeness**
   - Keep all text from the original intact.
   - Maintain structural and formatting consistency across all parts of the book.

---

**❗ FINAL REMINDER: Output ONLY valid LaTeX. No explanations, comments, or markdown.\n Only output corresponding data which is in latex. In many instances you will have more text data in json format than what is in latex. Ignore that.**

"""

    next_pages_prompt = r"""
You will receive a middle or later segment of an unformatted LaTeX (.tex) file along with a JSON array containing formatting metadata.

Your job is to **format this `.tex` content** using the JSON span information, maintaining consistency with earlier sections of the book.

Each JSON span has:
- `text`
- `is_italic`, `is_bold`, `is_superscript`

### Formatting Instructions:

1. **Formatting from JSON**
   - Only apply italics, bold, superscripts when marked in JSON.
   - Do NOT apply formatting by guessing or inference.

2. **Book Structure**
   - Use `\chapter`, `\section`, `\subsection` **only if already present** in the `.tex` input.
   - Do NOT guess chapter breaks based on page headers or repeated titles.
   - Strip hardcoded numbering from headings (e.g., "1 Introduction" → `\section{Introduction}`).
   - DO NOT use `\section*` — allow LaTeX to number everything.

3. **Figures & Tables**
   - Wrap each `\includegraphics{...}` in a `figure` environment.
   - Format any visible table-like structures into readable LaTeX tables.

4. **Math & Special Characters**
   - Use `$...$` for math expressions like `PK_A`, `SK_B`, `x_1`.
   - Escape `_`, `%`, `#`, `&`, `\`, and similar LaTeX-sensitive characters.

5. **Document Boundaries**
   - Do NOT add `\documentclass`, `\usepackage`, `\begin{document}`, or `\end{document}`.
   - Only format what’s in the given file segment.

6. **Output Requirements**
   - Output must be **pure LaTeX code**, ready to be appended to an existing file.
   - **No Markdown**, no explanations, no code block markers (e.g., ```latex), no comments.

7. **Consistency**
   - Formatting style must match previous parts.
   - Do NOT introduce any new structural or styling changes.

---

**❗ FINAL REMINDER: Output ONLY valid LaTeX. No explanations, comments, or markdown.\n Only output corresponding data which is in latex. In many instances you will have more text data in json format than what is in latex. Ignore that.**

"""
    
    if use_parallel:
        # Parallel processing with batching
        start_idx = 0
        tex_start_pos = 0
        first_part = 1
        counter = 1
        responses_dict = {}  # Store responses by index
        
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures_list = []  # Store pending API calls
            
            print(f"Processing {parts} parts with parallel execution (batch size: {batch_size})...")

            for idx, page in enumerate(tqdm(page_breaks[:parts])):
                try: 
                    end_idx = page_numbers.index(int(page))
                    tex_end_pos = page_positions[int(page)]                    
                    # Submit task to thread pool
                    future = executor.submit(
                        process_part, 
                        idx, 
                        start_idx, 
                        end_idx, 
                        tex_start_pos, 
                        tex_end_pos, 
                        counter, 
                        first_part, 
                        parts, 
                        page, 
                        doc, 
                        tex_file_contents,
                        first_page_command,
                        next_pages_prompt
                    )
                    futures_list.append(future)
                    
                    # Update positions for next iteration
                    tex_start_pos = tex_end_pos + 1
                    start_idx = end_idx + 1
                    first_part = 0
                    counter += 1
                    # Process completed futures when batch is full
                    if len(futures_list) >= batch_size:
                        for future in tqdm(as_completed(futures_list), desc="Processing batch"):
                            try:
                                index, response, page = future.result()
                                responses_dict[index] = (response, page)
                            except Exception as e:
                                print(f"[ERROR] Error while processing future: {e}")
                                print(f"print")
                        futures_list = []  # Clear batch
                        
                        time.sleep(2)

                except Exception as e:
                    print(f"[ERROR] Error during iteration {idx} for page {page}: {e}")

            # Process any remaining futures
            for future in tqdm(as_completed(futures_list), desc="Processing remaining"):
                index, response, page = future.result()
                responses_dict[index] = (response, page)
        
        # Write responses in order
        print("Writing results to output file...")
        with open(output_tex_file, 'a') as f:
            for index in sorted(responses_dict.keys()):
                response, page = responses_dict[index]
                f.write(response + "\n")
                f.write(f"%---- Page End Break Here ---- Page : {page}\n")
                
    else:
        # Sequential processing
        start_idx = 0
        tex_start_pos = 0
        first_part = 1
        counter = 1
        
        print(f"Processing {parts} parts sequentially...")
        
        for page in tqdm(page_breaks[:parts]):
            end_idx = page_numbers.index(int(page))
            text_data = get_pages_data(start_idx, end_idx, doc)
            
            tex_end_pos = page_positions[int(page)]
            tex_contents = tex_file_contents[tex_start_pos:tex_end_pos]
            
            # Prepare data for API call
            combined_data = (
                "Below is pre-generated TeX code without proper formatting.\n\n"
                f"{tex_contents}\n\n"
                "Below is the JSON data which contains formatting:\n\n"
                f"{text_data}"
            )
            
            if counter == parts:
                combined_data += "\n\nThis was the last part, close the LaTeX document with end document. Before that, make an index using \\makeindex command and similarly make a bibliography."
            else:
                combined_data += f"\n\nThis is the {counter} part of the book, do not close the LaTeX document with end document."
            
            command = first_page_command if first_part == 1 else next_pages_prompt
            response = generate_response(combined_data, command, "")
            response = remove_latex_and_ticks(response)
            
            # Write to output file
            with open(output_tex_file, 'a') as f:
                f.write(response + "\n")
                f.write(f"%---- Page End Break Here ---- Page : {page}\n")
            
            # Update positions for next iteration
            tex_start_pos = tex_end_pos + 1
            start_idx = end_idx + 1
            first_part = 0
            counter += 1
    
    print(f"Conversion complete! Output file saved at: {output_tex_file}")
    return output_tex_file


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert PDF books to properly formatted LaTeX")
    parser.add_argument("--book", type=str, help="Path to the PDF book file")
    parser.add_argument("--tex", type=str, help="Path to the input LaTeX file")
    parser.add_argument("--output", type=str, help="Path for the output LaTeX file")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size for parallel processing")
    parser.add_argument("--max-parts", type=int, help="Maximum number of parts to process")
    parser.add_argument("--sequential", action="store_true", help="Use sequential processing instead of parallel")
    
    args = parser.parse_args()
    
    format_with_gpt(
        book_path=args.book,
        tex_path=args.tex,
        output_tex_file=args.output,
        batch_size=args.batch_size,
        max_parts=args.max_parts,
        use_parallel=not args.sequential
    )