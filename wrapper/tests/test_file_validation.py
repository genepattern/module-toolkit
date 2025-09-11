#!/usr/bin/env python
"""
Test for wrapper script file validation.

This test validates that the script file exists, is readable,
and detects the script type.
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
    """Represents a validation issue found during wrapper script linting."""
    severity: str  # 'ERROR' or 'WARNING' or 'INFO'
    message: str
    context: str | None = None

    def format(self) -> str:
        """Format the issue for human-readable output."""
        context_info = f" ({self.context})" if self.context else ""
        return f"{self.severity}: {self.message}{context_info}"


def detect_script_type(script_path: str, content: str) -> str:
    """Detect the type of script based on file extension, shebang, and content.
    
    Args:
        script_path: Path to the script file
        content: Content of the script file
        
    Returns:
        Detected script type (python, bash, r, shell, other)
    """
    # Check file extension first
    path_lower = script_path.lower()
    
    if path_lower.endswith('.py'):
        return 'python'
    elif path_lower.endswith(('.sh', '.bash')):
        return 'bash'
    elif path_lower.endswith(('.r',)):
        return 'r'
    elif path_lower.endswith(('.pl', '.perl')):
        return 'perl'
    elif path_lower.endswith(('.js', '.javascript')):
        return 'javascript'
    elif path_lower.endswith(('.rb', '.ruby')):
        return 'ruby'
    
    # Check shebang line if no clear extension
    lines = content.split('\n')
    if lines and lines[0].startswith('#!'):
        shebang = lines[0].lower()
        
        if 'python' in shebang:
            return 'python'
        elif any(shell in shebang for shell in ['bash', 'sh', 'zsh', 'ksh']):
            return 'bash'
        elif '/r' in shebang or 'rscript' in shebang:
            return 'r'
        elif 'perl' in shebang:
            return 'perl'
        elif 'node' in shebang or 'javascript' in shebang:
            return 'javascript'
        elif 'ruby' in shebang:
            return 'ruby'
    
    # Content-based detection as fallback
    content_lower = content.lower()
    
    # Python indicators
    python_indicators = ['import ', 'from ', 'def ', 'class ', 'if __name__', 'print(']
    if any(indicator in content_lower for indicator in python_indicators):
        return 'python'
    
    # Bash/shell indicators
    bash_indicators = ['#!/bin/bash', '#!/bin/sh', 'echo ', '$1', '${', 'do\n', 'fi\n']
    if any(indicator in content_lower for indicator in bash_indicators):
        return 'bash'
    
    # R indicators
    r_indicators = ['library(', 'source(', '<-', 'args <-', 'commandargs(']
    if any(indicator in content_lower for indicator in r_indicators):
        return 'r'
    
    return 'other'


def check_file_permissions(script_path: str) -> tuple[bool, str]:
    """Check if the script file has appropriate permissions.
    
    Returns:
        Tuple of (is_executable, permission_info)
    """
    try:
        stat_info = os.stat(script_path)
        is_executable = stat_info.st_mode & 0o111 != 0  # Check if any execute bit is set
        
        # Format permissions in octal
        permissions = oct(stat_info.st_mode)[-3:]
        
        return is_executable, f"Permissions: {permissions}"
    except Exception as e:
        return False, f"Could not check permissions: {str(e)}"


def run_test(script_path: str, shared_context: dict) -> List[LintIssue]:
    """
    Test wrapper script file validation.
    
    Args:
        script_path: Path to wrapper script file
        shared_context: Mutable dict with test context
        
    Returns:
        List of LintIssue objects for any file validation failures
    """
    issues: List[LintIssue] = []
    
    # Check if file exists
    if not os.path.exists(script_path):
        issues.append(LintIssue(
            "ERROR",
            f"Script file does not exist: {script_path}"
        ))
        return issues
    
    # Check if it's a regular file
    if not os.path.isfile(script_path):
        issues.append(LintIssue(
            "ERROR",
            f"Path is not a regular file: {script_path}"
        ))
        return issues
    
    # Try to read the file
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Try with different encoding
        try:
            with open(script_path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            issues.append(LintIssue(
                "ERROR",
                f"Failed to read script file: {str(e)}"
            ))
            return issues
    except PermissionError:
        issues.append(LintIssue(
            "ERROR",
            f"Permission denied reading script file: {script_path}"
        ))
        return issues
    except Exception as e:
        issues.append(LintIssue(
            "ERROR",
            f"Failed to read script file: {str(e)}"
        ))
        return issues
    
    # Store content in shared context for other tests
    shared_context['script_content'] = content
    
    # Check if file is empty
    if not content.strip():
        issues.append(LintIssue(
            "ERROR",
            "Script file is empty"
        ))
        return issues
    
    # Detect script type
    script_type = detect_script_type(script_path, content)
    shared_context['script_type'] = script_type
    
    issues.append(LintIssue(
        "INFO",
        f"Detected script type: {script_type.upper()}"
    ))
    
    # Check file permissions
    is_executable, perm_info = check_file_permissions(script_path)
    
    if not is_executable:
        issues.append(LintIssue(
            "WARNING",
            f"Script file is not executable ({perm_info})",
            "Consider setting execute permissions with: chmod +x " + script_path
        ))
    else:
        issues.append(LintIssue(
            "INFO",
            f"Script file is executable ({perm_info})"
        ))
    
    # Basic content analysis
    lines = content.split('\n')
    line_count = len(lines)
    non_empty_lines = len([line for line in lines if line.strip()])
    
    issues.append(LintIssue(
        "INFO",
        f"Script contains {line_count} lines ({non_empty_lines} non-empty)"
    ))
    
    # Check for shebang
    if lines and lines[0].startswith('#!'):
        issues.append(LintIssue(
            "INFO",
            f"Found shebang: {lines[0]}"
        ))
    elif script_type in ['python', 'bash', 'r']:
        issues.append(LintIssue(
            "WARNING",
            f"No shebang found in {script_type.upper()} script",
            f"Consider adding appropriate shebang line"
        ))
    
    return issues
