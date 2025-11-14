#!/usr/bin/env python
"""
Test for wrapper script output generation validation.

This test checks that the wrapper script appears to generate output files
as expected based on the parameters and script content.
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


def check_python_output_patterns(content: str) -> tuple[bool, List[str]]:
    """Check for output generation patterns in Python scripts.

    Returns:
        Tuple of (has_output_generation, list_of_found_patterns)
    """
    patterns_found = []

    # File writing patterns
    file_write_patterns = [
        r'open\([^)]*["\']w["\']',  # open(file, 'w')
        r'\.write\(',  # file.write()
        r'\.to_csv\(',  # pandas DataFrame.to_csv()
        r'\.to_excel\(',  # pandas DataFrame.to_excel()
        r'\.savefig\(',  # matplotlib savefig()
        r'\.save\(',  # Various save methods
        r'pickle\.dump\(',  # Pickle dump
        r'json\.dump\(',  # JSON dump
        r'numpy\.save\(',  # Numpy save
        r'with\s+open\([^)]*["\']w',  # with open context manager
        r'pathlib\.Path\([^)]*\.write_',  # Pathlib write operations
    ]

    for pattern in file_write_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            patterns_found.append(f"Python output pattern: {pattern}")

    # Check for output-related variables
    output_vars = [
        r'output[_\.]?file',
        r'out[_\.]?file',
        r'result[_\.]?file',
        r'output[_\.]?path',
        r'out[_\.]?dir',
    ]

    for var_pattern in output_vars:
        if re.search(var_pattern, content, re.IGNORECASE):
            patterns_found.append(f"Output variable: {var_pattern}")

    return len(patterns_found) > 0, patterns_found


def check_bash_output_patterns(content: str) -> tuple[bool, List[str]]:
    """Check for output generation patterns in Bash scripts.

    Returns:
        Tuple of (has_output_generation, list_of_found_patterns)
    """
    patterns_found = []

    # Bash output redirection patterns
    output_patterns = [
        r'>\s*["\$]',  # Output redirection: > $file or > "file"
        r'>>\s*["\$]',  # Append redirection: >> $file
        r'\|\s*tee\s+',  # Tee command
        r'cat\s+.*>\s*',  # Cat with redirection
        r'echo\s+.*>\s*',  # Echo with redirection
        r'printf\s+.*>\s*',  # Printf with redirection
        r'\s+-o\s+',  # -o output flag
        r'\s+--output\s+',  # --output flag
        r'\s+--out\s+',  # --out flag
    ]

    for pattern in output_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            patterns_found.append(f"Bash output pattern: {pattern}")

    # Check for output-related variables
    output_vars = [
        r'output[_]?file',
        r'out[_]?file',
        r'result[_]?file',
        r'output[_]?dir',
    ]

    for var_pattern in output_vars:
        if re.search(var_pattern, content, re.IGNORECASE):
            patterns_found.append(f"Output variable: {var_pattern}")

    return len(patterns_found) > 0, patterns_found


def check_r_output_patterns(content: str) -> tuple[bool, List[str]]:
    """Check for output generation patterns in R scripts.

    Returns:
        Tuple of (has_output_generation, list_of_found_patterns)
    """
    patterns_found = []

    # R output patterns
    output_patterns = [
        r'write\.',  # write.table, write.csv, etc.
        r'save\(',  # save()
        r'saveRDS\(',  # saveRDS()
        r'ggsave\(',  # ggplot2 ggsave()
        r'pdf\(',  # PDF device
        r'png\(',  # PNG device
        r'jpeg\(',  # JPEG device
        r'svg\(',  # SVG device
        r'sink\(',  # Sink output
        r'cat\(.*file\s*=',  # cat() with file argument
        r'writeLines\(',  # writeLines()
        r'write\(',  # write()
    ]

    for pattern in output_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            patterns_found.append(f"R output pattern: {pattern}")

    # Check for output-related variables
    output_vars = [
        r'output[._]?file',
        r'out[._]?file',
        r'result[._]?file',
        r'output[._]?path',
    ]

    for var_pattern in output_vars:
        if re.search(var_pattern, content, re.IGNORECASE):
            patterns_found.append(f"Output variable: {var_pattern}")

    return len(patterns_found) > 0, patterns_found


def run_test(script_path: str, shared_context: dict) -> List[LintIssue]:
    """
    Test wrapper script output generation patterns.

    This test checks if the script appears to generate output files,
    which is essential for GenePattern modules.

    Args:
        script_path: Path to wrapper script file
        shared_context: Mutable dict with test context including script_content and script_type

    Returns:
        List of LintIssue objects for output generation validation
    """
    issues: List[LintIssue] = []

    # Get script content and type from previous tests
    script_content = shared_context.get('script_content')
    script_type = shared_context.get('script_type')

    if script_content is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate output generation: script content not available",
            "File validation must pass before output generation validation"
        ))
        return issues

    if script_type is None:
        issues.append(LintIssue(
            "WARNING",
            "Cannot determine script type for output generation validation"
        ))
        return issues

    # Check for output generation patterns based on script type
    has_output = False
    patterns_found = []

    if script_type == 'python':
        has_output, patterns_found = check_python_output_patterns(script_content)
    elif script_type == 'bash':
        has_output, patterns_found = check_bash_output_patterns(script_content)
    elif script_type == 'r':
        has_output, patterns_found = check_r_output_patterns(script_content)
    else:
        # Generic check for any script type
        generic_patterns = [
            r'>\s*["\$]',  # Output redirection
            r'write',  # Write operations
            r'save',  # Save operations
            r'output',  # Output mentions
        ]
        for pattern in generic_patterns:
            if re.search(pattern, script_content, re.IGNORECASE):
                patterns_found.append(f"Generic output pattern: {pattern}")
        has_output = len(patterns_found) > 0

    # Report findings
    if has_output:
        issues.append(LintIssue(
            "INFO",
            f"Script appears to generate output ({len(patterns_found)} pattern(s) found)"
        ))

        # Store output patterns in context for potential use by other tests
        shared_context['output_patterns'] = patterns_found
    else:
        issues.append(LintIssue(
            "WARNING",
            "No obvious output generation patterns found in script",
            "GenePattern modules typically generate output files. Verify the script produces expected outputs."
        ))

    return issues

