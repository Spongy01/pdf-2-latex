# import sys
# import os
# import fitz
# from tqdm import tqdm
# import shutil
# from fuzzysearch import find_near_matches

# def read_files(BOOK_PATH, TEX_PATH):
#     # Read the book (original pdf) and the LaTeX content (generated from mathpix)
#     book_pdf = fitz.open(BOOK_PATH)
#     with open(TEX_PATH, "r") as f:
#         latex_content = f.read()
    
#     return book_pdf, latex_content

# def add_linebreak_comment(match,latex_content ,page_num):
#     end_index = match.end
#     content="\n%---- Page End Break Here ---- Page : " + str(page_num) + "\n"
#     latex_content = latex_content[:end_index] + content + latex_content[end_index:]
#     return latex_content

# def pattern_matcher(content_range,latex_content,book_page_data,page_numbers, max_l_dist= 10,stop_counter=None, ):
#     matched_count = 0
#     # latex_content = latex_content.copy()
#     not_matched_count = 0
    
#     if stop_counter is None:
#         stop_counter = len(book_page_data)

#     for page_num, page_data in tqdm(book_page_data.items()):
#         if len(page_data) == 0:
#             continue

#         if stop_counter == 0:
#             break
#         to_match = page_data[content_range:]
        
#         matches = find_near_matches(to_match, latex_content, max_l_dist=max_l_dist)
#         if matches:
#             latex_content = add_linebreak_comment(matches[0], latex_content, page_numbers[page_num])
#             matched_count += 1
#         else:  
#             not_matched_count += 1
#         stop_counter -= 1
    
#     # print metrics
#     print("Matched PageBreaks: {}".format(matched_count))
#     print("Not Matched PageBreaks: {}".format(not_matched_count))
        
#     return latex_content

# def create_page_seperators(BOOK_PATH, TEX_PATH, OUTPUT_TEX_PATH):
#     # read books
#     print("\n=== Step 1: Creating Page Separators ===")
#     book_pdf, latex_content = read_files(BOOK_PATH, TEX_PATH)

#     # preprocess book metadata
#     book_page_data = {}
#     page_numbers = []
#     for i in range(len(book_pdf)):
#         page = book_pdf[i]
#         page_numbers.append(page.get_label())
#         # check if label is integer
#         if page.get_label() is None or not page.get_label().isdigit():
#             page_numbers[i] = i + 1
#         book_page_data[i] = page.get_text("text").replace("\n", " ")

#     # match page end patterns to add pagebreaks
#     print("Creating Page Breaks...\n")
#     new_latex_content = pattern_matcher(-100,latex_content,book_page_data, page_numbers, 10)

#     os.makedirs(os.path.dirname(OUTPUT_TEX_PATH), exist_ok=True)
#     with open(OUTPUT_TEX_PATH, "w", encoding="utf-8") as file:
#         file.write(new_latex_content)

#     print(f"Page Breaks created successfully at\n\t{OUTPUT_TEX_PATH}")
#     return book_pdf, new_latex_content, page_numbers

# if __name__ == '__main__':
#     # running as main function
#     if len(sys.argv) < 3:
#         print("Usage: python script.py <file_path> <tex_file_path>")
#         sys.exit(1)

#     # Get the filename from the arguments
#     file_path = sys.argv[1]
#     tex_file_path = sys.argv[2]
#     ROOT = "../../"

#     file_name = os.path.splitext(os.path.basename(file_path))[0]  # Extract 'file_name' from path
#     tex_filename = os.path.basename(tex_file_path)  # Extract actual .tex filename

#     book_folder = os.path.join(ROOT, f"files/{file_name}_book/")
#     tex_folder   = os.path.join(book_folder, f"{file_name}_book_tex/")
#     output_tex_folder = os.path.join(book_folder, f"outputs")

#     os.makedirs(book_folder, exist_ok=True)
#     os.makedirs(tex_folder, exist_ok=True)
#     os.makedirs(output_tex_folder, exist_ok=True)

#     # Define target file paths
#     BOOK_PATH = os.path.join(book_folder, f"{file_name}.pdf")
#     TEX_PATH = os.path.join(tex_folder, f"{file_name}.tex")
#     OUTPUT_TEX_PATH = os.path.join(output_tex_folder, f"{file_name}_pg_sep.tex" )
#     if not os.path.exists(BOOK_PATH):
#         shutil.copy2(file_path, BOOK_PATH)
#         print(f"Moved {file_path} -> {BOOK_PATH}")
#     else:
#         print(f"{BOOK_PATH} already exists.")

#     # Move TEX file if not already in the folder
#     if not os.path.exists(TEX_PATH):
#         shutil.copy2(tex_file_path, TEX_PATH)
#         print(f"Moved {tex_file_path} -> {TEX_PATH}")
#     else:
#         print(f"{TEX_PATH} already exists.")

#     create_page_seperators(BOOK_PATH, TEX_PATH, OUTPUT_TEX_PATH)

import sys
import os
import fitz
from tqdm import tqdm
import shutil
from fuzzysearch import find_near_matches
import re

def read_files(BOOK_PATH, TEX_PATH):
    print(f"🔍 Reading book from: {BOOK_PATH}")
    print(f"🔍 Reading LaTeX from: {TEX_PATH}")
    book_pdf = fitz.open(BOOK_PATH)
    with open(TEX_PATH, "r", encoding="utf-8") as f:
        latex_content = f.read()
    print("✅ Successfully read PDF and LaTeX files.\n")
    return book_pdf, latex_content

def add_linebreak_comment(match, latex_content, page_num):
    print(f"✏️ Adding linebreak comment at index {match.end} for page {page_num}")
    end_index = match.end
    content = "\n%---- Page End Break Here ---- Page : " + str(page_num) + "\n"
    latex_content = latex_content[:end_index] + content + latex_content[end_index:]
    return latex_content

def normalize(text):
    return re.sub(r'\s+', ' ', text.strip().lower())

def pattern_matcher(content_range, latex_content, book_page_data, page_numbers, stop_counter=None):
    matched_count = 0
    not_matched_count = 0

    if stop_counter is None:
        stop_counter = len(book_page_data)
    print(f"🔍 Starting pattern matching for {stop_counter} pages (adaptive max_l_dist)...")

    original_latex_content = latex_content  # For modification

    for page_num, page_data in tqdm(book_page_data.items()):
        if len(page_data) == 0:
            print(f"⚠️ Page {page_num} has no text, skipping...")
            continue

        if stop_counter == 0:
            break

        to_match = page_data[content_range:]
        # normalized_to_match = normalize(to_match)

        print(f"\n🔍 Page {page_num} | Label: {page_numbers[page_num]}")
        print(f"🧩 Trying match with snippet: \"{to_match[:100]}...\"")

        match_found = False
        for distance in range(16, 28, 4):
            matches = find_near_matches(to_match, latex_content, max_l_dist=distance)
            if matches:
                print(f"✅ Match found with max_l_dist={distance} at {matches[0].start}–{matches[0].end}")
                original_latex_content = add_linebreak_comment(matches[0], original_latex_content, page_numbers[page_num])
                matched_count += 1
                match_found = True
                break

        if not match_found:
            not_matched_count += 1
            print(f"❌ No match found for page {page_numbers[page_num]}")

        stop_counter -= 1

    print("\n📊 Matching Summary:")
    print(f"✔️ Matched Page Breaks: {matched_count}")
    print(f"❌ Not Matched Page Breaks: {not_matched_count}")

    return original_latex_content


def create_page_seperators(BOOK_PATH, TEX_PATH, OUTPUT_TEX_PATH):
    print("\n=== 🛠️ Step 1: Creating Page Separators ===")
    book_pdf, latex_content = read_files(BOOK_PATH, TEX_PATH)

    print("📄 Extracting text from PDF pages...\n")
    book_page_data = {}
    page_numbers = []
    for i in range(len(book_pdf)):
        page = book_pdf[i]
        label = page.get_label()
        if label is None or not label.isdigit():
            label = i + 1
        page_numbers.append(label)
        text = page.get_text("text").replace("\n", " ")
        book_page_data[i] = text
        print(f"📄 Page {i} (Label: {label}) text length: {len(text)}")

    print("\n🔧 Starting pattern matcher to insert page break comments...")
    new_latex_content = pattern_matcher(-100, latex_content, book_page_data, page_numbers)

    os.makedirs(os.path.dirname(OUTPUT_TEX_PATH), exist_ok=True)
    with open(OUTPUT_TEX_PATH, "w", encoding="utf-8") as file:
        file.write(new_latex_content)

    print(f"\n✅ Page Breaks inserted and written to:\n\t📁 {OUTPUT_TEX_PATH}")
    return book_pdf, new_latex_content, page_numbers

if __name__ == '__main__':
    print("🚀 Script Started")
    if len(sys.argv) < 3:
        print("⚠️ Usage: python script.py <file_path> <tex_file_path>")
        sys.exit(1)

    file_path = sys.argv[1]
    tex_file_path = sys.argv[2]
    ROOT = "../../"

    file_name = os.path.splitext(os.path.basename(file_path))[0]
    tex_filename = os.path.basename(tex_file_path)

    book_folder = os.path.join(ROOT, f"files/{file_name}_book/")
    tex_folder = os.path.join(book_folder, f"{file_name}_book_tex/")
    output_tex_folder = os.path.join(book_folder, f"outputs")

    os.makedirs(book_folder, exist_ok=True)
    os.makedirs(tex_folder, exist_ok=True)
    os.makedirs(output_tex_folder, exist_ok=True)

    BOOK_PATH = os.path.join(book_folder, f"{file_name}.pdf")
    TEX_PATH = os.path.join(tex_folder, f"{file_name}.tex")
    OUTPUT_TEX_PATH = os.path.join(output_tex_folder, f"{file_name}_pg_sep.tex")

    if not os.path.exists(BOOK_PATH):
        shutil.copy2(file_path, BOOK_PATH)
        print(f"📦 Moved {file_path} ➡️ {BOOK_PATH}")
    else:
        print(f"📁 {BOOK_PATH} already exists.")

    if not os.path.exists(TEX_PATH):
        shutil.copy2(tex_file_path, TEX_PATH)
        print(f"📦 Moved {tex_file_path} ➡️ {TEX_PATH}")
    else:
        print(f"📁 {TEX_PATH} already exists.")

    create_page_seperators(BOOK_PATH, TEX_PATH, OUTPUT_TEX_PATH)
