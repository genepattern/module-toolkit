#!/usr/bin/env python
"""
Test for JVMLevel field validation.

This test ensures that the JVMLevel field, if present and non-empty,
contains a valid Java version.
"""
from __future__ import annotations

import re
import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Regex for JVM level format (e.g., 1.8, 11, 17, etc.)
JVM_LEVEL_REGEX = re.compile(r'^(\d+\.?\d*|any)$', re.IGNORECASE)


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test JVMLevel field validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any JVMLevel violations
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

        # Check JVMLevel field (only if it has a value)
        if key == "JVMLevel" and value:
            if not JVM_LEVEL_REGEX.match(value):
                issues.append(LintIssue(
                    "WARNING",
                    f"JVMLevel '{value}' does not match expected format (e.g., '1.8', '11', 'any')",
                    idx,
                    line,
                ))

    return issues

