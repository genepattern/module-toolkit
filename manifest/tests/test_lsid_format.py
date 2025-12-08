#!/usr/bin/env python
"""
Test for LSID format validation.

This test ensures that if an LSID key is present, its value follows
the proper LSID format (starts with urn:lsid: or urn\:lsid\:).
"""
from __future__ import annotations

import re
import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Regex pattern for valid LSID format (accepts both escaped and unescaped forms)
AUTHORITY_SEGMENT = r"[A-Za-z0-9._-]+"
NAMESPACE_SEGMENT = r"[A-Za-z0-9._-]+"
OBJECT_SEGMENT = r"[0-9]+"
REVISION_SEGMENT = r"[0-9]+(?:\.[0-9]+)?"
# After normalizing escaped separators to literal colons we can enforce the exact LSID shape
LSID_REGEX = re.compile(
    rf"^urn:lsid:{AUTHORITY_SEGMENT}:{NAMESPACE_SEGMENT}:{OBJECT_SEGMENT}:{REVISION_SEGMENT}$",
    re.IGNORECASE,
)


def _normalize_lsid(value: str) -> str:
    """Treat escaped separators (\:) the same as literal colons."""
    return value.replace("\\:", ":")


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test LSID format validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any LSID format violations
    """
    issues: List[LintIssue] = []

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        # Skip empty lines and comments
        if stripped == "" or stripped.startswith("#") or stripped.startswith("!"):
            continue

        # Skip lines that don't have = separator (will be caught by basic format test)
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Skip empty keys (will be caught by basic format test)
        if key == "":
            continue

        # Check LSID format if this is an LSID key
        if key == "LSID":
            normalized_value = _normalize_lsid(value)
            if not LSID_REGEX.match(normalized_value):
                issues.append(
                    LintIssue(
                        "ERROR",
                        "LSID must follow 'urn:lsid:AuthorityID:NamespaceID:ObjectID:RevisionID' where ObjectID is an integer and RevisionID is numeric (escaped ':' via \\: accepted)",
                        idx,
                        line,
                    )
                )

    return issues
