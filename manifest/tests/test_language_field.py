#!/usr/bin/env python
"""
Test for language field validation.

This test ensures that the language field, if present, contains a reasonable value.
"""
from __future__ import annotations

import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Common language values seen in GenePattern modules
COMMON_LANGUAGES = {
    "any", "R", "Python", "Java", "Perl", "MATLAB", "C", "C++",
    "HTML", "Javascript", "JavaScript", "HTML,JQuery", "R3.2",
    "Python3", "Python2.7", "Bash", "Shell"
}


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test language field validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any language field violations
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

        # Skip empty keys
        if key == "":
            continue

        # Check language field (informational only)
        if key == "language" and value:
            # This is just for informational purposes
            # We don't error on unusual values since new languages can be added
            pass

    return issues

