#!/usr/bin/env python
"""
Test for Docker container runtime validation.

This test validates that a built Docker image can successfully
run commands in a container environment.
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
    Test Docker container runtime validation.
    
    This test only runs if a command is provided via --cmd argument.
    If no command is provided, the test passes (runtime testing is optional).
    
    Args:
        dockerfile_path: Path to the Dockerfile (for context)
        shared_context: Mutable dict with test context (tag, command, build_success, etc.)
        
    Returns:
        List of LintIssue objects for any runtime failures
    """
    issues: List[LintIssue] = []
    
    # Get runtime parameters
    command = shared_context.get('command')
    
    # If no command provided, runtime testing is optional - just pass
    if command is None:
        issues.append(LintIssue(
            "INFO",
            "Runtime testing skipped - no command provided",
            "Use --cmd to enable runtime validation"
        ))
        return issues
    
    # Check if build was successful (dependency on build validation)
    # Only fail if build explicitly failed
    if shared_context.get('build_success') is False:
        issues.append(LintIssue(
            "ERROR",
            "Cannot test runtime: Docker build failed",
            "Build validation must pass before runtime testing"
        ))
        return issues
    
    # Get the built image tag
    tag = shared_context.get('built_tag')
    
    if not tag:
        issues.append(LintIssue(
            "ERROR",
            "Cannot test runtime: No Docker tag available",
            "Build validation must provide a tag for runtime testing"
        ))
        return issues
    
    # Run command inside a shell for broader command compatibility.
    # We set entrypoint to 'sh' to avoid image CMD/ENTRYPOINT interference.
    # Note: If the image does not include a POSIX shell, this will fail and report accordingly.
    cmd = [
        "docker", "run", "--rm", "--entrypoint", "sh", tag, "-lc", command,
    ]
    
    try:
        res = run(cmd)
        
        if res.returncode != 0:
            issues.append(LintIssue(
                "ERROR",
                f"Container runtime failed for command: {command}",
                f"Run command: {res.cmd}"
            ))
            
            # Parse and add specific runtime errors
            if res.stderr.strip():
                error_lines = res.stderr.strip().split('\\n')
                for line in error_lines:
                    if 'error' in line.lower() or 'failed' in line.lower():
                        issues.append(LintIssue(
                            "ERROR",
                            f"Runtime error: {line.strip()}"
                        ))
                        
            # If container can't find shell, suggest alternative
            if 'executable file not found' in res.stderr.lower() and 'sh' in res.stderr:
                issues.append(LintIssue(
                    "ERROR",
                    "Container does not have POSIX shell (sh)",
                    "Image may be based on scratch or distroless - cannot run shell commands"
                ))
            
            # If no specific errors found, add output sample
            if len(issues) == 1:  # Only the main error so far
                full_output = res.stderr.strip() or res.stdout.strip()
                if full_output:
                    issues.append(LintIssue(
                        "ERROR",
                        f"Runtime output: {full_output[:300]}..." if len(full_output) > 300 else full_output
                    ))
        else:
            # Runtime test succeeded
            # Log successful output
            output = res.stdout.strip()
            if output:
                issues.append(LintIssue(
                    "INFO",
                    f"Runtime test output: {output}",
                    f"Command: {command}"
                ))
                    
    except FileNotFoundError:
        issues.append(LintIssue(
            "ERROR",
            "Docker CLI not found",
            "Ensure Docker Desktop/Engine is installed and docker is on PATH"
        ))
    except Exception as e:
        issues.append(LintIssue(
            "ERROR",
            f"Failed to run container: {str(e)}"
        ))
    
    return issues
