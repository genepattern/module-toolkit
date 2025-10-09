#!/usr/bin/env python
"""
Test for command line field validation.

This test ensures that the commandLine field is present and non-empty,
and checks for common issues in command line syntax.
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
    Test command line field validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any command line violations
    """
    issues: List[LintIssue] = []
    commandline_found = False
    commandline_value = ""
    commandline_line_no = 0
    commandline_line_text = ""

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

        # Check for commandLine field
        if key == "commandLine":
            commandline_found = True
            commandline_value = value
            commandline_line_no = idx
            commandline_line_text = line

    # Validate commandLine
    if commandline_found:
        # Check if commandLine is empty (this is also caught by required_keys but we can be more specific)
        if not commandline_value:
            issues.append(LintIssue(
                "ERROR",
                "commandLine field is present but empty",
                commandline_line_no,
                commandline_line_text,
            ))
        else:
            # Check for potential issues in commandLine
            # Look for parameter references like <param.name>
            if "<" in commandline_value and ">" in commandline_value:
                # This is expected - parameters are referenced with < >
                pass
            elif commandline_value and not any(c in commandline_value for c in ["<", ">", " "]):
                # CommandLine exists but has no parameters and no spaces - might be wrong
                issues.append(LintIssue(
                    "WARNING",
                    "commandLine does not contain any parameter references (<param.name>) or spaces. This may be incorrect.",
                    commandline_line_no,
                    commandline_line_text,
                ))

    return issues

