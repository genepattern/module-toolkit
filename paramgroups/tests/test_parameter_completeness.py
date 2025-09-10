#!/usr/bin/env python
"""
Test for parameter completeness validation.

This test validates that there are no extra parameters in the file
that are not represented in the expected parameters list.
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
    Test parameter completeness validation.
    
    This test only runs if parameters are provided via command line.
    If no parameters are provided, the test passes (completeness testing is optional).
    
    Args:
        paramgroups_path: Path to the paramgroups.json file
        shared_context: Mutable dict with test context including found_parameters and expected_parameters
        
    Returns:
        List of LintIssue objects for any parameter completeness failures
    """
    issues: List[LintIssue] = []
    
    # Get expected parameters from command line
    expected_parameters = shared_context.get('expected_parameters')
    
    # If no parameters provided, completeness testing is optional - just pass
    if not expected_parameters:
        issues.append(LintIssue(
            "INFO",
            "Parameter completeness testing skipped - no expected parameters provided",
            "Use --parameters to enable completeness validation"
        ))
        return issues
    
    # Get found parameters from coverage test, or collect them ourselves
    found_parameters = shared_context.get('found_parameters')
    if found_parameters is None:
        # If coverage test hasn't run yet, collect parameters ourselves
        data = shared_context.get('parsed_data')
        if data is None:
            issues.append(LintIssue(
                "ERROR",
                "Cannot validate parameter completeness: JSON parsing failed",
                "File validation must pass before parameter completeness validation"
            ))
            return issues
        
        # Collect all parameters from all groups
        found_parameters = set()
        for group in data:
            if isinstance(group, dict) and 'parameters' in group:
                if isinstance(group['parameters'], list):
                    for param in group['parameters']:
                        if isinstance(param, str):
                            found_parameters.add(param)
        
        # Store for future use
        shared_context['found_parameters'] = found_parameters
    
    # Check for extra parameters in file that aren't in expected list
    expected_set = set(expected_parameters)
    extra_parameters = found_parameters - expected_set
    
    if extra_parameters:
        sorted_extra = sorted(extra_parameters)
        for param in sorted_extra:
            issues.append(LintIssue(
                "ERROR",
                f"Unexpected parameter '{param}' found in paramgroups file",
                "Parameter not in expected parameters list"
            ))
    
    return issues
