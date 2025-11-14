#!/usr/bin/env python
"""
Test for wrapper script input validation.

This test checks that the wrapper script validates its inputs appropriately,
including file existence checks, format validation, and parameter validation.
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


def check_python_input_validation(content: str) -> tuple[int, List[str]]:
    """Check for input validation patterns in Python scripts.

    Returns:
        Tuple of (validation_score, list_of_found_patterns)
    """
    patterns_found = []
    score = 0

    # File existence checks
    if re.search(r'os\.path\.exists\s*\(', content):
        patterns_found.append("os.path.exists() checking")
        score += 2

    if re.search(r'Path\([^)]+\)\.exists\s*\(', content):
        patterns_found.append("pathlib Path.exists() checking")
        score += 2

    # File type checks
    if re.search(r'os\.path\.isfile\s*\(', content):
        patterns_found.append("os.path.isfile() checking")
        score += 1

    if re.search(r'os\.path\.isdir\s*\(', content):
        patterns_found.append("os.path.isdir() checking")
        score += 1

    # File permissions/readability
    if re.search(r'os\.access\s*\([^)]*os\.R_OK', content):
        patterns_found.append("File readability checking")
        score += 1

    # Required parameter validation
    if re.search(r'required\s*=\s*True', content):
        patterns_found.append("Required parameters defined")
        score += 1

    # Argument validation functions
    if re.search(r'def\s+validate_\w+\s*\(', content):
        patterns_found.append("Validation functions defined")
        score += 2

    # Type validation
    if re.search(r'type\s*=\s*(int|float|str)', content):
        patterns_found.append("Type validation in argparse")
        score += 1

    # Choices validation
    if re.search(r'choices\s*=\s*\[', content):
        patterns_found.append("Choice validation in argparse")
        score += 1

    # File format validation
    if re.search(r'\.endswith\s*\(', content):
        patterns_found.append("File extension checking")
        score += 1

    # Empty/None checks
    if re.search(r'if\s+not\s+\w+:|if\s+\w+\s+is\s+None', content):
        patterns_found.append("Empty/None value checking")
        score += 1

    # Value range checking
    if re.search(r'if\s+\w+\s*[<>]=?\s*\d+', content):
        patterns_found.append("Value range checking")
        score += 1

    return score, patterns_found


def check_bash_input_validation(content: str) -> tuple[int, List[str]]:
    """Check for input validation patterns in Bash scripts.

    Returns:
        Tuple of (validation_score, list_of_found_patterns)
    """
    patterns_found = []
    score = 0

    # File existence checks
    if re.search(r'\[\s*-[ef]\s+["\$]', content):
        patterns_found.append("File existence checking (-e/-f)")
        score += 2

    # File type checks
    if re.search(r'\[\s*-d\s+["\$]', content):
        patterns_found.append("Directory checking (-d)")
        score += 1

    # File readability
    if re.search(r'\[\s*-r\s+["\$]', content):
        patterns_found.append("File readability checking (-r)")
        score += 1

    # Empty variable checks
    if re.search(r'\[\s*-z\s+["\$]', content):
        patterns_found.append("Empty variable checking (-z)")
        score += 1

    # Required parameter checking
    if re.search(r'if\s+\[\[\s*-z\s+["\$].*\]\].*echo.*required', content, re.IGNORECASE):
        patterns_found.append("Required parameter validation")
        score += 2

    # Usage function
    if re.search(r'(usage|help)\s*\(\s*\)\s*\{', content):
        patterns_found.append("Usage/help function defined")
        score += 1

    # Parameter validation in case statements
    if re.search(r'case\s+\$\d+\s+in', content):
        patterns_found.append("Parameter validation in case statement")
        score += 1

    # Numeric validation
    if re.search(r'\[\[\s*\$\w+\s*=~\s*\^[0-9]', content):
        patterns_found.append("Numeric validation with regex")
        score += 1

    return score, patterns_found


def check_r_input_validation(content: str) -> tuple[int, List[str]]:
    """Check for input validation patterns in R scripts.

    Returns:
        Tuple of (validation_score, list_of_found_patterns)
    """
    patterns_found = []
    score = 0

    # File existence checks
    if re.search(r'file\.exists\s*\(', content):
        patterns_found.append("file.exists() checking")
        score += 2

    # Directory checks
    if re.search(r'dir\.exists\s*\(', content):
        patterns_found.append("dir.exists() checking")
        score += 1

    # NULL/NA checks
    if re.search(r'is\.null\s*\(', content):
        patterns_found.append("is.null() checking")
        score += 1

    if re.search(r'is\.na\s*\(', content):
        patterns_found.append("is.na() checking")
        score += 1

    # stopifnot validation
    if re.search(r'stopifnot\s*\(', content):
        patterns_found.append("stopifnot() assertions")
        score += 2

    # Required parameters in optparse
    if re.search(r'default\s*=\s*NULL', content):
        patterns_found.append("Required parameters (default=NULL)")
        score += 1

    # Type checking
    if re.search(r'is\.(numeric|integer|character|logical)\s*\(', content):
        patterns_found.append("Type validation functions")
        score += 1

    # Validation functions
    if re.search(r'validate\w*\s*<-\s*function', content):
        patterns_found.append("Validation functions defined")
        score += 2

    # File format checks
    if re.search(r'grepl\s*\(["\'].*\\.(csv|txt|tsv)', content):
        patterns_found.append("File format validation")
        score += 1

    # Argument parsing validation
    if re.search(r'if\s*\(\s*is\.null\s*\(\s*args\$\w+\s*\)\s*\)', content):
        patterns_found.append("Argument validation")
        score += 1

    return score, patterns_found


def run_test(script_path: str, shared_context: dict) -> List[LintIssue]:
    """
    Test wrapper script input validation patterns.

    This test checks if the script validates its inputs appropriately,
    which is crucial for robust and user-friendly GenePattern modules.

    Args:
        script_path: Path to wrapper script file
        shared_context: Mutable dict with test context including script_content and script_type

    Returns:
        List of LintIssue objects for input validation assessment
    """
    issues: List[LintIssue] = []

    # Get script content and type from previous tests
    script_content = shared_context.get('script_content')
    script_type = shared_context.get('script_type')

    if script_content is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate input validation: script content not available",
            "File validation must pass before input validation check"
        ))
        return issues

    if script_type is None:
        issues.append(LintIssue(
            "WARNING",
            "Cannot determine script type for input validation check"
        ))
        return issues

    # Check for input validation patterns based on script type
    score = 0
    patterns_found = []

    if script_type == 'python':
        score, patterns_found = check_python_input_validation(script_content)
    elif script_type == 'bash':
        score, patterns_found = check_bash_input_validation(script_content)
    elif script_type == 'r':
        score, patterns_found = check_r_input_validation(script_content)
    else:
        # Generic check for any script type
        generic_patterns = [
            (r'exists', "existence checking"),
            (r'validate|check', "validation/checking"),
            (r'required', "required parameter handling"),
        ]
        for pattern, desc in generic_patterns:
            if re.search(pattern, script_content, re.IGNORECASE):
                patterns_found.append(desc)
                score += 1

    # Store input validation info in context
    shared_context['input_validation_score'] = score
    shared_context['input_validation_patterns'] = patterns_found

    # Report findings based on score
    if score >= 6:
        issues.append(LintIssue(
            "INFO",
            f"Comprehensive input validation detected (score: {score}, {len(patterns_found)} pattern(s) found)"
        ))
    elif score >= 3:
        issues.append(LintIssue(
            "INFO",
            f"Basic input validation detected (score: {score}, {len(patterns_found)} pattern(s) found)"
        ))
    elif score >= 1:
        issues.append(LintIssue(
            "WARNING",
            f"Minimal input validation detected (score: {score}, {len(patterns_found)} pattern(s) found)",
            "Consider adding more input validation (file existence, type checking, required parameters)"
        ))
    else:
        issues.append(LintIssue(
            "WARNING",
            "No input validation patterns detected",
            "Input validation helps prevent errors and provides better user experience"
        ))

    return issues

