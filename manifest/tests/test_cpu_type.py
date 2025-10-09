#!/usr/bin/env python
"""
Test for CPU type field validation.

This test ensures that the cpuType field, if present, contains a valid value.
"""
from __future__ import annotations

import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Valid CPU types
VALID_CPU_TYPES = {"any", "Intel", "PowerPC", "Alpha"}


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test CPU type validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any CPU type violations
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

        # Check cpuType field
        if key == "cpuType":
            if value not in VALID_CPU_TYPES:
                issues.append(LintIssue(
                    "WARNING",
                    f"Unusual CPU type '{value}'. Expected one of: {sorted(VALID_CPU_TYPES)}",
                    idx,
                    line,
                ))

    return issues

