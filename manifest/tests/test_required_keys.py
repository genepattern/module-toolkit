#!/usr/bin/env python
"""
Test for required keys validation.

This test ensures that all required keys are present in the manifest file.
Required keys are: LSID, name, commandLine
"""
from __future__ import annotations

import sys
import os
from typing import List, Set

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Set of required keys that must be present in every manifest
REQUIRED_KEYS = {"LSID", "name", "commandLine"}


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test for presence of required keys in the manifest.
    
    Args:
        lines: List of lines from the manifest file
        
    Returns:
        List of LintIssue objects for any missing required keys
    """
    issues: List[LintIssue] = []
    found_keys: Set[str] = set()
    
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
            
        found_keys.add(key)
    
    # Check for missing required keys
    missing_keys = REQUIRED_KEYS - found_keys
    for req_key in sorted(missing_keys):
        issues.append(LintIssue(
            "ERROR",
            f"Missing required key '{req_key}'",
            None,
            None,
        ))
    
    return issues


