# input:
# pdf path
# tex path
# mathpix images
# gt path (make images here for comparison) (generally in version folder)

# output:
# updated tex file with added images which were missing in the original tex file

import pymupdf
import pdf_extract_kit.scripts.layout_detection as layout_detection
from image_macher import add_images_to_tex

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


def main(BOOK_PATH, TEX_PATH, CONFIG_PATH ,MATHPIX_IMAGES, GT_PATH, OUTPUT_TEX_PATH):
    print("\n=== Step 6: Fixing Images ===")
    print(f"Using PDF : {BOOK_PATH}")
    print(f"Using LaTeX file: {TEX_PATH}")
    print(f"Using config file: {CONFIG_PATH}")
    print(f"Mathpix Image folder: {MATHPIX_IMAGES}")
    print(f"GT Image folder: {GT_PATH}")
    print(f"Store output in: {OUTPUT_TEX_PATH}")

    # load pdf and tex file (if needed)
    # load tex file:
    latex_content = read_latex(TEX_PATH)

    # run pdf extract kit to extract images from pdf and store in output path
    results = layout_detection.main(config_path=CONFIG_PATH)
    # run image matcher to add the missing images, in a speicified format
    out_tex = add_images_to_tex(GT_PATH, MATHPIX_IMAGES, latex_content ,BOOK_PATH)
    # return tex file
    print(f"Writing result to: {OUTPUT_TEX_PATH}")
    with open(OUTPUT_TEX_PATH, "w", encoding="utf-8") as file:
        file.write(out_tex)
    print(f"Successfully wrote {len(out_tex)} characters to output file")
            
    return OUTPUT_TEX_PATH


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Fix LaTeX file by adding missing images extracted from PDF."
    )
    parser.add_argument("book_path", help="Path to the PDF book file.")
    parser.add_argument("tex_path", help="Path to the LaTeX file.")
    parser.add_argument(
        "mathpix_images",
        help="Path to the folder containing Mathpix extracted images.",
    )
    parser.add_argument(
        "gt_path",
        help="Path to the folder where ground truth images will be stored.",
    )

    args = parser.parse_args()

    main(args.book_path, args.tex_path, args.mathpix_images, args.gt_path)