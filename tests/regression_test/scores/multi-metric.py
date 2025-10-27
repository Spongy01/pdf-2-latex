
import os
import glob
import re
import json
from pathlib import Path
from typing import Optional
import logging

# module logger
logger = logging.getLogger(__name__)

def percent_compiled(log_file_path: str, output_directory, book_name) -> float:

    """Return percent of pages compiled.

    - output_directory: the directory where outputs (including .log) live
    - the inputs PDF is expected to be at (output_directory/..)/inputs/*.pdf
    - log_file_path: path to the .log file produced by the compile

    Behavior:
    - count total pages in the first PDF found in the inputs folder
    - parse the log for page markers like "[123]" and take the highest number
    - compute percent = (highest_compiled_page / total_pages) * 100
    - return 0.0 if PDF or log cannot be read
    """
    try:
        out_dir = Path(output_directory)
        inputs_dir = out_dir.parent / "inputs"
        logger.debug("percent_compiled: output_directory=%s, inputs_dir=%s", output_directory, inputs_dir)
        if not inputs_dir.exists():
            logger.warning("percent_compiled: inputs directory does not exist: %s", inputs_dir)
            return 0.0

        # prefer a PDF that matches the book_name (base name) if provided
        pdf_path = None
        if book_name:
            candidate = inputs_dir / f"{book_name}.pdf"
            logger.debug("percent_compiled: looking for candidate pdf %s", candidate)
            if candidate.exists():
                pdf_path = candidate
                logger.info("percent_compiled: using matched pdf %s", pdf_path)

        if pdf_path is None:
            # find a PDF in inputs folder
            pdf_files = sorted(inputs_dir.glob("*.pdf"))
            if not pdf_files:
                logger.warning("percent_compiled: no PDF files found in %s", inputs_dir)
                return 0.0
            pdf_path = pdf_files[0]
            logger.info("percent_compiled: using first pdf in inputs: %s", pdf_path)

        # count pages using PyMuPDF (fitz)
        total_pages: Optional[int] = None
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(pdf_path))
            total_pages = doc.page_count
            doc.close()
            logger.debug("percent_compiled: total_pages=%s for pdf=%s", total_pages, pdf_path)
        except Exception as e:
            logger.exception("percent_compiled: failed to read PDF %s: %s", pdf_path, e)
            total_pages = None

        if total_pages is None or total_pages == 0:
            return 0.0

        # parse log for highest page marker like [123]
        max_page = 0
        try:
            with open(log_file_path, "r", errors="ignore") as f:
                log_text = f.read()
            matches = re.findall(r"\[(\d+)\]", log_text)
            nums = [int(m) for m in matches] if matches else []
            logger.debug("percent_compiled: found %d page markers in log", len(nums))
            if nums:
                max_page = max(nums)
                logger.info("percent_compiled: highest compiled page found in log = %d", max_page)
        except Exception as e:
            logger.exception("percent_compiled: failed to parse log file %s: %s", log_file_path, e)
            return 0.0

        pct = (max_page / total_pages) * 100.0
        # clamp
        if pct < 0:
            pct = 0.0
        if pct > 100:
            pct = 100.0
        pct = round(pct, 2)
        logger.info("percent_compiled: percent=%s (max_page=%s / total_pages=%s)", pct, max_page, total_pages)
        return pct
    except Exception:
        logger.exception("percent_compiled: unexpected error")
        return 0.0

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

    print(f"Metadata file path: {metadata_file_path}")
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
    num_bibtex_json = 0
    json_files = glob.glob(os.path.join(output_directory, "*_bib.json"))
    print(f"Looking for bib json files in {output_directory}, found: {json_files}")
    if json_files:
        with open(json_files[0], "r") as f:
            try:
                bib_data = json.load(f)
                num_bibtex_json = len(bib_data)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from {json_files[0]}: {e}")
                num_bibtex_json = 0


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
    num_included_graphics = len(re.findall(r'\\includegraphics', output_content))
    print(f"Included Graphics in Output: {num_included_graphics}")
    num_figures_out = len(re.findall(r'\\begin\{figure\}', output_content))
    num_tables_out = len(re.findall(r'\\begin\{table\}', output_content)) + len(re.findall(r'\\begin\{tabular\}', output_content))
    print("Output - ", end="")
    print(f"Figures: {num_figures_out}, Tables: {num_tables_out}")  

    # get index entries from metadata
    num_index_entries = metadata.get("index_entries", -1)
    # caluclate index entries in output file
    num_index_entries_out = len(re.findall(r'\\index\{', output_content))
    print("Index Entries - ", end="")
    print(f"Metadata: {num_index_entries}, Output: {num_index_entries_out}")

    command_tags = ['document', 'figure', 'table','tabular' ,'itemize', 'enumerate', 'list','verbatim',
                    'center', 'flushleft', 'flushright', 'mathequation', 'align' ,'quote',
                    'equation', 'algorithm', 'algorithmic'    
                    ]

    # count different types of begins and ends
    # count number of begin and end gneeral tags
    num_total_begin = len(re.findall(r'\\begin\{', output_content))
    num_total_end = len(re.findall(r'\\end\{', output_content))
    diff_num_total = num_total_begin - num_total_end
    print(f"Total Begin: {num_total_begin}, Total End: {num_total_end}")
    print(f"Difference in total begin and end (begin - end): {diff_num_total}")

    num_begins = {}
    num_ends = {}
    diffs = {}

    for tag in command_tags:
        begin_count = len(re.findall(r'\\begin\{' + tag + r'\}', output_content))
        end_count = len(re.findall(r'\\end\{' + tag + r'\}', output_content))
        diff_count = begin_count - end_count
        num_begins[tag] = begin_count
        num_ends[tag] = end_count
        diffs[tag] = diff_count
        print(f"{tag.capitalize()} - Begin: {begin_count}, End: {end_count}, Difference (begin - end): {diff_count}")


    # --- Compute Score ---
    score = 0.0 
    
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
            score -= abs(num_figures - num_figures_out- num_included_graphics) * 0.5  # each mismatch costs 0.5 points
    if num_tables != -1:
        if num_tables != num_tables_out:
            score -= abs(num_tables - num_tables_out) * 0.5  # each mismatch costs 0.5 points

    # Deduct points for index entries mismatches
    if num_index_entries != -1:
        if num_index_entries != num_index_entries_out:
            score -= abs(num_index_entries - num_index_entries_out) * 0.2  # each mismatch costs 0.2 points

    # deduct points for begin-end mismatches
    score -= abs(diff_num_total) * 0.5      # each mismatch costs 0.5 points


    # Ensure score is within 0-100
    # score = max(0.0,  score)
    result = {}
    # round off score to 2 decimal places
    score = round(score, 2)
    result["Score"] = score
    # compute percent compiled using log and output directory
    try:
        pct = percent_compiled(log_file_path, output_directory, base_name)
    except Exception:
        pct = 0.01
    result["Percent Compiled"] = pct
    result["Latex Errors"] = round(num_errors * 100/pct, 2) if pct > 0 else num_errors * 100
    result["Latex Warnings"] = round(num_warnings * 100/pct, 2) if pct > 0 else num_warnings * 100
    result["Bibtex Extracted %"] = round((num_bibtex_json / num_bibtex_mtd * 100), 2) if num_bibtex_mtd > 0 else "N/A"
    result["Bibtex Cited %"] = round((num_cites / num_bibtex_json * 100), 2) if num_bibtex_json > 0 else 0
    result["Chapters %"] = round((num_chapters_out / num_chapters * 100), 2) if num_chapters > 0 else "N/A"
    result["Sections %"] = round((num_sections_out / num_sections * 100), 2) if num_sections > 0 else "N/A"
    result["Subsections %"] = round((num_subsections_out / num_subsections * 100), 2) if num_subsections > 0 else "N/A"       
    result["Figures %"] = round(((num_figures_out + num_included_graphics) / num_figures * 100), 2) if num_figures > 0 else "N/A"
    result["Tables %"] = round((num_tables_out / num_tables * 100), 2) if num_tables > 0 else "N/A"
    result["Index Entries %"] = round((num_index_entries_out / num_index_entries * 100), 2) if num_index_entries > 0 else "N/A"   
    result["Bibtex (metadata)"] = num_bibtex_mtd
    result["Bibtex extracted (json)"] = num_bibtex_json
    result["Entries Cited"] = num_cites
    result["Bibtex (diff [meta - extracted])"] =num_bibtex_mtd - num_bibtex_json  if num_bibtex_mtd != -1 and num_bibtex_json != -1 else "N/A"
    result["Bibtex (diff [extracted - cited])"] =num_bibtex_json - num_cites  if num_bibtex_json != -1 else "N/A"
    
    result["Chapters (metadata)"] = num_chapters
    result["Chapters (output)"] = num_chapters_out
    result["Chapters (diff [meta-out])"] = num_chapters - num_chapters_out if num_chapters != -1 else "N/A"

    result["Sections (metadata)"] = num_sections
    result["Sections (output)"] = num_sections_out
    result["Sections (diff [meta-out])"] = num_sections - num_sections_out if num_sections != -1 else "N/A"

    result["Subsections (metadata)"] = num_subsections
    result["Subsections (output)"] = num_subsections_out
    result["Subsections (diff [meta-out])"] = num_subsections - num_subsections_out if num_subsections != -1 else "N/A"

    result["Figures (metadata)"] = num_figures
    result["Figures (output)"] = num_figures_out
    result["Included Graphics (output)"] = num_included_graphics
    result["Figures (diff [meta-out])"] = num_figures - num_figures_out - num_included_graphics if num_figures != -1 else "N/A"

    result["Tables (metadata)"] = num_tables
    result["Tables (output)"] = num_tables_out
    result["Tables (diff [meta-out])"] = num_tables - num_tables_out if num_tables != -1 else "N/A"

    result["Index Entries (metadata)"] = num_index_entries
    result["Index Entries (output)"] = num_index_entries_out
    result["Index Entries (diff [meta-out])"] = num_index_entries - num_index_entries_out if num_index_entries != -1 else "N/A"

    result["Total Begin"] = num_total_begin
    result["Total End"] = num_total_end
    result["Total Begin-End Difference"] = diff_num_total
    
    for tag in command_tags:
        result[f"{tag.capitalize()} Begin"] = num_begins[tag]
        result[f"{tag.capitalize()} End"] = num_ends[tag]
        result[f"{tag.capitalize()} Difference"] = diffs[tag]

    return result

