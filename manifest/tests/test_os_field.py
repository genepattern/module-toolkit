#!/usr/bin/env python
"""
Test for OS field validation.

This test ensures that the os field, if present, contains a valid value.
"""
from __future__ import annotations

import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Valid OS types
VALID_OS_TYPES = {"any", "Linux", "Windows", "Mac", "Unix", "Solaris"}


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test OS field validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any OS field violations
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

        # Check os field
        if key == "os":
            if value not in VALID_OS_TYPES:
                issues.append(LintIssue(
                    "WARNING",
                    f"Unusual OS value '{value}'. Expected one of: {sorted(VALID_OS_TYPES)}",
                    idx,
                    line,
                ))

    return issues

