#!/usr/bin/env python
"""
Test for GPUnit file parameter existence validation.

This test validates that parameters identified as Files point to actual existing local files or accessible URLs.
"""
from __future__ import annotations

import sys
import os
import urllib.request
import urllib.error
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
    Test GPUnit file parameter existence.
    
    This test iterates over parameters. If a parameter is identified as a 'File' type
    via expected_param_types, it verifies the value is a reachable URL or existing file.
    
    Args:
        gpunit_path: Path to the GPUnit file (used as base for relative paths)
        shared_context: Mutable dict with test context including parsed_data and expected_param_types
        
    Returns:
        List of LintIssue objects for any file existence failures
    """
    issues: List[LintIssue] = []
    
    # Get expected parameter types from shared context
    expected_param_types: Dict[str, str] = shared_context.get('expected_param_types')
    
    # If no expected types provided, we can't know which params are files
    if not expected_param_types:
        issues.append(LintIssue(
            "INFO",
            "File existence validation skipped - no type information provided",
            "Context requires 'expected_param_types' map"
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
    
    gpunit_dir = os.path.dirname(os.path.abspath(gpunit_path))
    #Validate files
    for param_name, param_value in params.items():
        if param_name not in expected_param_types: continue
        type_str = expected_param_types[param_name]
        if 'file' not in type_str.lower(): continue
        if not param_value or not isinstance(param_value, str): continue
        # Check URL/Local File
        if param_value.startswith(("http://", "https://", "ftp://")):
            #URL validation
            error = None
            try:
                #HEAD request
                req = urllib.request.Request(param_value, method="HEAD")
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status != 200: error = f"URL returned status: {response.status}"
            except urllib.error.URLError as e:
                error = f"URL inaccessible: {str(e)}"
            except Exception as e:
                error = f"Error checking URL: {str(e)}"
            if error:
                issues.append(LintIssue("ERROR", 
                    f"File parameter '{param_name}' points to inaccessible URL",
                    f"{error} (Value: {param_value})"))
        else:
            #Local File validation
            error = None
            if os.path.isabs(param_value):
                if not (os.path.exists(param_value) and os.path.isfile(param_value)):
                    error = f"Absolute path not found: {param_value}"
            else:
                full_path = os.path.join(gpunit_dir, param_value)
                if not (os.path.exists(full_path) and os.path.isfile(full_path)):
                    error = f"File not found at: {full_path}"
            if error:
                issues.append(LintIssue("ERROR",
                    f"File parameter '{param_name}' points to missing file",
                    f"{error}"))
    return issues