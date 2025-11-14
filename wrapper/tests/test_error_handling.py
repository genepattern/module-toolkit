#!/usr/bin/env python
"""
Test for wrapper script error handling validation.

This test checks that the wrapper script includes appropriate error handling
mechanisms such as try-catch blocks, error checking, and proper exit codes.
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


def check_python_error_handling(content: str) -> tuple[int, List[str]]:
    """Check for error handling patterns in Python scripts.

    Returns:
        Tuple of (error_handling_score, list_of_found_patterns)
    """
    patterns_found = []
    score = 0

    # Try-except blocks
    if re.search(r'\btry\s*:', content):
        patterns_found.append("try-except block")
        score += 2

    # Exception handling
    if re.search(r'\bexcept\s+\w+', content):
        patterns_found.append("Specific exception catching")
        score += 1

    # Exit code handling
    if re.search(r'sys\.exit\s*\(', content):
        patterns_found.append("sys.exit() usage")
        score += 1

    # Raising exceptions
    if re.search(r'\braise\s+\w+', content):
        patterns_found.append("Raising exceptions")
        score += 1

    # Logging errors
    if re.search(r'logging\.(error|warning|exception)', content, re.IGNORECASE):
        patterns_found.append("Error logging")
        score += 1

    # Error messages to stderr
    if re.search(r'sys\.stderr\.write', content):
        patterns_found.append("Writing to stderr")
        score += 1

    # File/path validation
    if re.search(r'os\.path\.exists|Path\([^)]+\)\.exists', content):
        patterns_found.append("File existence checking")
        score += 1

    # Subprocess error checking
    if re.search(r'subprocess\.run\([^)]*check\s*=\s*True', content):
        patterns_found.append("Subprocess error checking (check=True)")
        score += 1

    if re.search(r'subprocess\.CalledProcessError', content):
        patterns_found.append("Subprocess error handling")
        score += 1

    # Assert statements (can be basic error checking)
    if re.search(r'\bassert\s+', content):
        patterns_found.append("Assert statements")
        score += 0.5

    return score, patterns_found


def check_bash_error_handling(content: str) -> tuple[int, List[str]]:
    """Check for error handling patterns in Bash scripts.

    Returns:
        Tuple of (error_handling_score, list_of_found_patterns)
    """
    patterns_found = []
    score = 0

    # Exit on error
    if re.search(r'set\s+-e', content):
        patterns_found.append("set -e (exit on error)")
        score += 2

    # Pipefail
    if re.search(r'set\s+-o\s+pipefail', content):
        patterns_found.append("set -o pipefail")
        score += 1

    # Exit code checking
    if re.search(r'\$\?', content):
        patterns_found.append("Exit code checking ($?)")
        score += 1

    # Conditional error checking
    if re.search(r'if\s+\[\s*\$\?\s*-ne\s*0', content):
        patterns_found.append("Explicit exit code checking")
        score += 1

    # File existence checks
    if re.search(r'\[\s*-[ef]\s+', content):
        patterns_found.append("File existence checking (-e/-f)")
        score += 1

    # Error messages to stderr
    if re.search(r'>&2|1>&2', content):
        patterns_found.append("Redirecting to stderr")
        score += 1

    # Error trap
    if re.search(r'trap\s+', content):
        patterns_found.append("Error trap handling")
        score += 2

    # Explicit exit statements
    if re.search(r'\bexit\s+[1-9]', content):
        patterns_found.append("Non-zero exit codes")
        score += 1

    # Die/error functions
    if re.search(r'(die|error|fail)\s*\(\s*\)', content):
        patterns_found.append("Error handling function")
        score += 1

    return score, patterns_found


def check_r_error_handling(content: str) -> tuple[int, List[str]]:
    """Check for error handling patterns in R scripts.

    Returns:
        Tuple of (error_handling_score, list_of_found_patterns)
    """
    patterns_found = []
    score = 0

    # tryCatch blocks
    if re.search(r'tryCatch\s*\(', content):
        patterns_found.append("tryCatch block")
        score += 2

    # try blocks
    if re.search(r'\btry\s*\(', content):
        patterns_found.append("try() block")
        score += 1

    # Error handlers
    if re.search(r'error\s*=\s*function', content):
        patterns_found.append("Error handling function")
        score += 1

    # Warning handlers
    if re.search(r'warning\s*=\s*function', content):
        patterns_found.append("Warning handling function")
        score += 1

    # Stop on error
    if re.search(r'\bstop\s*\(', content):
        patterns_found.append("stop() calls")
        score += 1

    # Warnings
    if re.search(r'\bwarning\s*\(', content):
        patterns_found.append("warning() calls")
        score += 0.5

    # quit/q with status
    if re.search(r'quit\s*\(\s*status\s*=', content):
        patterns_found.append("quit() with status code")
        score += 1

    # File existence checks
    if re.search(r'file\.exists\s*\(', content):
        patterns_found.append("file.exists() checking")
        score += 1

    # stopifnot
    if re.search(r'\bstopifnot\s*\(', content):
        patterns_found.append("stopifnot() assertions")
        score += 1

    # Message/cat for errors
    if re.search(r'cat\s*\(\s*["\']Error', content, re.IGNORECASE):
        patterns_found.append("Error messages")
        score += 0.5

    return score, patterns_found


def run_test(script_path: str, shared_context: dict) -> List[LintIssue]:
    """
    Test wrapper script error handling patterns.

    This test checks if the script includes appropriate error handling
    mechanisms, which is crucial for robust GenePattern modules.

    Args:
        script_path: Path to wrapper script file
        shared_context: Mutable dict with test context including script_content and script_type

    Returns:
        List of LintIssue objects for error handling validation
    """
    issues: List[LintIssue] = []

    # Get script content and type from previous tests
    script_content = shared_context.get('script_content')
    script_type = shared_context.get('script_type')

    if script_content is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate error handling: script content not available",
            "File validation must pass before error handling validation"
        ))
        return issues

    if script_type is None:
        issues.append(LintIssue(
            "WARNING",
            "Cannot determine script type for error handling validation"
        ))
        return issues

    # Check for error handling patterns based on script type
    score = 0
    patterns_found = []

    if script_type == 'python':
        score, patterns_found = check_python_error_handling(script_content)
    elif script_type == 'bash':
        score, patterns_found = check_bash_error_handling(script_content)
    elif script_type == 'r':
        score, patterns_found = check_r_error_handling(script_content)
    else:
        # Generic check for any script type
        generic_patterns = [
            (r'\btry\b', "try statement"),
            (r'\bcatch\b', "catch statement"),
            (r'\berror\b', "error handling"),
            (r'\bexit\s+[1-9]', "non-zero exit"),
        ]
        for pattern, desc in generic_patterns:
            if re.search(pattern, script_content, re.IGNORECASE):
                patterns_found.append(desc)
                score += 1

    # Store error handling info in context
    shared_context['error_handling_score'] = score
    shared_context['error_handling_patterns'] = patterns_found

    # Report findings based on score
    if score >= 5:
        issues.append(LintIssue(
            "INFO",
            f"Good error handling detected (score: {score}, {len(patterns_found)} pattern(s) found)"
        ))
    elif score >= 3:
        issues.append(LintIssue(
            "INFO",
            f"Basic error handling detected (score: {score}, {len(patterns_found)} pattern(s) found)"
        ))
    elif score >= 1:
        issues.append(LintIssue(
            "WARNING",
            f"Minimal error handling detected (score: {score}, {len(patterns_found)} pattern(s) found)",
            "Consider adding more comprehensive error handling (try-catch, input validation, exit codes)"
        ))
    else:
        issues.append(LintIssue(
            "WARNING",
            "No error handling patterns detected",
            "Robust error handling is important for production GenePattern modules"
        ))

    return issues

