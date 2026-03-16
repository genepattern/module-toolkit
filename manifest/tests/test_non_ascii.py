#!/usr/bin/env python
"""
Test for non-ASCII characters in manifest files.

GenePattern's database does not support non-ASCII (unicode) characters in
manifest files.  This test detects any characters outside the ASCII range
(ordinal > 127) and reports them with their line number, column, Unicode
code-point, and surrounding context so the author can replace them with
ASCII equivalents.
"""
from __future__ import annotations

import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue


# Common Unicode → ASCII replacements for helpful error messages
_COMMON_REPLACEMENTS = {
    '\u2014': '--',   # em dash
    '\u2013': '-',    # en dash
    '\u2018': "'",    # left single quote
    '\u2019': "'",    # right single quote
    '\u201c': '"',    # left double quote
    '\u201d': '"',    # right double quote
    '\u2026': '...',  # ellipsis
    '\u00e9': 'e',    # é
    '\u00ed': 'i',    # í
    '\u00f1': 'n',    # ñ
    '\u00e8': 'e',    # è
    '\u00e0': 'a',    # à
    '\u00fc': 'u',    # ü
    '\u00f6': 'o',    # ö
    '\u00e4': 'a',    # ä
    '\u00d7': 'x',    # ×
    '\u2265': '>=',   # ≥
    '\u2264': '<=',   # ≤
    '\u00b1': '+/-',  # ±
    '\u2192': '->',   # →
    '\u00a0': ' ',    # non-breaking space
}


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test that the manifest contains only ASCII characters.

    GenePattern's server and database do not support non-ASCII characters in
    manifest files.  Any character with an ordinal value greater than 127 will
    cause the module installation to fail.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any non-ASCII characters found
    """
    issues: List[LintIssue] = []

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")

        # Skip empty lines and comments
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#") or stripped.startswith("!"):
            continue

        non_ascii_chars = []
        for col, ch in enumerate(line):
            if ord(ch) > 127:
                replacement = _COMMON_REPLACEMENTS.get(ch)
                hint = f" (try replacing with '{replacement}')" if replacement else ""
                non_ascii_chars.append(
                    f"U+{ord(ch):04X} {ch!r} at column {col + 1}{hint}"
                )

        if non_ascii_chars:
            char_list = "; ".join(non_ascii_chars)
            issues.append(LintIssue(
                "ERROR",
                f"Non-ASCII characters found: {char_list}. "
                f"GenePattern's database does not support non-ASCII/unicode characters "
                f"in manifest files. Replace them with ASCII equivalents.",
                idx,
                line,
            ))

    return issues

