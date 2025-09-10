#!/usr/bin/env python
"""
Test for duplicate key detection.

This test ensures that no key appears more than once in the manifest file.
"""
from __future__ import annotations

import sys
import os
from typing import List, Dict, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test for duplicate keys in the manifest.
    
    Args:
        lines: List of lines from the manifest file
        
    Returns:
        List of LintIssue objects for any duplicate key violations
    """
    issues: List[LintIssue] = []
    props: Dict[str, Tuple[int, str]] = {}
    
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
        
        # Skip empty keys (will be caught by basic format test)
        if key == "":
            continue
            
        # Check for duplicate keys
        if key in props:
            prev_idx, prev_line = props[key]
            issues.append(LintIssue(
                "ERROR",
                f"Duplicate key '{key}' (previously defined at line {prev_idx})",
                idx,
                line,
            ))
        else:
            props[key] = (idx, line)
    
    return issues


