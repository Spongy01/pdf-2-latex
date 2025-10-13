import re
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict, Counter
import os


@dataclass
class CommandMatch:
    """Represents a matched LaTeX command with position information."""
    command_type: str  # 'begin' or 'end'
    environment: str
    line_number: int
    column: int
    full_match: str


@dataclass
class BalanceIssue:
    """Represents a balance issue found in the LaTeX file."""
    issue_type: str  # 'unclosed', 'premature_end', 'mismatch', 'orphaned_end'
    environment: str
    line_number: int
    details: str
    severity: str  # 'error', 'warning'


@dataclass
class BalanceReport:
    """Complete balance analysis report."""
    total_commands: int
    total_issues: int
    issues_by_type: Dict[str, int]
    issues_by_environment: Dict[str, int]
    issues: List[BalanceIssue]
    environments_found: List[str]
    nesting_depth_stats: Dict[str, int]
    file_path: str


@dataclass
class FixReport:
    """Report of balance fixing operations."""
    fixes_applied: int
    fixes_details: List[str]
    pre_correction_report: BalanceReport
    post_correction_report: BalanceReport
    corrected_content: str


class LaTeXBalanceChecker:
    """Checks LaTeX command balance and nesting."""
    
    def __init__(self):
        # Regex patterns for LaTeX commands
        self.begin_pattern = re.compile(r'\\begin\{([^}]+)\}')
        self.end_pattern = re.compile(r'\\end\{([^}]+)\}')
        
        # Commands that don't need balancing (single commands)
        self.single_commands = {
            'document', 'input', 'include', 'usepackage', 'newcommand', 
            'renewcommand', 'def', 'newcommand', 'providecommand',
            'DeclareMathOperator', 'DeclarePairedDelimiter'
        }
        
        # Commands that are self-closing or special
        self.special_commands = {
            'itemize', 'enumerate', 'description',  # These can be self-closing
            'center', 'flushleft', 'flushright',    # These can be self-closing
            'quote', 'quotation', 'verse'           # These can be self-closing
        }

    def find_commands(self, content: str) -> List[CommandMatch]:
        """Find all begin and end commands in the LaTeX content."""
        commands = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Find begin commands
            for match in self.begin_pattern.finditer(line):
                commands.append(CommandMatch(
                    command_type='begin',
                    environment=match.group(1),
                    line_number=line_num,
                    column=match.start(),
                    full_match=match.group(0)
                ))
            
            # Find end commands
            for match in self.end_pattern.finditer(line):
                commands.append(CommandMatch(
                    command_type='end',
                    environment=match.group(1),
                    line_number=line_num,
                    column=match.start(),
                    full_match=match.group(0)
                ))
        
        return commands

    def check_balance(self, content: str) -> BalanceReport:
        """Check the balance of LaTeX commands and return a detailed report."""
        commands = self.find_commands(content)
        
        # Initialize tracking structures
        stack = []  # Stack to track open environments
        issues = []
        environments_found = set()
        nesting_depths = []
        
        # Process each command
        for cmd in commands:
            environments_found.add(cmd.environment)
            
            if cmd.command_type == 'begin':
                # Push onto stack
                stack.append(cmd)
                nesting_depths.append(len(stack))
                
            elif cmd.command_type == 'end':
                if not stack:
                    # Orphaned end command
                    issues.append(BalanceIssue(
                        issue_type='orphaned_end',
                        environment=cmd.environment,
                        line_number=cmd.line_number,
                        details=f"\\end{{{cmd.environment}}} found without matching \\begin",
                        severity='error'
                    ))
                else:
                    # Check if it matches the most recent begin
                    last_begin = stack[-1]
                    if last_begin.environment == cmd.environment:
                        # Properly matched, remove from stack
                        stack.pop()
                    else:
                        # Mismatched environment
                        issues.append(BalanceIssue(
                            issue_type='mismatch',
                            environment=cmd.environment,
                            line_number=cmd.line_number,
                            details=f"\\end{{{cmd.environment}}} found but expected \\end{{{last_begin.environment}}} (opened at line {last_begin.line_number})",
                            severity='error'
                        ))
        
        # Check for unclosed commands
        for unclosed in stack:
            issues.append(BalanceIssue(
                issue_type='unclosed',
                environment=unclosed.environment,
                line_number=unclosed.line_number,
                details=f"\\begin{{{unclosed.environment}}} opened but never closed",
                severity='error'
            ))
        
        # Calculate statistics
        issues_by_type = Counter(issue.issue_type for issue in issues)
        issues_by_environment = Counter(issue.environment for issue in issues)
        
        nesting_depth_stats = {
            'max_depth': max(nesting_depths) if nesting_depths else 0,
            'avg_depth': sum(nesting_depths) / len(nesting_depths) if nesting_depths else 0,
            'total_nested': len(nesting_depths)
        }
        
        return BalanceReport(
            total_commands=len(commands),
            total_issues=len(issues),
            issues_by_type=dict(issues_by_type),
            issues_by_environment=dict(issues_by_environment),
            issues=issues,
            environments_found=sorted(environments_found),
            nesting_depth_stats=nesting_depth_stats,
            file_path=""
        )

    def analyze_environment_usage(self, content: str) -> Dict[str, Dict]:
        """Analyze usage patterns for each environment type."""
        commands = self.find_commands(content)
        environment_stats = defaultdict(lambda: {'begins': 0, 'ends': 0, 'unclosed': 0})
        
        for cmd in commands:
            env = cmd.environment
            if cmd.command_type == 'begin':
                environment_stats[env]['begins'] += 1
            else:
                environment_stats[env]['ends'] += 1
        
        # Calculate unclosed counts
        for env, stats in environment_stats.items():
            stats['unclosed'] = max(0, stats['begins'] - stats['ends'])
            stats['balance_ratio'] = stats['ends'] / stats['begins'] if stats['begins'] > 0 else 0
        
        return dict(environment_stats)

    def generate_detailed_report(self, report: BalanceReport, content: str) -> str:
        """Generate a detailed text report of the balance analysis."""
        lines = content.split('\n')
        
        report_text = []
        report_text.append("=" * 80)
        report_text.append("LATEX COMMAND BALANCE ANALYSIS REPORT")
        report_text.append("=" * 80)
        report_text.append(f"File: {report.file_path}")
        report_text.append(f"Total commands found: {report.total_commands}")
        report_text.append(f"Total issues found: {report.total_issues}")
        report_text.append("")
        
        # Summary statistics
        report_text.append("SUMMARY STATISTICS:")
        report_text.append("-" * 40)
        report_text.append(f"Environments found: {len(report.environments_found)}")
        report_text.append(f"Max nesting depth: {report.nesting_depth_stats['max_depth']}")
        report_text.append(f"Average nesting depth: {report.nesting_depth_stats['avg_depth']:.2f}")
        report_text.append("")
        
        # Issues by type
        report_text.append("ISSUES BY TYPE:")
        report_text.append("-" * 40)
        for issue_type, count in report.issues_by_type.items():
            report_text.append(f"{issue_type}: {count}")
        report_text.append("")
        
        # Issues by environment
        report_text.append("ISSUES BY ENVIRONMENT:")
        report_text.append("-" * 40)
        for env, count in report.issues_by_environment.items():
            report_text.append(f"{env}: {count}")
        report_text.append("")
        
        # Detailed issues
        if report.issues:
            report_text.append("DETAILED ISSUES:")
            report_text.append("-" * 40)
            for i, issue in enumerate(report.issues, 1):
                report_text.append(f"{i}. {issue.issue_type.upper()} - {issue.environment}")
                report_text.append(f"   Line {issue.line_number}: {issue.details}")
                report_text.append(f"   Severity: {issue.severity}")
                report_text.append("")
        else:
            report_text.append("No balance issues found! ✓")
            report_text.append("")
        
        # Environment usage analysis
        env_analysis = self.analyze_environment_usage(content)
        report_text.append("ENVIRONMENT USAGE ANALYSIS:")
        report_text.append("-" * 40)
        for env, stats in sorted(env_analysis.items()):
            report_text.append(f"{env}:")
            report_text.append(f"  Begins: {stats['begins']}, Ends: {stats['ends']}")
            report_text.append(f"  Unclosed: {stats['unclosed']}, Balance ratio: {stats['balance_ratio']:.2f}")
            report_text.append("")
        
        return "\n".join(report_text)

    def check_latex_file(self, file_path: str) -> BalanceReport:
        """Check a LaTeX file and return a balance report."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            report = self.check_balance(content)
            report.file_path = file_path
            
            return report
        except Exception as e:
            # Return error report
            return BalanceReport(
                total_commands=0,
                total_issues=1,
                issues_by_type={'file_error': 1},
                issues_by_environment={},
                issues=[BalanceIssue(
                    issue_type='file_error',
                    environment='',
                    line_number=0,
                    details=f"Error reading file: {e}",
                    severity='error'
                )],
                environments_found=[],
                nesting_depth_stats={},
                file_path=file_path
            )

    def fix_duplicate_ends(self, content: str) -> Tuple[str, List[str]]:
        """Fix duplicate \\end commands using stack methodology to verify if they're actually duplicates."""
        lines = content.split('\n')
        fixes = []
        
        # First, fix duplicates on same line
        for i, line in enumerate(lines):
            end_matches = list(self.end_pattern.finditer(line))
            if len(end_matches) > 1:
                # Keep only the first end command
                first_end = end_matches[0]
                lines[i] = line[:first_end.end()]
                fixes.append(f"Line {i+1}: Removed {len(end_matches)-1} duplicate \\end commands on same line")
        
        # Now use stack methodology to identify and remove true duplicates
        stack = []
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Track begin commands
            for match in self.begin_pattern.finditer(line):
                env = match.group(1)
                stack.append((env, i+1))
            
            # Check end commands
            end_matches = list(self.end_pattern.finditer(line))
            if end_matches:
                for match in end_matches:
                    env = match.group(1)
                    
                    if not stack:
                        # No open environments - this end is orphaned, remove it
                        lines[i] = line[:match.start()] + line[match.end():]
                        fixes.append(f"Line {i+1}: Removed orphaned \\end{{{env}}} command")
                        continue
                    
                    # Check if this matches the most recent begin
                    last_begin_env, last_begin_line = stack[-1]
                    if env == last_begin_env:
                        # Properly matched, remove from stack
                        stack.pop()
                    else:
                        # Mismatch - check if this is a duplicate of a previous end
                        # Look for this environment in the stack
                        found_match = False
                        for j in range(len(stack) - 1, -1, -1):
                            if stack[j][0] == env:
                                # Found a match, remove it from stack
                                stack.pop(j)
                                found_match = True
                                break
                        
                        if not found_match:
                            # This end has no matching begin, it's a duplicate/orphaned
                            lines[i] = line[:match.start()] + line[match.end():]
                            fixes.append(f"Line {i+1}: Removed duplicate/orphaned \\end{{{env}}} command")
            
            i += 1
        
        return '\n'.join(lines), fixes

    def fix_orphaned_ends(self, content: str) -> Tuple[str, List[str]]:
        """Remove only clearly orphaned \\end commands (very conservative approach)."""
        lines = content.split('\n')
        fixes = []
        
        # Use the existing balance checker to identify orphaned ends
        report = self.check_balance(content)
        
        # Only remove lines that are clearly orphaned (no matching begin anywhere)
        orphaned_lines = set()
        for issue in report.issues:
            if issue.issue_type == 'orphaned_end':
                orphaned_lines.add(issue.line_number - 1)  # Convert to 0-based index
        
        # Remove orphaned end commands (be very conservative)
        for line_idx in sorted(orphaned_lines, reverse=True):
            if line_idx < len(lines):
                line = lines[line_idx]
                # Only remove if the line contains ONLY end commands (no other content)
                stripped = line.strip()
                if stripped.startswith('\\end{') and stripped.endswith('}'):
                    lines.pop(line_idx)  # Remove the entire line
                    fixes.append(f"Line {line_idx + 1}: Removed orphaned \\end command line")
        
        return '\n'.join(lines), fixes

    def fix_missing_document_end(self, content: str) -> Tuple[str, List[str]]:
        """Remove any \\end{document} not at the end and add it to the last line if needed."""
        lines = content.split('\n')
        fixes = []
        
        # Check if document environment exists
        has_begin_document = any('\\begin{document}' in line for line in lines)
        
        if not has_begin_document:
            return content, fixes  # No document environment to close
        
        # Find and remove any existing \end{document} commands
        end_document_lines = []
        for i, line in enumerate(lines):
            if '\\end{document}' in line:
                end_document_lines.append(i)
        
        # Remove all existing \end{document} commands
        for line_idx in sorted(end_document_lines, reverse=True):
            line = lines[line_idx]
            # Remove \end{document} from the line
            lines[line_idx] = line.replace('\\end{document}', '').strip()
            if not lines[line_idx]:  # If line is now empty, remove it
                lines.pop(line_idx)
            fixes.append(f"Line {line_idx + 1}: Removed \\end{{document}} from middle of file")
        
        # Check if we need to add \end{document} at the end
        # Use the balance checker to see if there are unclosed issues
        temp_content = '\n'.join(lines)
        report = self.check_balance(temp_content)
        unclosed_count = report.issues_by_type.get('unclosed', 0)
        
        if unclosed_count > 0:
            lines.append('\\end{document}')
            fixes.append(f"Line {len(lines)}: Added \\end{{document}} to close {unclosed_count} unclosed environments")
        
        return '\n'.join(lines), fixes

    def fix_balance_issues(self, content: str, max_iterations: int = 3) -> FixReport:
        """Apply all balance fixes and return detailed report."""
        # Pre-correction analysis
        pre_report = self.check_balance(content)
        pre_report.file_path = "pre-correction"
        
        all_fixes = []
        
        for iteration in range(max_iterations):
            iteration_fixes = []
            
            # Fix duplicate end commands using stack methodology
            content, fixes = self.fix_duplicate_ends(content)
            iteration_fixes.extend(fixes)
            
            # Remove orphaned end commands (commented out)
            # content, fixes = self.fix_orphaned_ends(content)
            # iteration_fixes.extend(fixes)
            
            # Fix document end - remove from middle, add to end if needed
            content, fixes = self.fix_missing_document_end(content)
            iteration_fixes.extend(fixes)
            
            all_fixes.extend(iteration_fixes)
            
            if not iteration_fixes:
                break  # No more fixes possible
        
        # Post-correction analysis
        post_report = self.check_balance(content)
        post_report.file_path = "post-correction"
        
        return FixReport(
            fixes_applied=len(all_fixes),
            fixes_details=all_fixes,
            pre_correction_report=pre_report,
            post_correction_report=post_report,
            corrected_content=content
        )


def check_latex_balance(tex_file_path: str, output_dir: str = None, apply_fixes: bool = False) -> str:
    """
    Check and optionally fix LaTeX command balance.
    
    Args:
        tex_file_path: Path to the LaTeX file to check
        output_dir: Directory to save the report (optional)
        apply_fixes: Whether to apply fixes (default: False)
    
    Returns:
        Path to the JSON report file
    """
    print("\n=== Step 6: Checking LaTeX Command Balance ===")
    print(f"Checking file: {tex_file_path}")
    
    checker = LaTeXBalanceChecker()
    
    # Read the file
    with open(tex_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if apply_fixes:
        print("Applying fixes...")
        fix_report = checker.fix_balance_issues(content)
        
        print(f"Fixes applied: {fix_report.fixes_applied}")
        print(f"Pre-correction issues: {fix_report.pre_correction_report.total_issues}")
        print(f"Post-correction issues: {fix_report.post_correction_report.total_issues}")
        
        # Save JSON report with pre/post data
        if output_dir is None:
            output_dir = os.path.dirname(tex_file_path)
        
        json_report_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(tex_file_path))[0]}_balance_report.json")
        with open(json_report_path, 'w', encoding='utf-8') as f:
            json.dump({
                'pre_correction': {
                    'total_commands': fix_report.pre_correction_report.total_commands,
                    'total_issues': fix_report.pre_correction_report.total_issues,
                    'issues_by_type': fix_report.pre_correction_report.issues_by_type,
                    'issues_by_environment': fix_report.pre_correction_report.issues_by_environment,
                },
                'post_correction': {
                    'total_commands': fix_report.post_correction_report.total_commands,
                    'total_issues': fix_report.post_correction_report.total_issues,
                    'issues_by_type': fix_report.post_correction_report.issues_by_type,
                    'issues_by_environment': fix_report.post_correction_report.issues_by_environment,
                },
                'fixes_applied': fix_report.fixes_applied,
                'fixes_details': fix_report.fixes_details,
                'environments_found': fix_report.post_correction_report.environments_found,
                'nesting_depth_stats': fix_report.post_correction_report.nesting_depth_stats,
            }, f, indent=2)
        
        print(f"JSON report saved to: {json_report_path}")
        
        # Return the corrected content
        return fix_report.corrected_content
    
    else:
        # Original checking behavior
        report = checker.check_latex_file(tex_file_path)
        
        # Save JSON report for programmatic access
        if output_dir is None:
            output_dir = os.path.dirname(tex_file_path)
        
        json_report_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(tex_file_path))[0]}_balance_report.json")
        with open(json_report_path, 'w', encoding='utf-8') as f:
            json.dump({
                'total_commands': report.total_commands,
                'total_issues': report.total_issues,
                'issues_by_type': report.issues_by_type,
                'issues_by_environment': report.issues_by_environment,
                'environments_found': report.environments_found,
                'nesting_depth_stats': report.nesting_depth_stats,
                'issues': [
                    {
                        'issue_type': issue.issue_type,
                        'environment': issue.environment,
                        'line_number': issue.line_number,
                        'details': issue.details,
                        'severity': issue.severity
                    }
                    for issue in report.issues
                ]
            }, f, indent=2)
        
        print(f"Balance check complete!")
        print(f"Total commands: {report.total_commands}")
        print(f"Total issues: {report.total_issues}")
        print(f"JSON report saved to: {json_report_path}")
        
        return json_report_path


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Check LaTeX command balance')
    parser.add_argument('tex_file', help='Path to the LaTeX file to check')
    parser.add_argument('output_dir', nargs='?', help='Output directory for reports')
    parser.add_argument('--fix-balance', action='store_true', help='Apply automatic fixes to balance issues')
    
    args = parser.parse_args()
    
    check_latex_balance(args.tex_file, args.output_dir, args.fix_balance)
