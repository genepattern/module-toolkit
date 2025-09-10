#!/usr/bin/env python
"""
Test for Docker CLI availability.

This test validates that Docker is installed and accessible
for building and running containers.
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
    from dockerfile.linter import run, CmdResult
except ImportError:
    try:
        from linter import run, CmdResult  
    except ImportError:
        # Define minimal classes if can't import
        class CmdResult:
            pass
        def run(cmd, **kwargs):
            import subprocess
            result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
            return type('CmdResult', (), {
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'cmd': ' '.join(cmd),
                'cwd': kwargs.get('cwd', os.getcwd())
            })()


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
    Test Docker CLI availability.
    
    Args:
        dockerfile_path: Path to the Dockerfile (unused but required for interface)
        shared_context: Mutable dict with test context (unused)
        
    Returns:
        List of LintIssue objects for any Docker availability issues
    """
    issues: List[LintIssue] = []
    
    try:
        # Check if docker command is available
        res = run(["docker", "version", "--format", "{{.Server.Version}}"])
        
        if res.returncode != 0:
            issues.append(LintIssue(
                "ERROR",
                "Docker daemon is not running or accessible",
                f"Command failed with exit code {res.returncode}"
            ))
            
            # Add specific error details if available
            if res.stderr.strip():
                issues.append(LintIssue(
                    "ERROR",
                    f"Docker error: {res.stderr.strip()}"
                ))
                
    except FileNotFoundError:
        issues.append(LintIssue(
            "ERROR",
            "Docker CLI not found",
            "Ensure Docker Desktop/Engine is installed and 'docker' is on PATH"
        ))
    except Exception as e:
        issues.append(LintIssue(
            "ERROR",
            f"Failed to check Docker availability: {str(e)}"
        ))
    
    return issues
