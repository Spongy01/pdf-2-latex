import pymupdf
import os, sys
import re
from tqdm import tqdm
from fuzzysearch import find_near_matches
import re




def read_latex(TEX_PATH):
    with open(TEX_PATH, "r") as f:
        latex_content = f.read()
    return latex_content

def find_closest_page(page,page_breaks ,page_positions, book_len , is_forward=True):

    if str(page) in page_breaks:
        return page_positions[page]
    if is_forward:
        bound = book_len
        forward = page
        while (forward) <= bound:
            if str(forward) in page_breaks:
                return page_positions[forward]
            forward += 1
        return -1
    
    else:
        bound = 0
        backward = page
        while (backward) >= bound:
            if str(backward) in page_breaks:
                return page_positions[backward]
            backward -= 1
        return 0  # No valid page found


def get_main_sub_coords(span_list):
  x_list = set()
  pattern = re.compile(r"(.+?),\s*((?:\d+,?\s*)+)")

  for span in span_list:
    text = span['text']
    # match for pattern using regex
    match = pattern.match(text)
    if match:
      x_list.add(int(span['origin'][0]))
    
  x_list = sorted(list(x_list))
  print(x_list)
  x_main = [x_list[0], x_list[2]]
  x_sub = [x_list[1], x_list[3]]
  return x_main, x_sub



def check_valid_index(text):
  pattern = re.compile(r"(.+?),\s*((?:\d+,?\s*)+)")
  match = pattern.match(text)
  if match:
    return True
  return False


def valid_coords(doc):
    span_list = []
    for page in doc:
    # extract the spans of the page
        text_dict = page.get_text("dict")
        for block in text_dict["blocks"]:
            for line in block["lines"]:
                for span in line["spans"]:
                    if span["text"].strip() == "":
                        continue
                    # store all spans in a list
                    span_list.append(span)
                    # print(span)


    # sort the span list 
    # get 2 main entries and 2 subindex entries

        x_main, x_sub = get_main_sub_coords(span_list)
        break

    return x_main, x_sub




def create_index(INDEX_PATH):
    index_pdf = pymupdf.open(INDEX_PATH)
    
    # for i in range(len(index_pdf)):
    #     page = index_pdf[i]
    #     index_data[i] = page.get_text("text")

    # get valid_coords
    x_main, x_sub = valid_coords(index_pdf)



    last_main_entry = None
    pattern = re.compile(r"(.+?),\s*((?:\d+,?\s*)+)")
    index = {}
    for page in index_pdf:
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
                        elif x_coord in x_sub:
                            t = last_main_entry + "!" + term
                            index[t] = pages
    return index


def clean_and_merge_toc(toc):
    cleaned_toc = []

    def remove_numbering(title):
        title = title.replace('\r', '').replace('\x0c', 'fi')
        return re.sub(r'^\s*\d+(\.\d+)*\s*', '', title).strip()

    for entry in toc:
        level, title, page = entry
        title_clean = title.replace('\r', '').replace('\x0c', 'fi').strip()

        if cleaned_toc:
            prev_level, prev_title, prev_page = cleaned_toc[-1]
            # If same level and same page, and this one doesn’t start with a number — join
            if level == prev_level and page == prev_page and not re.match(r'^\s*\d+(\.\d+)*', title_clean):
                cleaned_toc[-1] = (prev_level, prev_title + " " + title_clean, prev_page)
                continue

        cleaned_title = remove_numbering(title_clean)
        cleaned_toc.append((level, cleaned_title, page))

    return cleaned_toc


def clean_latex_content(latex_content, toc):
    # Step 1: Remove the asterisk from section*, subsection*, and chapter*
    latex_content = re.sub(r'\\(section|subsection|chapter)\*{', r'\\\1{', latex_content)

    # Step 2: Remove duplicate chapter titles
    seen_chapters = set()
    
    # This regex pattern captures \chapter{...} and extracts the chapter title
    def remove_duplicate_chapters(match):
        chapter_title = match.group(1)
        if chapter_title in seen_chapters:
            return ""  # Return an empty string to remove the duplicate chapter
        seen_chapters.add(chapter_title)
        return match.group(0)  # Keep the first occurrence of the chapter

    latex_content = re.sub(r'\\chapter{(.*?)}', remove_duplicate_chapters, latex_content)

    # make sure the contents are similar to the original toc
    def check_sectioning(latex, toc):
        main_start = latex_content.find(r"\mainmatter")
        if main_start == -1:
            print("No \\mainmatter found in the LaTeX content.")
            return latex_content
        
        print("Found \\mainmatter at position:", main_start)
        content_after_main = latex_content[main_start:]

        toc_dict = {title.lower(): level for level, title, _ in toc}

        print("toc_dict: ", toc_dict)

        def replacer(match):
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
                return f"% Mismatched: \\{cmd}name{{{title}}}"

            return match.group(0)

        
        updated_main = re.sub(r"\\(chapter|section|subsection)\{([^\}]+)\}", replacer, content_after_main)
        return latex[:main_start] + updated_main
    
    latex_content = check_sectioning(latex_content, toc)


    def remove_duplicate_sections(latex_content):
        # Split LaTeX into chapter blocks (each starts with \chapter)
        print("Removing duplicate sections and subsections...")
        chapters = re.split(r'(\\chapter\{[^\}]+\})', latex_content)
        print(f"Found {len(chapters)//2} chapters.")
        cleaned_content = ""
        seen_titles = set()
        duplicate = 0
        flip = 1
        for i in range(0, len(chapters), 2):
            # print("I is ", i)
            pre_chapter = chapters[i]
            chapter_heading = chapters[i+1] if i+1 < len(chapters) else ""
            chapter_block = chapters[i+2] if i+2 < len(chapters) else ""
            

            # print("Chapter heading: ", chapter_heading)
            # Reset for each chapter
            seen_titles.clear()

            # Replace duplicate sections/subsections
            def remove_duplicates(match):
                command = match.group(1)
                title = match.group(2).strip().lower()
                if title in seen_titles:
                    nonlocal duplicate
                    duplicate += 1
                    # print(f"Duplicate found: {title} in {command}")
                    return ''  # remove duplicate
                seen_titles.add(title)
                return match.group(0)

            cleaned_block = re.sub(r'\\(section|subsection)\{([^\}]+)\}', remove_duplicates, chapter_block)
            if flip == 1:
                cleaned_content += pre_chapter + chapter_heading + cleaned_block
                flip = 0
            else:
                cleaned_content += chapter_heading + cleaned_block


        return cleaned_content
    latex_content = remove_duplicate_sections(latex_content)


    return latex_content



def add_indexes(latex_content, index, book_len, toc): 
    matched = 0
    not_matched = 0
    not_found_terms = {}  # Dictionary to store terms not found along with page numbers

    for index_term, pages in tqdm(index.items()):
        # check = False
        # if index_term == 'application':
        #     check = True
        for page in pages:
            # upadte page number indexes as terms will be added

            page_breaks = re.findall(r'%---- Page End Break Here ---- Page : (\d+)', latex_content)
            page_positions = {int(page): pos.start() for page, pos in zip(page_breaks, re.finditer(r'%---- Page End Break Here ---- Page : \d+', latex_content))}

            upper_bound = find_closest_page(page+1, page_breaks, page_positions ,True)
            lower_bound = find_closest_page(page-2, page_breaks, page_positions ,False)

            page_content = latex_content[lower_bound:upper_bound]
            
            # match = re.search(r'\b' + re.escape(index_term) + r'\b', page_content, re.IGNORECASE)
            term = index_term
            if '!' in index_term:
                # subindex entry
                term = index_term.split("!", 1)[1]
            match = re.search(  re.escape(term), page_content, re.IGNORECASE)

            if match:
                # pattern = r"\{[^{}]*\b" + re.escape(index_term) + r"\b[^{}]*\}"
                pattern = (
                    r"\{[^{}]*" + re.escape(term) + r"[^{}]*\}" +
                    r"|" +  # OR
                    r"\[[^\[\]]*" + re.escape(term) + r"[^\[\]]*\]"
                )
                brace_match = re.search( pattern, page_content, re.IGNORECASE)
                if brace_match:
                    # word is inside a command
                    term_end = lower_bound + brace_match.end() + 1
                    indexed_term = "\index{" + index_term + "}"
                    latex_content = latex_content[:term_end] + indexed_term + latex_content[term_end:]
                
                else:
                    # word is not inside a command

                    term_end = lower_bound + match.end() + 1
                    indexed_term = "\index{" + index_term + "}"
                    latex_content = latex_content[:term_end] + indexed_term + latex_content[term_end:]

                
                matched += 1
                continue
                # old code
                term_start = lower_bound + match.start()  # Adjust index relative to book_text
                term_end = term_start + len(index_term)
                indexed_term = "\index{" + index_term + "}"
                latex_content = latex_content[:term_start] +index_term + indexed_term + latex_content[term_end:]
                matched += 1
            else:
                # # try fuzzy matching
                # term_length = len(index_term)
                # max_dist = max(1, term_length // 3)  # 1/3rd of term length
                # near_matches = find_near_matches(index_term, page_content, max_l_dist=max_dist)

                # if near_matches:
                #     best_match = min(near_matches, key=lambda x: x.dist)  # Get the closest match
                #     term_start = lower_bound + best_match.start  # Adjust index relative to book_text
                #     term_end = term_start + term_length
                #     indexed_term = "\index{" + index_term + "}"
                #     latex_content = latex_content[:term_start] + index_term + indexed_term + latex_content[term_end:]
                #     matched += 1
                #     continue
                
                ################################################################################################
                # New try failed

                # index_position = lower_bound + (upper_bound - lower_bound) // 2
                # middle_content = latex_content[index_position: index_position+1]  # Extract some content around the middle
                # pattern = r"\{[^{}]*\b" + re.escape(middle_content) + r"\b[^{}]*\}"

                # brace_match = re.search( pattern, page_content, re.IGNORECASE)
                
                # if brace_match:
                #     # word is inside a command
                #     term_end = lower_bound + brace_match.end() + 1
                #     indexed_term = "\index{" + index_term + "}"
                #     latex_content = latex_content[:term_end] + indexed_term + latex_content[term_end:]
                #     matched += 1
                # else:
                #     indexed_term = "\index{" + index_term + "}"
                #     latex_content = latex_content[:index_position] + indexed_term + latex_content[index_position:]
                #     matched += 1
                    
                if index_term not in not_found_terms:
                    not_found_terms[index_term] = []
                not_found_terms[index_term].append(page)

    # print(f"Matched: {matched}, Not Matched: {not_matched}")

    # handle not found terms
    page_based_terms = {}

    # Iterate through the original not_found_terms dictionary
    for index_term, pages in not_found_terms.items():
        for page in pages:
            if page not in page_based_terms:
                page_based_terms[page] = []  # Initialize list if page is not already in the dictionary
            page_based_terms[page].append(index_term)  # Add the index term to the list for the current page

    
    for page, not_found_index_terms in page_based_terms.items():
        index_string = ""
        index_string = "".join([f"\\index{{{term}}}" for term in not_found_index_terms])

        page_breaks = re.findall(r'%---- Page End Break Here ---- Page : (\d+)', latex_content)
        page_positions = {int(page): pos.start() for page, pos in zip(page_breaks, re.finditer(r'%---- Page End Break Here ---- Page : \d+', latex_content))}

        upper_bound = find_closest_page(page+0, page_breaks, page_positions ,True)
        lower_bound = find_closest_page(page-1, page_breaks, page_positions ,False)

        page_content = latex_content[lower_bound:upper_bound]
        index_position = lower_bound + (upper_bound - lower_bound) // 2

        # Move forward until a newline
        next_newline_pos = latex_content.find("\n", index_position)
        if next_newline_pos == -1:
            next_newline_pos = upper_bound  # In case no newline is found, go till the end of the content

        latex_content = latex_content[:next_newline_pos] + index_string + latex_content[next_newline_pos:]


        # middle_content = latex_content[index_position: index_position+1]  # Extract some content around the middle
        # pattern = (
        #     r"\{[^{}]*" + re.escape(middle_content) + r"[^{}]*\}" +
        #     r"|" +  # OR
        #     r"\[[^\[\]]*" + re.escape(middle_content) + r"[^\[\]]*\]"
        # )
        # brace_match = re.search( pattern, page_content, re.IGNORECASE)
        # if brace_match:
        #     # word is inside a command
        #     term_end = lower_bound + brace_match.end() + 1        
        #     latex_content = latex_content[:term_end] + index_string + latex_content[term_end:]
        # else:
        #     latex_content = latex_content[:index_position] + index_string + latex_content[index_position:]

    # Clean up the LaTeX content
    latex_content = clean_latex_content(latex_content, toc)
    return latex_content, not_found_terms



def create_indexing(INDEX_PATH, TEX_PATH, CONTENT_PATH , OUTPUT_TEX_PATH):

    # Create index
    index = create_index(INDEX_PATH)

    # Read LaTeX content
    latex_content = read_latex(TEX_PATH)

    # READ CONTENT BOOK
    content_book_pdf = pymupdf.open(CONTENT_PATH)
    toc = content_book_pdf.get_toc()
    toc = clean_and_merge_toc(toc)
    book_len = len(content_book_pdf)
    page_breaks = re.findall(r'%---- Page End Break Here ---- Page : (\d+)', latex_content)
    page_positions = {int(page): pos.start() for page, pos in zip(page_breaks, re.finditer(r'%---- Page End Break Here ---- Page : \d+', latex_content))}


    # Add indexes to LaTeX content
    latex_content, _ = add_indexes(latex_content, index, book_len, toc)

    # Write the updated LaTeX content to a new file
    with open(OUTPUT_TEX_PATH, "w", encoding="utf-8") as file:
        file.write(latex_content)


if __name__ == '__main__':
    # running as main function
    if len(sys.argv) < 5:
        print("Usage: python script.py <file_path> <tex_file_path> <index_file_path>")
        sys.exit(1)

    # Get the filename from the arguments
    CONTENT_PATH = sys.argv[1] # content book pdf path
    TEX_PATH = sys.argv[2] # page break output tex path
    INDEX_PATH = sys.argv[3] # index file path
    OUTPUT_TEX_PATH = sys.argv[4] #
    # ROOT = "../../"

    create_indexing(INDEX_PATH, TEX_PATH, CONTENT_PATH , OUTPUT_TEX_PATH)