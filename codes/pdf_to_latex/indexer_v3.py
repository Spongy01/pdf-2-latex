import pymupdf
import os, sys
import re
from tqdm import tqdm
from fuzzysearch import find_near_matches
import fitz  # PyMuPDF

def read_latex(TEX_PATH):
    print(f"Reading LaTeX content from {TEX_PATH}")
    try:
        with open(TEX_PATH, "r", encoding="utf-8") as f:
            latex_content = f.read()
        print(f"Successfully read LaTeX content, size: {len(latex_content)} characters")
        return latex_content
    except Exception as e:
        print(f"Error reading LaTeX file: {e}")
        raise

def find_closest_page(page, page_breaks, page_positions, book_len, is_forward=True):
    print(f"Finding closest page for page {page}, is_forward={is_forward}")
    print(f"Page breaks available: {page_breaks[:5] if len(page_breaks) > 5 else page_breaks}... (total: {len(page_breaks)})")
    
    if str(page) in page_breaks:
        print(f"Exact match found for page {page}")
        return page_positions[page]
    
    if is_forward:
        bound = book_len
        forward = page
        while forward <= bound:
            if str(forward) in page_breaks:
                print(f"Forward match found: {forward}")
                return page_positions[forward]
            forward += 1
        print(f"No forward match found for page {page}")
        return -1
    else:
        bound = 0
        backward = page
        while backward >= bound:
            if str(backward) in page_breaks:
                print(f"Backward match found: {backward}")
                return page_positions[backward]
            backward -= 1
        print(f"No backward match found for page {page}")
        return 0  # No valid page found


import re

def ensure_latex_index(latex_str: str) -> str:
    """
    Ensures that a LaTeX document:
    - Uses makeidx package
    - Calls \\makeindex before \\begin{document}
    - Prints the index before \\end{document}
    - Adds \\end{document} if missing
    """

    text = latex_str

    # Normalize line endings
    text = text.replace("\r\n", "\n")

    # --- 1. Ensure makeidx + makeindex before \begin{document} ---
    begin_doc_match = re.search(r"\\begin\{document\}", text)

    if begin_doc_match:
        preamble = text[:begin_doc_match.start()]
        body = text[begin_doc_match.start():]

        if r"\usepackage{makeidx}" not in preamble:
            preamble += "\n\\usepackage{makeidx}\n"

        if r"\makeindex" not in preamble:
            preamble += "\\makeindex\n"

        text = preamble + body
    else:
        # No \begin{document} — prepend preamble anyway
        if r"\usepackage{makeidx}" not in text:
            text = "\\usepackage{makeidx}\n" + text
        if r"\makeindex" not in text:
            text = "\\makeindex\n" + text

    # --- 2. Ensure \printindex before \end{document} ---
    end_doc_match = re.search(r"\\end\{document\}", text)

    if end_doc_match:
        before_end = text[:end_doc_match.start()]
        after_end = text[end_doc_match.start():]

        if r"\printindex" not in before_end:
            before_end += "\n\\printindex\n"

        text = before_end + after_end
    else:
        # No \end{document} — append printindex + enddocument
        if r"\printindex" not in text:
            text += "\n\\printindex\n"
        text += "\n\\end{document}\n"

    return text



# Pattern Matchers
def is_pattern(text):
    pattern = re.compile(
    r"""
    ^(.+?),                # group 1: text (greedy, up to last comma before numbers)
    \s*                    # optional spaces
    ((?:\d+(?:–\d+)?       # one number or range (e.g., 150 or 204–208)
        (?:,\s*\d+(?:–\d+)?)*))  # optionally more numbers/ranges separated by commas
    $                      # end of string
    """,
    re.VERBOSE
    )

    pattern = re.compile(
        r"""
        ^\s*                                # optional leading spaces
        (?P<entry>.+?)                      # capture entry text (lazy)
        # \s*,?\s*                            # optional comma before numbers
        \s*,?\s+                     # **at least one space** before numbers, optional comma allowed here
        ((?P<pages>(\d+(?:\s*[–-]\s*\d+)?   # a number or range
                (?:\s*,\s*\d+(?:\s*[–-]\s*\d+)?)*   # more numbers/ranges separated by commas
                )
        )
        |
        (?:see\s+                  # OR the cross-reference "see" keyword (case-insensitive)
            (?P<see_ref>.+)         # cross-reference text (rest of line)
        ))
        
        \s*$                               # optional trailing spaces
        """,
        re.IGNORECASE | re.VERBOSE
    )
    if '©' in text:
        return False, None, None, None
    match = pattern.match(text)
    if match:
        text= match.group("entry")
        pages = match.group("pages")
        see_ref = match.group("see_ref")
        return True, text, pages, see_ref
    else:
        return False, None, None, None
    
def is_numbers_part(s):
    """
    Returns True if s matches a valid list of numbers and/or ranges separated by commas.
    Examples:
        '150'
        '150, 205, 299'
        '204-208, 324'
        '9, 49, 66–67'
    """
    pattern = re.compile(
        r"""^
        \s*                             # optional leading spaces
        \d+                             # first number
        (?:\s*[–-]\s*\d+)?             # optional range (hyphen or en-dash)
        (?:                            # zero or more additional numbers/ranges
            \s*,\s*                    # comma separator
            \d+                       # next number
            (?:\s*[–-]\s*\d+)?        # optional range
        )*
        \s*$                           # optional trailing spaces
        """,
        re.VERBOSE
    )
    return bool(pattern.match(s))

def get_line_indexes(PDF_PATH:str):
    doc = fitz.open(PDF_PATH)
    final_list = []
    x0 = -1
    y0 = -1
    x1 = -1
    y1 = -1 # working coordinates
    current_line = -1
    line_string = ""
    current_block = -1
    for page_num, page in enumerate(doc, start=1):
        print(f"--- Page {page_num} ---")
        text = page.get_text()
        # print(text)
        text = page.get_text("words")  # extracts text in reading order
        current_line = -1
        line_string = ""
        current_block = -1
        
        page_data = []
        for word in text:
            x0_, y0_, x1_, y1_, word_str, block_no, line_no, word_no = word
            print(word)
            # sometimes pymupdf gives different lin index to things that are on same line, manuakl check with x and y coords
            flag = ((abs(y0_ - y0) < 5) and x0_ -x1 <= 50) or line_no == current_line   # flag true means same line

            if block_no != current_block or (not flag ):
                # save current line before moving to next
                if current_line != -1:
                    page_data.append((x0, y0, x1, y1, line_string))
                
                current_block = block_no
                current_line = line_no
                line_string = ""
                x0, y0, x1, y1 = x0_, y0_, x1_, y1_
            
            # appending word and managing coordinates
            line_string += word_str + " "
            x1 = max(x1, x1_)
            y1 = max(y1, y1_)
            x0 = min(x0, x0_)
            y0 = min(y0, y0_)

        page_data.append((x0, y0, x1, y1, line_string))
        final_list.append((page_num, page_data))

    return final_list

def make_columns(final_list):
    columnar_data = [] # (page number,  columns = {column_dims = [], column_lines = []} )

    current_column = [-1,-1,-1,-1]
    page_columns = []
    column_data =[]
    is_valid = False
    is_footer = False
    for page_num, page_data in final_list:
        is_valid = False
        print(f"Processing page {page_num}")
        for line in page_data:
            x0, y0, x1, y1, line_string = line

            # print(f"Line: {line_string.strip()} at ({x0}, {y0}, {x1}, {y1})")
            # # check if line fits in current column
            if current_column[0] == -1:
                # initialize column
                print("New column detected")
                print(f"Current column: {current_column}")
                current_column = [x0,y0,x1,y1]
                print(f"Starting new column with line at ({x0}, {y0}, {x1}, {y1}) with text: {line_string.strip()}")
                if '©' in line_string:
                    is_footer = True
                is_valid = False
                column_data = []
                column_data.append(line)
                chk, _, _,_ = is_pattern(line_string.strip())
                is_valid = is_valid or chk

            else:
                # check if line fits in current column

                if ((current_column[0] <= x0 and x0  <= current_column[2] ) or (current_column[0] <= x1 and x1 <= current_column[2]) or (x0 <= current_column[0] and current_column[2] <= x1)) and \
                    (current_column[0]- x0 <= 50):
                    # print("Fits in current column")
                    # update column coordinates
                    current_column[0] = min(current_column[0], x0)
                    current_column[2] = max(current_column[2], x1)
                    current_column[1] = min(current_column[1], y0)
                    current_column[3] = max(current_column[3], y1)
                    column_data.append(line)
                    chk, _, _,_ = is_pattern(line_string.strip())
                    if '©' in line_string:
                        is_footer = True
                    is_valid = is_valid or chk
                else:
                    # save current column and start new one
                    print("New column detected")
                    print(f"Current column: {current_column}")
                    print(f"Starting new column with line at ({x0}, {y0}, {x1}, {y1}) with text: {line_string.strip()}")
                    if is_valid and not is_footer:
                        page_columns.append({"dimensions" : current_column, "lines": column_data})
                    current_column = [x0,y0,x1,y1]
                    is_valid = False
                    is_footer = False
                    column_data = []
                    column_data.append(line)
                    chk, _, _, _ = is_pattern(line_string.strip())
                    is_valid = is_valid or chk
                    if '©' in line_string:
                        is_footer = True
        # save last column of the page
        if is_valid and not is_footer:
            page_columns.append({"dimensions" : current_column, "lines": column_data})
        is_valid = False
        is_footer = False
        print(f"End of page {page_num}, columns: {page_columns}")
        if current_column[0] != -1:
            columnar_data.append([page_num, page_columns])
            current_column = [-1,-1,-1,-1]
        page_columns = []

    return columnar_data

def get_indentations(columnar_data):
    diffs = []
    for page_data in columnar_data:
        print(f"Page {page_data[0]} has {len(page_data[1])} columns.")
        for column in page_data[1]:
            print("Column Coordinates:", column["dimensions"])
            x_main = column["dimensions"][0]
            for line in column["lines"]:
                print(" Line:", line)
                x_line = line[0]
                diffs.append(abs(x_main - x_line))

    # remove diffs less than 1
    diffs = [d for d in diffs if d >= 1]
    diffs.sort()

    # check first and last diff to see range
    min_diff = diffs[0]
    max_diff = diffs[-1]
    # subtract min_diff from max_diff
    range_diff = max_diff - min_diff

    # if range is greater than 2, then we have subindexes and continuations, else only subindexes
    if range_diff > 2:
        print("Both subindexes and continuations detected")
        # separate diffs into two groups based on a threshold
        subindexes = [d for d in diffs if abs(d - min_diff) <= 2]
        continuations = [d for d in diffs if abs(d - max_diff) <= 2]
        # average diff for subindexes
        avg_diff_subindexes = sum(subindexes) / len(subindexes)
        avg_diff_subindexes
        # average diff for continuations
        avg_diff_continuations = sum(continuations) / len(continuations)
        avg_diff_continuations
        print(f"Avg Subindexes Diff: {avg_diff_subindexes}, Avg Continuations Diff: {avg_diff_continuations}")
    else:
        print("Only subindexes detected")
        # average diff
        avg_diff = sum(diffs) / len(diffs)
        avg_diff_subindexes = avg_diff
        avg_diff_continuations = None
        print(f"Avg Subindexes Diff: {avg_diff_subindexes}")

    return avg_diff_subindexes, avg_diff_continuations

def get_index_list(columnar_data):
    # index dict will hold the index key and as key a dict, which will have pages or see refs
    index_dict = {}
    last_main_entry_text = ""
    hold_buffer = ""
    hold_flag = False
    entries_found = 0

    # get subindex and continuation differences
    avg_diff_subindexes, avg_diff_continuations = get_indentations(columnar_data)

    for page_num, columns in columnar_data:
        for column in columns:
            for line in column["lines"]:
                x0, y0, x1, y1, line_string = line
                chk, text, pages, see_ref = is_pattern(line_string.strip())
                if chk:
                    # determine if main or subindex or continuation
                    diff = abs(column["dimensions"][0] - x0)
                    if diff <= 2:
                        # main entry point
                        # add to index dict
                        # if previous was buffered, that was wrong entry, ignore
                        if hold_flag:
                            hold_flag = False
                            print(f"Hold Cleared : {hold_buffer}")
                        if see_ref:
                            index_dict[text] = {"pages": None, "see_ref": see_ref}
                        else:
                            index_dict[text] = {"pages": pages.split(", "), "see_ref": None}
                            entries_found += len(pages.split(", "))
                        last_main_entry_text = text
                    if avg_diff_subindexes is not None and abs(diff - avg_diff_subindexes) <= 2:
                        # subindex
                        if hold_flag:
                            print(f"Hold Addressed subent.: {hold_buffer}")
                            # main entry text didnt have page entries
                            entry = hold_buffer + "!" + text

                        if last_main_entry_text != "":
                            entry = last_main_entry_text + "!" + text
                        # add to last main entry
                        if see_ref:
                            index_dict[entry] = {"pages": None, "see_ref": see_ref}
                        else:
                            index_dict[entry] = {"pages": pages.split(", "), "see_ref": None}
                            entries_found += len(pages.split(", "))
                    if avg_diff_continuations is not None and abs(diff - avg_diff_continuations) <= 2:
                        # continuation
                        if hold_flag:
                            
                            entry = hold_buffer + " " + line_string.strip()
                            print(f"Hold Addressed cont.: {entry}")
                            chk, text, pages, see_ref = is_pattern(entry)
                            # add to last main entry
                            if chk:
                                if see_ref:
                                    index_dict[text] = {"pages": None, "see_ref": see_ref}
                                else:
                                    index_dict[text] = {"pages": pages.split(", "), "see_ref": None}
                                    entries_found += len(pages.split(", "))

                                last_main_entry_text = text
                            hold_flag = False
                    
                else:
                    # cases:
                        # only text, because of next line continuation, or possible subentries
                        # only numbers, as a continuation of previous main line entry
                    # check second case here, if not, hold in buffer for next line
                    chk = is_numbers_part(line_string.strip())
                    if chk:
                        print("num check pat")
                        # positive
                        # could be previous hold or main entry
                        if hold_flag:
                            print(f"Hold Addressed in num check: {hold_buffer}")
                            entry = hold_buffer + " " + line_string
                            print(f" --------------------------- {entry}")
                        elif last_main_entry_text!="":
                            entry = last_main_entry_text + " " + line_string
                        chk, text, pages, see_ref = is_pattern(entry.strip())
                        if chk:
                            if see_ref:
                                index_dict[text] = {"pages": None, "see_ref": see_ref}
                            else:
                                index_dict[text] = {"pages": pages.split(", "), "see_ref": None}
                                entries_found += len(pages.split(", "))
                            last_main_entry_text = text
                            hold_flag = False
                        else:
                            print(f"Not Pat! Num! Not Pat : {entry}")
                            hold_flag = False
                
                        # did we register some last mainline or subline:
                    else:
                        print(f"Hold : {line_string}")

                        # no check, because of maybe next subentry, or continuation
                        hold_flag = True
                        hold_buffer = line_string.strip()

    return index_dict

def handle_ranges(page_list):
    """
    Given a list of page numbers and ranges as strings, for the ranges, only keep the first term
    Example:
        Input: ['150', '204-208', '299']
        Output: [150, 204, 299]
    """
    result = []
    for item in page_list:
        if '–' in item:
            start, end = item.split('–')
            result.append(int(start.strip()))
        elif '-' in item:
            start, end = item.split('-')
            result.append(int(start.strip()))
        else:
            result.append(int(item.strip()))
    return result

def index_cleaner(index_dict):
    cleaned_index = {}
    for key in index_dict:
        value = index_dict[key]
        pages = value['pages']
        see_ref = value['see_ref']
        if pages is not None:
            cleaned_pages = handle_ranges(pages)
            cleaned_index[key] = {'pages': cleaned_pages, 'see_ref': see_ref}
        else:
            cleaned_index[key] = {'pages': None, 'see_ref': see_ref}
    return cleaned_index

def extract_index(INDEX_PATH:str):
    index_lines = get_line_indexes(INDEX_PATH)
    index_columns = make_columns(index_lines)
    index_dict = get_index_list(index_columns)
    index_dict = index_cleaner(index_dict)

    return index_dict

def add_indexes(latex_content, index, book_len):
    print(f"Adding indexes to LaTeX content. Index has {len(index)} terms.")
    matched = 0
    not_matched = 0
    not_found_terms = {}  # Dictionary to store terms not found along with page numbers

    # Extract page breaks once to avoid repeated searches
    print("Extracting page breaks from LaTeX content...")
    page_breaks = re.findall(r'%---- Page End Break Here ---- Page : (\d+)', latex_content)
    page_positions = {int(page): pos for page, pos in zip(page_breaks, [m.start() for m in re.finditer(r'%---- Page End Break Here ---- Page : \d+', latex_content)])}
    print(f"Found {len(page_breaks)} page breaks in the LaTeX content")
    
    if not page_breaks:
        print("WARNING: No page breaks found in LaTeX content. Check page break format.")
    
    # Debug information for page positions
    if page_positions:
        print(f"Page position examples: {list(page_positions.items())[:3]}")
    
    for index_term, values in tqdm(index.items()):
        if values['pages'] is None:
            continue  # Skip see references for now
        pages = values['pages']
        for page in pages:
            # Debug for specific terms, if needed
            # debug = (index_term == 'application')  # Example term to debug
            debug = False
            
            if debug:
                print(f"DEBUG: Processing '{index_term}' on page {page}")
            
            try:
                # Find page boundaries
                upper_bound = find_closest_page(page+1, page_breaks, page_positions, book_len, True)
                lower_bound = find_closest_page(page-2, page_breaks, page_positions, False)
                
                if debug:
                    print(f"DEBUG: Page {page} bounds - lower: {lower_bound}, upper: {upper_bound}")
                
                if upper_bound == -1 or lower_bound == 0:
                    # print(f"Warning: Could not find proper bounds for page {page} with term '{index_term}'")
                    if index_term not in not_found_terms:
                        not_found_terms[index_term] = []
                    not_found_terms[index_term].append(page)
                    not_matched += 1
                    continue
                
                page_content = latex_content[lower_bound:upper_bound]
                
                # Extract the search term (for subindex entries)
                term = index_term
                if '!' in index_term:
                    # subindex entry
                    term = index_term.split("!", 1)[1]
                
                if debug:
                    print(f"DEBUG: Searching for term '{term}' (from '{index_term}')")
                
                match = re.search(re.escape(term), page_content, re.IGNORECASE)

                if match:
                    if debug:
                        print(f"DEBUG: Found match at position {match.start()} in page content")
                    
                    # Look for the term inside braces or brackets
                    pattern = (
                        r"\{[^{}]*" + re.escape(term) + r"[^{}]*\}" +
                        r"|" +  # OR
                        r"\[[^\[\]]*" + re.escape(term) + r"[^\[\]]*\]"
                    )
                    brace_match = re.search(pattern, page_content, re.IGNORECASE)
                    
                    if brace_match:
                        # Term is inside a command
                        if debug:
                            print(f"DEBUG: Term found inside braces/brackets at position {brace_match.start()}")
                        
                        term_end = lower_bound + brace_match.end()
                        indexed_term = "\\index{" + index_term + "}"
                        
                        # Add debug check to see what we're inserting and where
                        if debug:
                            context_before = latex_content[term_end-10:term_end]
                            context_after = latex_content[term_end:term_end+10]
                            print(f"DEBUG: Inserting '{indexed_term}' at position {term_end}")
                            print(f"DEBUG: Context: ...{context_before}|HERE|{context_after}...")
                        
                        newline_pos = latex_content.find("\n", term_end)
                        if newline_pos != -1 and term_end < newline_pos:
                            term_end = newline_pos
                        
                        latex_content = latex_content[:term_end] + indexed_term + latex_content[term_end:]

                    
                    else:
                        # Term is not inside a command
                        if debug:
                            print(f"DEBUG: Term found in regular text")
                        
                        term_end = lower_bound + match.end()
                        indexed_term = "\\index{" + index_term + "}"
                        
                        # Add debug check to see what we're inserting and where
                        if debug:
                            context_before = latex_content[term_end-10:term_end]
                            context_after = latex_content[term_end:term_end+10]
                            print(f"DEBUG: Inserting '{indexed_term}' at position {term_end}")
                            print(f"DEBUG: Context: ...{context_before}|HERE|{context_after}...")
                        
                        newline_pos = latex_content.find("\n", term_end)
                        if newline_pos != -1 and term_end < newline_pos:
                            term_end = newline_pos

                        latex_content = latex_content[:term_end] + indexed_term + latex_content[term_end:]
                    
                    matched += 1
                    
                    # Progress update
                    if matched % 100 == 0:
                        print(f"Matched {matched} terms so far")
                        
                else:
                    if debug:
                        print(f"DEBUG: No match found for term '{term}' on page {page}")
                    
                    # Record not found term
                    if index_term not in not_found_terms:
                        not_found_terms[index_term] = []
                    not_found_terms[index_term].append(page)
                    not_matched += 1
                    
                    # Progress update
                    if not_matched % 100 == 0:
                        print(f"Not matched {not_matched} terms so far")
                        
            except Exception as e:
                # print(f"Error processing term '{index_term}' on page {page}: {e}")
                if index_term not in not_found_terms:
                    not_found_terms[index_term] = []
                not_found_terms[index_term].append(page)
                not_matched += 1
    
    print(f"Matched: {matched}, Not Matched: {not_matched}")

    # handle not found terms
    print(f"Processing {len(not_found_terms)} terms that were not found")
    page_based_terms = {}

    # Iterate through the original not_found_terms dictionary
    for index_term, pages in not_found_terms.items():
        for page in pages:
            if page not in page_based_terms:
                page_based_terms[page] = []  # Initialize list if page is not already in the dictionary
            page_based_terms[page].append(index_term)  # Add the index term to the list for the current page

    print(f"Grouping not found terms by {len(page_based_terms)} pages")
    for page, not_found_index_terms in page_based_terms.items():
        # print(f"Adding {len(not_found_index_terms)} not found terms to page {page}")
        
        index_string = ""
        index_string = "".join([f"\\index{{{term}}}" for term in not_found_index_terms])

        # Re-find the page breaks and positions
        try:
            page_breaks = re.findall(r'%---- Page End Break Here ---- Page : (\d+)', latex_content)
            page_positions = {int(page): pos for page, pos in zip(page_breaks, [m.start() for m in re.finditer(r'%---- Page End Break Here ---- Page : \d+', latex_content)])}

            upper_bound = find_closest_page(page+0, page_breaks, page_positions, book_len, True)
            lower_bound = find_closest_page(page-1, page_breaks, page_positions, False)

            if upper_bound == -1 or lower_bound == 0:
                print(f"Warning: Could not find proper bounds for page {page} when adding not found terms")
                continue
                
            page_content = latex_content[lower_bound:upper_bound]
            index_position = lower_bound + (upper_bound - lower_bound) // 2

            # if index_position is before \begin{document}, move it to after
            begin_doc_pos = latex_content.find(r"\begin{document}")
            if begin_doc_pos != -1 and index_position < begin_doc_pos:
                index_position = begin_doc_pos + len(r"\begin{document}")

            # Move forward until a newline
            next_newline_pos = latex_content.find("\n", index_position)
            if next_newline_pos == -1:
                print(f"Warning: No newline found after position {index_position}")
                next_newline_pos = upper_bound  # In case no newline is found, go till the end of the content

            # Debug info to see what we're inserting and where
            try:
                context_before = latex_content[next_newline_pos-10:next_newline_pos]
                context_after = latex_content[next_newline_pos:next_newline_pos+10]
                # print(f"Inserting {len(not_found_index_terms)} index entries at position {next_newline_pos}")
                # print(f"Context: ...{context_before}|HERE|{context_after}...")
            except Exception as e:
                print(f"Error showing context: {e}")
            
            latex_content = latex_content[:next_newline_pos] + index_string + latex_content[next_newline_pos:]
        
        except Exception as e:
            print(f"Error processing not found terms for page {page}: {e}")
    print(f"Matched: {matched}, Not Matched: {not_matched}")

    # Clean up the LaTeX content
    return latex_content, not_found_terms

def create_indexing(INDEX_PATH, TEX_PATH, CONTENT_PATH, OUTPUT_TEX_PATH):
    print("\n=== Step 5: Adding Indexing ===")
    print(f"Creating index from: {INDEX_PATH}")
    print(f"Using LaTeX file: {TEX_PATH}")
    print(f"Using content book: {CONTENT_PATH}")
    
    try:
        # Create index
        index = extract_index(INDEX_PATH)
        print(f"Successfully created index with {len(index)} unique entries")
        
        # Read LaTeX content
        latex_content = read_latex(TEX_PATH)
        print(f"Successfully read LaTeX content ({len(latex_content)} characters)")
        
        # READ CONTENT BOOK
        try:
            content_book_pdf = pymupdf.open(CONTENT_PATH)
            book_len = len(content_book_pdf)

            print(f"Successfully opened content book PDF with {book_len} pages")
            
            # toc = content_book_pdf.get_toc()
            # print(f"Retrieved TOC with {len(toc)} entries")
            
            # toc = clean_and_merge_toc(toc)
            
            # Extract page breaks once
            page_breaks = re.findall(r'%---- Page End Break Here ---- Page : (\d+)', latex_content)
            page_positions = {int(page): pos for page, pos in zip(page_breaks, [m.start() for m in re.finditer(r'%---- Page End Break Here ---- Page : \d+', latex_content)])}
            print(f"Found {len(page_breaks)} page breaks in the LaTeX content")
            
            # Add indexes to LaTeX content
            latex_content, not_found = add_indexes(latex_content, index, book_len)
            print(f"Successfully added all the indexes. {len(not_found)} terms were not found but were handled.")
            
            # Ensure LaTeX index structure
            latex_content = ensure_latex_index(latex_content)
            print("Ensured LaTeX document has proper index structure")
            # Write the updated LaTeX content to a new file
            print(f"Writing result to: {OUTPUT_TEX_PATH}")
            with open(OUTPUT_TEX_PATH, "w", encoding="utf-8") as file:
                file.write(latex_content)
            print(f"Successfully wrote {len(latex_content)} characters to output file")
            
            return OUTPUT_TEX_PATH
        except Exception as e:
            print(f"Error processing content book: {e}")
            raise
    except Exception as e:
        print(f"Error in create_indexing: {e}")
        raise


if __name__ == '__main__':
    print("Starting indexing script")
    # running as main function
    if len(sys.argv) < 5:
        print("Usage: python script.py <content_book_pdf_path> <tex_file_path> <index_file_path> <output_tex_path>")
        sys.exit(1)

    try:
        # Get the filename from the arguments
        CONTENT_PATH = sys.argv[1]  # content book pdf path
        TEX_PATH = sys.argv[2]      # page break output tex path
        INDEX_PATH = sys.argv[3]    # index file path
        OUTPUT_TEX_PATH = sys.argv[4]
        
        print(f"Content Book Path: {CONTENT_PATH}")
        print(f"LaTeX File Path: {TEX_PATH}")
        print(f"Index File Path: {INDEX_PATH}")
        print(f"Output File Path: {OUTPUT_TEX_PATH}")
        
        create_indexing(INDEX_PATH, TEX_PATH, CONTENT_PATH, OUTPUT_TEX_PATH)
        print("Indexing completed successfully!")
    except Exception as e:
        print(f"Error during indexing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)