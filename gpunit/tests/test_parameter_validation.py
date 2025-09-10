#!/usr/bin/env python
"""
Test for GPUnit parameter validation.

This test validates that the parameters in the GPUnit file match
the expected parameter list if provided.
"""
from __future__ import annotations

import sys
import os
from typing import List, Set
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
    Test GPUnit parameter validation.
    
    This test only runs if expected parameters are provided.
    If no expected parameters are provided, the test passes (parameter validation is optional).
    
    Args:
        gpunit_path: Path to the GPUnit file
        shared_context: Mutable dict with test context including parsed_data and expected_parameters
        
    Returns:
        List of LintIssue objects for any parameter validation failures
    """
    issues: List[LintIssue] = []
    
    # Get expected parameters from command line
    expected_parameters = shared_context.get('expected_parameters')
    
    # If no expected parameters provided, parameter validation is optional - just pass
    if not expected_parameters:
        issues.append(LintIssue(
            "INFO",
            "Parameter validation skipped - no expected parameters provided",
            "Use --parameters to enable parameter validation"
        ))
        return issues
    
    # Get parsed data from file validation test
    data = shared_context.get('parsed_data')
    if data is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate parameters: YAML parsing failed",
            "File validation must pass before parameter validation"
        ))
        return issues
    
    # Check if params field exists (structure validation handles missing fields)
    if 'params' not in data:
        return issues  # Structure validation will catch this
    
    params = data['params']
    if not isinstance(params, dict):
        return issues  # Structure validation will catch this
    
    # Get actual parameters from GPUnit file
    actual_parameters: Set[str] = set(params.keys())
    expected_set = set(expected_parameters)
    
    # Check for parameters in GPUnit that are not in expected list
    unexpected_parameters = actual_parameters - expected_set
    if unexpected_parameters:
        sorted_unexpected = sorted(unexpected_parameters)
        for param in sorted_unexpected:
            issues.append(LintIssue(
                "ERROR",
                f"Unexpected parameter '{param}' found in GPUnit file",
                "Parameter not in expected parameters list"
            ))
    
    # Check for missing expected parameters (optional - might be warnings instead of errors)
    missing_parameters = expected_set - actual_parameters
    if missing_parameters:
        sorted_missing = sorted(missing_parameters)
        for param in sorted_missing:
            issues.append(LintIssue(
                "WARNING",
                f"Expected parameter '{param}' not found in GPUnit file",
                "Parameter was expected but not provided in this test"
            ))
    
    # Report summary info
    if not unexpected_parameters and not missing_parameters:
        issues.append(LintIssue(
            "INFO",
            f"All {len(expected_parameters)} expected parameters found and validated"
        ))
    
    return issues
