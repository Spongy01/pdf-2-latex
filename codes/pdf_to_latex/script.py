"""
PDF to LaTeX Conversion Pipeline

This script combines four key steps to convert a PDF book to a well-formatted LaTeX document:
1. Add page separators to the LaTeX file
2. Process bibliography and update citations
3. Use GPT to improve formatting
4. Add indexing to the book

"""

import os
import sys
import re
import shutil
import argparse
from datetime import datetime
import json
from tqdm import tqdm
import fitz  # PyMuPDF
import pymupdf
import copy
from fuzzysearch import find_near_matches
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from dotenv import load_dotenv
import time

from indexer import create_indexing
from gpt_script import format_with_gpt
from bib import process_bibliography
from page_separator_v2 import create_page_separators
from cleaner import clean_it_up
import subprocess
import shutil


def get_current_version_name():
    """
    Get the current version name from version control.
    Returns the name of the currently active version.
    If no version is found or version control is not initialized,
    returns 'original' as the default.
    """
    try:
        # Get the path to version_control relative to this file
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        version_control_path = os.path.join(current_file_dir, "../version_control")

        # Add to path if needed
        if version_control_path not in sys.path:
            sys.path.insert(0, version_control_path)

        # Import the core module
        from version_history import load_version_history, get_current_version

        # Load version history
        versions = load_version_history()

        # Get current version
        current = get_current_version(versions)

        if current:
            return current["name"]
        else:
            # Fallback to original if no current version found
            print("⚠ Warning: No current version found, using 'original'")
            return "original"

    except ImportError as e:
        # If version_control module not found, return default
        print(f"⚠ Warning: Version control not found ({e}), using 'original'")
        return "original"
    except Exception as e:
        # Any other error, return default
        print(f"⚠ Warning: Error loading version ({e}), using 'original'")
        return "original"


def setup_folders(file_path, tex_file_path, output_folder, file_name=None):
    """Set up folder structure for the conversion process with version control."""

    # Extract file_name if not provided
    if file_name is None:
        file_name = os.path.splitext(os.path.basename(file_path))[0]

    # Create folder structure
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(current_dir, "../../"))

    # Book folder (main folder for this book)
    book_folder = os.path.join(root_dir, f"files/{file_name}")
    os.makedirs(book_folder, exist_ok=True)

    # Get current version name from version control
    version_name = get_current_version_name()

    # Create version folder: files/{file_name}/{version_name}
    version_folder = os.path.join(book_folder, version_name)

    # Use version folder as output folder if not explicitly provided
    # if output_folder is None:
    output_folder = version_folder

    # Create version-specific output folder
    os.makedirs(output_folder, exist_ok=True)

    print(f"📁 Using version: {version_name}")
    print(f"📂 Output folder: {output_folder}")

    # Define paths
    book_path = file_path
    tex_path = tex_file_path

    # Return paths
    paths = {
        "book_path": book_path,
        "tex_path": tex_path,
        "output_folder": output_folder,
        "version_name": version_name,  # Changed from version_number
        "version_folder": version_folder,  # Added for clarity
        "book_folder": book_folder,
        "pg_sep_path": os.path.join(output_folder, f"{file_name}_pg_sep.tex"),
        "bib_path": os.path.join(output_folder, f"{file_name}_pg_sep_bib.tex"),
        "gpt_path": os.path.join(output_folder, f"{file_name}_gpt.tex"),
        "cleaned_path": os.path.join(output_folder, f"{file_name}_cleaned.tex"),
        "indexed_path": os.path.join(output_folder, f"{file_name}_indexed.tex"),
        "bib_json_path": os.path.join(output_folder, f"{file_name}_bib.json"),
        "bib_output_path": os.path.join(output_folder, f"{file_name}_references.bib"),
        "final_path": os.path.join(output_folder, f"{file_name}_final.tex"),
    }

    return paths


def store_final(out_tex_path, final_output_path):
    """Store the final output to a designated path."""
    if os.path.exists(out_tex_path):
        shutil.copy2(out_tex_path, final_output_path)
        print(f"Stored final output: {out_tex_path} -> {final_output_path}")
    else:
        print(f"Final output file does not exist: {out_tex_path}")


# ------------- MAIN PIPELINE FUNCTION -------------


def run_pipeline(
    book_path,
    tex_path,
    bib_path=None,
    index_path=None,
    output_folder=None,
    file_name=None,
    max_parts=None,
    batch_size=5,
    use_parallel=True,
    skip_steps=[],
    bib_json_path=None,
):
    """Run the complete PDF to LaTeX conversion pipeline."""
    start_time = datetime.now()
    print(f"Starting PDF to LaTeX conversion pipeline at {start_time}")

    # Setup folders and paths
    if file_name is None:
        file_name = os.path.splitext(os.path.basename(book_path))[0]

    paths = setup_folders(book_path, tex_path, output_folder, file_name)
    # print("Paths set up:")
    # for key, value in paths.items():
    #     print(f"  {key}: {value}")

    # Initialize OpenAI client
    load_dotenv()
    api_key = os.getenv("API_KEY")
    if not api_key:
        print(
            "No API key found in environment variables. Please set the API_KEY environment variable."
        )
        return None

    client = OpenAI(api_key=api_key)

    # Create a dictionary to store results
    results = {
        "book_path": book_path,
        "tex_path": tex_path,
        "steps_completed": [],
        "final_output": None,
    }

    # Step 1: Create page separators (if not skipped)
    current_tex_path = paths["tex_path"]
    print("Book path:", paths["book_path"])
    print("Current tex path:", current_tex_path)
    print("Page separator path:", paths["pg_sep_path"])

    if 1 not in skip_steps:
        try:
            book_pdf, latex_with_pages, page_numbers = create_page_separators(
                paths["book_path"],
                current_tex_path,
                paths["pg_sep_path"],
                paths["output_folder"],
            )
            current_tex_path = paths["pg_sep_path"]
            results["steps_completed"].append(1)
            results["page_separator_output"] = current_tex_path
        except Exception as e:
            print(f"Error in Step 1 (Page Separators): {e}")
    else:
        print("Skipping Step 1: Page Separators")
        if os.path.exists(paths["pg_sep_path"]):
            current_tex_path = paths["pg_sep_path"]

    # Step 2: Process bibliography (if not skipped and bib_path provided)
    if 2 not in skip_steps and bib_path:
        try:
            bib_dict, current_tex_path = process_bibliography(
                bib_path,
                current_tex_path,
                paths["bib_json_path"],
                paths["bib_output_path"],
                paths["bib_path"],
                bib_json=bib_json_path,
            )
            results["steps_completed"].append(2)
            results["bibliography_output"] = current_tex_path
        except Exception as e:
            print(f"Error in Step 2 (Bibliography): {e}")
    else:
        print("Skipping Step 2: Bibliography Processing")
        if os.path.exists(paths["bib_path"]):
            current_tex_path = paths["bib_path"]

    # Step 3: Format with AI (if not skipped)
    if 3 not in skip_steps:
        try:
            current_tex_path = format_with_gpt(  # here the output current_tex_path is final_path that is _cleaned_final.tex
                paths["book_path"],
                current_tex_path,
                paths["gpt_path"],
                batch_size=batch_size,
                max_parts=max_parts,
                use_parallel=use_parallel,
            )
            results["steps_completed"].append(3)
            results["ai_formatting_output"] = current_tex_path
        except Exception as e:
            print(f"Error in Step 3 (AI Formatting): {e}")
    else:
        print("Skipping Step 3: AI Formatting")
        if os.path.exists(paths["gpt_path"]):
            current_tex_path = paths["gpt_path"]

    if 4 not in skip_steps:
        try:
            current_tex_path = clean_it_up(  # output file is _cleaned.tex
                current_tex_path, paths["book_path"], paths["cleaned_path"]
            )
            results["steps_completed"].append(4)
            results["cleaning_output"] = current_tex_path
        except Exception as e:
            print(f"Error in Step 4 (Cleaning): {e}")

    # Step 5: Process indexing (if not skipped and index_path provided)
    if 5 not in skip_steps and index_path:
        try:
            current_tex_path = create_indexing(
                index_path, current_tex_path, paths["book_path"], paths["indexed_path"]
            )
            results["steps_completed"].append(5)
            results["indexing_output"] = current_tex_path
        except Exception as e:
            print(f"Error in Step 5 (Indexing): {e}")
    else:
        print("Skipping Step 5: Indexing")

    # Final result
    results["final_output"] = current_tex_path

    # store to the final output path
    store_final(current_tex_path, paths["final_path"])

    end_time = datetime.now()
    duration = end_time - start_time
    print(f"\nPDF to LaTeX conversion pipeline completed in {duration}")
    print(f"Steps completed: {results['steps_completed']}")
    print(f"Final output: {results['final_output']}")

    print("Compiling the final LaTeX document to a PDF...")
    log_path = os.path.join(paths["output_folder"], "compile_log.txt")

    with open(log_path, "w", encoding="utf-8") as log_file:
        compile_result = subprocess.run(
            ["latexmk", f"-outdir={paths['output_folder']}", paths["final_path"]],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
    print(f"Compilation complete. Log saved to: {log_path}")

    # print("stdout:\n", compile_result.stdout)
    # print("stderr:\n", compile_result.stderr)

    return results


# Add this function to read configuration from a JSON file
def read_config(config_file):
    """Read configuration parameters from a JSON file."""
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        print(f"Configuration loaded from {config_file}")
        return config
    except Exception as e:
        print(f"Error reading configuration file {config_file}: {e}")
        return None


# Modify the __main__ section like this:
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF to LaTeX Conversion Pipeline")

    # Add a config file option
    parser.add_argument("--config", help="Path to configuration JSON file")

    # Required arguments (required only if no config file is provided)
    parser.add_argument("--book", help="Path to the book PDF file")
    parser.add_argument("--tex", help="Path to the initial LaTeX file")

    # Optional arguments
    parser.add_argument("--bib", help="Path to the bibliography PDF file")
    parser.add_argument("--index", help="Path to the index PDF file")
    parser.add_argument("--output", help="Path to output folder")
    parser.add_argument("--filename", help="Base filename for outputs")
    parser.add_argument(
        "--max-parts", type=int, help="Maximum number of parts to process"
    )
    parser.add_argument(
        "--batch-size", type=int, default=5, help="Batch size for parallel processing"
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Use sequential processing instead of parallel",
    )
    parser.add_argument(
        "--skip", type=int, nargs="+", help="Steps to skip (1-4)", default=[]
    )
    parser.add_argument(
        "--bib-json", help="Path to the JSON file for bibliography processing"
    )
    args = parser.parse_args()

    # Get parameters from config file if provided
    if args.config:
        config = read_config(args.config)
        if config:
            # Create a merged configuration with command-line arguments taking precedence
            params = {
                "book_path": args.book or config.get("book"),
                "tex_path": args.tex or config.get("tex"),
                "bib_path": args.bib or config.get("bib"),
                "index_path": args.index or config.get("index"),
                "output_folder": args.output or config.get("output"),
                "file_name": args.filename or config.get("filename"),
                "max_parts": args.max_parts or config.get("max_parts"),
                "batch_size": (
                    args.batch_size
                    if args.batch_size != 5
                    else config.get("batch_size", 5)
                ),
                "use_parallel": (
                    not args.sequential
                    if args.sequential
                    else not config.get("sequential", False)
                ),
                "skip_steps": args.skip or config.get("skip", []),
                "bib_json_path": args.bib_json or config.get("bib_json", None),
            }
        else:
            print(
                "Configuration file not found or invalid. Using command-line arguments."
            )
            params = {
                "book_path": args.book,
                "tex_path": args.tex,
                "bib_path": args.bib,
                "index_path": args.index,
                "output_folder": args.output,
                "file_name": args.filename,
                "max_parts": args.max_parts,
                "batch_size": args.batch_size,
                "use_parallel": not args.sequential,
                "skip_steps": args.skip,
                "bib_json_path": args.bib_json,
            }
    else:
        # No config file, use command-line arguments
        if not args.book or not args.tex:
            parser.error("--book and --tex are required unless --config is provided")

        params = {
            "book_path": args.book,
            "tex_path": args.tex,
            "bib_path": args.bib,
            "index_path": args.index,
            "output_folder": args.output,
            "file_name": args.filename,
            "max_parts": args.max_parts,
            "batch_size": args.batch_size,
            "use_parallel": not args.sequential,
            "skip_steps": args.skip,
            "bib_json_path": args.bib_json,
        }

    # Remove None values to avoid passing None to the pipeline
    params = {k: v for k, v in params.items() if v is not None}

    # Run the pipeline with the parameters
    run_pipeline(**params)
