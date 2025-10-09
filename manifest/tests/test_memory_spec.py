#!/usr/bin/env python
"""
Test for memory specification validation.

This test ensures that the job.memory field, if present, follows
a reasonable format (e.g., 8Gb, 4Mb, etc.).
"""
from __future__ import annotations

import re
import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Regex for memory format (number followed by unit: Gb, Mb, etc.)
MEMORY_REGEX = re.compile(r'^\d+(\.\d+)?(Gb|Mb|Kb|G|M|K|gb|mb|kb)$', re.IGNORECASE)


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test memory specification validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any memory specification violations
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

        # Check job.memory field
        if key == "job.memory" and value:
            if not MEMORY_REGEX.match(value):
                issues.append(LintIssue(
                    "WARNING",
                    f"Memory specification '{value}' may not follow standard format. Expected format: <number><unit> (e.g., 8Gb, 4Mb)",
                    idx,
                    line,
                ))

    return issues

