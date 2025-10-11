
import os
import glob
import re
import json
def calculate_score(input_file_path: str, output_file_path: str) -> float:
    """
    Calculate similarity score based on multiple metrics.
        - errors in LaTeX log
        - bibtex references
        - Chapters, sections, subsections
        - Figures, tables
        - Index entries
    

    Args:
        input_file_path: Path to the input LaTeX file (e.g., files/ai/inputs/ai.tex)
        output_file_path: Path to the output LaTeX file (e.g., files/ai/outputs/ai_cleaned_final.tex)

        this does not use the input file path, but keeping for consistency with other score functions

    Returns:
        Float score from 0.0 to 100.0, where 100.0 means identical files
    """


    output_directory = os.path.dirname(output_file_path)
    input_directory = os.path.dirname(input_file_path)
    base_name = os.path.splitext(os.path.basename(output_file_path))[0]

    log_file_path = os.path.join(output_directory, base_name + ".log")
    metadata_file_path = os.path.join(input_directory, "metadata.json")

    # get number of errors from log file
    num_errors = 0
    num_warnings = 0
    with open(log_file_path, "r") as f:
        log_file = f.read()
        num_errors = log_file.count("Error:")
        num_warnings = log_file.count("Warning")

    print(f"Errors: {num_errors}")
    print(f"Warnings: {num_warnings}")

    # get metadata from metadata file
    metadata = {}
    with open(metadata_file_path, "r") as f:
        metadata = json.load(f)

    num_bibtex_mtd = metadata.get("bibtex_references", -1)
    # get bibs from the book name_bib.json file in the output directory as well
    num_bibtex_json = -1
    json_files = glob.glob(os.path.join(output_directory, "*_bib.json"))
    if json_files:
        with open(json_files[0], "r") as f:
            bib_data = json.load(f)
            num_bibtex_json = len(bib_data)


    # get the number of \cite commands in the output file as well
    with open(output_file_path, "r") as f:
        output_content = f.read()
    
    # Regex to match \cite{...} (captures content inside {})
    matches = re.findall(r'\\cite\{([^}]*)\}', output_content)

    # Some \cite{} can have multiple keys separated by commas
    all_cites = set()
    for match in matches:
        keys = [key.strip() for key in match.split(',')]
        all_cites.update(keys)

    num_cites = len(all_cites)
    print(f"Number of unique citations: {len(all_cites)}")

    # compare the three bibtex counts
    print(f"Bibtex (metadata): {num_bibtex_mtd}, Bibtex extracted (json): {num_bibtex_json}, Entries Cited: {num_cites}")

    # check chapters, sections, subsections in metadata and output
    num_chapters = metadata.get("chapters", -1)
    num_sections = metadata.get("sections", -1)
    num_subsections = metadata.get("subsections", -1)
    print("Metadata - ", end="")
    print(f"Chapters: {num_chapters}, Sections: {num_sections}, Subsections: {num_subsections}")
    # count in output file
    num_chapters_out = len(re.findall(r'\\chapter\{', output_content))
    num_sections_out = len(re.findall(r'\\section\{', output_content))
    num_subsections_out = len(re.findall(r'\\subsection\{', output_content))
    print("Output - ", end="")
    print(f"Chapters: {num_chapters_out}, Sections: {num_sections_out}, Subsections: {num_subsections_out}")

    # check figures, tables in metadata and output
    num_figures = metadata.get("figures", -1)
    num_tables = metadata.get("tables", -1)
    print("Metadata - ", end="")
    print(f"Figures: {num_figures}, Tables: {num_tables}")
    # count in output file
    num_figures_out = len(re.findall(r'\\begin\{figure\}', output_content))
    num_tables_out = len(re.findall(r'\\begin\{table\}', output_content))
    print("Output - ", end="")
    print(f"Figures: {num_figures_out}, Tables: {num_tables_out}")  

    # get index entries from metadata
    num_index_entries = metadata.get("index_entries", -1)
    # caluclate index entries in output file
    num_index_entries_out = len(re.findall(r'\\index\{', output_content))
    print("Index Entries - ", end="")
    print(f"Metadata: {num_index_entries}, Output: {num_index_entries_out}")

    # --- Compute Score ---
    score = 100.0
    
    # Deduct points for errors/warnings
    score -= num_errors * 0.5       # each error costs 5 points
    score -= num_warnings * 0.1     # each warning costs 1 point

    # Deduct points for bibtex mismatches
    if num_bibtex_mtd != -1 and num_bibtex_json != -1:
        if num_bibtex_mtd != num_bibtex_json:
            score -= abs(num_bibtex_mtd - num_bibtex_json) * 0.5  # each mismatch costs 0.5 points
    if num_bibtex_json != -1:
        if num_bibtex_json != num_cites:
            score -= abs(num_bibtex_json - num_cites) * 0.5  # each mismatch costs 0.5 points
    
    # Deduct points for chapters, sections, subsections mismatches
    if num_chapters != -1:
        if num_chapters != num_chapters_out:
            score -= abs(num_chapters - num_chapters_out) * 0.5  # each mismatch costs 0.5 points
    if num_sections != -1:
        if num_sections != num_sections_out:
            score -= abs(num_sections - num_sections_out) * 0.5  # each mismatch costs 0.5 points
    if num_subsections != -1:
        if num_subsections != num_subsections_out:
            score -= abs(num_subsections - num_subsections_out) * 0.5  # each mismatch costs 0.5 points
    
    # Deduct points for figures, tables mismatches
    if num_figures != -1:
        if num_figures != num_figures_out:
            score -= abs(num_figures - num_figures_out) * 0.5  # each mismatch costs 0.5 points
    if num_tables != -1:
        if num_tables != num_tables_out:
            score -= abs(num_tables - num_tables_out) * 0.5  # each mismatch costs 0.5 points

    # Deduct points for index entries mismatches
    if num_index_entries != -1:
        if num_index_entries != num_index_entries_out:
            score -= abs(num_index_entries - num_index_entries_out) * 0.2  # each mismatch costs 0.2 points

    # Ensure score is within 0-100
    # score = max(0.0,  score)
    result = {}
    # round off score to 2 decimal places
    score = round(score, 2)
    result["Score"] = score
    result["Latex Errors"] = num_errors
    result["Latex Warnings"] = num_warnings
    result["Bibtex (metadata)"] = num_bibtex_mtd
    result["Bibtex extracted (json)"] = num_bibtex_json
    result["Entries Cited"] = num_cites
    result["Chapters (metadata)"] = num_chapters
    result["Chapters (output)"] = num_chapters_out
    result["Sections (metadata)"] = num_sections
    result["Sections (output)"] = num_sections_out
    result["Subsections (metadata)"] = num_subsections
    result["Subsections (output)"] = num_subsections_out
    result["Figures (metadata)"] = num_figures
    result["Figures (output)"] = num_figures_out
    result["Tables (metadata)"] = num_tables
    result["Tables (output)"] = num_tables_out
    result["Index Entries (metadata)"] = num_index_entries
    result["Index Entries (output)"] = num_index_entries_out
    return result

