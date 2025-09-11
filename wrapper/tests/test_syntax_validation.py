#!/usr/bin/env python
"""
Test for wrapper script syntax validation.

This test validates Python syntax if the script is detected as Python.
For other script types, it performs basic syntax checks where possible.
"""
from __future__ import annotations

import sys
import os
import ast
import re
import subprocess
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


def validate_python_syntax(content: str) -> tuple[bool, str]:
    """Validate Python syntax using AST parsing.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        ast.parse(content)
        return True, ""
    except SyntaxError as e:
        error_msg = f"Line {e.lineno}: {e.msg}"
        if e.text:
            error_msg += f" ('{e.text.strip()}')"
        return False, error_msg
    except Exception as e:
        return False, f"Parse error: {str(e)}"


def validate_bash_syntax(script_path: str) -> tuple[bool, str]:
    """Validate Bash syntax using bash -n (dry run).
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Use bash -n to check syntax without executing
        result = subprocess.run(
            ['bash', '-n', script_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return True, ""
        else:
            return False, result.stderr.strip()
            
    except subprocess.TimeoutExpired:
        return False, "Syntax check timed out"
    except FileNotFoundError:
        return False, "bash command not found - cannot validate bash syntax"
    except Exception as e:
        return False, f"Syntax check failed: {str(e)}"


def validate_r_syntax(script_path: str) -> tuple[bool, str]:
    """Validate R syntax using Rscript --slave -e 'parse(file="script")'.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Use R to parse the script without executing
        result = subprocess.run([
            'Rscript', '--slave', '-e', 
            f'tryCatch(parse(file="{script_path}"), error=function(e) cat("ERROR:", e$message, "\\n"))'
        ], capture_output=True, text=True, timeout=10)
        
        if "ERROR:" in result.stdout:
            return False, result.stdout.replace("ERROR:", "").strip()
        elif result.returncode == 0:
            return True, ""
        else:
            return False, result.stderr.strip() if result.stderr else "Unknown R syntax error"
            
    except subprocess.TimeoutExpired:
        return False, "R syntax check timed out"
    except FileNotFoundError:
        return False, "Rscript command not found - cannot validate R syntax"
    except Exception as e:
        return False, f"R syntax check failed: {str(e)}"


def check_basic_syntax_issues(content: str, script_type: str) -> List[str]:
    """Check for basic syntax issues common across script types.
    
    Returns:
        List of potential syntax issues
    """
    issues = []
    lines = content.split('\n')
    
    # Check for common syntax issues
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        
        if not line_stripped:
            continue
            
        # Check for unmatched quotes (basic)
        single_quotes = line_stripped.count("'") - line_stripped.count("\\'")
        double_quotes = line_stripped.count('"') - line_stripped.count('\\"')
        
        if single_quotes % 2 != 0:
            issues.append(f"Line {i}: Potential unmatched single quote")
        if double_quotes % 2 != 0:
            issues.append(f"Line {i}: Potential unmatched double quote")
        
        # Check for unmatched parentheses/brackets (basic)
        parens = line_stripped.count('(') - line_stripped.count(')')
        brackets = line_stripped.count('[') - line_stripped.count(']')
        braces = line_stripped.count('{') - line_stripped.count('}')
        
        if parens != 0:
            issues.append(f"Line {i}: Unmatched parentheses")
        if brackets != 0:
            issues.append(f"Line {i}: Unmatched brackets")
        if braces != 0:
            issues.append(f"Line {i}: Unmatched braces")
    
    return issues


def run_test(script_path: str, shared_context: dict) -> List[LintIssue]:
    """
    Test wrapper script syntax validation.
    
    This test only performs detailed syntax validation for Python scripts.
    For other script types, it attempts basic validation where possible.
    
    Args:
        script_path: Path to wrapper script file
        shared_context: Mutable dict with test context including script_content and script_type
        
    Returns:
        List of LintIssue objects for any syntax validation failures
    """
    issues: List[LintIssue] = []
    
    # Get script content and type from file validation test
    script_content = shared_context.get('script_content')
    script_type = shared_context.get('script_type')
    
    if script_content is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot validate syntax: script content not available",
            "File validation must pass before syntax validation"
        ))
        return issues
    
    if script_type is None:
        issues.append(LintIssue(
            "WARNING",
            "Cannot determine script type for syntax validation"
        ))
        return issues
    
    # Perform syntax validation based on script type
    if script_type == 'python':
        is_valid, error_msg = validate_python_syntax(script_content)
        
        if is_valid:
            issues.append(LintIssue(
                "INFO",
                "Python syntax is valid"
            ))
        else:
            issues.append(LintIssue(
                "ERROR",
                f"Python syntax error: {error_msg}"
            ))
            
    elif script_type == 'bash':
        is_valid, error_msg = validate_bash_syntax(script_path)
        
        if is_valid:
            issues.append(LintIssue(
                "INFO",
                "Bash syntax is valid"
            ))
        elif "not found" in error_msg:
            issues.append(LintIssue(
                "WARNING",
                f"Could not validate bash syntax: {error_msg}"
            ))
        else:
            issues.append(LintIssue(
                "ERROR",
                f"Bash syntax error: {error_msg}"
            ))
            
    elif script_type == 'r':
        is_valid, error_msg = validate_r_syntax(script_path)
        
        if is_valid:
            issues.append(LintIssue(
                "INFO",
                "R syntax is valid"
            ))
        elif "not found" in error_msg:
            issues.append(LintIssue(
                "WARNING",
                f"Could not validate R syntax: {error_msg}"
            ))
        else:
            issues.append(LintIssue(
                "ERROR",
                f"R syntax error: {error_msg}"
            ))
            
    else:
        # For other script types, perform basic syntax checks
        issues.append(LintIssue(
            "INFO",
            f"Syntax validation for {script_type.upper()} scripts not fully supported",
            "Performing basic syntax checks only"
        ))
        
        basic_issues = check_basic_syntax_issues(script_content, script_type)
        for basic_issue in basic_issues:
            issues.append(LintIssue(
                "WARNING",
                f"Potential syntax issue: {basic_issue}"
            ))
        
        if not basic_issues:
            issues.append(LintIssue(
                "INFO",
                "No obvious syntax issues found in basic check"
            ))
    
    return issues
