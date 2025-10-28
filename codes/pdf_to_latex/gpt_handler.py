# process_tex_figures: read a .tex file, group consecutive \includegraphics, find nearby captions starting with "Figure" or "Fig.", and wrap groups in a figure environment.
import re
from pathlib import Path

def make_book(input_path, output_path):
    """
    Replace a LaTeX document class declaration that uses the `article`
    class with the `book` class. Specifically targets declarations that
    include the 10pt option such as:

        \documentclass[10pt]{article}

    The replacement is done via regex so small variations in whitespace are
    tolerated. If `output_path` is None the input file is overwritten.

    Returns output_path
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    text = input_path.read_text(encoding="utf-8")

    # Primary pattern: matches \documentclass[10pt]{article} allowing
    # for optional whitespace between tokens.
    pattern = re.compile(r"(\\documentclass\s*\[\s*10pt\s*\]\s*\{\s*)article(\s*\})",
                         re.IGNORECASE)

    new_text, count = pattern.subn(r"\1book\2", text)

    # Fallback: if the exact 10pt pattern wasn't found, replace any
    # \documentclass[...]{article} occurrence (still using regex to
    # preserve surrounding formatting).
    if count == 0:
        pattern2 = re.compile(r"(\\documentclass\s*\[[^\]]*\]\s*\{\s*)article(\s*\})",
                              re.IGNORECASE)
        new_text, count2 = pattern2.subn(r"\1book\2", new_text)
        count += count2

    out_path = Path(output_path) if output_path is not None else input_path
    out_path.write_text(new_text, encoding="utf-8")
    return out_path


def process_tex_figures(input_path, output_path):
    """
    Read input .tex file, find groups of consecutive \includegraphics commands,
    extract nearby captions (within 2 lines above or below) that start with
    "Figure" or "Fig.", and replace the original lines with a wrapped
    \begin{figure}[h] ... \end{figure} containing the graphics and a \caption{}.

    Args:
        input_path (str or Path): path to the source .tex file.
        output_path (str or Path): path to write the modified .tex file.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    caption_re = re.compile(r"^\s*(?:Figure|Fig\.)\s*(\d+(?:\.\d+)*)\s*[:\.\-]?\s*(.*)", re.IGNORECASE)

    def inside_existing_figure(idx):
        # Scan backwards from idx to find nearest \begin{figure} or \end{figure}
        # If \begin{figure} found before a matching \end{figure}, we assume inside.
        j = idx
        while j >= 0 and (idx - j) <= 200:  # limit search distance to avoid huge scans
            line = lines[j]
            if "\\begin{figure}" in line:
                return True
            if "\\end{figure}" in line:
                return False
            j -= 1
        return False


    new_lines = []
    last_appended_index = 0
    i = 0
    n = len(lines)

    while i < n:
        if "\\includegraphics" in lines[i]:
            # if already inside a figure, just move on (don't wrap)
            if inside_existing_figure(i):
                i += 1
                continue

            # start of a group
            start = i
            group_graphics = []
            # collect consecutive includegraphics lines (allow blank lines between)
            while i < n:
                if "\\includegraphics" in lines[i]:
                    group_graphics.append(lines[i].rstrip("\n"))
                    i += 1
                    # continue collecting
                    # also consume any immediately following lines that are purely options or braces
                    # but keep it simple: only gather lines that contain includegraphics
                elif lines[i].strip() == "":
                    # allow a single blank line between graphics; include it in group span
                    i += 1
                    # continue
                else:
                    break
            end = i - 1

            # find caption up to 2 lines above start and up to 2 lines below end
            caption_idx = None
            caption_text = ""
            # check above
            for off in range(1, 5):
                idx = start - off
                if idx >= 0:
                    m = caption_re.match(lines[idx])
                    if m:
                        caption_idx = idx
                        caption_text = m.group(2).strip()
                        break
            # check below if not found
            if caption_idx is None:
                for off in range(0, 4):
                    idx = end + 1 + off
                    if idx < n:
                        m = caption_re.match(lines[idx])
                        if m:
                            caption_idx = idx
                            caption_text = m.group(2).strip()
                            break

            # check if caption contains a :
            if caption_text and ':' in caption_text:
                # find location of first :
                colon_pos = caption_text.find(':')
                # truncate caption_text to only include text after the colon
                caption_text = caption_text[colon_pos + 1 :].strip()

            # append all lines from last_appended_index up to start, skipping caption_idx if it's there
            for k in range(last_appended_index, start):
                if caption_idx is not None and k == caption_idx:
                    # skip the original caption line
                    continue
                new_lines.append(lines[k])

            # construct figure block
            figure_block = []
            figure_block.append("\\begin{figure}[h]\n")
            figure_block.append("    \\centering\n")
            for g in group_graphics:
                figure_block.append("    " + g + "\n")
            if caption_text:
                figure_block.append("    \\caption{" + caption_text + "}\n")
            figure_block.append("\\end{figure}\n")

            new_lines.extend(figure_block)

            # update last_appended_index to i; also if caption was below, preserve
            # any intervening non-blank lines between the graphics group and caption
            # (e.g., structural commands like \end{itemize}), then skip the caption line
            if caption_idx is not None and caption_idx > end:
                # append intervening non-blank lines between end+1 and caption_idx (exclusive)
                for k in range(end + 1, caption_idx):
                    if lines[k].strip() != "":
                        new_lines.append(lines[k])
                # skip the caption line itself
                last_appended_index = caption_idx + 1
            else:
                last_appended_index = i

        else:
            i += 1

    # append remaining lines
    for k in range(last_appended_index, n):
        # skip caption lines that were located above groups and already removed
        new_lines.append(lines[k])

    # write output
    # If nothing changed, still write the content to output_path
    with output_path.open("w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return output_path


# Quick self-test with an inline example: write a temp input and run the function
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert PDF books to properly formatted LaTeX"
    )
    parser.add_argument("--tex", type=str, help="Path to the input LaTeX file")
    parser.add_argument("--output", type=str, help="Path for the output LaTeX file")
    
    args = parser.parse_args()

   

    process_tex_figures(args.tex, args.output)
    print('Wrote', args.output)
    print('--- Output preview ---')
    print(Path(args.output).read_text(encoding='utf-8'))
