#!/usr/bin/env python
"""
Test for basic paramgroups.json file validation.

This test validates basic file existence, type, and JSON parsing
for paramgroups.json files.
"""
from __future__ import annotations

import sys
import os
import json
from typing import List
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
    Test basic paramgroups.json file validation.
    
    Args:
        paramgroups_path: Path to the paramgroups.json file
        shared_context: Mutable dict with test context
        
    Returns:
        List of LintIssue objects for any validation failures
    """
    issues: List[LintIssue] = []
    
    # Resolve absolute path for consistent handling
    paramgroups_path = os.path.abspath(paramgroups_path)
    
    # Check file existence
    if not os.path.exists(paramgroups_path):
        issues.append(LintIssue(
            "ERROR",
            f"Paramgroups file does not exist: {paramgroups_path}"
        ))
        return issues
    
    # Check that it's a regular file
    if not os.path.isfile(paramgroups_path):
        issues.append(LintIssue(
            "ERROR", 
            f"Path is not a regular file: {paramgroups_path}"
        ))
        return issues
    
    # Check filename (should be 'paramgroups.json')
    filename = os.path.basename(paramgroups_path)
    if filename != "paramgroups.json":
        issues.append(LintIssue(
            "WARNING",
            f"Paramgroups file has non-standard name: {filename}",
            "Expected 'paramgroups.json'"
        ))
    
    # Check file is readable and valid JSON
    try:
        with open(paramgroups_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Basic content validation
        if not content.strip():
            issues.append(LintIssue(
                "ERROR",
                "Paramgroups file is empty"
            ))
            return issues
        
        # Parse JSON
        try:
            data = json.loads(content)
            # Store parsed data for other tests
            shared_context['parsed_data'] = data
            
        except json.JSONDecodeError as e:
            issues.append(LintIssue(
                "ERROR",
                f"Invalid JSON format: {str(e)}"
            ))
            return issues
            
    except PermissionError:
        issues.append(LintIssue(
            "ERROR",
            f"Cannot read paramgroups file: Permission denied"
        ))
    except UnicodeDecodeError:
        issues.append(LintIssue(
            "ERROR",
            f"Paramgroups file contains invalid UTF-8 encoding"
        ))
    except Exception as e:
        issues.append(LintIssue(
            "ERROR",
            f"Failed to read paramgroups file: {str(e)}"
        ))
    
    return issues
