#!/usr/bin/env python
"""
Test for basic key=value format validation.

This test ensures that each non-empty, non-comment line in the manifest
follows the key=value format where value may be empty.
"""
from __future__ import annotations

import re
import sys
import os
from typing import List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Regex for valid keys (no whitespace, no =, :, or # characters)
KEY_VALID_REGEX = re.compile(r"^[^\s=:#][^=:#]*$")


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test basic key=value format validation.
    
    Args:
        lines: List of lines from the manifest file
        
    Returns:
        List of LintIssue objects for any validation failures
    """
    issues: List[LintIssue] = []
    in_continuation = False

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        
        # Skip empty lines and comments
        if stripped == "" or stripped.startswith("#") or stripped.startswith("!"):
            continue

        # Check if this line is a continuation of a previous line
        if in_continuation:
            # This is a continuation line, it doesn't need '='
            # Check if this line also ends with a continuation character
            in_continuation = line.rstrip().endswith("\\")
            continue

        # Check for basic key=value format
        if "=" not in line:
            issues.append(LintIssue(
                "ERROR",
                "Expected key=value format with '=' separator",
                idx,
                line,
            ))
            continue
            
        # Extract key and validate it
        key, value = line.split("=", 1)
        key = key.strip()
        
        if key == "":
            issues.append(LintIssue(
                "ERROR",
                "Empty key before '=' is not allowed",
                idx,
                line,
            ))
            continue
            
        if not KEY_VALID_REGEX.match(key):
            issues.append(LintIssue(
                "ERROR",
                "Invalid key: keys must not contain whitespace or the characters '=' ':' '#'",
                idx,
                line,
            ))
            continue

        # Check if this line ends with a continuation character
        in_continuation = line.rstrip().endswith("\\")

    return issues
