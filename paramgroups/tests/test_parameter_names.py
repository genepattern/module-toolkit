#!/usr/bin/env python
"""
Test for parameter name format validation.

This test validates that all parameter names follow the expected naming rules:
- No spaces allowed (ERROR)
- Must be alphanumeric or contain periods
- Other special characters (e.g., underscores) are flagged as WARNINGS
"""
from __future__ import annotations

import sys
import os
import re
from typing import List
from dataclasses import dataclass

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


@dataclass
class LintIssue:
    """Represents a validation issue found during paramgroups linting."""
    severity: str  # 'ERROR' or 'WARNING' or 'INFO'
    message: str
    context: str | None = None

    def format(self) -> str:
        """Format the issue for human-readable output."""
        context_info = f" ({self.context})" if self.context else ""
        return f"{self.severity}: {self.message}{context_info}"


def run_test(paramgroups_path: str, shared_context: dict) -> List[LintIssue]:
    """
    Test parameter name format validation.

    Args:
        paramgroups_path: Path to the paramgroups.json file
        shared_context: Mutable dict with test context

    Returns:
        List of LintIssue objects for any parameter name format violations
    """
    issues: List[LintIssue] = []

    data = shared_context.get('parsed_data')
    if data is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate parameter names: JSON parsing failed",
            "File validation must pass before parameter name validation"
        ))
        return issues
    
    # Root should be an array; if not, warning
    if not isinstance(data, list):
        issues.append(LintIssue(
            "WARNING",
            f"Skipping parameter name checks: root element is {type(data).__name__}, expected array"
        ))
        return issues

    # Collect all parameter names
    found_parameters = set()
    for idx, group in enumerate(data):
        if isinstance(group, dict):
            group_context = f"Group {idx}"

            # Check missing or empty parameters
            if "parameters" not in group:
                issues.append(LintIssue(
                    "WARNING",
                    f"Skipping parameter name validation for {group_context}: Missing required field 'parameters'"
                ))
                continue  # no parameters to check

            if not group["parameters"]:
                issues.append(LintIssue(
                    "WARNING",
                    f"Skipping parameter name validation for {group_context}: Field 'parameters' is empty"
                ))
                continue

            # Validate parameter names if list is non-empty
            if isinstance(group["parameters"], list):
                for param in group["parameters"]:
                    if isinstance(param, str):
                        found_parameters.add(param)

    # valid names (alphanumeric + periods only)
    valid_pattern = re.compile(r'^[A-Za-z0-9.]+$')

    # Validate each parameter name
    for param in sorted(found_parameters):
        if " " in param:
            issues.append(LintIssue(
                "ERROR",
                f"Parameter name '{param}' contains spaces",
                "Spaces are not allowed in parameter names"
            ))
        elif not valid_pattern.match(param):
            issues.append(LintIssue(
                "WARNING",
                f"Parameter name '{param}' contains non-standard characters",
                "Only alphanumeric characters and periods are recommended"
            ))

    if not issues:
        issues.append(LintIssue(
            "INFO",
            "All parameter names follow the expected format",
            None
        ))

    return issues