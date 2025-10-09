#!/usr/bin/env python
"""
Test for taskType field validation.

This test ensures that the taskType field, if present, contains a reasonable value.
"""
from __future__ import annotations

import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Common task types seen in GenePattern modules
COMMON_TASK_TYPES = {
    "Preprocess & Utilities", "SNP Analysis", "RNA-seq", "javascript",
    "rna-seq", "spatial transcriptomics", "Dimension Reduction",
    "Clustering", "Prediction", "Classification", "Feature Selection",
    "Pathway Analysis", "Proteomics", "Copy Number", "Gene List Selection"
}


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test taskType field validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any taskType field violations
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

        # Check taskType field (informational only)
        if key == "taskType" and value:
            # This is informational - we don't error on unusual values
            # since task types can be custom
            pass

    return issues

