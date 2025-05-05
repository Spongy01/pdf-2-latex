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
        model="gpt-4o",
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
    response = generate_response(combined_data, command, "")
    response = remove_latex_and_ticks(response)

    return index, response, page

def format_with_gpt(book_path=None, tex_path=None, output_tex_file=None, batch_size=5, max_parts=None, use_parallel=True):
    """Main function to process the book and convert it to properly formatted LaTeX."""
    # Set default paths if not provided
    book_path = book_path or "../../files/data-science_book/data-science.pdf"
    tex_path = tex_path or "../../files/data-science_book/outputs/data-science_pg_sep_bib.tex"
    output_tex_file = output_tex_file or "../../files/data-science_book/outputs/data-science_cleaned_2p__toc.tex"
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
        book_page_data[i] = page.get_text("text").replace("\n", " ")
    
    # If max_parts is specified, limit the number of parts to process
    if max_parts:
        parts = min(max_parts, len(page_breaks))
    else:
        parts = len(page_breaks)
    
    # Define prompt templates from the document
    first_page_command = """
You will receive an unformatted LaTeX (.tex) file part of a book along with a separate JSON file containing formatting instructions.  
Your task is to format the LaTeX file part according to the JSON data while ensuring proper structure and presentation for a book.  

### **Formatting Guidelines:**  

**1. Apply JSON Formatting Instructions:**  
   - Modify only the necessary parts based on JSON data.  
   - Do **not** make arbitrary changes—only apply specified formatting corrections.  

**2. Book Structure:**  
   - The given tex file considers the document as an article, but you need to treat it as a book in the imports section as well as the actual data.
   - Add a usepackage command for indexing, makeidx and \makeindex in the import section
   - Generate table of contents dynamically.
   - Organize content into proper **chapters, sections, and subsections** 
   - **Do not assume chapter starts based on recurring text** (e.g., headers repeated on every page).  
   - If chapter names and numbers appear on every page in the JSON, **ignore them** when determining chapter breaks.  
   - **Remove hardcoded numbering** for chapters and sections, allowing LaTeX to handle it automatically.  
   - Make the Contents Page dynamically if contents is present in the .tex file part. Do not hardcode the table of contents.

**3. Image Handling:**  
   - Convert all instances of `\includegraphics{}` into a proper `figure` environment:  

**4. Table Formatting:**  
   - Ensure tables are properly structured with appropriate spacing, alignment, and captions for readability.  

**5. Italics Handling:**  
   - Apply italics **only** to content explicitly marked as italicized in the JSON data.  

**6. Document Setup:**  
   - This is the **first part of the book**, so include **all necessary LaTeX imports and the document class**.  
   - **Do not modify LaTeX package imports unless explicitly required in the JSON file.** 
   - Do **not** manually start or end the document unless such commands are explicitly present.  

**7. Strict Output Requirements:**  
   - The output **must be pure LaTeX code**—**no explanations, comments, or markdown syntax.**  
   - The formatted output will be **directly appended** to the `.tex` file, so it must be immediately compilable.  

**8. Accuracy and Consistency:**  
   - Since the book is processed in parts, formatting should be **consistent across all sections**.  
   - **Do not introduce new formatting styles** that conflict with previous or upcoming sections.  
   - Ensure that all content is preserved and formatted correctly—no missing text, no misinterpretations.  

**Final Note:**  
Errors in formatting can **significantly affect the compiled document.** Ensure precise execution of all instructions while preserving the document's original meaning and intent.  
  
"""

    next_pages_prompt = """
You will receive a portion of a LaTeX (.tex) file part of a book along with a separate JSON file containing formatting instructions.  
Your task is to format this LaTeX file part according to the provided JSON data while maintaining consistency with previous sections.  

### **Formatting Guidelines:**  

**1. Apply JSON Formatting Instructions:**  
   - Modify only the necessary parts as specified in the JSON data.  
   - Do **not** assume formatting—only apply explicit corrections.  

**2. Maintain Book Structure:**
   - The given tex file considers the document as an article, but you need to treat it as a book in the actual data.
   - Organize content into proper **chapters, sections, and subsections** only if explicitly marked in the `.tex` file.  
   - **Do not assume chapter starts based on recurring text** (e.g., headers repeated on every page).  
   - If chapter names and numbers appear on every page in the JSON, **ignore them** when determining chapter breaks.  
   - **Remove hardcoded numbering** on chapters, sections and subsections and rely on LaTeX's automatic numbering system strictly.
   - Dont use * tags like \section*{section name} as they remove the latex numbering system.  
   - Make the Contents Page dynamically if contents is present in the .tex file part. Do not hardcode the table of contents.
**3. Image Handling:**  
   - Convert `\includegraphics{}` into a properly formatted `figure` environment:  


**4. Table Formatting:**  
   - Ensure tables are properly structured, aligned, and formatted for readability.  

**5. Italics Handling:**  
   - Apply italics **only** to content explicitly marked as italicized in the JSON data.  

**6. Document Integrity:**  
   - **Do not add any LaTeX preamble, document class, or import statements.**  
   - **Do not modify LaTeX package imports unless explicitly required in the JSON file.** 
   - **Do not include `\begin{document}` or `\end{document}`** unless explicitly present in the provided `.tex` file.  

**7. Strict Output Requirements:**  
   - The output **must be pure LaTeX code**—no explanations, comments, or markdown syntax.  
   - The formatted output will be **directly appended** to an existing `.tex` file, so it must be immediately compilable.  

**8. Accuracy and Consistency:**  
   - Ensure formatting is **consistent with previous sections** of the book.  
   - **Do not introduce new formatting styles** that conflict with earlier parts.  
   - Ensure **all content is retained**, formatted correctly, and adheres to the document's original intent.  

**Final Note:**  
Errors in formatting can **significantly impact the final compiled document.** Follow the instructions precisely to maintain a high-quality, structured LaTeX book.  

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
                end_idx = page_numbers.index(page)
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
                        index, response, page = future.result()
                        responses_dict[index] = (response, page)
                    futures_list = []  # Clear batch
                    
                    # Add a small delay to avoid rate limits
                    time.sleep(2)
            
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
            end_idx = page_numbers.index(page)
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