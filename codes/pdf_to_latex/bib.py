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
# import fitzs
from pdf2image import convert_from_path
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
api_key = os.getenv("API_KEY")

OPENAI_API_KEY = api_key
client = OpenAI(api_key=OPENAI_API_KEY)

def get_api_response(prompt, text, model="gpt-4o-mini"):
    """
    Get response from OpenAI API.
    
    Parameters:
        prompt (str): The prompt to send to the API.
        text (str): Text content to include in the prompt.
        model (str): OpenAI model to use.
        
    Returns:
        str: API response content.
    """
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "developer", "content": "You are a helpful assistant."},
            {"role": "user", "content": f" {prompt}. Here is the text: {text}"}
        ]
    )
    return completion.choices[0].message.content

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

def replace_citations(tex_filename, bib_dict, output_filename="updated.tex"):
    """
    Replaces citation keys in a LaTeX file with \cite{...} using a dictionary.

    Parameters:
        tex_filename (str): The name of the input .tex file.
        bib_dict (dict): Dictionary where keys are the citation keys in text (e.g., 'Abe13'),
                         and values are the BibTeX citation keys (e.g., 'abela2013advanced').
        output_filename (str): The name of the output file with updated citations (default: 'updated.tex').

    Returns:
        None
    """
    # Read the LaTeX file
    with open(tex_filename, "r", encoding="utf-8") as f:
        tex_content = f.read()
    
    # Replace each citation key with \cite{bibtex_key}
    for key, bibtex_key in bib_dict.items():
        tex_content = re.sub(rf'\b{re.escape(key)}\b', rf'\\cite{{{bibtex_key}}}', tex_content, count=1)

    # Save the updated content to a new file
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(tex_content)

    print(f"Updated LaTeX file saved as {output_filename}")


def process_bibliography(pdf_path=None, tex_path=None, output_json_path=None, output_bib_path=None, output_tex_path=None, model="gpt-4o", bib_json=None):
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
            
            bibliography = ""
            for page in pdf_document:
                bibliography += page.get_text()
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return None
        
        # Define prompt for OpenAI API
        prompt = r""" 

        I am going to pass the extracted text from a PDF file of a textbook. It contains a bibliography section. 
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


        Here is the text: """
        
        print(f"Sending request to OpenAI API using model: {model}")
        
        # Get API response
        try:
            api_response = get_api_response(prompt, bibliography, model=model)
            
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
            
            # Save JSON content
            with open(output_json_path, "w") as f:
                f.write(json_content)
            
            print(f"Bibliography JSON saved to: {output_json_path}")
        except Exception as e:
            print(f"Error in API processing: {e}")
            
            # Try to load existing JSON file if API fails
            try:
                with open(output_json_path, "r") as f:
                    ds_bib_dict = json.load(f)
                print(f"Loaded existing bibliography from: {output_json_path}")
            except:
                print(f"Could not load existing bibliography. Process failed.")
                return None
                # Parse JSON content
        try:
            ds_bib_dict = json.loads(json_content)
        except json.JSONDecodeError:
            print("Failed to parse JSON from API response, attempting to load from file")
            # If JSON parsing fails, try to load the file that was saved earlier
            with open(output_json_path, "r") as f:
                ds_bib_dict = json.load(f)
    
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
            replace_citations(tex_path, citation_dict, output_filename=output_tex_path)
            print(f"Updated LaTeX file saved to: {output_tex_path}")
        except Exception as e:
            print(f"Error updating LaTeX file: {e}")
    
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