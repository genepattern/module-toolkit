#!/usr/bin/env python
"""
Test for GPUnit structure validation.

This test validates that the GPUnit YAML file has the correct
structure with required fields: name, module, params, assertions.
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
    Test GPUnit structure validation.
    
    Args:
        gpunit_path: Path to the GPUnit file
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
            "Cannot validate structure: YAML parsing failed",
            "File validation must pass before structure validation"
        ))
        return issues
    
    # Root should be a dict/object
    if not isinstance(data, dict):
        issues.append(LintIssue(
            "ERROR",
            f"Root element must be an object/dict, found: {type(data).__name__}"
        ))
        return issues
    
    # Check required fields
    required_fields = ['name', 'module', 'params', 'assertions']
    for field in required_fields:
        if field not in data:
            issues.append(LintIssue(
                "ERROR",
                f"Missing required field '{field}'"
            ))
        elif data[field] is None:
            issues.append(LintIssue(
                "ERROR",
                f"Required field '{field}' cannot be null"
            ))
    
    # Validate field types and content
    if 'name' in data:
        if not isinstance(data['name'], str):
            issues.append(LintIssue(
                "ERROR",
                f"Field 'name' must be a string, found: {type(data['name']).__name__}"
            ))
        elif not data['name'].strip():
            issues.append(LintIssue(
                "ERROR",
                "Field 'name' cannot be empty"
            ))
    
    if 'module' in data:
        if not isinstance(data['module'], str):
            issues.append(LintIssue(
                "ERROR",
                f"Field 'module' must be a string, found: {type(data['module']).__name__}"
            ))
        elif not data['module'].strip():
            issues.append(LintIssue(
                "ERROR",
                "Field 'module' cannot be empty"
            ))
    
    if 'params' in data:
        if not isinstance(data['params'], dict):
            issues.append(LintIssue(
                "ERROR",
                f"Field 'params' must be an object/dict, found: {type(data['params']).__name__}"
            ))
        else:
            # Validate parameter names and values
            for param_name, param_value in data['params'].items():
                if not isinstance(param_name, str):
                    issues.append(LintIssue(
                        "ERROR",
                        f"Parameter name must be a string, found: {type(param_name).__name__}",
                        f"Parameter: {param_name}"
                    ))
                elif not param_name.strip():
                    issues.append(LintIssue(
                        "ERROR",
                        "Parameter name cannot be empty"
                    ))
                
                # Parameter values can be strings, numbers, booleans, but not null
                if param_value is None:
                    issues.append(LintIssue(
                        "WARNING",
                        f"Parameter '{param_name}' has null value"
                    ))
    
    if 'assertions' in data:
        if not isinstance(data['assertions'], dict):
            issues.append(LintIssue(
                "ERROR",
                f"Field 'assertions' must be an object/dict, found: {type(data['assertions']).__name__}"
            ))
        elif len(data['assertions']) == 0:
            issues.append(LintIssue(
                "WARNING",
                "Field 'assertions' is empty - no test assertions defined"
            ))
    
    # Check for unexpected top-level fields (informational)
    expected_fields = {'name', 'module', 'params', 'assertions'}
    unexpected_fields = set(data.keys()) - expected_fields
    if unexpected_fields:
        issues.append(LintIssue(
            "INFO",
            f"Additional fields found: {', '.join(sorted(unexpected_fields))}",
            "These may be valid but are not standard GPUnit fields"
        ))
    
    return issues
