#!/usr/bin/env python
"""
Test for file format field validation.

This test ensures that fileFormat fields contain valid file extensions
without leading dots and are properly formatted.
"""
from __future__ import annotations

import re
import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Regex for valid file format (semicolon-separated extensions, no leading dots)
FILE_FORMAT_REGEX = re.compile(r'^[a-zA-Z0-9]+(;[a-zA-Z0-9]+)*$')


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test file format field validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any file format violations
    """
    issues: List[LintIssue] = []

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        # Skip empty lines and comments
        if stripped == "" or stripped.startswith("#") or stripped.startswith("!"):
            continue

        # Skip lines that don't have = separator
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Skip empty keys or empty values
        if key == "" or value == "":
            continue

        # Check fileFormat field (both top-level and parameter-level)
        if key == "fileFormat" or key.endswith("_fileFormat"):
            # Split by semicolon and check each format individually
            formats = [f.strip() for f in value.split(';')]

            # Check for leading dots in any format
            leading_dot_formats = [f for f in formats if f.startswith('.')]
            if leading_dot_formats:
                issues.append(LintIssue(
                    "WARNING",
                    f"File format(s) {leading_dot_formats} have leading dots. File extensions should not include leading dots (e.g., use 'txt' not '.txt')",
                    idx,
                    line,
                ))

            # Check for spaces which should not be present
            if " " in value and ";" not in value:
                issues.append(LintIssue(
                    "WARNING",
                    f"File format '{value}' contains spaces. Use semicolons to separate multiple formats",
                    idx,
                    line,
                ))

    return issues
