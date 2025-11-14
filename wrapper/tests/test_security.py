#!/usr/bin/env python
"""
Test for wrapper script security validation.

This test checks for common security issues in wrapper scripts, including
command injection vulnerabilities, unsafe file operations, and other security concerns.
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


def check_python_security(content: str) -> tuple[List[str], List[str]]:
    """Check for security issues in Python scripts.

    Returns:
        Tuple of (security_issues, safe_patterns_found)
    """
    security_issues = []
    safe_patterns = []

    # Check for shell=True in subprocess (potential command injection)
    if re.search(r'subprocess\.(run|call|Popen)\s*\([^)]*shell\s*=\s*True', content):
        security_issues.append("subprocess with shell=True (command injection risk)")

    # Check for safe subprocess usage
    if re.search(r'subprocess\.(run|call|Popen)\s*\(\s*\[', content):
        safe_patterns.append("Using subprocess with list arguments (safe)")

    # Check for eval/exec usage (code injection)
    if re.search(r'\beval\s*\(', content):
        security_issues.append("eval() usage (code injection risk)")

    if re.search(r'\bexec\s*\(', content):
        security_issues.append("exec() usage (code injection risk)")

    # Check for unsafe pickle usage
    if re.search(r'pickle\.loads?\s*\(', content):
        security_issues.append("pickle.load() usage (arbitrary code execution risk)")

    # Check for os.system (unsafe)
    if re.search(r'os\.system\s*\(', content):
        security_issues.append("os.system() usage (command injection risk)")

    # Check for unsafe file operations
    if re.search(r'open\s*\([^)]*\+["\']', content):
        security_issues.append("File opened in read+write mode (potential security risk)")

    # Check for path traversal protection
    if re.search(r'os\.path\.abspath|os\.path\.realpath', content):
        safe_patterns.append("Path normalization used (prevents traversal attacks)")

    # Check for input sanitization
    if re.search(r'shlex\.quote|re\.escape', content):
        safe_patterns.append("Input sanitization found")

    # Check for hardcoded credentials (basic check)
    if re.search(r'password\s*=\s*["\'](?!.*\$|.*%s)[^"\']{8,}["\']', content, re.IGNORECASE):
        security_issues.append("Possible hardcoded password")

    if re.search(r'api[_-]?key\s*=\s*["\'](?!.*\$|.*%s)[^"\']{16,}["\']', content, re.IGNORECASE):
        security_issues.append("Possible hardcoded API key")

    return security_issues, safe_patterns


def check_bash_security(content: str) -> tuple[List[str], List[str]]:
    """Check for security issues in Bash scripts.

    Returns:
        Tuple of (security_issues, safe_patterns_found)
    """
    security_issues = []
    safe_patterns = []

    # Check for unquoted variables (command injection risk)
    unquoted_vars = re.findall(r'(?<!["\'])\$\w+(?!["\'])', content)
    if len(unquoted_vars) > 5:  # Some tolerance for simple cases
        security_issues.append(f"Many unquoted variables ({len(unquoted_vars)} found) - injection risk")

    # Check for eval usage
    if re.search(r'\beval\s+', content):
        security_issues.append("eval usage (code injection risk)")

    # Check for safe variable quoting
    quoted_vars = re.findall(r'"\$\w+"', content)
    if len(quoted_vars) > 5:
        safe_patterns.append(f"Good variable quoting ({len(quoted_vars)} quoted variables)")

    # Check for ${var} usage (safer)
    if re.search(r'\$\{[^}]+\}', content):
        safe_patterns.append("Using ${var} syntax")

    # Check for command substitution without quoting
    if re.search(r'\$\(\s*[^)]+\s*\)(?!["\'"])', content):
        security_issues.append("Unquoted command substitution")

    # Check for dangerous commands
    if re.search(r'\brm\s+-rf\s+/(?!\w)', content):
        security_issues.append("Dangerous rm -rf on root paths")

    # Check for set -u (undefined variable protection)
    if re.search(r'set\s+-u|set\s+-[a-z]*u', content):
        safe_patterns.append("Using set -u (undefined variable protection)")

    # Check for input validation before using in commands
    if re.search(r'if\s+\[\[.*\]\]\s*;\s*then', content):
        safe_patterns.append("Conditional validation before execution")

    return security_issues, safe_patterns


def check_r_security(content: str) -> tuple[List[str], List[str]]:
    """Check for security issues in R scripts.

    Returns:
        Tuple of (security_issues, safe_patterns_found)
    """
    security_issues = []
    safe_patterns = []

    # Check for eval/parse usage (code injection)
    if re.search(r'\beval\s*\(', content):
        security_issues.append("eval() usage (code injection risk)")

    if re.search(r'\bparse\s*\([^)]*text\s*=', content):
        security_issues.append("parse() with text argument (code injection risk)")

    # Check for system() calls
    if re.search(r'\bsystem\s*\(', content):
        security_issues.append("system() call (command injection risk)")

    if re.search(r'\bsystem2\s*\(', content):
        safe_patterns.append("Using system2() instead of system()")

    # Check for source() with user input
    if re.search(r'\bsource\s*\([^)]*paste|sprintf', content):
        security_issues.append("source() with dynamic path (code injection risk)")

    # Check for load() without validation
    if re.search(r'\bload\s*\(', content):
        security_issues.append("load() usage (arbitrary code execution risk)")

    # Check for safe file operations
    if re.search(r'file\.exists\s*\(', content):
        safe_patterns.append("File existence validation")

    # Check for path sanitization
    if re.search(r'normalizePath|path\.expand', content):
        safe_patterns.append("Path normalization used")

    # Check for hardcoded credentials
    if re.search(r'password\s*<-\s*["\'][^"\']{8,}["\']', content, re.IGNORECASE):
        security_issues.append("Possible hardcoded password")

    return security_issues, safe_patterns


def run_test(script_path: str, shared_context: dict) -> List[LintIssue]:
    """
    Test wrapper script security.

    This test checks for common security vulnerabilities and unsafe patterns
    in wrapper scripts.

    Args:
        script_path: Path to wrapper script file
        shared_context: Mutable dict with test context including script_content and script_type

    Returns:
        List of LintIssue objects for security assessment
    """
    issues: List[LintIssue] = []

    # Get script content and type from previous tests
    script_content = shared_context.get('script_content')
    script_type = shared_context.get('script_type')

    if script_content is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate security: script content not available",
            "File validation must pass before security check"
        ))
        return issues

    if script_type is None:
        issues.append(LintIssue(
            "WARNING",
            "Cannot determine script type for security check"
        ))
        return issues

    # Check for security issues based on script type
    security_issues = []
    safe_patterns = []

    if script_type == 'python':
        security_issues, safe_patterns = check_python_security(script_content)
    elif script_type == 'bash':
        security_issues, safe_patterns = check_bash_security(script_content)
    elif script_type == 'r':
        security_issues, safe_patterns = check_r_security(script_content)
    else:
        # Generic security checks
        if re.search(r'\beval\s*\(', script_content):
            security_issues.append("eval() usage detected")
        if re.search(r'\bexec\s*\(', script_content):
            security_issues.append("exec() usage detected")

    # Store security info in context
    shared_context['security_issues'] = security_issues
    shared_context['security_safe_patterns'] = safe_patterns

    # Report security issues
    if security_issues:
        for issue in security_issues:
            issues.append(LintIssue(
                "WARNING",
                f"Security concern: {issue}",
                "Review and mitigate potential security risks"
            ))

    # Report safe patterns
    if safe_patterns:
        issues.append(LintIssue(
            "INFO",
            f"Found {len(safe_patterns)} secure coding pattern(s)"
        ))

    # Overall security assessment
    if not security_issues and safe_patterns:
        issues.append(LintIssue(
            "INFO",
            "No obvious security issues detected, good security practices found"
        ))
    elif not security_issues:
        issues.append(LintIssue(
            "INFO",
            "No obvious security issues detected"
        ))

    return issues

