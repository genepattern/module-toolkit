#!/usr/bin/env python
"""
Test for wrapper script parameter validation.

This test validates that expected parameter names appear in the script
if parameter names are provided. Different search strategies are used
based on the detected script type.
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
    """Represents a validation issue found during wrapper script linting."""
    severity: str  # 'ERROR' or 'WARNING' or 'INFO'
    message: str
    context: str | None = None

    def format(self) -> str:
        """Format the issue for human-readable output."""
        context_info = f" ({self.context})" if self.context else ""
        return f"{self.severity}: {self.message}{context_info}"


def search_python_parameters(content: str, parameter_name: str) -> tuple[bool, List[str]]:
    """Search for parameter in Python script using Python-specific patterns.
    
    Returns:
        Tuple of (found, list_of_matched_contexts)
    """
    content_lower = content.lower()
    param_lower = parameter_name.lower()
    
    matches = []
    
    # Common Python parameter patterns
    patterns = [
        # argparse patterns
        rf'add_argument\(["\']--{re.escape(param_lower)}["\']',
        rf'add_argument\(["\']-{re.escape(param_lower)}["\']',
        rf'add_argument\(["\']{re.escape(param_lower)}["\']',
        
        # Direct argument access
        rf'args\.{re.escape(param_lower)}\b',
        rf'options\.{re.escape(param_lower)}\b',
        rf'config\.{re.escape(param_lower)}\b',
        
        # Dictionary/config access
        rf'["\']?{re.escape(param_lower)}["\']?\s*[:\]]\s*',
        
        # Variable assignments
        rf'{re.escape(param_lower)}\s*=',
        
        # Function parameters
        rf'def\s+\w+\([^)]*\b{re.escape(param_lower)}\b',
        
        # sys.argv access (less specific)
        rf'sys\.argv',
        
        # Click decorators
        rf'@click\.option\(["\']--{re.escape(param_lower)}["\']',
        
        # Environment variable access
        rf'os\.environ\.get\(["\']{re.escape(param_lower)}["\']',
        rf'getenv\(["\']{re.escape(param_lower)}["\']',
    ]
    
    for pattern in patterns:
        if re.search(pattern, content_lower, re.MULTILINE):
            matches.append(f"Python pattern: {pattern}")
    
    # Simple string search as fallback
    if param_lower in content_lower:
        matches.append(f"String match: '{parameter_name}'")
    
    return len(matches) > 0, matches


def search_bash_parameters(content: str, parameter_name: str) -> tuple[bool, List[str]]:
    """Search for parameter in Bash script using Bash-specific patterns.
    
    Returns:
        Tuple of (found, list_of_matched_contexts)
    """
    content_lower = content.lower()
    param_lower = parameter_name.lower()
    
    matches = []
    
    # Common Bash parameter patterns
    patterns = [
        # Positional parameters
        rf'\$\d+',  # $1, $2, etc.
        
        # Variable assignments
        rf'{re.escape(param_lower)}\s*=',
        
        # Variable usage
        rf'\${re.escape(param_lower)}\b',
        rf'\${{{re.escape(param_lower)}[}}:]',
        
        # Command line option parsing
        rf'--{re.escape(param_lower)}\b',
        rf'-{re.escape(param_lower)}\b',
        
        # getopts patterns
        rf'getopts.*{re.escape(param_lower)}',
        
        # case statement options
        rf'--{re.escape(param_lower)}\)',
        rf'-{re.escape(param_lower)}\)',
        
        # Read statements
        rf'read\s+{re.escape(param_lower)}\b',
    ]
    
    for pattern in patterns:
        if re.search(pattern, content_lower, re.MULTILINE):
            matches.append(f"Bash pattern: {pattern}")
    
    # Simple string search as fallback
    if param_lower in content_lower:
        matches.append(f"String match: '{parameter_name}'")
    
    return len(matches) > 0, matches


def search_r_parameters(content: str, parameter_name: str) -> tuple[bool, List[str]]:
    """Search for parameter in R script using R-specific patterns.
    
    Returns:
        Tuple of (found, list_of_matched_contexts)
    """
    content_lower = content.lower()
    param_lower = parameter_name.lower()
    
    matches = []
    
    # Common R parameter patterns
    patterns = [
        # Variable assignments
        rf'{re.escape(param_lower)}\s*<-',
        rf'{re.escape(param_lower)}\s*=',
        
        # Command line arguments
        rf'commandargs\(\)',
        rf'args\[["\']?{re.escape(param_lower)}["\']?\]',
        
        # optparse patterns
        rf'add_option\(["\']--{re.escape(param_lower)}["\']',
        rf'make_option\(["\']--{re.escape(param_lower)}["\']',
        
        # argparse patterns (newer R)
        rf'add_argument\(["\']--{re.escape(param_lower)}["\']',
        
        # Configuration access
        rf'config\${re.escape(param_lower)}\b',
        rf'params\${re.escape(param_lower)}\b',
        
        # List access
        rf'args\${re.escape(param_lower)}\b',
        rf'options\${re.escape(param_lower)}\b',
    ]
    
    for pattern in patterns:
        if re.search(pattern, content_lower, re.MULTILINE):
            matches.append(f"R pattern: {pattern}")
    
    # Simple string search as fallback
    if param_lower in content_lower:
        matches.append(f"String match: '{parameter_name}'")
    
    return len(matches) > 0, matches


def search_generic_parameters(content: str, parameter_name: str) -> tuple[bool, List[str]]:
    """Search for parameter using generic patterns for unknown script types.
    
    Returns:
        Tuple of (found, list_of_matched_contexts)
    """
    content_lower = content.lower()
    param_lower = parameter_name.lower()
    
    matches = []
    
    # Generic patterns that might work across languages
    patterns = [
        # Variable assignments (various forms)
        rf'{re.escape(param_lower)}\s*[=:]',
        
        # Command line flags
        rf'--{re.escape(param_lower)}\b',
        rf'-{re.escape(param_lower)}\b',
        
        # Variable usage patterns
        rf'\${re.escape(param_lower)}\b',
        rf'\$\{{{re.escape(param_lower)}',
        
        # Word boundary match
        rf'\b{re.escape(param_lower)}\b',
    ]
    
    for pattern in patterns:
        if re.search(pattern, content_lower, re.MULTILINE):
            matches.append(f"Generic pattern: {pattern}")
    
    return len(matches) > 0, matches


def run_test(script_path: str, shared_context: dict) -> List[LintIssue]:
    """
    Test wrapper script parameter validation.
    
    This test only runs if expected parameters are provided.
    If no expected parameters are provided, the test passes (parameter validation is optional).
    
    Args:
        script_path: Path to wrapper script file
        shared_context: Mutable dict with test context including script_content, script_type, and expected_parameters
        
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
    
    # Get script content and type from previous tests
    script_content = shared_context.get('script_content')
    script_type = shared_context.get('script_type', 'other')
    
    if script_content is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate parameters: script content not available",
            "File validation must pass before parameter validation"
        ))
        return issues
    
    # Search for each parameter based on script type
    found_parameters: Set[str] = set()
    missing_parameters: Set[str] = set()
    
    for param_name in expected_parameters:
        if script_type == 'python':
            found, match_contexts = search_python_parameters(script_content, param_name)
        elif script_type == 'bash':
            found, match_contexts = search_bash_parameters(script_content, param_name)
        elif script_type == 'r':
            found, match_contexts = search_r_parameters(script_content, param_name)
        else:
            found, match_contexts = search_generic_parameters(script_content, param_name)
        
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
                f"Parameter '{param_name}' not found in {script_type.upper()} script",
                f"Expected parameter should appear in script"
            ))
    
    # Summary
    total_params = len(expected_parameters)
    found_count = len(found_parameters)
    missing_count = len(missing_parameters)
    
    if missing_count == 0:
        issues.append(LintIssue(
            "INFO",
            f"All {total_params} expected parameters found in script"
        ))
    else:
        issues.append(LintIssue(
            "INFO",
            f"Parameter validation summary: {found_count}/{total_params} parameters found, {missing_count} missing"
        ))
    
    return issues
