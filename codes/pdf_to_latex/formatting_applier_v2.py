"""
Formatting Applier v2 - Clean rewrite

Simple, correct approach:
1. Find PDF text in LaTeX using exact/normalized matching
2. Check if position is safe (not in math, verbatim, or command arguments that can't have formatting)
3. Wrap with \textit{} or \textbf{}

Key fixes from v1:
- Proper bracket/brace tracking from start of content (not just nearest backslash)
- BLOCKED commands list instead of ALLOWED (inverted logic)
- Simpler position calculation - use exact match bounds, not word hunting
- Expand search area beyond page boundaries
"""

import os
import re
import json
import fitz
from typing import List, Dict, Any, Tuple, Optional
from tqdm import tqdm
from pdf_text_extractor import PDFTextExtractor, SpanData


def normalize_pdf_text(text: str) -> str:
    """Normalize PDF text: remove bullets, normalize quotes/hyphens/whitespace."""
    # Remove bullets
    text = text.replace('\u2022', '').replace('•', '').replace('·', '')
    # Normalize quotes
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    # Normalize hyphens
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    return text


def dehyphenate(text: str) -> str:
    """Remove hyphens that are likely line breaks: 'Al-gorithm' -> 'Algorithm'."""
    # Pattern: lowercase-lowercase suggests line break hyphenation
    return re.sub(r'([a-z])-([a-z])', r'\1\2', text)


def split_camelcase(text: str) -> str:
    """Split CamelCase into separate words: 'AlgorithmDesign' -> 'Algorithm Design'."""
    # Insert space before uppercase letters that follow lowercase
    return re.sub(r'([a-z])([A-Z])', r'\1 \2', text)


def strip_toc_numbers(text: str) -> str:
    """Strip leading/trailing numbers from TOC entries: '2Algorithm Analysis31' -> 'Algorithm Analysis'."""
    # Remove Roman numerals at start (when directly followed by uppercase)
    text = re.sub(r'^[IVX]+(?=[A-Z])', '', text)
    # Remove leading Arabic numbers
    text = re.sub(r'^\d+\s*', '', text)
    # Remove page numbers embedded in text (digits between lowercase and uppercase)
    text = re.sub(r'(?<=[a-zA-Z])\d+(?=[A-Z]|\s|$)', ' ', text)
    # Remove trailing numbers
    text = re.sub(r'\s*\d+$', '', text)
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def split_merged_words(text: str) -> str:
    """Try to split merged lowercase words: 'travelingsalesman' -> 'traveling salesman'."""
    # Common word patterns that indicate split points
    split_patterns = [
        (r'traveling(?=salesman)', 'traveling '),
        (r'basis(?=cases)', 'basis '),
        (r'(?<=War)(?=and)', ' '),
        (r'(?<=Find)(?=the)', ' '),
        (r'(?<=Principled)(?=calculations)', ' '),
        (r'(?<=necessary)(?=[A-Za-z])', ' '),
    ]
    
    for pattern, replacement in split_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text


def normalize_for_matching(text: str) -> str:
    """Aggressive normalization for matching - removes spacing around punctuation."""
    # Remove all spaces around parentheses, brackets, commas
    text = re.sub(r'\s*\(\s*', '(', text)
    text = re.sub(r'\s*\)\s*', ')', text)
    text = re.sub(r'\s*\[\s*', '[', text)
    text = re.sub(r'\s*\]\s*', ']', text)
    text = re.sub(r'\s*,\s*', ',', text)
    text = re.sub(r'\s*:\s*', ':', text)
    # Normalize remaining whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    return text.lower()


def normalize_latex_text(text: str) -> str:
    """Normalize LaTeX for matching: replace \item, remove commands, normalize whitespace."""
    # Replace \item with space
    text = re.sub(r'\\item\s*', ' ', text)
    # Remove $ (math delimiters)
    text = text.replace('$', '')
    # Remove \operatorname{...} but keep content
    text = re.sub(r'\\operatorname\{([^}]*)\}', r'\1', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    return text


def strip_latex_commands(text: str) -> str:
    """Remove LaTeX commands but KEEP content inside braces."""
    # Replace \command{content} with just content
    text = re.sub(r'\\[a-zA-Z]+\*?(\[[^\]]*\])?\{([^}]*)\}', r'\2', text)
    # Remove standalone commands like \item
    text = re.sub(r'\\[a-zA-Z]+\*?', ' ', text)
    # Remove remaining braces
    text = re.sub(r'[{}]', '', text)
    text = re.sub(r'\s+', ' ', text.strip())
    return text


def should_skip_span(text: str) -> bool:
    """Skip spans that shouldn't be matched."""
    text = text.strip()
    if not text:
        return True
    # Skip number patterns like "1.5.1Kaggle"
    if re.match(r'^\d+(\.\d+)+', text):
        return True
    # Need at least 4 alphabetic characters
    if len(re.findall(r'[a-zA-Z]', text)) < 4:
        return True
    # Skip if too many math symbols
    if len(re.findall(r'[+\-*/=<>≤≥≠±×÷∑∏∫√∞∈∉⊂⊃∪∩≈]', text)) > 1:
        return True
    return False


def find_unclosed_delimiters(text: str, pos: int) -> Dict[str, int]:
    """
    Count unclosed brackets and braces from start to position.
    Returns counts of unclosed [ and {.
    
    This is the KEY fix - we scan from the START of the region,
    not from the nearest backslash.
    """
    bracket_count = 0  # [
    brace_count = 0    # {
    
    i = 0
    while i < pos and i < len(text):
        char = text[i]
        prev_char = text[i-1] if i > 0 else ''
        
        # Skip escaped characters
        if prev_char == '\\':
            i += 1
            continue
            
        if char == '[':
            bracket_count += 1
        elif char == ']':
            bracket_count = max(0, bracket_count - 1)
        elif char == '{':
            brace_count += 1
        elif char == '}':
            brace_count = max(0, brace_count - 1)
        
        i += 1
    
    return {'brackets': bracket_count, 'braces': brace_count}


def find_enclosing_command(text: str, pos: int) -> Optional[str]:
    """
    Find the LaTeX command that encloses position pos.
    Returns command name or None.
    
    We look backwards from pos to find the command whose argument we're in.
    """
    # Get unclosed delimiters
    delims = find_unclosed_delimiters(text, pos)
    
    if delims['brackets'] == 0 and delims['braces'] == 0:
        return None  # Not inside any command argument
    
    # Find the opening delimiter
    target_delim = '[' if delims['brackets'] > 0 else '{'
    
    # Scan backwards to find the unmatched opening delimiter
    count = 0
    target_count = delims['brackets'] if target_delim == '[' else delims['braces']
    
    i = pos - 1
    while i >= 0:
        char = text[i]
        prev_char = text[i-1] if i > 0 else ''
        
        if prev_char != '\\':
            if char == target_delim:
                count += 1
                if count == target_count:
                    # Found the opening delimiter, now find the command before it
                    # Look backwards for \commandname
                    j = i - 1
                    # Skip whitespace
                    while j >= 0 and text[j] in ' \t\n':
                        j -= 1
                    
                    # Check if there's a ] before (optional argument before required)
                    if j >= 0 and text[j] == ']':
                        # Skip the optional argument
                        bracket_depth = 1
                        j -= 1
                        while j >= 0 and bracket_depth > 0:
                            if text[j] == ']' and (j == 0 or text[j-1] != '\\'):
                                bracket_depth += 1
                            elif text[j] == '[' and (j == 0 or text[j-1] != '\\'):
                                bracket_depth -= 1
                            j -= 1
                        # Now skip whitespace again
                        while j >= 0 and text[j] in ' \t\n':
                            j -= 1
                    
                    # Now we should be at the end of the command name
                    if j >= 0:
                        # Find command name (letters and *)
                        cmd_end = j + 1
                        while j >= 0 and (text[j].isalpha() or text[j] == '*'):
                            j -= 1
                        
                        # Check for backslash
                        if j >= 0 and text[j] == '\\':
                            return text[j+1:cmd_end]
                    
                    return None
            elif char == (']' if target_delim == '[' else '}'):
                count -= 1
        
        i -= 1
    
    return None


def is_in_protected_area(content: str, start: int, end: int) -> Tuple[bool, str]:
    """
    Check if position is in a protected area.
    Returns (is_protected, reason).
    
    Protected areas:
    1. Comments (line starts with %)
    2. Math mode ($...$ or \(...\) or equation environments)
    3. Arguments of commands that CAN'T have formatting inside
    """
    # Check comment - find line start
    line_start = content.rfind('\n', 0, start)
    line_start = 0 if line_start == -1 else line_start + 1
    line_prefix = content[line_start:start].lstrip()
    if line_prefix.startswith('%'):
        return True, 'comment'
    
    # Check math mode - look for unclosed $ or \( NEARBY (not in entire file!)
    # Only check within the current line or nearby context
    
    # Find line boundaries
    line_end = content.find('\n', start)
    if line_end == -1:
        line_end = len(content)
    
    # Get the current line
    current_line = content[line_start:line_end]
    pos_in_line = start - line_start
    
    # Check for unclosed $ in this line before our position
    dollar_count = 0
    i = 0
    while i < pos_in_line and i < len(current_line):
        if current_line[i] == '$' and (i == 0 or current_line[i-1] != '\\'):
            # Check for $$ (display math) vs $ (inline)
            if i + 1 < len(current_line) and current_line[i+1] == '$':
                i += 2  # Skip $$
                continue
            dollar_count += 1
        i += 1
    
    if dollar_count % 2 == 1:
        return True, 'inline_math'
    
    # Check \( \) math in this line
    text_before_in_line = current_line[:pos_in_line]
    paren_opens = len(re.findall(r'(?<!\\)\\\(', text_before_in_line))
    paren_closes = len(re.findall(r'(?<!\\)\\\)', text_before_in_line))
    if paren_opens > paren_closes:
        return True, 'paren_math'
    
    # Check for math/table environments using begin/end
    # Find all \begin{env} and \end{env} to track nesting
    text_before = content[:start]  # Text from start of content to our position
    protected_envs = {
        'equation', 'equation*', 'align', 'align*', 'gather', 'gather*',
        'multline', 'multline*', 'eqnarray', 'eqnarray*', 'cases',
        'matrix', 'pmatrix', 'bmatrix', 'vmatrix', 'array',
        'tabular', 'tabular*', 'longtable', 'table', 'table*',
        'verbatim', 'lstlisting', 'minted'
    }
    
    env_stack = []
    for match in re.finditer(r'\\(begin|end)\{([^}]+)\}', text_before):
        cmd, env = match.groups()
        if cmd == 'begin':
            env_stack.append(env)
        elif cmd == 'end':
            # Pop matching environment (handle mismatched nesting gracefully)
            if env_stack and env_stack[-1] == env:
                env_stack.pop()
            elif env in env_stack:
                # Mismatched but env exists somewhere in stack - remove it
                env_stack.remove(env)
            # If env not in stack at all, ignore (already closed or never opened)
    
    for env in env_stack:
        if env in protected_envs:
            return True, f'environment:{env}'
    
    # Check if inside a BLOCKED command's argument
    # These are commands where you CAN'T put \textit{} inside
    blocked_commands = {
        'includegraphics', 'ref', 'cite', 'label', 'url', 'href',
        'input', 'include', 'bibliography', 'bibliographystyle',
        'usepackage', 'documentclass', 'newcommand', 'renewcommand',
        'def', 'let', 'index', 'pageref', 'eqref', 'autoref', 'cref'
    }
    
    enclosing_cmd = find_enclosing_command(content, start)
    if enclosing_cmd and enclosing_cmd.rstrip('*') in blocked_commands:
        return True, f'blocked_command:{enclosing_cmd}'
    
    return False, ''


def find_text_match(target: str, content: str, search_start: int = 0, search_end: int = None) -> Optional[Tuple[int, int]]:
    """
    Find target text in content. Returns (start, end) or None.
    Tries multiple strategies:
    1. Exact match
    2. Case-insensitive match
    3. Normalized match (remove bullets from target, \item from content)
    """
    if search_end is None:
        search_end = len(content)
    
    search_region = content[search_start:search_end]
    
    # Strategy 1: Exact match
    pos = search_region.find(target)
    if pos != -1:
        return (search_start + pos, search_start + pos + len(target))
    
    # Strategy 2: Case-insensitive
    lower_region = search_region.lower()
    lower_target = target.lower()
    pos = lower_region.find(lower_target)
    if pos != -1:
        return (search_start + pos, search_start + pos + len(target))
    
    # Strategy 3: Try de-hyphenation (handles "Al-gorithm" -> "Algorithm")
    dehyphenated = dehyphenate(target)
    if dehyphenated != target:
        pos = search_region.lower().find(dehyphenated.lower())
        if pos != -1:
            return (search_start + pos, search_start + pos + len(dehyphenated))
    
    # Strategy 4: Try CamelCase splitting (handles "AlgorithmDesign" -> "Algorithm Design")
    camel_split = split_camelcase(target)
    if camel_split != target:
        pos = search_region.lower().find(camel_split.lower())
        if pos != -1:
            return (search_start + pos, search_start + pos + len(camel_split))
    
    # Strategy 5: TOC number stripping (handles "2Algorithm Analysis31" -> "Algorithm Analysis")
    toc_stripped = strip_toc_numbers(target)
    if toc_stripped and toc_stripped != target and len(toc_stripped) > 5:
        pos = search_region.lower().find(toc_stripped.lower())
        if pos != -1:
            return (search_start + pos, search_start + pos + len(toc_stripped))
    
    # Strategy 6: Try splitting merged words
    merged_split = split_merged_words(target)
    if merged_split != target:
        pos = search_region.lower().find(merged_split.lower())
        if pos != -1:
            return (search_start + pos, search_start + pos + len(merged_split))
    
    # Strategy 7: Combined transformations
    combined = split_merged_words(dehyphenate(split_camelcase(normalize_pdf_text(target))))
    if combined != target:
        pos = search_region.lower().find(combined.lower())
        if pos != -1:
            return (search_start + pos, search_start + pos + len(combined))
    
    # Strategy 7: Aggressive normalized matching (handles spacing differences)
    # This handles cases like "Push(x,s)" vs "Push (x, s)"
    norm_target = normalize_for_matching(normalize_pdf_text(target))
    if len(norm_target) < 3:
        return None
    
    # Normalize LaTeX: remove $, commands, then aggressive space normalization
    latex_normalized = normalize_latex_text(search_region)
    latex_stripped = strip_latex_commands(latex_normalized)
    latex_for_match = normalize_for_matching(latex_stripped)
    
    norm_pos = latex_for_match.find(norm_target)
    if norm_pos == -1:
        return None
    
    # Found in normalized - now map back to original LaTeX
    # Extract just the alphabetic first word for finding start position
    # IMPORTANT: normalize first to handle bullets, quotes, etc.
    normalized_target_for_word = normalize_pdf_text(target)
    first_alpha_word = re.match(r'[A-Za-z]+', normalized_target_for_word)
    if not first_alpha_word:
        return None
    
    first_word = first_alpha_word.group()
    
    # Check if target has parentheses with arguments - likely a function call
    # Only use this special pattern for function-like patterns: Word(args)
    has_func_parens = re.match(r'^[A-Za-z]+\([^)]+\)$', target.strip())
    
    if has_func_parens:
        # Look for "Word $(" or "Word (" pattern - this is a function-like call
        pattern = r'\b' + re.escape(first_word) + r'\s*\$?\s*\([^)]*\)\s*\$?'
        func_match = re.search(pattern, search_region, re.IGNORECASE)
        if func_match:
            start = search_start + func_match.start()
            end = search_start + func_match.end()
            # Trim trailing $ or : or space
            while end > start and content[end-1] in ':$ \n':
                end -= 1
            return (start, end)
    
    # Standard approach: find first word in original LaTeX (case-insensitive)
    first_match = re.search(r'\b' + re.escape(first_word) + r'\b', search_region, re.IGNORECASE)
    if not first_match:
        return None
    
    start = search_start + first_match.start()
    
    # For non-function targets, estimate end based on target length
    # Check if target has multiple words
    target_words = target.split()
    if len(target_words) > 1:
        # Find last word
        last_word_match = re.match(r'.*[A-Za-z]+', target)
        if last_word_match:
            last_word = re.findall(r'[A-Za-z]+', target)[-1]
            search_window = search_region[first_match.start():first_match.start() + len(target) * 3]
            last_match = None
            for m in re.finditer(r'\b' + re.escape(last_word) + r'\b', search_window, re.IGNORECASE):
                last_match = m
            if last_match:
                end = search_start + first_match.start() + last_match.end()
            else:
                end = start + len(target)
        else:
            end = start + len(target)
    else:
        end = search_start + first_match.end()
    
    # Ensure we don't go past search region
    end = min(end, search_end)
    
    # SAFETY CHECK: Look at what we're about to select
    actual = search_region[start - search_start:end - search_start]
    
    # If there's a backslash, trim BEFORE it (don't include LaTeX commands)
    if '\\' in actual:
        backslash_pos = actual.find('\\')
        # Only trim if we have enough text before the backslash
        if backslash_pos >= len(first_word):
            # Trim to word boundary before backslash
            trimmed = actual[:backslash_pos].rstrip()
            # Find the last complete word
            last_space = trimmed.rfind(' ')
            if last_space > 0:
                end = start + last_space
            else:
                end = start + backslash_pos
            actual = search_region[start - search_start:end - search_start]
        else:
            # Backslash too early, can't safely match
            return None
    
    # Final verification: must not contain backslash
    if '\\' in actual:
        return None
    
    return (start, end)


def group_spans(spans: List[SpanData]) -> List[Dict[str, Any]]:
    """Group consecutive spans with same formatting."""
    if not spans:
        return []
    
    groups = []
    current = None
    
    for span in spans:
        is_bold = span.style.is_bold
        is_italic = span.style.is_italic
        
        if not is_bold and not is_italic:
            if current:
                groups.append(current)
                current = None
            continue
        
        if current and current['is_bold'] == is_bold and current['is_italic'] == is_italic:
            current['text'] += span.text
        else:
            if current:
                groups.append(current)
            current = {'text': span.text, 'is_bold': is_bold, 'is_italic': is_italic}
    
    if current:
        groups.append(current)
    
    return groups


def apply_formatting(
    book_path: str,
    tex_path: str,
    output_path: str,
    output_dir: str,
    page_margin: int = 2000  # Characters to search beyond page boundary
) -> str:
    """Apply bold/italic formatting from PDF to LaTeX."""
    
    print("\n=== Formatting Applier v2 ===")
    
    # Read LaTeX
    with open(tex_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse page separators
    separator_pattern = re.compile(r'%---- Page End Break Here ---- Page : (\d+)')
    separators = []
    for match in separator_pattern.finditer(content):
        separators.append({
            'page': int(match.group(1)),
            'pos': match.start()
        })
    separators.sort(key=lambda x: x['pos'])
    print(f"Found {len(separators)} page separators")
    
    # Extract PDF spans
    print(f"Extracting from PDF: {book_path}")
    pdf = fitz.open(book_path)
    extractor = PDFTextExtractor(skip_first_block=True)
    spans = extractor.extract_document_text(pdf)
    print(f"Extracted {len(spans)} spans")
    
    # Stats
    stats = {
        'matched': 0, 'not_found': 0, 'protected': 0, 'skipped': 0,
        'expected_bold': 0, 'expected_italic': 0, 'expected_both': 0,
        'applied_bold': 0, 'applied_italic': 0, 'applied_both': 0
    }
    page_info = {}
    
    # Process pages in reverse order (to avoid position shifts)
    modified = content
    
    for sep_idx in tqdm(range(len(separators) - 1, -1, -1)):
        sep = separators[sep_idx]
        page_num = sep['page']
        
        # Define search region: include previous AND next page as well
        # This handles cases where page separators are slightly off
        if sep_idx > 1:
            # Start from 2 pages before (to include previous page fully)
            region_start = max(0, separators[sep_idx - 2]['pos'])
        elif sep_idx > 0:
            region_start = max(0, separators[sep_idx - 1]['pos'])
        else:
            region_start = 0
        
        if sep_idx < len(separators) - 1:
            # End at next page separator (to include next page)
            region_end = min(len(modified), separators[sep_idx + 1]['pos'] + page_margin)
        else:
            region_end = min(len(modified), sep['pos'] + page_margin)
        
        # Get PDF spans for this page
        pdf_page = page_num - 1  # 0-indexed
        page_spans = [s for s in spans if s.page_number == pdf_page]
        groups = group_spans(page_spans)
        
        page_info[page_num] = []
        changes = []
        
        for group in groups:
            text = group['text'].strip()
            is_bold = group['is_bold']
            is_italic = group['is_italic']
            
            # Track info
            info = {
                'text': text[:100],
                'is_bold': is_bold,
                'is_italic': is_italic,
                'matched': False
            }
            
            # Count expected
            if is_bold and is_italic:
                stats['expected_both'] += 1
            elif is_bold:
                stats['expected_bold'] += 1
            elif is_italic:
                stats['expected_italic'] += 1
            
            # Skip check
            if should_skip_span(text):
                stats['skipped'] += 1
                info['reason'] = 'skipped'
                page_info[page_num].append(info)
                continue
            
            # Find match
            match = find_text_match(text, modified, region_start, region_end)
            
            if not match:
                stats['not_found'] += 1
                info['reason'] = 'not_found'
                page_info[page_num].append(info)
                continue
            
            start, end = match
            
            # Check protected area
            is_protected, reason = is_in_protected_area(modified, start, end)
            if is_protected:
                stats['protected'] += 1
                info['reason'] = f'protected:{reason}'
                page_info[page_num].append(info)
                continue
            
            # Get actual text to wrap
            actual_text = modified[start:end]
            
            # CRITICAL: Fix word cutting by extending to complete words
            # If character before start is alphanumeric, we're cutting a word - go back to word start
            while start > 0 and modified[start - 1].isalnum():
                start -= 1
            
            # If character after end is alphanumeric, we're cutting a word - go forward to word end
            while end < len(modified) and modified[end].isalnum():
                end += 1
            
            # Re-get the actual text after boundary adjustment
            actual_text = modified[start:end]
            
            # Final safety: reject if contains backslash (LaTeX command)
            if '\\' in actual_text:
                # Try to trim to before the backslash
                backslash_pos = actual_text.find('\\')
                if backslash_pos > 3:  # Keep at least a few chars
                    # Trim to last complete word before backslash
                    trimmed = actual_text[:backslash_pos].rstrip()
                    last_space = trimmed.rfind(' ')
                    if last_space > 0:
                        end = start + last_space
                        actual_text = modified[start:end]
                    else:
                        end = start + backslash_pos
                        actual_text = modified[start:end].rstrip()
                
                # Check again after trimming
                if '\\' in actual_text:
                    stats['protected'] += 1
                    info['reason'] = 'contains_backslash'
                    page_info[page_num].append(info)
                    continue
            
            # Verify boundaries are still good after adjustments
            # Don't start/end mid-word
            if start > 0 and modified[start - 1].isalnum():
                stats['not_found'] += 1
                info['reason'] = 'boundary_error'
                page_info[page_num].append(info)
                continue
            if end < len(modified) and modified[end].isalnum():
                stats['not_found'] += 1
                info['reason'] = 'boundary_error'
                page_info[page_num].append(info)
                continue
            
            # Skip if too short after adjustments
            if len(actual_text.strip()) < 2:
                stats['skipped'] += 1
                info['reason'] = 'too_short'
                page_info[page_num].append(info)
                continue
            
            # Create replacement
            if is_bold and is_italic:
                replacement = f"\\textbf{{\\textit{{{actual_text}}}}}"
                stats['applied_both'] += 1
            elif is_bold:
                replacement = f"\\textbf{{{actual_text}}}"
                stats['applied_bold'] += 1
            else:
                replacement = f"\\textit{{{actual_text}}}"
                stats['applied_italic'] += 1
            
            stats['matched'] += 1
            info['matched'] = True
            page_info[page_num].append(info)
            changes.append((start, end, replacement))
        
        # Remove overlapping changes - keep the longer (more complete) match
        changes.sort(key=lambda x: x[0])  # Sort by start position
        filtered_changes = []
        for change in changes:
            start, end, replacement = change
            # Check if this overlaps with any previous change
            overlaps = False
            for prev_start, prev_end, _ in filtered_changes:
                # Overlap if ranges intersect
                if start < prev_end and end > prev_start:
                    overlaps = True
                    break
            if not overlaps:
                filtered_changes.append(change)
        
        # Apply changes in reverse order (to avoid position shifts)
        for start, end, replacement in sorted(filtered_changes, key=lambda x: -x[0]):
            modified = modified[:start] + replacement + modified[end:]
    
    # Write output
    print(f"Writing to: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(modified)
    
    # Calculate match ratio (exclude protected from ratio since they're correctly identified)
    total_applied = stats['applied_bold'] + stats['applied_italic'] + stats['applied_both']
    # total_considered excludes protected (correctly skipped items)
    total_matchable = total_applied + stats['not_found']
    match_ratio = (total_applied / total_matchable * 100) if total_matchable > 0 else 0
    
    # Save stats
    final_stats = {
        'applied_bold': stats['applied_bold'],
        'applied_italic': stats['applied_italic'],
        'applied_both': stats['applied_both'],
        'total_applied': total_applied,
        'expected_bold': stats['expected_bold'],
        'expected_italic': stats['expected_italic'],
        'expected_both': stats['expected_both'],
        'not_found': stats['not_found'],
        'protected': stats['protected'],
        'skipped': stats['skipped'],
        'total_matchable': total_matchable,
        'match_ratio_percent': round(match_ratio, 1),
        'per_page': {f'page_{p}': info for p, info in sorted(page_info.items())}
    }
    
    stats_path = os.path.join(output_dir, 'formatting_statistics.json')
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(final_stats, f, indent=2)
    
    print(f"\nResults:")
    print(f"  Matched: {stats['matched']}")
    print(f"  Not found: {stats['not_found']}")
    print(f"  Protected: {stats['protected']}")
    print(f"  Skipped: {stats['skipped']}")
    print(f"  Applied - Bold: {stats['applied_bold']}, Italic: {stats['applied_italic']}, Both: {stats['applied_both']}")
    print(f"  Match ratio: {match_ratio:.1f}% ({total_applied}/{total_matchable} matchable, {stats['protected']} protected)")
    
    pdf.close()
    return output_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", required=True)
    parser.add_argument("--tex", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--margin", type=int, default=2000, help="Search margin beyond page boundary")
    args = parser.parse_args()
    
    apply_formatting(args.book, args.tex, args.output, args.output_dir, args.margin)

