#!/usr/bin/env python
"""
Test for paramgroups.json structure validation.

This test validates that the paramgroups.json file has the correct
structure: an array of objects with required fields.
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
    Test paramgroups.json structure validation.
    
    Args:
        paramgroups_path: Path to the paramgroups.json file
        shared_context: Mutable dict with test context including parsed_data
        
    Returns:
        List of LintIssue objects for any structure validation failures
    """
    issues: List[LintIssue] = []
    
    # Get parsed data from file validation test
    data = shared_context.get('parsed_data')
    if data is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate structure: JSON parsing failed",
            "File validation must pass before structure validation"
        ))
        return issues
    
    # Root should be an array
    if not isinstance(data, list):
        issues.append(LintIssue(
            "ERROR",
            f"Root element must be an array, found: {type(data).__name__}"
        ))
        return issues
    
    # Array should not be empty
    if len(data) == 0:
        issues.append(LintIssue(
            "WARNING",
            "Paramgroups array is empty"
        ))
        return issues
    
    # Validate each group object
    for i, group in enumerate(data):
        group_context = f"Group {i}"
        
        # Each element should be an object
        if not isinstance(group, dict):
            issues.append(LintIssue(
                "ERROR",
                f"Group element must be an object, found: {type(group).__name__}",
                group_context
            ))
            continue
        
        # Check required fields
        required_fields = ['name', 'parameters']
        for field in required_fields:
            if field not in group:
                issues.append(LintIssue(
                    "ERROR",
                    f"Missing required field '{field}'",
                    group_context
                ))
            elif group[field] is None:
                issues.append(LintIssue(
                    "ERROR",
                    f"Required field '{field}' cannot be null",
                    group_context
                ))
        
        # Validate field types
        if 'name' in group:
            if not isinstance(group['name'], str):
                issues.append(LintIssue(
                    "ERROR",
                    f"Field 'name' must be a string, found: {type(group['name']).__name__}",
                    group_context
                ))
            elif not group['name'].strip():
                issues.append(LintIssue(
                    "ERROR",
                    "Field 'name' cannot be empty",
                    group_context
                ))
        
        if 'description' in group:
            if not isinstance(group['description'], str):
                issues.append(LintIssue(
                    "ERROR",
                    f"Field 'description' must be a string, found: {type(group['description']).__name__}",
                    group_context
                ))
        
        if 'hidden' in group:
            if not isinstance(group['hidden'], bool):
                issues.append(LintIssue(
                    "ERROR",
                    f"Field 'hidden' must be a boolean, found: {type(group['hidden']).__name__}",
                    group_context
                ))
        
        if 'parameters' in group:
            if not isinstance(group['parameters'], list):
                issues.append(LintIssue(
                    "ERROR",
                    f"Field 'parameters' must be an array, found: {type(group['parameters']).__name__}",
                    group_context
                ))
            else:
                # Validate parameter names
                for j, param in enumerate(group['parameters']):
                    if not isinstance(param, str):
                        issues.append(LintIssue(
                            "ERROR",
                            f"Parameter {j} must be a string, found: {type(param).__name__}",
                            f"{group_context}, parameter {j}"
                        ))
                    elif not param.strip():
                        issues.append(LintIssue(
                            "ERROR",
                            f"Parameter {j} cannot be empty",
                            f"{group_context}, parameter {j}"
                        ))
        
        # Check for unexpected fields (warning only)
        expected_fields = {'name', 'description', 'hidden', 'parameters'}
        unexpected_fields = set(group.keys()) - expected_fields
        if unexpected_fields:
            issues.append(LintIssue(
                "WARNING",
                f"Unexpected fields found: {', '.join(sorted(unexpected_fields))}",
                group_context
            ))
    
    return issues
