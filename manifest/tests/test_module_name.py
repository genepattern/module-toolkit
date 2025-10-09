#!/usr/bin/env python
"""
Test for module name validation.

This test ensures that the name field is present, non-empty, and follows
reasonable naming conventions.
"""
from __future__ import annotations

import re
import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Regex for valid module names (alphanumeric, dots, underscores, hyphens)
MODULE_NAME_REGEX = re.compile(r'^[a-zA-Z0-9._-]+$')


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test module name validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any name field violations
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

        # Check name field
        if key == "name":
            if not value:
                issues.append(LintIssue(
                    "ERROR",
                    "Module name field is present but empty",
                    idx,
                    line,
                ))
            elif not MODULE_NAME_REGEX.match(value):
                issues.append(LintIssue(
                    "WARNING",
                    f"Module name '{value}' contains unusual characters. Recommended to use only alphanumeric, dots, underscores, and hyphens",
                    idx,
                    line,
                ))
            elif value.startswith(".") or value.endswith("."):
                issues.append(LintIssue(
                    "WARNING",
                    f"Module name '{value}' starts or ends with a dot, which is unusual",
                    idx,
                    line,
                ))

    return issues

