import pymupdf
import os, sys
import re
from tqdm import tqdm
from fuzzysearch import find_near_matches
import re



def create_index(INDEX_PATH):
    index_pdf = pymupdf.open(INDEX_PATH)
    index_data = {}
    for i in range(len(index_pdf)):
        page = index_pdf[i]
        index_data[i] = page.get_text("text")
    
    pattern = re.compile(r"(.+?),\s*((?:\d+,?\s*)+)")
    index = {}
    for page, text in index_data.items():
        for match in pattern.finditer(text):
            term = match.group(1).strip()
            pages = [int(p) for p in re.findall(r"\d+", match.group(2))]
            index[term] = pages

    return index

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


def add_indexes(latex_content, index, book_len): 
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
            match = re.search(  re.escape(index_term), page_content, re.IGNORECASE)

            if match:
                term_start = lower_bound + match.start()  # Adjust index relative to book_text
                term_end = term_start + len(index_term)
                indexed_term = "\index{" + index_term + "}"
                latex_content = latex_content[:term_start] +index_term + indexed_term + latex_content[term_end:]
                matched += 1
            else:
                # try fuzzy matching
                term_length = len(index_term)
                max_dist = max(1, term_length // 3)  # 1/3rd of term length
                near_matches = find_near_matches(index_term, page_content, max_l_dist=max_dist)

                if near_matches:
                    best_match = min(near_matches, key=lambda x: x.dist)  # Get the closest match
                    term_start = lower_bound + best_match.start  # Adjust index relative to book_text
                    term_end = term_start + term_length
                    indexed_term = "\index{" + index_term + "}"
                    latex_content = latex_content[:term_start] + index_term + indexed_term + latex_content[term_end:]
                    matched += 1
                    continue

                # index_position = lower_bound + (upper_bound - lower_bound) // 2
                # indexed_term = "\index{" + index_term + "}"
                # latex_content = latex_content[:index_position] + indexed_term + latex_content[index_position:]
                
                not_matched += 1
                if index_term not in not_found_terms:
                    not_found_terms[index_term] = []
                not_found_terms[index_term].append(page)

    # print(f"Matched: {matched}, Not Matched: {not_matched}")
    return latex_content, not_found_terms



def create_indexing(INDEX_PATH, TEX_PATH, CONTENT_PATH , OUTPUT_TEX_PATH):

    # Create index
    index = create_index(INDEX_PATH)

    # Read LaTeX content
    latex_content = read_latex(TEX_PATH)

    # READ CONTENT BOOK
    content_book_pdf = pymupdf.open(CONTENT_PATH)
    book_len = len(content_book_pdf)
    page_breaks = re.findall(r'%---- Page End Break Here ---- Page : (\d+)', latex_content)
    page_positions = {int(page): pos.start() for page, pos in zip(page_breaks, re.finditer(r'%---- Page End Break Here ---- Page : \d+', latex_content))}


    # Add indexes to LaTeX content
    latex_content, _ = add_indexes(latex_content, index, book_len)

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