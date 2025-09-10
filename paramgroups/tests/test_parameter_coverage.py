#!/usr/bin/env python
"""
Test for parameter coverage validation.

This test validates that all provided parameters (from command line)
are represented somewhere in the paramgroups.json file.
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
    Test parameter coverage validation.
    
    This test only runs if parameters are provided via command line.
    If no parameters are provided, the test passes (coverage testing is optional).
    
    Args:
        paramgroups_path: Path to the paramgroups.json file
        shared_context: Mutable dict with test context including parsed_data and expected_parameters
        
    Returns:
        List of LintIssue objects for any parameter coverage failures
    """
    issues: List[LintIssue] = []
    
    # Get expected parameters from command line
    expected_parameters = shared_context.get('expected_parameters')
    
    # If no parameters provided, coverage testing is optional - just pass
    if not expected_parameters:
        issues.append(LintIssue(
            "INFO",
            "Parameter coverage testing skipped - no expected parameters provided",
            "Use --parameters to enable coverage validation"
        ))
        return issues
    
    # Get parsed data from file validation test
    data = shared_context.get('parsed_data')
    if data is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate parameter coverage: JSON parsing failed",
            "File validation must pass before parameter coverage validation"
        ))
        return issues
    
    # Collect all parameters from all groups
    found_parameters: Set[str] = set()
    for group in data:
        if isinstance(group, dict) and 'parameters' in group:
            if isinstance(group['parameters'], list):
                for param in group['parameters']:
                    if isinstance(param, str):
                        found_parameters.add(param)
    
    # Check that all expected parameters are found
    expected_set = set(expected_parameters)
    missing_parameters = expected_set - found_parameters
    
    if missing_parameters:
        sorted_missing = sorted(missing_parameters)
        for param in sorted_missing:
            issues.append(LintIssue(
                "ERROR",
                f"Expected parameter '{param}' not found in any parameter group"
            ))
    
    # Store found parameters for completeness test
    shared_context['found_parameters'] = found_parameters
    
    return issues
