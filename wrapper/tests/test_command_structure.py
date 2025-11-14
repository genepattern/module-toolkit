#!/usr/bin/env python
"""
Test for wrapper script command structure validation.

This test checks that the wrapper script follows expected patterns for
GenePattern modules, including main execution blocks, function organization,
and proper command-line interface structure.
"""
from __future__ import annotations

import sys
import os
import re
from typing import List
from dataclasses import dataclass

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


@dataclass
class LintIssue:
    """Represents a validation issue found during wrapper script linting."""
    severity: str  # 'ERROR' or 'WARNING' or 'INFO'
    message: str
    context: str | None = None

    def format(self) -> str:
        """Format the issue for human-readable output."""
        context_info = f" ({self.context})" if self.context else ""
        return f"{self.severity}: {self.message}{context_info}"


def check_python_command_structure(content: str) -> tuple[int, List[str]]:
    """Check for proper command structure in Python scripts.

    Returns:
        Tuple of (structure_score, list_of_found_patterns)
    """
    patterns_found = []
    score = 0

    # Main execution block
    if re.search(r'if\s+__name__\s*==\s*["\']__main__["\']', content):
        patterns_found.append("Proper main execution block")
        score += 3

    # Argument parsing
    if re.search(r'argparse\.ArgumentParser', content):
        patterns_found.append("Using argparse for CLI")
        score += 2
    elif re.search(r'import\s+sys.*sys\.argv', content, re.DOTALL):
        patterns_found.append("Manual argument parsing")
        score += 1

    # Main function
    if re.search(r'def\s+main\s*\(', content):
        patterns_found.append("Main function defined")
        score += 2

    # Function organization (multiple functions suggest good structure)
    func_count = len(re.findall(r'def\s+\w+\s*\(', content))
    if func_count >= 5:
        patterns_found.append(f"Well-organized with {func_count} functions")
        score += 2
    elif func_count >= 3:
        patterns_found.append(f"Organized with {func_count} functions")
        score += 1

    # Import statements
    if re.search(r'^import\s+|^from\s+\w+\s+import', content, re.MULTILINE):
        patterns_found.append("Proper import statements")
        score += 1

    # Subprocess/command execution (typical for wrappers)
    if re.search(r'subprocess\.(run|call|Popen)', content):
        patterns_found.append("Uses subprocess for command execution")
        score += 1

    # Class-based organization (optional but good)
    if re.search(r'class\s+\w+', content):
        patterns_found.append("Class-based organization")
        score += 1

    return score, patterns_found


def check_bash_command_structure(content: str) -> tuple[int, List[str]]:
    """Check for proper command structure in Bash scripts.

    Returns:
        Tuple of (structure_score, list_of_found_patterns)
    """
    patterns_found = []
    score = 0

    # Proper shebang
    lines = content.split('\n')
    if lines and lines[0].strip() in ['#!/bin/bash', '#!/usr/bin/env bash']:
        patterns_found.append("Proper bash shebang")
        score += 1

    # Strict error handling
    if re.search(r'set\s+-[euo]+', content):
        patterns_found.append("Strict error handling (set -e/u/o)")
        score += 2

    # Function definitions (good organization)
    func_count = len(re.findall(r'\w+\s*\(\s*\)\s*\{', content))
    if func_count >= 5:
        patterns_found.append(f"Well-organized with {func_count} functions")
        score += 2
    elif func_count >= 3:
        patterns_found.append(f"Organized with {func_count} functions")
        score += 1

    # Usage/help function
    if re.search(r'(usage|help)\s*\(\s*\)\s*\{', content):
        patterns_found.append("Usage/help function")
        score += 2

    # Proper argument parsing loop
    if re.search(r'while\s+\[\[\s*\$#\s*-gt\s*0\s*\]\]', content):
        patterns_found.append("Proper argument parsing loop")
        score += 2
    elif re.search(r'case\s+\$1\s+in', content):
        patterns_found.append("Case-based argument parsing")
        score += 1

    # Main execution section
    if re.search(r'#.*[Mm]ain|#.*[Ee]xecution', content):
        patterns_found.append("Clearly marked main section")
        score += 1

    return score, patterns_found


def check_r_command_structure(content: str) -> tuple[int, List[str]]:
    """Check for proper command structure in R scripts.

    Returns:
        Tuple of (structure_score, list_of_found_patterns)
    """
    patterns_found = []
    score = 0

    # Proper shebang
    lines = content.split('\n')
    if lines and 'rscript' in lines[0].lower():
        patterns_found.append("Proper Rscript shebang")
        score += 1

    # Using optparse library
    if re.search(r'library\s*\(\s*optparse\s*\)', content):
        patterns_found.append("Using optparse for CLI")
        score += 3
    elif re.search(r'commandArgs\s*\(', content):
        patterns_found.append("Manual argument parsing")
        score += 1

    # OptionParser setup
    if re.search(r'OptionParser\s*\(', content):
        patterns_found.append("OptionParser configured")
        score += 2

    # Function definitions (good organization)
    func_count = len(re.findall(r'\w+\s*<-\s*function\s*\(', content))
    if func_count >= 5:
        patterns_found.append(f"Well-organized with {func_count} functions")
        score += 2
    elif func_count >= 3:
        patterns_found.append(f"Organized with {func_count} functions")
        score += 1

    # Main execution function
    if re.search(r'(main|run_analysis)\s*<-\s*function', content):
        patterns_found.append("Main execution function")
        score += 2

    # Library loading with suppressPackageStartupMessages
    if re.search(r'suppressPackageStartupMessages', content):
        patterns_found.append("Clean library loading")
        score += 1

    # tryCatch for main execution
    if re.search(r'tryCatch\s*\(\s*\{', content):
        patterns_found.append("Main execution in tryCatch")
        score += 1

    return score, patterns_found


def run_test(script_path: str, shared_context: dict) -> List[LintIssue]:
    """
    Test wrapper script command structure.

    This test checks if the script follows proper organizational patterns
    and command-line interface conventions for GenePattern modules.

    Args:
        script_path: Path to wrapper script file
        shared_context: Mutable dict with test context including script_content and script_type

    Returns:
        List of LintIssue objects for command structure assessment
    """
    issues: List[LintIssue] = []

    # Get script content and type from previous tests
    script_content = shared_context.get('script_content')
    script_type = shared_context.get('script_type')

    if script_content is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate command structure: script content not available",
            "File validation must pass before command structure check"
        ))
        return issues

    if script_type is None:
        issues.append(LintIssue(
            "WARNING",
            "Cannot determine script type for command structure check"
        ))
        return issues

    # Check for command structure patterns based on script type
    score = 0
    patterns_found = []

    if script_type == 'python':
        score, patterns_found = check_python_command_structure(script_content)
    elif script_type == 'bash':
        score, patterns_found = check_bash_command_structure(script_content)
    elif script_type == 'r':
        score, patterns_found = check_r_command_structure(script_content)
    else:
        # Generic check for any script type
        generic_patterns = [
            (r'def\s+\w+|function\s+\w+|\w+\s*\(\s*\)', "Function definitions"),
            (r'#!', "Shebang line"),
        ]
        for pattern, desc in generic_patterns:
            if re.search(pattern, script_content):
                patterns_found.append(desc)
                score += 1

    # Store command structure info in context
    shared_context['command_structure_score'] = score
    shared_context['command_structure_patterns'] = patterns_found

    # Report findings based on score
    if score >= 8:
        issues.append(LintIssue(
            "INFO",
            f"Excellent command structure (score: {score}, {len(patterns_found)} pattern(s) found)"
        ))
    elif score >= 5:
        issues.append(LintIssue(
            "INFO",
            f"Good command structure (score: {score}, {len(patterns_found)} pattern(s) found)"
        ))
    elif score >= 2:
        issues.append(LintIssue(
            "WARNING",
            f"Basic command structure (score: {score}, {len(patterns_found)} pattern(s) found)",
            "Consider improving organization (main function, proper CLI parsing, function decomposition)"
        ))
    else:
        issues.append(LintIssue(
            "WARNING",
            "Poor command structure detected",
            "Improve script organization for better maintainability"
        ))

    return issues

