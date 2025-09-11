#!/usr/bin/env python
"""
Test for documentation parameter validation.

This test validates that the documentation mentions all expected
parameter names if provided.
"""
from __future__ import annotations

import sys
import os
import re
from typing import List, Set
from dataclasses import dataclass

# Add parent directory to path for imports  
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


@dataclass
class LintIssue:
    """Represents a validation issue found during documentation linting."""
    severity: str  # 'ERROR' or 'WARNING' or 'INFO'
    message: str
    context: str | None = None

    def format(self) -> str:
        """Format the issue for human-readable output."""
        context_info = f" ({self.context})" if self.context else ""
        return f"{self.severity}: {self.message}{context_info}"


def search_parameter_in_content(content: str, parameter_name: str) -> tuple[bool, List[str]]:
    """Search for parameter name in content with various patterns.
    
    Returns:
        Tuple of (found, list_of_matched_contexts)
    """
    if not content or not parameter_name:
        return False, []
    
    content_lower = content.lower()
    param_lower = parameter_name.lower()
    
    matches = []
    
    # Exact case-sensitive match
    if parameter_name in content:
        matches.append(f"Exact match: '{parameter_name}'")
    
    # Case-insensitive match
    elif param_lower in content_lower:
        matches.append(f"Case-insensitive match for '{parameter_name}'")
    
    # Pattern matching for common parameter formats
    patterns = [
        # Word boundary match
        rf'\b{re.escape(param_lower)}\b',
        # Parameter with common prefixes/suffixes
        rf'param\w*[:\s]+{re.escape(param_lower)}',  # "parameter: name" or "param name"
        rf'{re.escape(param_lower)}[:\s]+\w+',       # "name: value" or "name value"
        rf'--{re.escape(param_lower)}\b',            # "--parameter"
        rf'-{re.escape(param_lower)}\b',             # "-parameter"
        rf'{re.escape(param_lower)}=',               # "parameter="
        rf'<{re.escape(param_lower)}>',              # "<parameter>"
        rf'\${re.escape(param_lower)}\b',            # "$parameter"
        rf'{re.escape(param_lower)}\.file',          # "parameter.file"
        rf'{re.escape(param_lower)}\.name',          # "parameter.name"
    ]
    
    for pattern in patterns:
        if re.search(pattern, content_lower, re.IGNORECASE):
            matches.append(f"Pattern match: {pattern}")
    
    # Handle dotted parameter names (e.g., "input.file")
    if '.' in parameter_name:
        base_param = parameter_name.split('.')[0]
        if base_param.lower() in content_lower:
            matches.append(f"Base parameter match: '{base_param}' (from '{parameter_name}')")
    
    return len(matches) > 0, matches


def run_test(doc_path_or_url: str, shared_context: dict) -> List[LintIssue]:
    """
    Test documentation parameter validation.
    
    This test only runs if expected parameters are provided.
    If no expected parameters are provided, the test passes (parameter validation is optional).
    
    Args:
        doc_path_or_url: Path to documentation file or URL
        shared_context: Mutable dict with test context including doc_content and expected_parameters
        
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
    
    # Get processed content from content retrieval test
    doc_content = shared_context.get('doc_content')
    if doc_content is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate parameters: document content not available",
            "Content retrieval must pass before parameter validation"
        ))
        return issues
    
    # Search for each parameter in content
    found_parameters: Set[str] = set()
    missing_parameters: Set[str] = set()
    
    for param_name in expected_parameters:
        found, match_contexts = search_parameter_in_content(doc_content, param_name)
        
        if found:
            found_parameters.add(param_name)
            # Report first match context for each found parameter
            if match_contexts:
                issues.append(LintIssue(
                    "INFO",
                    f"Parameter '{param_name}' found: {match_contexts[0]}"
                ))
        else:
            missing_parameters.add(param_name)
            issues.append(LintIssue(
                "ERROR",
                f"Parameter '{param_name}' not found in documentation",
                "All expected parameters should be documented"
            ))
    
    # Summary
    total_params = len(expected_parameters)
    found_count = len(found_parameters)
    missing_count = len(missing_parameters)
    
    if missing_count == 0:
        issues.append(LintIssue(
            "INFO",
            f"All {total_params} expected parameters found in documentation"
        ))
    else:
        issues.append(LintIssue(
            "INFO",
            f"Parameter validation summary: {found_count}/{total_params} parameters found, {missing_count} missing"
        ))
    
    return issues
