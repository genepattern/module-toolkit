#!/usr/bin/env python
"""
Test for GPUnit parameter type validation.

This test validates that the values provided for parameters in the GPUnit file match the expected data types.
"""
from __future__ import annotations

import sys
import os
from typing import List, Dict
from dataclasses import dataclass

# Add parent directory to path for imports  
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


@dataclass
class LintIssue:
    """Represents a validation issue found during GPUnit linting."""
    severity: str  # 'ERROR' or 'WARNING' or 'INFO'
    message: str
    context: str | None = None

    def format(self) -> str:
        """Format the issue for human-readable output."""
        context_info = f" ({self.context})" if self.context else ""
        return f"{self.severity}: {self.message}{context_info}"


def run_test(gpunit_path: str, shared_context: dict) -> List[LintIssue]:
    """
    Test GPUnit parameter type validation.
    
    This test only runs if expected parameter types are provided in the shared context.
    
    Args:
        gpunit_path: Path to the GPUnit file
        shared_context: Mutable dict with test context including parsed_data and expected_param_types
        
    Returns:
        List of LintIssue objects for any type validation failures
    """
    issues: List[LintIssue] = []
    
    # Get expected parameter types from shared context
    expected_param_types: Dict[str, str] = shared_context.get('expected_param_types')
    
    # If no expected types provided, skip validation
    if not expected_param_types:
        issues.append(LintIssue(
            "INFO",
            "Parameter type validation skipped - no expected parameter types provided",
            "Context requires 'expected_param_types' map"
        ))
        return issues
    
    # Get parsed data from file validation test
    data = shared_context.get('parsed_data')
    if data is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate parameter types: YAML parsing failed",
            "File validation must pass before type validation"
        ))
        return issues
    
    # Check if params field exists (structure validation handles missing fields)
    if 'params' not in data:
        return issues  # Structure validation will catch this
    
    params = data['params']
    if not isinstance(params, dict):
        return issues  # Structure validation will catch this
    
    #Validate parameter types
    for param_name, param_value in params.items():
        if param_name not in expected_param_types: continue
        expected_type = expected_param_types[param_name]
        type_lower = expected_type.lower()
        if param_value is None:
            issues.append(LintIssue("WARNING",f"Parameter '{param_name}' has no value",f"Expected type: {expected_type}"))
            continue
        is_valid = True
        #Number validation
        if 'number' in type_lower:
            if not (isinstance(param_value, (int, float)) and not isinstance(param_value, bool)): is_valid = False
        #Text validation
        elif 'text' in type_lower:
            if not isinstance(param_value, str): is_valid = False
        #File validation
        elif 'file' in type_lower:
            if not isinstance(param_value, str): is_valid = False
        if not is_valid:
            issues.append(LintIssue("ERROR",f"Invalid type for parameter '{param_name}'",
                f"Expected {expected_type} but got {type(param_value).__name__} (Value: {param_value})"))
    return issues