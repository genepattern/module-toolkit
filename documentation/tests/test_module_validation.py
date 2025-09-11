#!/usr/bin/env python
"""
Test for documentation module validation.

This test validates that the documentation mentions the expected
module name if provided.
"""
from __future__ import annotations

import sys
import os
import re
from typing import List
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


def search_module_in_content(content: str, module_name: str) -> tuple[bool, List[str]]:
    """Search for module name in content with various patterns.
    
    Returns:
        Tuple of (found, list_of_matched_contexts)
    """
    if not content or not module_name:
        return False, []
    
    content_lower = content.lower()
    module_lower = module_name.lower()
    
    matches = []
    
    # Exact case-sensitive match
    if module_name in content:
        matches.append(f"Exact match: '{module_name}'")
    
    # Case-insensitive match
    elif module_lower in content_lower:
        matches.append(f"Case-insensitive match for '{module_name}'")
    
    # Pattern matching for common module name formats
    patterns = [
        # Module name with common prefixes/suffixes
        rf'\b{re.escape(module_lower)}\b',  # Word boundary match
        rf'{re.escape(module_lower)}\.py',   # Python module file
        rf'{re.escape(module_lower)}\.jar',  # Java module
        rf'module\s+{re.escape(module_lower)}',  # "module ModuleName"
        rf'{re.escape(module_lower)}\s+module',  # "ModuleName module"
        rf'class\s+{re.escape(module_lower)}',   # "class ModuleName"
    ]
    
    for pattern in patterns:
        if re.search(pattern, content_lower, re.IGNORECASE):
            matches.append(f"Pattern match: {pattern}")
    
    # LSID pattern matching if module name looks like an LSID
    if ':' in module_name and 'urn:lsid:' in module_name.lower():
        # Extract the last part of LSID as potential module identifier
        lsid_parts = module_name.split(':')
        if len(lsid_parts) >= 5:
            module_id = lsid_parts[-1]
            if module_id.lower() in content_lower:
                matches.append(f"LSID module identifier match: '{module_id}'")
    
    return len(matches) > 0, matches


def run_test(doc_path_or_url: str, shared_context: dict) -> List[LintIssue]:
    """
    Test documentation module validation.
    
    This test only runs if an expected module name is provided.
    If no expected module is provided, the test passes (module validation is optional).
    
    Args:
        doc_path_or_url: Path to documentation file or URL
        shared_context: Mutable dict with test context including doc_content and expected_module
        
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
    
    # Get processed content from content retrieval test
    doc_content = shared_context.get('doc_content')
    if doc_content is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate module: document content not available",
            "Content retrieval must pass before module validation"
        ))
        return issues
    
    # Search for module name in content
    found, match_contexts = search_module_in_content(doc_content, expected_module)
    
    if not found:
        issues.append(LintIssue(
            "ERROR",
            f"Module name '{expected_module}' not found in documentation",
            "Module should be mentioned in the documentation"
        ))
    else:
        # Report successful matches
        for match_context in match_contexts:
            issues.append(LintIssue(
                "INFO",
                f"Module found: {match_context}"
            ))
    
    return issues
