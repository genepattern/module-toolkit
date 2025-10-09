#!/usr/bin/env python
"""
Test for author field validation.

This test ensures that the author field, if present, follows reasonable format.
"""
from __future__ import annotations

import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test author field validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any author field violations
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

        # Check author field (informational only)
        if key == "author" and not value:
            issues.append(LintIssue(
                "WARNING",
                "Author field is present but empty. Consider providing author information",
                idx,
                line,
            ))

    return issues

