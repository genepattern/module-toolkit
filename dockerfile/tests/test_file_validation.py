#!/usr/bin/env python
"""
Test for basic Dockerfile file validation.

This test validates basic file existence, type, and naming requirements
for Dockerfile files.
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

# Import will work if this is run as a module or standalone
try:
    from dockerfile.linter import CmdResult
except ImportError:
    try:
        from linter import CmdResult  
    except ImportError:
        # Define a minimal CmdResult if can't import
        class CmdResult:
            pass


@dataclass
class LintIssue:
    """Represents a validation issue found during Dockerfile linting."""
    severity: str  # 'ERROR' or 'WARNING'
    message: str
    context: str | None = None

    def format(self) -> str:
        """Format the issue for human-readable output."""
        context_info = f" ({self.context})" if self.context else ""
        return f"{self.severity}: {self.message}{context_info}"


def run_test(dockerfile_path: str, shared_context: dict) -> List[LintIssue]:
    """
    Test basic Dockerfile file validation.
    
    Args:
        dockerfile_path: Path to the Dockerfile
        shared_context: Mutable dict with test context (unused for file validation)
        
    Returns:
        List of LintIssue objects for any validation failures
    """
    issues: List[LintIssue] = []
    
    # Resolve absolute path for consistent handling
    dockerfile_path = os.path.abspath(dockerfile_path)
    
    # Check file existence
    if not os.path.exists(dockerfile_path):
        issues.append(LintIssue(
            "ERROR",
            f"Dockerfile does not exist: {dockerfile_path}"
        ))
        return issues
    
    # Check that it's a regular file
    if not os.path.isfile(dockerfile_path):
        issues.append(LintIssue(
            "ERROR", 
            f"Path is not a regular file: {dockerfile_path}"
        ))
        return issues
    
    # Check filename (should be 'Dockerfile' or have .dockerfile extension)
    filename = os.path.basename(dockerfile_path)
    if not (filename == "Dockerfile" or filename.endswith(".dockerfile")):
        issues.append(LintIssue(
            "WARNING",
            f"Dockerfile has non-standard name: {filename}",
            "Expected 'Dockerfile' or '*.dockerfile'"
        ))
    
    # Check file is readable
    try:
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Basic content validation
        if not content.strip():
            issues.append(LintIssue(
                "ERROR",
                "Dockerfile is empty"
            ))
        else:
            # Check that the first non-comment, non-empty line is FROM
            lines = content.split('\n')
            first_instruction = None
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    first_instruction = stripped
                    break
            
            if first_instruction is None:
                issues.append(LintIssue(
                    "ERROR",
                    "Dockerfile contains no instructions"
                ))
            elif not first_instruction.upper().startswith('FROM'):
                issues.append(LintIssue(
                    "ERROR",
                    "Dockerfile must start with FROM instruction as first non-comment line"
                ))
            
    except PermissionError:
        issues.append(LintIssue(
            "ERROR",
            f"Cannot read Dockerfile: Permission denied"
        ))
    except UnicodeDecodeError:
        issues.append(LintIssue(
            "ERROR",
            f"Dockerfile contains invalid UTF-8 encoding"
        ))
    except Exception as e:
        issues.append(LintIssue(
            "ERROR",
            f"Failed to read Dockerfile: {str(e)}"
        ))
    
    return issues
