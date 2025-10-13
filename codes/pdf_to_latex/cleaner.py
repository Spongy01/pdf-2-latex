import pymupdf
import re
import fitz
import sys

# 1. Remove * from section titles
def remove_star_from_sectioning(input_tex: str) -> str:
    """
    Removes the * from \chapter*, \section*, \subsection*, \subsubsection*
    and converts them to their non-starred versions.
    """
    pattern = r'\\(chapter|section|subsection|subsubsection)\*\{(.*?)\}'
    replacement = r'\\\1{\2}'
    return re.sub(pattern, replacement, input_tex, flags=re.DOTALL)

# 2. Remove initial numbers from section titles
def remove_leading_numbers_from_headings(input_tex: str) -> str:
    """
    Removes leading numbers (like '7.10 ') from chapter/section/subsection/subsubsection titles.
    """
    pattern = r'(\\(?:chapter|section|subsection|subsubsection)\{)\s*\d+(?:\.\d+)*\s*(.*?)\}'
    replacement = r'\1\2}'
    return re.sub(pattern, replacement, input_tex)

# 3. Remove empty sections or chapters
def remove_empty_headings(input_tex: str) -> str:
    """
    Removes chapter/section/subsection/subsubsection headings that have no
    actual text content before the next heading or end of file.
    """
    # Split the tex into (heading, content) pairs
    pattern = r'(\\(?:chapter|section|subsection|subsubsection)\{.*?\})(.*?)(?=(\\(?:chapter|section|subsection|subsubsection)\{|$))'
    
    def replacer(match):
        heading = match.group(1)
        content = match.group(2)
        # If content is only whitespace/newlines, drop this heading block
        if content.strip() == '':
            return ''
        return heading + content

    return re.sub(pattern, replacer, input_tex, flags=re.DOTALL)


# 4. Replace contents section with \tableofcontents

# extract a good quality TOC from the PDF file
def get_cleaned_toc(pdf_path: str):
    """
    Extracts the table of contents from a PDF and removes leading numbers
    from the titles (like '1.2.3 ' or '1\\r').
    """
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    
    cleaned_toc = []
    for level, title, page in toc:
        # Clean \r and other weird whitespace
        title = title.replace('\r', ' ').strip()
        # Remove leading numbers + dots (like "1.2.3 " or "7 ")
        title = re.sub(r'^\s*\d+(?:\.\d+)*\s*', '', title)
        cleaned_toc.append([level, title, page])
    
    return cleaned_toc


# fix latex file with the chapters
def fix_latex_headings(input_tex: str, cleaned_toc: list) -> str:
    """
    Fix LaTeX headings based on cleaned TOC and print changes.

    Parameters:
        input_tex (str): The LaTeX document as a string.
        cleaned_toc (list): List of tuples [(level, title, page), ...] from TOC.

    Returns:
        str: Corrected LaTeX string.
    """
    # Build a mapping from TOC title -> level
    toc_map = {title: level for (level, title, _) in cleaned_toc}

    # Regex to match all LaTeX headings
    heading_pattern = re.compile(r'\\(chapter|section|subsection|subsubsection)\{(.*?)\}')
    
    # Use provided parameters for chapter level mapping
    print(f"Using chapter level: {chapter_level}")
    print(f"Using section level: {section_level}")
    print(f"Using subsection level: {subsection_level}")

    # Map TOC levels to LaTeX commands based on user input
    level_to_cmd = {
        int(chapter_level): 'chapter',
        int(section_level): 'section',
        int(subsection_level): 'subsection',
    }
    def correct_heading(match):
        current_cmd = match.group(1)      # current LaTeX command
        title = match.group(2).strip()    # heading title

        

        

        # Check if this title exists in TOC
        if title in toc_map:
            toc_level = toc_map[title]

            # Map TOC level to LaTeX command
            
            correct_cmd = level_to_cmd.get(toc_level, current_cmd)

            if correct_cmd != current_cmd:
                print(f"Modified Heading :: {title} : {current_cmd} -> {correct_cmd}")
                return f'\\{correct_cmd}{{{title}}}'

        return match.group(0)  # no change

    # Replace all headings with corrected ones
    corrected_tex = heading_pattern.sub(correct_heading, input_tex)
    return corrected_tex

def replace_first_contents_with_toc(input_tex: str) -> str:
    """
    Replace the first chapter/section/subsection whose title contains 'content' or 'contents'
    with \tableofcontents.
    Only removes the section starting from that heading until the next heading of the same or higher level.
    """
    # Match headings and capture level
    heading_pattern = re.compile(
        r'\\(chapter|section|subsection|subsubsection)\{.*?(content|contents).*?\}',
        re.IGNORECASE
    )

    match = heading_pattern.search(input_tex)
    if not match:
        # No "Contents"-like heading found
        return input_tex

    start_idx = match.start()
    end_idx = match.end()
    heading_level = match.group(1)  # chapter, section, etc.

    # Map LaTeX headings to numeric levels
    level_map = {'chapter': 1, 'section': 2, 'subsection': 3, 'subsubsection': 4}
    this_level = level_map.get(heading_level, 2)  # default to 2 if unknown

    # Find the next heading of same or higher level after this match
    next_heading_pattern = re.compile(
        r'\\(chapter|section|subsection|subsubsection)\{',
        re.IGNORECASE
    )

    next_matches = list(next_heading_pattern.finditer(input_tex, end_idx))
    for nm in next_matches:
        next_level = level_map.get(nm.group(1).lower(), 2)
        if next_level <= this_level:
            end_idx = nm.start()
            break
    else:
        # No next heading found; remove until the end
        end_idx = len(input_tex)

    # Replace the "Contents" section with \tableofcontents
    print(f"Removed '{input_tex[match.start():end_idx][:60]}... {input_tex[match.start():end_idx][:-60]}' and replaced with \\tableofcontents")
    new_tex = input_tex[:start_idx] + "\\tableofcontents\n\n" + input_tex[end_idx:]
    return new_tex


def clean_it_up(INPUT_TEX_FILE: str, BOOK_PDF_FILE: str, OUTPUT_TEX_FILE: str, chapter_level: int = 0, section_level: int = 1, subsection_level: int = 2):
    # INPUT_TEX_FILE = "../../files/data-science-book_book/outputs/data-science-book_pg_sep_bib.tex"
    # BOOK_PDF_FILE = "../../files/data-science-book_book/inputs/data-science-book.pdf"
    # OUTPUT_TEX_FILE = "../../files/data-science-book_book/outputs/data-science-book_pg_sep_testing_cleaned.tex"

    print("\n=== Step 4: Cleaning it up ===")
    print(f"Using LaTeX file: {INPUT_TEX_FILE}")
    print(f"Using content book: {BOOK_PDF_FILE}")

    tex_file = ""
    with open(INPUT_TEX_FILE, "r") as file:
        tex_file = file.read()      # Read the entire file
        # print(tex_file[1000:1500])  # Print the first 500 characters to verify
        print(f"Length of tex file: {len(tex_file)} characters")

    unstared_tex = remove_star_from_sectioning(tex_file)
    print("Removed * from section titles")
    no_numbers_tex = remove_leading_numbers_from_headings(unstared_tex)
    print("Removed leading numbers from section titles")
    cleaned_tex = remove_empty_headings(no_numbers_tex)
    print("Removed empty sections/chapters from the tex file")

    # get cleaned toc
    toc = get_cleaned_toc(BOOK_PDF_FILE)
    print(f"Extracted TOC with {len(toc)} entries")

    fixed_headings_tex = fix_latex_headings(cleaned_tex, toc)
    print("Fixed LaTeX headings based on cleaned TOC")
    final_tex = replace_first_contents_with_toc(fixed_headings_tex)
    print("Replaced 'Contents' section/chapter with \\tableofcontents")

    # Write the final cleaned LaTeX to the output file
    with open(OUTPUT_TEX_FILE, "w") as out_file:
        out_file.write(final_tex)
    print(f"Final cleaned LaTeX written to: {OUTPUT_TEX_FILE}")

    return OUTPUT_TEX_FILE



if __name__ == '__main__':
    print("Starting cleaning script")
    # running as main function
    if len(sys.argv) < 4:
        print("Usage: python script.py <tex_file_path> <content_book_pdf_path> <output_tex_path>")
        sys.exit(1)

    try:
        # Get the filename from the arguments
        TEX_PATH = sys.argv[1]  # content book pdf path
        CONTENT_PATH = sys.argv[2]      # tex path
        OUTPUT_TEX_PATH = sys.argv[3]
        
        print(f"Content Book Path: {CONTENT_PATH}")
        print(f"LaTeX File Path: {TEX_PATH}")
        print(f"Output File Path: {OUTPUT_TEX_PATH}")
        
        clean_it_up(TEX_PATH, CONTENT_PATH, OUTPUT_TEX_PATH)
        print("Indexing completed successfully!")
    except Exception as e:
        print(f"Error during indexing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


    

