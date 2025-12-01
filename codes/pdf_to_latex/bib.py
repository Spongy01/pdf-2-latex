# import Levenshtein
import pymupdf
import json
from tqdm import tqdm
from openai import OpenAI
import copy
import io
import os
import sys
import time
import re
import hashlib
import threading
# import fitzs
from pdf2image import convert_from_path
from PIL import Image
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()
api_key = os.getenv("API_KEY")

OPENAI_API_KEY = api_key
# client = OpenAI(api_key=OPENAI_API_KEY)

client = OpenAI(
    organization='org-njwcb70yqPRnJe1N2MK0Bf36',
    project='proj_XqOTFZ0yRIM304plxTavtUzx',
    api_key=OPENAI_API_KEY
)

# Global cache management
cache_lock = threading.Lock()
_global_cache = None
_cache_file = "bib_cache.json"

def get_cache_key(prompt, text, model):
    """Generate a simple hash-based cache key."""
    content = f"{prompt}|{text}|{model}"
    return hashlib.md5(content.encode()).hexdigest()

def load_bib_cache():
    """Load bibliography cache from JSON file with thread safety."""
    global _global_cache
    with cache_lock:
        if _global_cache is None:
            if os.path.exists(_cache_file):
                try:
                    with open(_cache_file, 'r') as f:
                        _global_cache = json.load(f)
                        print(f"📂 Loaded bibliography cache with {len(_global_cache)} entries")
                except Exception as e:
                    print(f"⚠️ Warning: Could not load cache file {_cache_file}: {e}")
                    _global_cache = {}
            else:
                _global_cache = {}
                print(f"📂 Created new bibliography cache")
        return _global_cache

def save_bib_cache():
    """Save bibliography cache to JSON file with thread safety."""
    global _global_cache
    with cache_lock:
        if _global_cache is not None:
            try:
                with open(_cache_file, 'w') as f:
                    json.dump(_global_cache, f, indent=2)
                print(f"💾 Saved bibliography cache with {len(_global_cache)} entries")
            except Exception as e:
                print(f"❌ Error saving cache file {_cache_file}: {e}")
                raise e

def add_to_cache(cache_key, response):
    """Add a response to the global cache."""
    global _global_cache
    with cache_lock:
        if _global_cache is None:
            _global_cache = {}
        _global_cache[cache_key] = response

def get_api_response(prompt, text, model="gpt-5", use_cache=True):
    """
    Get response from OpenAI API with simple caching.
    
    Parameters:
        prompt (str): The prompt to send to the API.
        text (str): Text content to include in the prompt.
        model (str): OpenAI model to use.
        
    Returns:
        str: API response content.
    """
    # Generate cache key
    cache_key = get_cache_key(prompt, text, model)
    
    # Check cache only if enabled
    if use_cache:
        # Load cache (this will initialize global cache if needed)
        cache = load_bib_cache()
        
        # Check if response is cached
        if cache_key in cache:
            print("🎯 Cache HIT - Using cached response for bibliography processing...")
            return cache[cache_key]
    
    # Make API call
    if use_cache:
        print("🚀 Cache MISS - Sending request to OpenAI API...")
    else:
        print("🚀 Cache DISABLED - Sending request to OpenAI API...")
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "developer", "content": "You are a helpful assistant."},
                {"role": "user", "content": f" {prompt}. Here is the text: {text}"}
            ],
            temperature=1
        )
        response = completion.choices[0].message.content
        print("✅ Received response from OpenAI API.")
        
        # Add to global cache only if cache is enabled
        if use_cache:
            add_to_cache(cache_key, response)
            print(f"💾 Added response to cache (will save at end)")
        else:
            print(f"💾 Cache disabled - response not cached")
        
        return response
    except Exception as e:
        print(f"❌ API call failed: {e}")
        raise e

def save_bibtex(bib_dict, filename="references.bib"):
    """
    Saves a dictionary of BibTeX entries to a .bib file.

    Parameters:
        bib_dict (dict): Dictionary where keys are citation keys and values are BibTeX-formatted strings.
        filename (str): The name of the output .bib file (default: 'references.bib').

    Returns:
        None
    """
    with open(filename, "w", encoding="utf-8") as f:
        for entry in bib_dict.values():
            f.write(entry + "\n\n")  # Ensure entries are separated by a blank line

    print(f"BibTeX file saved as {filename}")

def replace_citations(tex_filename, bib_dict, output_filename="updated.tex", bibliography_filename=None):
    r"""
    Replaces citation keys in a LaTeX file with \cite{...} using a dictionary.
    Skips replacements inside \usepackage options and command definitions.
    Also skips replacements before \begin{document} (in the preamble).

    Parameters:
        tex_filename (str): The name of the input .tex file.
        bib_dict (dict): Dictionary where keys are the citation keys in text (e.g., 'Abe13'),
                         and values are the BibTeX citation keys (e.g., 'abela2013advanced').
        output_filename (str): The name of the output file with updated citations (default: 'updated.tex').
        bibliography_filename (str): The name of the bibliography file (without .bib extension) to add to \bibliography{}.
                                     If None, will be derived from output_filename if it's a .bib file path.

    Returns:
        None
    """
    # Read the LaTeX file
    with open(tex_filename, "r", encoding="utf-8") as f:
        tex_content = f.read()
    
    # Find the position of \begin{document} to protect the preamble
    begin_doc_match = re.search(r'\\begin\{document\}', tex_content, re.IGNORECASE)
    preamble_end = begin_doc_match.start() if begin_doc_match else None
    
    # First, identify protected regions where we should NOT replace citations:
    # 1. \usepackage[...] - package options
    # 2. \newcommand, \renewcommand, \providecommand, \DeclareRobustCommand, etc. - command definitions
    # 3. Everything before \begin{document} (preamble)
    protected_ranges = []
    
    # Protect the entire preamble (everything before \begin{document})
    if preamble_end is not None and preamble_end > 0:
        protected_ranges.append((0, preamble_end))
    
    # Pattern for \usepackage[options]{package}
    usepackage_pattern = re.compile(r'\\usepackage\s*(\[[^\]]*\])', re.IGNORECASE)
    for match in usepackage_pattern.finditer(tex_content):
        protected_ranges.append((match.start(1), match.end(1)))
    
    # Pattern for command definitions: \newcommand, \renewcommand, \providecommand, \DeclareRobustCommand
    # These can have: \newcommand\cmd[opt1][opt2]{def} or \newcommand{\cmd}[opt1][opt2]{def}
    # We need to protect ALL optional arguments [opt] and the definition {def}
    # Command name can be: \cmd or {\cmd} or \cmd (directly attached, can include @, numbers, etc.)
    cmd_pattern = re.compile(
        r'\\(?:new|renew|provide|DeclareRobust)command\s*'
        r'(?:\\[^\s\[\{]+|\{[^}]+\})?'  # command name: \cmd (any non-whitespace/non-bracket) or {\cmd}
        r'(?:\[[^\]]*\])*'  # zero or more optional arguments
        r'(\{[^\}]*\})',  # required definition argument
        re.IGNORECASE
    )
    for match in cmd_pattern.finditer(tex_content):
        protected_ranges.append((match.start(1), match.end(1)))
    
    # Find and protect ALL optional arguments in command definitions
    # This pattern finds the command definition start, then captures all [opt] arguments
    cmd_full_pattern = re.compile(
        r'\\(?:new|renew|provide|DeclareRobust)command\s*'
        r'(?:\\[^\s\[\{]+|\{[^}]+\})?'  # command name: \cmd (any non-whitespace/non-bracket) or {\cmd}
        r'((?:\[[^\]]*\])+)',  # one or more optional arguments
        re.IGNORECASE
    )
    for match in cmd_full_pattern.finditer(tex_content):
        # For each match, find all [opt] groups within it
        opt_content = match.group(1)
        start_offset = match.start(1)
        # Find all [opt] patterns within this match
        opt_pattern = re.compile(r'\[[^\]]*\]')
        for opt_match in opt_pattern.finditer(opt_content):
            protected_ranges.append((
                start_offset + opt_match.start(),
                start_offset + opt_match.end()
            ))
    
    # Helper function to check if a position is in a protected range
    def is_protected(pos):
        return any(start <= pos < end for start, end in protected_ranges)
    
    # Helper function to check if a key is purely numeric
    def is_numeric_key(key):
        return key.isdigit()
    
    # For numbered citations, we need to replace [number] with \cite{bibtex_key}
    # For alphanumeric citations (like Abe13), we use word boundary matching
    for key, bibtex_key in bib_dict.items():
        if is_numeric_key(key):
            # For numeric keys, ONLY match when inside square brackets: [1], [34], etc.
            # This avoids replacing page numbers, ISBN digits, section numbers, etc.
            pattern = rf'\[{re.escape(key)}\]'
            matches = list(re.finditer(pattern, tex_content))
            
            # Replace from end to start to maintain positions
            for match in reversed(matches):
                start_pos = match.start()
                # Only replace if not in a protected region
                if not is_protected(start_pos):
                    tex_content = (tex_content[:match.start()] + 
                                 rf'\\cite{{{bibtex_key}}}' + 
                                 tex_content[match.end():])
        else:
            # For alphanumeric keys (like Abe13), use word boundary matching
            pattern = rf'\b{re.escape(key)}\b'
            matches = list(re.finditer(pattern, tex_content))
            
            # Replace from end to start to maintain positions
            for match in reversed(matches):
                start_pos = match.start()
                # Only replace if not in a protected region
                if not is_protected(start_pos):
                    tex_content = (tex_content[:match.start()] + 
                                 rf'\\cite{{{bibtex_key}}}' + 
                                 tex_content[match.end():])

    # Add \bibliographystyle{plain} and \bibliography{filename} before \end{document} if bibliography_filename is provided
    if bibliography_filename:
        # Remove .bib extension if present
        bib_name = bibliography_filename
        if bib_name.endswith('.bib'):
            bib_name = bib_name[:-4]
        
        # Check if \bibliography or \bibliographystyle already exists
        if r'\bibliography{' not in tex_content and r'\bibliographystyle{' not in tex_content:
            # Find \end{document} and insert \bibliographystyle and \bibliography before it
            if r'\end{document}' in tex_content:
                # Insert \bibliographystyle{plain} and \bibliography before \end{document}
                tex_content = re.sub(
                    r'(\\end\{document\})',
                    rf'\\bibliographystyle{{plain}}\n\\bibliography{{{bib_name}}}\n\\1',
                    tex_content
                )
            else:
                # If \end{document} doesn't exist, append at the end
                tex_content += f'\n\\bibliographystyle{{plain}}\n\\bibliography{{{bib_name}}}\n'
        else:
            print(f"⚠️ Warning: \\bibliography or \\bibliographystyle already exists in the file, skipping addition")

    # Save the updated content to a new file
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(tex_content)

    print(f"Updated LaTeX file saved as {output_filename}")


def process_bibliography(pdf_path=None, tex_path=None, output_json_path=None, output_bib_path=None, output_tex_path=None, model="gpt-5", bib_json=None, use_cache=True):
    """
    Process a PDF bibliography and update LaTeX citations.
    
    Parameters:
        pdf_path (str): Path to the PDF file containing bibliography. 
                        Default: 'pdf2latex/data-science-bib.pdf'
        tex_path (str): Path to the LaTeX file to update with citations.
                        Default: "../../files/data-science_book/outputs/data-science_pg_sep.tex"
        output_json_path (str): Path to save the output JSON file.
                               Default: "ds_bib.json"
        output_bib_path (str): Path to save the output BibTeX file.
                              Default: "ds_bib.bib"
        output_tex_path (str): Path to save the updated LaTeX file.
                              Default: "../../files/data-science_book/outputs/data-science_pg_sep_bib.tex"
        model (str): The OpenAI model to use.
                     Default: "gpt-4o"
    
    Returns:
        dict: The citation dictionary mapping original keys to BibTeX keys
    """
    # Use default paths if not provided
    print("\n=== Step 2: Processing Bibliography ===")
    
    # Initialize cache at the beginning
    print("🔄 Initializing bibliography cache...")
    if use_cache:
        load_bib_cache()
        print("✅ Cache enabled - will use existing cache entries")
    else:
        print("⚠️ Cache disabled - will make fresh API calls")
    
    print(f"Processing PDF: {pdf_path}")
    print(f"Using LaTeX file: {tex_path}")
    if bib_json:
        print(f"Using existing JSON file: {bib_json}")
        with open(bib_json, "r") as f:
            ds_bib_dict = json.load(f)
    else:
    # Read PDF using pymupdf
        try:
            pdf_document = pymupdf.open(pdf_path)
            print(f"📄 PDF opened successfully with {len(pdf_document)} pages")
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return None
        
        # Define prompt for page-by-page processing
        prompt = r""" 
 

        I am going to pass the extracted text from a SINGLE PAGE of a PDF file bibliography section. 
        I want you to extract the references mentioned in the bibliography section. This should be a dictionary and the dictionary's keys 
        should be the key given as [something] for the references in the text.

        Some entries may also be in numbered format, like:
        1. Accenture: 2017 Cost of Cyber Crime Study. Tech. rep. (2017). Web publication: https://www.accenture.com/... [Accessed 22-June-2023]

        In these cases, the dictionary key should be the number (e.g., "1", "2", ...), and the value should still be a correct BibTeX entry.
        Use the correct entry type (`@book`, `@techreport`, `@misc`, etc.) based on the format of the reference.

        You can return the bibtex. Create the bibtex format yourself. Understand what the bibtex format should be for each reference and return that as a string. 
        If a URL is present, include it as `url={...}`. If there is an "Accessed" date, include it as `note={Accessed: ...}`.

        Do not hallucinate or make up information. Only use what is in the text.

        Here is an example of a reference and the BibTeX you should return:

        **Example (Bracketed citation):**

        Text:
        [Abe13] Andrew Abela. Advanced Presentations by Design: Creating Communi-
        cation that Drives Action. Pfeiﬀer, 2nd edition, 2013.

        Output:
        {
            "Abe13": "@book{abela2013advanced,\n    title={Advanced presentations by design: Creating communication that drives action},\n    author={Abela, Andrew},\n    year={2013},\n    publisher={Pfeiffer}\n}"
        }

        **Example (Numbered citation):**

        Text:
        1. Accenture: 2017 Cost of Cyber Crime Study. Tech. rep. (2017). Web publication: https://www.accenture.com/_acnmedia/PDF-62/Accenture-2017CostCybercrime-US-FINAL.pdf [Accessed 22-June-2023]

        Output:
        {
            "1": "@techreport{accenture2017cyber,\n  title={2017 Cost of Cyber Crime Study},\n  author={Accenture},\n  year={2017},\n  institution={Accenture},\n  url={https://www.accenture.com/_acnmedia/PDF-62/Accenture-2017CostCybercrime-US-FINAL.pdf},\n  note={Accessed: 22-June-2023}\n}"
        }

        Only and only extract the information from the text I provide. If you are not sure about the information,
        do not make any assumptions. Just return the information as it is.

        What is most important to me is that the citation key is created for each reference. 
        Return ONLY and ONLY the dictionary (in JSON-style), so that I can use it in my code. Do not return any other text.


        Here is the text from this page: """
        
        # Define helper function to process a single page
        def process_page(page_num, page):
            """Process a single page and extract bibliography entries."""
            page_text = page.get_text()
            
            # Skip empty pages
            if not page_text.strip():
                return page_num + 1, None, f"⚠️ Page {page_num + 1} is empty, skipping"
            
            try:
                print(f"   🚀 Sending page {page_num + 1} to API...")
                api_response = get_api_response(prompt, page_text, model=model, use_cache=use_cache)
                print(f"   ✅ Received response for page {page_num + 1}")
            
                # Extract JSON content from API response
                text_split = api_response.split("```json\n")
                if len(text_split) > 1:
                    json_content = text_split[1].split("\n```")[0]
                else:
                    # Try another format
                    text_split = api_response.split("```\n")
                    if len(text_split) > 1:
                        json_content = text_split[1].split("\n```")[0]
                    else:
                        # Assume the entire response is JSON
                        json_content = api_response
                
                # Parse JSON content for this page
                try:
                    page_bib_dict = json.loads(json_content)
                    print(f"   ✅ Extracted {len(page_bib_dict)} entries from page {page_num + 1}")
                    return page_num + 1, page_bib_dict, f"✅ Processed {len(page_bib_dict)} entries"
                except json.JSONDecodeError as e:
                    print(f"   ⚠️ Failed to parse JSON from page {page_num + 1}: {e}")
                    print(f"   Response was: {api_response[:200]}...")
                    return page_num + 1, None, f"⚠️ Failed to parse JSON: {e}"
                    
            except Exception as e:
                print(f"   ❌ Error processing page {page_num + 1}: {e}")
                return page_num + 1, None, f"❌ Error: {e}"
        
        # Process bibliography page by page in parallel
        print(f"🔄 Processing {len(pdf_document)} bibliography pages in parallel...")
        
        # Initialize combined dictionary to store all references
        all_bib_entries = {}
        
        # Process all pages in parallel
        with ThreadPoolExecutor(max_workers=30) as executor:
            # Submit all page processing tasks
            future_to_page = {
                executor.submit(process_page, page_num, page): page_num 
                for page_num, page in enumerate(pdf_document)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_page):
                page_num_index = future_to_page[future]
                try:
                    result_page_num, page_bib_dict, message = future.result()
                    print(f"   Page {result_page_num}: {message}")
                    
                    # Merge entries if successful
                    if page_bib_dict:
                        for key, value in page_bib_dict.items():
                            # Handle duplicate keys by appending page number
                            if key in all_bib_entries:
                                print(f"   ⚠️ Duplicate key '{key}' found, renaming to '{key}_p{result_page_num}'")
                                key = f"{key}_p{result_page_num}"
                            all_bib_entries[key] = value
                            
                except Exception as e:
                    print(f"   ❌ Exception processing page {page_num_index + 1}: {e}")
        
        # Save combined JSON content
        print(f"\n📝 Saving combined bibliography with {len(all_bib_entries)} entries...")
        ds_bib_dict = all_bib_entries
        
        try:
            with open(output_json_path, "w") as f:
                json.dump(ds_bib_dict, f, indent=2)
            print(f"✅ Bibliography JSON saved to: {output_json_path}")
        except Exception as e:
            print(f"❌ Error saving bibliography JSON: {e}")
    
    # Save BibTeX file
    try:
        save_bibtex(ds_bib_dict, filename=output_bib_path)
        print(f"BibTeX saved to: {output_bib_path}")
    except Exception as e:
        print(f"Error saving BibTeX: {e}")
    
    # Create citation dictionary
    try:
        citation_dict = {key: re.search(r'@[\w]+\{([^,]+),', value).group(1) 
                         for key, value in ds_bib_dict.items() 
                         if re.search(r'@[\w]+\{([^,]+),', value)}
        
        # Handle any entries that didn't match the regex
        missing_keys = [key for key in ds_bib_dict.keys() if key not in citation_dict]
        if missing_keys:
            print(f"Warning: Could not extract citation keys for: {missing_keys}")
    except Exception as e:
        print(f"Error creating citation dictionary: {e}")
        return None
    
    # Replace citations in LaTeX file if tex_path is provided
    if tex_path:
        try:
            # Extract bibliography filename from output_bib_path (without .bib extension)
            bib_filename = None
            if output_bib_path:
                # Get just the filename without directory and extension
                bib_filename = os.path.basename(output_bib_path)
            
            replace_citations(tex_path, citation_dict, output_filename=output_tex_path, bibliography_filename=bib_filename)
            print(f"Updated LaTeX file saved to: {output_tex_path}")
        except Exception as e:
            print(f"Error updating LaTeX file: {e}")
    
    # Save cache at the end only if cache is enabled
    if use_cache:
        print("💾 Saving bibliography cache...")
        save_bib_cache()
    else:
        print("💾 Cache disabled - not saving cache")
    
    return citation_dict, output_tex_path

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Process bibliography from PDF and update LaTeX citations.')
    parser.add_argument('--pdf', type=str, help='Path to the PDF file containing bibliography')
    parser.add_argument('--tex', type=str, help='Path to the LaTeX file to update with citations')
    parser.add_argument('--output-json', type=str, help='Path to save the output JSON file')
    parser.add_argument('--output-bib', type=str, help='Path to save the output BibTeX file')
    parser.add_argument('--output-tex', type=str, help='Path to save the updated LaTeX file')
    parser.add_argument('--model', type=str, default="gpt-4o", help='OpenAI model to use')
    parser.add_argument('--bib-json', type=str, help='Path to existing JSON file for bibliography')
    
    args = parser.parse_args()
    
    process_bibliography(
        pdf_path=args.pdf,
        tex_path=args.tex,
        output_json_path=args.output_json,
        output_bib_path=args.output_bib,
        output_tex_path=args.output_tex,
        model=args.model,
        bib_json=args.bib_json
    )