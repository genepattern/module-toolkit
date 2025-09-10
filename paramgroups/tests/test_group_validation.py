#!/usr/bin/env python
"""
Test for parameter group validation.

This test validates that all parameter groups have a non-zero
number of parameters.
"""
from __future__ import annotations

import sys
import os
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
    Test parameter group validation.
    
    Args:
        paramgroups_path: Path to the paramgroups.json file
        shared_context: Mutable dict with test context including parsed_data
        
    Returns:
        List of LintIssue objects for any group validation failures
    """
    issues: List[LintIssue] = []
    
    # Get parsed data from file validation test
    data = shared_context.get('parsed_data')
    if data is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate groups: JSON parsing failed",
            "File validation must pass before group validation"
        ))
        return issues
    
    # Validate each group
    for i, group in enumerate(data):
        group_context = f"Group {i}"
        
        # Skip if not a dict (structure validation will catch this)
        if not isinstance(group, dict):
            continue
        
        # Get group name for better context
        group_name = group.get('name', f'Unnamed group {i}')
        if isinstance(group_name, str) and group_name.strip():
            group_context = f"Group '{group_name}'"
        
        # Check if parameters field exists and is valid
        if 'parameters' not in group:
            continue  # Structure validation will catch this
        
        parameters = group['parameters']
        if not isinstance(parameters, list):
            continue  # Structure validation will catch this
        
        # Check for empty parameters list
        if len(parameters) == 0:
            issues.append(LintIssue(
                "ERROR",
                "Parameter group has zero parameters",
                group_context
            ))
            continue
        
        # Check for duplicate parameters within the group
        seen_params = set()
        for j, param in enumerate(parameters):
            if isinstance(param, str):
                if param in seen_params:
                    issues.append(LintIssue(
                        "WARNING",
                        f"Duplicate parameter '{param}' in group",
                        group_context
                    ))
                else:
                    seen_params.add(param)
    
    return issues
