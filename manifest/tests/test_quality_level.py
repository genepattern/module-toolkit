#!/usr/bin/env python
"""
Test for quality level validation.

This test ensures that the quality field, if present, contains a valid value.
"""
from __future__ import annotations

import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Valid quality levels
VALID_QUALITY_LEVELS = {"development", "preproduction", "production", "deprecated"}


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test quality level validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any quality level violations
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

        # Check quality field
        if key == "quality":
            if value not in VALID_QUALITY_LEVELS:
                issues.append(LintIssue(
                    "WARNING",
                    f"Unusual quality level '{value}'. Expected one of: {sorted(VALID_QUALITY_LEVELS)}",
                    idx,
                    line,
                ))

    return issues

