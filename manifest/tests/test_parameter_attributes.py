#!/usr/bin/env python
"""
Test for parameter attribute validation.

This test ensures that parameters have required attributes and that
attribute values are consistent and valid.
"""
from __future__ import annotations

import re
import sys
import os
from typing import List, Dict, Set

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Regex to match parameter keys
PARAM_KEY_REGEX = re.compile(r"^p(\d+)_(.+)$")

# Common required attributes for parameters
COMMON_PARAM_ATTRIBUTES = {"name", "description", "optional"}

# Valid values for specific attributes
VALID_MODES = {"IN", "OUT", ""}
VALID_TYPES = {"FILE", "TEXT", ""}

NUMVALUES_INT_PATTERN = re.compile(r"^-?\d+$")
NUMVALUES_RANGE_PATTERN = re.compile(r"^(-?\d+)\.\.(-?\d+)$")
NUMVALUES_MIN_PATTERN = re.compile(r"^(-?\d+)\+$")


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test parameter attribute validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any parameter attribute violations
    """
    issues: List[LintIssue] = []
    params: Dict[int, Dict[str, tuple]] = {}  # param_num -> {attr_name: (value, line_no, line_text)}

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

        # Check if this is a parameter key
        match = PARAM_KEY_REGEX.match(key)
        if match:
            param_num = int(match.group(1))
            attr_name = match.group(2)

            if param_num not in params:
                params[param_num] = {}

            params[param_num][attr_name] = (value, idx, line)

    # Validate each parameter
    for param_num in sorted(params.keys()):
        param_attrs = params[param_num]
        is_file_param = _is_file_parameter(param_attrs)

        # Check for required attributes
        missing_attrs = COMMON_PARAM_ATTRIBUTES - set(param_attrs.keys())
        if missing_attrs:
            issues.append(LintIssue(
                "WARNING",
                f"Parameter p{param_num} is missing recommended attribute(s): {sorted(missing_attrs)}",
                None,
                None,
            ))

        # Validate MODE values if present
        if "MODE" in param_attrs:
            mode_value = param_attrs["MODE"][0]
            if mode_value not in VALID_MODES:
                _, line_no, line_text = param_attrs["MODE"]
                issues.append(LintIssue(
                    "WARNING",
                    f"Parameter p{param_num} has unusual MODE value '{mode_value}'. Common values are: IN, OUT, or empty",
                    line_no,
                    line_text,
                ))

        # Validate TYPE values if present
        if "TYPE" in param_attrs:
            type_value = param_attrs["TYPE"][0]
            if type_value not in VALID_TYPES:
                # This is just informational since TYPE can have other values like Integer, Float, etc.
                pass

        # Check that file parameters have MODE=IN or MODE=OUT
        if "type" in param_attrs:
            type_value = param_attrs["type"][0]
            if type_value == "java.io.File" and "MODE" in param_attrs:
                mode_value = param_attrs["MODE"][0]
                if mode_value not in {"IN", "OUT"}:
                    _, line_no, line_text = param_attrs["MODE"]
                    issues.append(LintIssue(
                        "WARNING",
                        f"Parameter p{param_num} is a File type but MODE is '{mode_value}'. Expected 'IN' or 'OUT'",
                        line_no,
                        line_text,
                    ))

        if is_file_param:
            if "numValues" not in param_attrs:
                issues.append(LintIssue(
                    "WARNING",
                    f"Parameter p{param_num} is a file type but is missing required attribute 'numValues'",
                    None,
                    None,
                ))
            else:
                num_values_value, line_no, line_text = param_attrs["numValues"]
                if not _is_valid_numvalues(num_values_value):
                    issues.append(LintIssue(
                        "WARNING",
                        f"Parameter p{param_num} has numValues '{num_values_value}'. Expected an integer, range like '0..4', or minimum like '1+'",
                        line_no,
                        line_text,
                    ))

    return issues


def _is_file_parameter(attrs: Dict[str, tuple]) -> bool:
    if "type" in attrs and attrs["type"][0] == "java.io.File":
        return True
    if "TYPE" in attrs and attrs["TYPE"][0] == "FILE":
        return True
    return False


def _is_valid_numvalues(value: str) -> bool:
    if NUMVALUES_INT_PATTERN.fullmatch(value):
        return True
    range_match = NUMVALUES_RANGE_PATTERN.fullmatch(value)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        return start <= end
    if NUMVALUES_MIN_PATTERN.fullmatch(value):
        return True
    return False
