#!/usr/bin/env python
"""
Test for basic GPUnit file validation.

This test validates basic file existence, extension, and YAML parsing
for GPUnit files.
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

# Import YAML with safe fallback
try:
    import yaml
except ImportError:
    yaml = None


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
    Test basic GPUnit file validation.
    
    Args:
        gpunit_path: Path to the GPUnit file
        shared_context: Mutable dict with test context
        
    Returns:
        List of LintIssue objects for any validation failures
    """
    issues: List[LintIssue] = []
    
    # Check if YAML library is available
    if yaml is None:
        issues.append(LintIssue(
            "ERROR",
            "PyYAML library not available - install with: pip install PyYAML"
        ))
        return issues
    
    # Resolve absolute path for consistent handling
    gpunit_path = os.path.abspath(gpunit_path)
    
    # Check file existence
    if not os.path.exists(gpunit_path):
        issues.append(LintIssue(
            "ERROR",
            f"GPUnit file does not exist: {gpunit_path}"
        ))
        return issues
    
    # Check that it's a regular file
    if not os.path.isfile(gpunit_path):
        issues.append(LintIssue(
            "ERROR", 
            f"Path is not a regular file: {gpunit_path}"
        ))
        return issues
    
    # Check filename extension (should end with .yml)
    filename = os.path.basename(gpunit_path)
    if not filename.endswith('.yml'):
        issues.append(LintIssue(
            "WARNING",
            f"GPUnit file should end with .yml extension: {filename}",
            "Expected *.yml"
        ))
    
    # Check file is readable and valid YAML
    try:
        with open(gpunit_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Basic content validation
        if not content.strip():
            issues.append(LintIssue(
                "ERROR",
                "GPUnit file is empty"
            ))
            return issues
        
        # Parse YAML
        try:
            data = yaml.safe_load(content)
            # Store parsed data for other tests
            shared_context['parsed_data'] = data
            shared_context['file_content'] = content
            
            # Basic data type check
            if data is None:
                issues.append(LintIssue(
                    "ERROR",
                    "GPUnit file contains no valid YAML data"
                ))
                return issues
            
        except yaml.YAMLError as e:
            issues.append(LintIssue(
                "ERROR",
                f"Invalid YAML format: {str(e)}"
            ))
            return issues
            
    except PermissionError:
        issues.append(LintIssue(
            "ERROR",
            f"Cannot read GPUnit file: Permission denied"
        ))
    except UnicodeDecodeError:
        issues.append(LintIssue(
            "ERROR",
            f"GPUnit file contains invalid UTF-8 encoding"
        ))
    except Exception as e:
        issues.append(LintIssue(
            "ERROR",
            f"Failed to read GPUnit file: {str(e)}"
        ))
    
    return issues
