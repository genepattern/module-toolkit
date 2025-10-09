#!/usr/bin/env python
"""
Test for description field validation.

This test ensures that the description field, if present, is non-empty.
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
    Test description field validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any description field violations
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

        # Check description field
        if key == "description" and not value:
            issues.append(LintIssue(
                "WARNING",
                "Description field is present but empty. Consider providing a description",
                idx,
                line,
            ))

    return issues

