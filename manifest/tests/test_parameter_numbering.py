#!/usr/bin/env python
"""
Test for parameter numbering validation.

This test ensures that parameters are numbered sequentially starting from p1,
and that there are no gaps in the numbering sequence.
"""
from __future__ import annotations

import re
import sys
import os
from typing import List, Set

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Regex to match parameter keys (e.g., p1_name, p10_TYPE, etc.)
PARAM_KEY_REGEX = re.compile(r"^p(\d+)_")


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test parameter numbering validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any parameter numbering violations
    """
    issues: List[LintIssue] = []
    param_numbers: Set[int] = set()

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

        # Skip empty keys
        if key == "":
            continue

        # Check if this is a parameter key
        match = PARAM_KEY_REGEX.match(key)
        if match:
            param_num = int(match.group(1))
            param_numbers.add(param_num)

    # If no parameters found, no validation needed
    if not param_numbers:
        return issues

    # Check for sequential numbering starting from 1
    max_param = max(param_numbers)
    expected_params = set(range(1, max_param + 1))
    missing_params = expected_params - param_numbers

    if missing_params:
        issues.append(LintIssue(
            "ERROR",
            f"Parameters are not numbered sequentially. Missing parameter number(s): {sorted(missing_params)}",
            None,
            None,
        ))

    # Check that numbering starts from 1
    if param_numbers and 1 not in param_numbers:
        issues.append(LintIssue(
            "ERROR",
            f"Parameters should start from p1, but first parameter found is p{min(param_numbers)}",
            None,
            None,
        ))

    return issues

