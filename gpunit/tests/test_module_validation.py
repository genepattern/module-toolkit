#!/usr/bin/env python
"""
Test for GPUnit module validation.

This test validates that the module field in the GPUnit matches
the expected module name or LSID if provided.
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
    Test GPUnit module validation.
    
    This test only runs if an expected module name/LSID is provided.
    If no expected module is provided, the test passes (module validation is optional).
    
    Args:
        gpunit_path: Path to the GPUnit file
        shared_context: Mutable dict with test context including parsed_data and expected_module
        
    Returns:
        List of LintIssue objects for any module validation failures
    """
    issues: List[LintIssue] = []
    
    # Get expected module from command line
    expected_module = shared_context.get('expected_module')
    
    # If no expected module provided, module validation is optional - just pass
    if not expected_module:
        issues.append(LintIssue(
            "INFO",
            "Module validation skipped - no expected module provided",
            "Use --module to enable module validation"
        ))
        return issues
    
    # Get parsed data from file validation test
    data = shared_context.get('parsed_data')
    if data is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate module: YAML parsing failed",
            "File validation must pass before module validation"
        ))
        return issues
    
    # Check if module field exists (structure validation handles missing fields)
    if 'module' not in data:
        return issues  # Structure validation will catch this
    
    actual_module = data['module']
    if not isinstance(actual_module, str):
        return issues  # Structure validation will catch this
    
    # Compare expected vs actual module
    # Handle both exact match and case-insensitive match for flexibility
    if actual_module != expected_module:
        # Check for case-insensitive match
        if actual_module.lower() == expected_module.lower():
            issues.append(LintIssue(
                "WARNING",
                f"Module name case mismatch: expected '{expected_module}', found '{actual_module}'"
            ))
        else:
            # Check if one might be an LSID and the other a module name
            # LSID format: urn:lsid:domain:type:id
            is_expected_lsid = expected_module.startswith('urn:lsid:')
            is_actual_lsid = actual_module.startswith('urn:lsid:')
            
            if is_expected_lsid and not is_actual_lsid:
                # Expected LSID but got module name
                issues.append(LintIssue(
                    "ERROR",
                    f"Expected LSID '{expected_module}' but found module name '{actual_module}'"
                ))
            elif not is_expected_lsid and is_actual_lsid:
                # Expected module name but got LSID - extract module name from LSID if possible
                if ':' in actual_module:
                    lsid_parts = actual_module.split(':')
                    if len(lsid_parts) >= 5:
                        # Last part of LSID might be the module identifier
                        lsid_module_part = lsid_parts[-1]
                        if lsid_module_part == expected_module:
                            issues.append(LintIssue(
                                "INFO",
                                f"Expected module name '{expected_module}' matches LSID identifier in '{actual_module}'"
                            ))
                        else:
                            issues.append(LintIssue(
                                "ERROR",
                                f"Expected module name '{expected_module}' but found LSID '{actual_module}'"
                            ))
                    else:
                        issues.append(LintIssue(
                            "ERROR",
                            f"Expected module name '{expected_module}' but found malformed LSID '{actual_module}'"
                        ))
                else:
                    issues.append(LintIssue(
                        "ERROR",
                        f"Expected module name '{expected_module}' but found LSID '{actual_module}'"
                    ))
            else:
                # Both are same type but don't match
                module_type = "LSID" if is_expected_lsid else "module name"
                issues.append(LintIssue(
                    "ERROR",
                    f"Module {module_type} mismatch: expected '{expected_module}', found '{actual_module}'"
                ))
    
    return issues
