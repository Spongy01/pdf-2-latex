# import pymupdf
# import os, sys
# import re
# from tqdm import tqdm
# from fuzzysearch import find_near_matches
# import re


# def read_latex(TEX_PATH):
#     with open(TEX_PATH, "r") as f:
#         latex_content = f.read()
#     return latex_content

# def find_closest_page(page,page_breaks ,page_positions, book_len , is_forward=True):

#     if str(page) in page_breaks:
#         return page_positions[page]
#     if is_forward:
#         bound = book_len
#         forward = page
#         while (forward) <= bound:
#             if str(forward) in page_breaks:
#                 return page_positions[forward]
#             forward += 1
#         return -1
    
#     else:
#         bound = 0
#         backward = page
#         while (backward) >= bound:
#             if str(backward) in page_breaks:
#                 return page_positions[backward]
#             backward -= 1
#         return 0  # No valid page found


# def get_main_sub_coords(span_list):
#   x_list = set()
#   pattern = re.compile(r"(.+?),\s*((?:\d+,?\s*)+)")

#   for span in span_list:
#     text = span['text']
#     # match for pattern using regex
#     match = pattern.match(text)
#     if match:
#       x_list.add(int(span['origin'][0]))
    
#   x_list = sorted(list(x_list))
#   print(x_list)
#   x_main = [x_list[0], x_list[2]]
#   x_sub = [x_list[1], x_list[3]]
#   return x_main, x_sub



# def check_valid_index(text):
#   pattern = re.compile(r"(.+?),\s*((?:\d+,?\s*)+)")
#   match = pattern.match(text)
#   if match:
#     return True
#   return False


# def valid_coords(doc):
#     span_list = []
#     for page in doc:
#     # extract the spans of the page
#         text_dict = page.get_text("dict")
#         for block in text_dict["blocks"]:
#             for line in block["lines"]:
#                 for span in line["spans"]:
#                     if span["text"].strip() == "":
#                         continue
#                     # store all spans in a list
#                     span_list.append(span)
#                     # print(span)


#     # sort the span list 
#     # get 2 main entries and 2 subindex entries

#         x_main, x_sub = get_main_sub_coords(span_list)
#         break

#     return x_main, x_sub




# def create_index(INDEX_PATH):
#     index_pdf = pymupdf.open(INDEX_PATH)
    
#     # for i in range(len(index_pdf)):
#     #     page = index_pdf[i]
#     #     index_data[i] = page.get_text("text")

#     # get valid_coords
#     x_main, x_sub = valid_coords(index_pdf)



#     last_main_entry = None
#     pattern = re.compile(r"(.+?),\s*((?:\d+,?\s*)+)")
#     index = {}
#     for page in index_pdf:
#         # extract the spans of the page
#         text_dict = page.get_text("dict")
#         for block in text_dict["blocks"]:
#             for line in block["lines"]:
#                 for span in line["spans"]:
#                     if span["text"].strip() == "":
#                         continue
#                     text = span['text']
#                     if check_valid_index(text):
#                         match = pattern.match(text)
#                         term = match.group(1).strip()
#                         pages = [int(p) for p in re.findall(r"\d+", match.group(2))]
#                         x_coord = int(span['origin'][0])
#                         if x_coord in x_main:
#                             last_main_entry = term
#                             index[term] = pages
#                         elif x_coord in x_sub:
#                             t = last_main_entry + "!" + term
#                             index[t] = pages
#     return index


# def clean_and_merge_toc(toc):
#     cleaned_toc = []

#     def remove_numbering(title):
#         title = title.replace('\r', '').replace('\x0c', 'fi')
#         return re.sub(r'^\s*\d+(\.\d+)*\s*', '', title).strip()

#     for entry in toc:
#         level, title, page = entry
#         title_clean = title.replace('\r', '').replace('\x0c', 'fi').strip()

#         if cleaned_toc:
#             prev_level, prev_title, prev_page = cleaned_toc[-1]
#             # If same level and same page, and this one doesn’t start with a number — join
#             if level == prev_level and page == prev_page and not re.match(r'^\s*\d+(\.\d+)*', title_clean):
#                 cleaned_toc[-1] = (prev_level, prev_title + " " + title_clean, prev_page)
#                 continue

#         cleaned_title = remove_numbering(title_clean)
#         cleaned_toc.append((level, cleaned_title, page))

#     return cleaned_toc


# def clean_latex_content(latex_content, toc):
#     # Step 1: Remove the asterisk from section*, subsection*, and chapter*
#     latex_content = re.sub(r'\\(section|subsection|chapter)\*{', r'\\\1{', latex_content)

#     # Step 2: Remove duplicate chapter titles
#     seen_chapters = set()
    
#     # This regex pattern captures \chapter{...} and extracts the chapter title
#     def remove_duplicate_chapters(match):
#         chapter_title = match.group(1)
#         if chapter_title in seen_chapters:
#             return ""  # Return an empty string to remove the duplicate chapter
#         seen_chapters.add(chapter_title)
#         return match.group(0)  # Keep the first occurrence of the chapter

#     latex_content = re.sub(r'\\chapter{(.*?)}', remove_duplicate_chapters, latex_content)

#     # make sure the contents are similar to the original toc
#     def check_sectioning(latex, toc):
#         main_start = latex_content.find(r"\mainmatter")
#         if main_start == -1:
#             print("No \\mainmatter found in the LaTeX content.")
#             return latex_content
        
#         print("Found \\mainmatter at position:", main_start)
#         content_after_main = latex_content[main_start:]

#         toc_dict = {title.lower(): level for level, title, _ in toc}

#         print("toc_dict: ", toc_dict)

#         def replacer(match):
#             cmd = match.group(1)         # chapter / section / subsection
#             title = match.group(2).strip()
#             norm_title = title.lower()

#             # Expected level based on LaTeX command
#             level_map = {'chapter': 1, 'section': 2, 'subsection': 3}
#             expected_level = level_map[cmd]

#             # Check if this title exists in TOC
#             actual_level = toc_dict.get(norm_title)
#             if actual_level is None:
#                 print(f"Warning: Title '{norm_title}' not found in TOC.")
#             if actual_level and actual_level != expected_level:
#                 # Comment out this line if mismatch
#                 return f"% Mismatched: \\{cmd}name{{{title}}}"

#             return match.group(0)

        
#         updated_main = re.sub(r"\\(chapter|section|subsection)\{([^\}]+)\}", replacer, content_after_main)
#         return latex[:main_start] + updated_main
    
#     latex_content = check_sectioning(latex_content, toc)


#     def remove_duplicate_sections(latex_content):
#         # Split LaTeX into chapter blocks (each starts with \chapter)
#         print("Removing duplicate sections and subsections...")
#         chapters = re.split(r'(\\chapter\{[^\}]+\})', latex_content)
#         print(f"Found {len(chapters)//2} chapters.")
#         cleaned_content = ""
#         seen_titles = set()
#         duplicate = 0
#         flip = 1
#         for i in range(0, len(chapters), 2):
#             # print("I is ", i)
#             pre_chapter = chapters[i]
#             chapter_heading = chapters[i+1] if i+1 < len(chapters) else ""
#             chapter_block = chapters[i+2] if i+2 < len(chapters) else ""
            

#             # print("Chapter heading: ", chapter_heading)
#             # Reset for each chapter
#             seen_titles.clear()

#             # Replace duplicate sections/subsections
#             def remove_duplicates(match):
#                 command = match.group(1)
#                 title = match.group(2).strip().lower()
#                 if title in seen_titles:
#                     nonlocal duplicate
#                     duplicate += 1
#                     # print(f"Duplicate found: {title} in {command}")
#                     return ''  # remove duplicate
#                 seen_titles.add(title)
#                 return match.group(0)

#             cleaned_block = re.sub(r'\\(section|subsection)\{([^\}]+)\}', remove_duplicates, chapter_block)
#             if flip == 1:
#                 cleaned_content += pre_chapter + chapter_heading + cleaned_block
#                 flip = 0
#             else:
#                 cleaned_content += chapter_heading + cleaned_block


#         return cleaned_content
#     latex_content = remove_duplicate_sections(latex_content)


#     return latex_content



# def add_indexes(latex_content, index, book_len, toc): 
#     matched = 0
#     not_matched = 0
#     not_found_terms = {}  # Dictionary to store terms not found along with page numbers

#     for index_term, pages in tqdm(index.items()):
#         # check = False
#         # if index_term == 'application':
#         #     check = True
#         for page in pages:
#             # upadte page number indexes as terms will be added

#             page_breaks = re.findall(r'%---- Page End Break Here ---- Page : (\d+)', latex_content)
#             page_positions = {int(page): pos.start() for page, pos in zip(page_breaks, re.finditer(r'%---- Page End Break Here ---- Page : \d+', latex_content))}

#             upper_bound = find_closest_page(page+1, page_breaks, page_positions ,True)
#             lower_bound = find_closest_page(page-2, page_breaks, page_positions ,False)

#             page_content = latex_content[lower_bound:upper_bound]
            
#             # match = re.search(r'\b' + re.escape(index_term) + r'\b', page_content, re.IGNORECASE)
#             term = index_term
#             if '!' in index_term:
#                 # subindex entry
#                 term = index_term.split("!", 1)[1]
#             match = re.search(  re.escape(term), page_content, re.IGNORECASE)

#             if match:
#                 # pattern = r"\{[^{}]*\b" + re.escape(index_term) + r"\b[^{}]*\}"
#                 pattern = (
#                     r"\{[^{}]*" + re.escape(term) + r"[^{}]*\}" +
#                     r"|" +  # OR
#                     r"\[[^\[\]]*" + re.escape(term) + r"[^\[\]]*\]"
#                 )
#                 brace_match = re.search( pattern, page_content, re.IGNORECASE)
#                 if brace_match:
#                     # word is inside a command
#                     term_end = lower_bound + brace_match.end() + 1
#                     indexed_term = "\index{" + index_term + "}"
#                     latex_content = latex_content[:term_end] + indexed_term + latex_content[term_end:]
                
#                 else:
#                     # word is not inside a command

#                     term_end = lower_bound + match.end() + 1
#                     indexed_term = "\index{" + index_term + "}"
#                     latex_content = latex_content[:term_end] + indexed_term + latex_content[term_end:]

                
#                 matched += 1
#                 continue
#                 # old code
#                 term_start = lower_bound + match.start()  # Adjust index relative to book_text
#                 term_end = term_start + len(index_term)
#                 indexed_term = "\index{" + index_term + "}"
#                 latex_content = latex_content[:term_start] +index_term + indexed_term + latex_content[term_end:]
#                 matched += 1
#             else:
#                 # # try fuzzy matching
#                 # term_length = len(index_term)
#                 # max_dist = max(1, term_length // 3)  # 1/3rd of term length
#                 # near_matches = find_near_matches(index_term, page_content, max_l_dist=max_dist)

#                 # if near_matches:
#                 #     best_match = min(near_matches, key=lambda x: x.dist)  # Get the closest match
#                 #     term_start = lower_bound + best_match.start  # Adjust index relative to book_text
#                 #     term_end = term_start + term_length
#                 #     indexed_term = "\index{" + index_term + "}"
#                 #     latex_content = latex_content[:term_start] + index_term + indexed_term + latex_content[term_end:]
#                 #     matched += 1
#                 #     continue
                
#                 ################################################################################################
#                 # New try failed

#                 # index_position = lower_bound + (upper_bound - lower_bound) // 2
#                 # middle_content = latex_content[index_position: index_position+1]  # Extract some content around the middle
#                 # pattern = r"\{[^{}]*\b" + re.escape(middle_content) + r"\b[^{}]*\}"

#                 # brace_match = re.search( pattern, page_content, re.IGNORECASE)
                
#                 # if brace_match:
#                 #     # word is inside a command
#                 #     term_end = lower_bound + brace_match.end() + 1
#                 #     indexed_term = "\index{" + index_term + "}"
#                 #     latex_content = latex_content[:term_end] + indexed_term + latex_content[term_end:]
#                 #     matched += 1
#                 # else:
#                 #     indexed_term = "\index{" + index_term + "}"
#                 #     latex_content = latex_content[:index_position] + indexed_term + latex_content[index_position:]
#                 #     matched += 1
                    
#                 if index_term not in not_found_terms:
#                     not_found_terms[index_term] = []
#                 not_found_terms[index_term].append(page)

#     # print(f"Matched: {matched}, Not Matched: {not_matched}")

#     # handle not found terms
#     page_based_terms = {}

#     # Iterate through the original not_found_terms dictionary
#     for index_term, pages in not_found_terms.items():
#         for page in pages:
#             if page not in page_based_terms:
#                 page_based_terms[page] = []  # Initialize list if page is not already in the dictionary
#             page_based_terms[page].append(index_term)  # Add the index term to the list for the current page

    
#     for page, not_found_index_terms in page_based_terms.items():
#         index_string = ""
#         index_string = "".join([f"\\index{{{term}}}" for term in not_found_index_terms])

#         page_breaks = re.findall(r'%---- Page End Break Here ---- Page : (\d+)', latex_content)
#         page_positions = {int(page): pos.start() for page, pos in zip(page_breaks, re.finditer(r'%---- Page End Break Here ---- Page : \d+', latex_content))}

#         upper_bound = find_closest_page(page+0, page_breaks, page_positions ,True)
#         lower_bound = find_closest_page(page-1, page_breaks, page_positions ,False)

#         page_content = latex_content[lower_bound:upper_bound]
#         index_position = lower_bound + (upper_bound - lower_bound) // 2

#         # Move forward until a newline
#         next_newline_pos = latex_content.find("\n", index_position)
#         if next_newline_pos == -1:
#             next_newline_pos = upper_bound  # In case no newline is found, go till the end of the content

#         latex_content = latex_content[:next_newline_pos] + index_string + latex_content[next_newline_pos:]


#         # middle_content = latex_content[index_position: index_position+1]  # Extract some content around the middle
#         # pattern = (
#         #     r"\{[^{}]*" + re.escape(middle_content) + r"[^{}]*\}" +
#         #     r"|" +  # OR
#         #     r"\[[^\[\]]*" + re.escape(middle_content) + r"[^\[\]]*\]"
#         # )
#         # brace_match = re.search( pattern, page_content, re.IGNORECASE)
#         # if brace_match:
#         #     # word is inside a command
#         #     term_end = lower_bound + brace_match.end() + 1        
#         #     latex_content = latex_content[:term_end] + index_string + latex_content[term_end:]
#         # else:
#         #     latex_content = latex_content[:index_position] + index_string + latex_content[index_position:]

#     # Clean up the LaTeX content
#     latex_content = clean_latex_content(latex_content, toc)
#     return latex_content, not_found_terms



# def create_indexing(INDEX_PATH, TEX_PATH, CONTENT_PATH , OUTPUT_TEX_PATH):
#     print("\n=== Step 4: Adding Indexing ===")
#     print(f"Creating index from: {INDEX_PATH}")
#     print(f"Using LaTeX file: {TEX_PATH}")
#     print(f"Using content book: {CONTENT_PATH}")
#     # Create index
#     index = create_index(INDEX_PATH)

#     # Read LaTeX content
#     latex_content = read_latex(TEX_PATH)

#     # READ CONTENT BOOK
#     content_book_pdf = pymupdf.open(CONTENT_PATH)
#     toc = content_book_pdf.get_toc()
#     toc = clean_and_merge_toc(toc)
#     book_len = len(content_book_pdf)
#     page_breaks = re.findall(r'%---- Page End Break Here ---- Page : (\d+)', latex_content)
#     page_positions = {int(page): pos.start() for page, pos in zip(page_breaks, re.finditer(r'%---- Page End Break Here ---- Page : \d+', latex_content))}


#     # Add indexes to LaTeX content
#     latex_content, _ = add_indexes(latex_content, index, book_len, toc)

#     # Write the updated LaTeX content to a new file
#     with open(OUTPUT_TEX_PATH, "w", encoding="utf-8") as file:
#         file.write(latex_content)
#     return OUTPUT_TEX_PATH

# if __name__ == '__main__':
#     # running as main function
#     if len(sys.argv) < 5:
#         print("Usage: python script.py <file_path> <tex_file_path> <index_file_path>")
#         sys.exit(1)

#     # Get the filename from the arguments
#     CONTENT_PATH = sys.argv[1] # content book pdf path
#     TEX_PATH = sys.argv[2] # page break output tex path
#     INDEX_PATH = sys.argv[3] # index file path
#     OUTPUT_TEX_PATH = sys.argv[4] #
#     # ROOT = "../../"

#     create_indexing(INDEX_PATH, TEX_PATH, CONTENT_PATH , OUTPUT_TEX_PATH)

import pymupdf
import os, sys
import re
from tqdm import tqdm
from fuzzysearch import find_near_matches

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

def get_main_sub_coords(span_list):
    print(f"Getting main and sub coordinates from {len(span_list)} spans")
    x_list = set()
    pattern = re.compile(r"(.+?),\s*((?:\d+,?\s*)+)")

    for span in span_list:
        text = span['text']
        # match for pattern using regex
        match = pattern.match(text)
        if match:
            x_list.add(int(span['origin'][0]))

    x_list = sorted(list(x_list))
    print(f"Detected x coordinates: {x_list}")
    
    # Check if we have enough x coordinates
    if len(x_list) < 4:
        print(f"Warning: Not enough x coordinates found. Expected 4, got {len(x_list)}")
        return None, None  # Return None to indicate failure
    
    x_main = [x_list[0], x_list[2]]
    x_sub = [x_list[1], x_list[3]]
    print(f"Main coordinates: {x_main}, Sub coordinates: {x_sub}")
    return x_main, x_sub

def check_valid_index(text):
    pattern = re.compile(r"(.+?),\s*((?:\d+,?\s*)+)")
    match = pattern.match(text)
    return True if match else False

def valid_coords(doc):
    print(f"Finding valid coordinates in document with {len(doc)} pages")
    span_list = []
    for page_num, page in enumerate(doc):
        print(f"Analyzing page {page_num+1}/{len(doc)} for coordinates")
        # extract the spans of the page
        text_dict = page.get_text("dict")
        for block in text_dict["blocks"]:
            for line in block["lines"]:
                for span in line["spans"]:
                    if span["text"].strip() == "":
                        continue
                    # store all spans in a list
                    span_list.append(span)

    print(f"Found {len(span_list)} spans with text")
    
    try:
        x_main, x_sub = get_main_sub_coords(span_list)
        if x_main is None or x_sub is None:
            print("Error: Failed to determine coordinates for index entries")
            raise ValueError("Failed to determine index entry coordinates")
        print(f"Successfully determined coordinates: main={x_main}, sub={x_sub}")
        return x_main, x_sub
    except Exception as e:
        print(f"Error determining coordinates: {e}")
        raise

def create_index(INDEX_PATH):
    print(f"Creating index from {INDEX_PATH}")
    try:
        index_pdf = pymupdf.open(INDEX_PATH)
        print(f"Successfully opened index PDF with {len(index_pdf)} pages")
        
        # get valid_coords
        x_main, x_sub = valid_coords(index_pdf)
        
        last_main_entry = None
        pattern = re.compile(r"(.+?),\s*((?:\d+,?\s*)+)")
        index = {}
        entries_processed = 0
        
        for page_num, page in enumerate(index_pdf):
            print(f"Processing page {page_num+1}/{len(index_pdf)} of index PDF")
            # extract the spans of the page
            text_dict = page.get_text("dict")
            for block in text_dict["blocks"]:
                for line in block["lines"]:
                    for span in line["spans"]:
                        if span["text"].strip() == "":
                            continue
                        text = span['text']
                        if check_valid_index(text):
                            match = pattern.match(text)
                            term = match.group(1).strip()
                            pages = [int(p) for p in re.findall(r"\d+", match.group(2))]
                            x_coord = int(span['origin'][0])
                            if x_coord in x_main:
                                last_main_entry = term
                                index[term] = pages
                                entries_processed += 1
                                if entries_processed % 100 == 0:
                                    print(f"Processed {entries_processed} index entries so far")
                            elif x_coord in x_sub:
                                if last_main_entry is None:
                                    print(f"Warning: Found subindex entry '{term}' without a main entry")
                                    continue
                                t = last_main_entry + "!" + term
                                index[t] = pages
                                entries_processed += 1
        
        print(f"Created index with {len(index)} entries from {entries_processed} processed entries")
        if entries_processed == 0:
            print("Warning: No index entries were processed. Check coordinate detection.")
            
        # Debug: Print a few sample entries
        sample_entries = list(index.items())[:5]
        print(f"Sample index entries: {sample_entries}")
        
        return index
    except Exception as e:
        print(f"Error creating index: {e}")
        raise

def clean_and_merge_toc(toc):
    print(f"Cleaning and merging TOC with {len(toc)} entries")
    cleaned_toc = []

    def remove_numbering(title):
        title = title.replace('\r', '').replace('\x0c', 'fi')
        return re.sub(r'^\s*\d+(\.\d+)*\s*', '', title).strip()

    for entry in toc:
        level, title, page = entry
        title_clean = title.replace('\r', '').replace('\x0c', 'fi').strip()

        if cleaned_toc:
            prev_level, prev_title, prev_page = cleaned_toc[-1]
            # If same level and same page, and this one doesn't start with a number — join
            if level == prev_level and page == prev_page and not re.match(r'^\s*\d+(\.\d+)*', title_clean):
                cleaned_toc[-1] = (prev_level, prev_title + " " + title_clean, prev_page)
                continue

        cleaned_title = remove_numbering(title_clean)
        cleaned_toc.append((level, cleaned_title, page))

    print(f"Cleaned TOC now has {len(cleaned_toc)} entries")
    return cleaned_toc

def clean_latex_content(latex_content, toc):
    print(f"Cleaning LaTeX content, initial size: {len(latex_content)} characters")
    # Step 1: Remove the asterisk from section*, subsection*, and chapter*
    latex_content = re.sub(r'\\(section|subsection|chapter)\*{', r'\\\1{', latex_content)
    print("Step 1: Removed asterisks from section commands")
    
    # Step 2: Remove duplicate chapter titles
    seen_chapters = set()

    # This regex pattern captures \chapter{...} and extracts the chapter title
    def remove_duplicate_chapters(match):
        chapter_title = match.group(1)
        if chapter_title in seen_chapters:
            print(f"Removing duplicate chapter: {chapter_title}")
            return ""  # Return an empty string to remove the duplicate chapter
        seen_chapters.add(chapter_title)
        return match.group(0)  # Keep the first occurrence of the chapter

    latex_content = re.sub(r'\\chapter{(.*?)}', remove_duplicate_chapters, latex_content)
    print(f"Step 2: Processed chapter duplicates, found {len(seen_chapters)} unique chapters")

    # make sure the contents are similar to the original toc
    def check_sectioning(latex, toc):
        main_start = latex.find(r"\mainmatter")
        if main_start == -1:
            print("No \\mainmatter found in the LaTeX content.")
            return latex
        
        print("Found \\mainmatter at position:", main_start)
        content_after_main = latex[main_start:]

        toc_dict = {title.lower(): level for level, title, _ in toc}

        print(f"TOC dictionary has {len(toc_dict)} entries")

        mismatches = 0
        def replacer(match):
            nonlocal mismatches
            cmd = match.group(1)         # chapter / section / subsection
            title = match.group(2).strip()
            norm_title = title.lower()

            # Expected level based on LaTeX command
            level_map = {'chapter': 1, 'section': 2, 'subsection': 3}
            expected_level = level_map[cmd]

            # Check if this title exists in TOC
            actual_level = toc_dict.get(norm_title)
            if actual_level is None:
                print(f"Warning: Title '{norm_title}' not found in TOC.")
            if actual_level and actual_level != expected_level:
                # Comment out this line if mismatch
                mismatches += 1
                return f"% Mismatched: \\{cmd}{{{title}}}"

            return match.group(0)

        
        updated_main = re.sub(r"\\(chapter|section|subsection)\{([^\}]+)\}", replacer, content_after_main)
        print(f"Found {mismatches} mismatches between LaTeX and TOC")
        return latex[:main_start] + updated_main

    latex_content = check_sectioning(latex_content, toc)
    print("Step 3: Checked sectioning against TOC")

    def remove_duplicate_sections(latex_content):
        # Split LaTeX into chapter blocks (each starts with \chapter)
        print("Removing duplicate sections and subsections...")
        chapters = re.split(r'(\\chapter\{[^\}]+\})', latex_content)
        print(f"Found {len(chapters)//2} chapters.")
        cleaned_content = ""
        seen_titles = set()
        duplicate = 0
        flip = 1
        
        # Debug the chapters array length
        print(f"Chapters array length: {len(chapters)}")
        
        try:
            for i in range(0, len(chapters), 2):
                print(f"Processing chapter block {i//2 + 1}")
                
                if i >= len(chapters):
                    print(f"Warning: Index {i} out of range for chapters array")
                    break
                    
                pre_chapter = chapters[i]
                
                if i+1 < len(chapters):
                    chapter_heading = chapters[i+1]
                else:
                    print(f"Warning: No chapter heading at index {i+1}")
                    chapter_heading = ""
                
                if i+2 < len(chapters):
                    chapter_block = chapters[i+2]
                else:
                    print(f"Warning: No chapter block at index {i+2}")
                    chapter_block = ""
                
                # Reset for each chapter
                seen_titles.clear()

                # Replace duplicate sections/subsections
                def remove_duplicates(match):
                    nonlocal duplicate
                    command = match.group(1)
                    title = match.group(2).strip().lower()
                    if title in seen_titles:
                        duplicate += 1
                        print(f"Found duplicate {command}: '{title}'")
                        return ''  # remove duplicate
                    seen_titles.add(title)
                    return match.group(0)

                cleaned_block = re.sub(r'\\(section|subsection)\{([^\}]+)\}', remove_duplicates, chapter_block)
                
                if flip == 1:
                    cleaned_content += pre_chapter + chapter_heading + cleaned_block
                    flip = 0
                else:
                    cleaned_content += chapter_heading + cleaned_block
                    
        except Exception as e:
            print(f"Error in remove_duplicate_sections: {e}")
            raise

        print(f"Removed {duplicate} duplicate sections/subsections")
        return cleaned_content
        
    try:
        latex_content = remove_duplicate_sections(latex_content)
        print(f"Final cleaned LaTeX content size: {len(latex_content)} characters")
    except Exception as e:
        print(f"Error cleaning LaTeX content: {e}")
        raise

    return latex_content

def add_indexes(latex_content, index, book_len, toc):
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
    
    for index_term, pages in tqdm(index.items()):
        for page in pages:
            # Debug for specific terms, if needed
            debug = (index_term == 'application')  # Example term to debug
            
            if debug:
                print(f"DEBUG: Processing '{index_term}' on page {page}")
            
            try:
                # Find page boundaries
                upper_bound = find_closest_page(page+1, page_breaks, page_positions, book_len, True)
                lower_bound = find_closest_page(page-2, page_breaks, page_positions, False)
                
                if debug:
                    print(f"DEBUG: Page {page} bounds - lower: {lower_bound}, upper: {upper_bound}")
                
                if upper_bound == -1 or lower_bound == 0:
                    print(f"Warning: Could not find proper bounds for page {page} with term '{index_term}'")
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
                print(f"Error processing term '{index_term}' on page {page}: {e}")
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
        print(f"Adding {len(not_found_index_terms)} not found terms to page {page}")
        
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

            # Move forward until a newline
            next_newline_pos = latex_content.find("\n", index_position)
            if next_newline_pos == -1:
                print(f"Warning: No newline found after position {index_position}")
                next_newline_pos = upper_bound  # In case no newline is found, go till the end of the content

            # Debug info to see what we're inserting and where
            try:
                context_before = latex_content[next_newline_pos-10:next_newline_pos]
                context_after = latex_content[next_newline_pos:next_newline_pos+10]
                print(f"Inserting {len(not_found_index_terms)} index entries at position {next_newline_pos}")
                print(f"Context: ...{context_before}|HERE|{context_after}...")
            except Exception as e:
                print(f"Error showing context: {e}")
            
            latex_content = latex_content[:next_newline_pos] + index_string + latex_content[next_newline_pos:]
        
        except Exception as e:
            print(f"Error processing not found terms for page {page}: {e}")

    # Clean up the LaTeX content
    print("Cleaning LaTeX content after adding indexes")
    latex_content = clean_latex_content(latex_content, toc)
    return latex_content, not_found_terms

def create_indexing(INDEX_PATH, TEX_PATH, CONTENT_PATH, OUTPUT_TEX_PATH):
    print("\n=== Step 4: Adding Indexing ===")
    print(f"Creating index from: {INDEX_PATH}")
    print(f"Using LaTeX file: {TEX_PATH}")
    print(f"Using content book: {CONTENT_PATH}")
    
    try:
        # Create index
        index = create_index(INDEX_PATH)
        print(f"Successfully created index with {len(index)} entries")
        
        # Read LaTeX content
        latex_content = read_latex(TEX_PATH)
        print(f"Successfully read LaTeX content ({len(latex_content)} characters)")
        
        # READ CONTENT BOOK
        try:
            content_book_pdf = pymupdf.open(CONTENT_PATH)
            print(f"Successfully opened content book PDF with {len(content_book_pdf)} pages")
            
            toc = content_book_pdf.get_toc()
            print(f"Retrieved TOC with {len(toc)} entries")
            
            toc = clean_and_merge_toc(toc)
            book_len = len(content_book_pdf)
            
            # Extract page breaks once
            page_breaks = re.findall(r'%---- Page End Break Here ---- Page : (\d+)', latex_content)
            page_positions = {int(page): pos for page, pos in zip(page_breaks, [m.start() for m in re.finditer(r'%---- Page End Break Here ---- Page : \d+', latex_content)])}
            print(f"Found {len(page_breaks)} page breaks in the LaTeX content")
            
            # Add indexes to LaTeX content
            latex_content, not_found = add_indexes(latex_content, index, book_len, toc)
            print(f"Successfully added indexes. {len(not_found)} terms were not found and handled.")
            
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