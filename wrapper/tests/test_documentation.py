#!/usr/bin/env python
"""
Test for wrapper script documentation quality.

This test checks that the wrapper script includes appropriate documentation,
including docstrings, comments, help text, and usage information.
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


def check_python_documentation(content: str) -> tuple[int, List[str]]:
    """Check for documentation patterns in Python scripts.

    Returns:
        Tuple of (documentation_score, list_of_found_patterns)
    """
    patterns_found = []
    score = 0

    # Module-level docstring
    if re.search(r'^[\s]*["\'{3}]', content, re.MULTILINE):
        patterns_found.append("Module-level docstring")
        score += 2

    # Function docstrings
    func_with_docs = len(re.findall(r'def\s+\w+\s*\([^)]*\)\s*:\s*["\'{3}]', content))
    if func_with_docs > 0:
        patterns_found.append(f"Function docstrings ({func_with_docs} found)")
        score += min(func_with_docs, 3)  # Cap at 3 points

    # Inline comments
    comment_count = len(re.findall(r'^\s*#[^!]', content, re.MULTILINE))
    if comment_count > 5:
        patterns_found.append(f"Inline comments ({comment_count} found)")
        score += 2
    elif comment_count > 0:
        patterns_found.append(f"Some inline comments ({comment_count} found)")
        score += 1

    # Help text in argparse
    if re.search(r'help\s*=\s*["\']', content):
        patterns_found.append("Argument help text")
        score += 2

    # Description in argparse
    if re.search(r'description\s*=\s*["\']', content):
        patterns_found.append("Script description")
        score += 1

    # Usage examples
    if re.search(r'(usage|example|Usage|Example|USAGE|EXAMPLE)', content):
        patterns_found.append("Usage examples or instructions")
        score += 1

    return score, patterns_found


def check_bash_documentation(content: str) -> tuple[int, List[str]]:
    """Check for documentation patterns in Bash scripts.

    Returns:
        Tuple of (documentation_score, list_of_found_patterns)
    """
    patterns_found = []
    score = 0

    # Header comments
    header_comments = len(re.findall(r'^#[^!].*', content[:500], re.MULTILINE))
    if header_comments > 3:
        patterns_found.append(f"Header documentation ({header_comments} lines)")
        score += 2
    elif header_comments > 0:
        patterns_found.append(f"Some header comments ({header_comments} lines)")
        score += 1

    # Usage function
    if re.search(r'(usage|help)\s*\(\s*\)\s*\{', content):
        patterns_found.append("Usage/help function")
        score += 3

    # Function comments
    func_comments = len(re.findall(r'#.*\n\s*\w+\s*\(\s*\)\s*\{', content))
    if func_comments > 0:
        patterns_found.append(f"Function comments ({func_comments} found)")
        score += 2

    # Inline comments
    comment_count = len(re.findall(r'^\s*#[^!]', content, re.MULTILINE))
    if comment_count > 10:
        patterns_found.append(f"Inline comments ({comment_count} found)")
        score += 2
    elif comment_count > 5:
        patterns_found.append(f"Some inline comments ({comment_count} found)")
        score += 1

    # Parameter descriptions in usage
    if re.search(r'echo.*--\w+.*#', content):
        patterns_found.append("Parameter descriptions in help")
        score += 1

    return score, patterns_found


def check_r_documentation(content: str) -> tuple[int, List[str]]:
    """Check for documentation patterns in R scripts.

    Returns:
        Tuple of (documentation_score, list_of_found_patterns)
    """
    patterns_found = []
    score = 0

    # Header comments
    header_comments = len(re.findall(r'^#[^!].*', content[:500], re.MULTILINE))
    if header_comments > 3:
        patterns_found.append(f"Header documentation ({header_comments} lines)")
        score += 2
    elif header_comments > 0:
        patterns_found.append(f"Some header comments ({header_comments} lines)")
        score += 1

    # Function documentation
    func_docs = len(re.findall(r'#\'.*\n\s*\w+\s*<-\s*function', content))
    if func_docs > 0:
        patterns_found.append(f"Roxygen-style function docs ({func_docs} found)")
        score += 3

    # Regular function comments
    func_comments = len(re.findall(r'#.*\n\s*\w+\s*<-\s*function', content))
    if func_comments > func_docs:
        patterns_found.append(f"Function comments ({func_comments} found)")
        score += 2

    # Option descriptions in optparse
    if re.search(r'help\s*=\s*["\']', content):
        patterns_found.append("Parameter help text")
        score += 2

    # Script description
    if re.search(r'description\s*=\s*["\']', content):
        patterns_found.append("Script description")
        score += 1

    # Inline comments
    comment_count = len(re.findall(r'^\s*#[^!]', content, re.MULTILINE))
    if comment_count > 10:
        patterns_found.append(f"Inline comments ({comment_count} found)")
        score += 2
    elif comment_count > 5:
        patterns_found.append(f"Some inline comments ({comment_count} found)")
        score += 1

    return score, patterns_found


def run_test(script_path: str, shared_context: dict) -> List[LintIssue]:
    """
    Test wrapper script documentation quality.

    This test checks if the script includes appropriate documentation
    to help users and maintainers understand its purpose and usage.

    Args:
        script_path: Path to wrapper script file
        shared_context: Mutable dict with test context including script_content and script_type

    Returns:
        List of LintIssue objects for documentation quality assessment
    """
    issues: List[LintIssue] = []

    # Get script content and type from previous tests
    script_content = shared_context.get('script_content')
    script_type = shared_context.get('script_type')

    if script_content is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate documentation: script content not available",
            "File validation must pass before documentation check"
        ))
        return issues

    if script_type is None:
        issues.append(LintIssue(
            "WARNING",
            "Cannot determine script type for documentation check"
        ))
        return issues

    # Check for documentation patterns based on script type
    score = 0
    patterns_found = []

    if script_type == 'python':
        score, patterns_found = check_python_documentation(script_content)
    elif script_type == 'bash':
        score, patterns_found = check_bash_documentation(script_content)
    elif script_type == 'r':
        score, patterns_found = check_r_documentation(script_content)
    else:
        # Generic check for any script type
        comment_count = len(re.findall(r'^\s*#', script_content, re.MULTILINE))
        if comment_count > 10:
            patterns_found.append(f"Comments ({comment_count} found)")
            score += 3
        elif comment_count > 5:
            patterns_found.append(f"Some comments ({comment_count} found)")
            score += 2
        elif comment_count > 0:
            patterns_found.append(f"Minimal comments ({comment_count} found)")
            score += 1

    # Store documentation info in context
    shared_context['documentation_score'] = score
    shared_context['documentation_patterns'] = patterns_found

    # Report findings based on score
    if score >= 8:
        issues.append(LintIssue(
            "INFO",
            f"Well-documented script (score: {score}, {len(patterns_found)} pattern(s) found)"
        ))
    elif score >= 5:
        issues.append(LintIssue(
            "INFO",
            f"Adequately documented script (score: {score}, {len(patterns_found)} pattern(s) found)"
        ))
    elif score >= 2:
        issues.append(LintIssue(
            "WARNING",
            f"Minimally documented script (score: {score}, {len(patterns_found)} pattern(s) found)",
            "Consider adding more documentation (docstrings, comments, help text)"
        ))
    else:
        issues.append(LintIssue(
            "WARNING",
            "Poorly documented script",
            "Add documentation to help users understand the script's purpose and usage"
        ))

    return issues

