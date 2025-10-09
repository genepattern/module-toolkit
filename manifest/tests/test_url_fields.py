#!/usr/bin/env python
"""
Test for URL field validation.

This test ensures that URL fields (src.repo, documentationUrl, etc.) follow
a valid URL format.
"""
from __future__ import annotations

import re
import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Regex for URL validation (simplified)
URL_REGEX = re.compile(
    r'^https?://'  # http:// or https://
    r'[^\s/$.?#]+'  # domain
    r'[^\s]*$',     # path and query
    re.IGNORECASE
)

# URL-related fields to validate
URL_FIELDS = {"src.repo", "documentationUrl"}


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test URL field validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any URL format violations
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

        # Check URL fields
        if key in URL_FIELDS and value:
            if not URL_REGEX.match(value):
                issues.append(LintIssue(
                    "WARNING",
                    f"Field '{key}' value '{value}' does not appear to be a valid URL",
                    idx,
                    line,
                ))

    return issues

