#!/usr/bin/env python
"""
Test for Docker image build validation.

This test validates that a Dockerfile can be successfully built
into a Docker image.
"""
from __future__ import annotations

import sys
import os
import time
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
    Test Docker image build validation.
    
    Args:
        dockerfile_path: Path to the Dockerfile to build
        shared_context: Mutable dict with test context (tag, cleanup, etc.)
        
    Returns:
        List of LintIssue objects for any build failures
    """
    issues: List[LintIssue] = []
    
    # Get build parameters from CLI arguments
    tag = shared_context.get('tag')  # User-provided tag or None
    cleanup = shared_context.get('cleanup', True)
    
    dockerfile_path = os.path.abspath(dockerfile_path)
    context_dir = os.path.dirname(dockerfile_path) or "."
    
    # Generate a tag if not supplied
    if not tag:
        base = os.path.basename(context_dir) or "dockerfile-test"
        ts = time.strftime("%Y%m%d-%H%M%S")
        tag = f"gpmod/{base}:{ts}"
    
    # Store tag for potential cleanup or subsequent tests
    # This is important for runtime validation which needs the built image tag
    
    # Build command
    cmd = [
        "docker", "build",
        "-t", tag,
        "-f", dockerfile_path,
        context_dir,
    ]
    
    try:
        res = run(cmd, cwd=context_dir)
        
        if res.returncode != 0:
            issues.append(LintIssue(
                "ERROR",
                f"Docker build failed for {dockerfile_path}",
                f"Build command: {res.cmd}"
            ))
            
            # Parse and add specific build errors
            if res.stderr.strip():
                # Extract meaningful error from Docker output
                error_lines = res.stderr.strip().split('\\n')
                for line in error_lines:
                    if 'ERROR' in line.upper() or 'failed' in line.lower():
                        issues.append(LintIssue(
                            "ERROR",
                            f"Build error: {line.strip()}"
                        ))
                        
            # If no specific errors found, add full output
            if len(issues) == 1:  # Only the main error so far
                full_output = res.stderr.strip() or res.stdout.strip()
                if full_output:
                    issues.append(LintIssue(
                        "ERROR",
                        f"Full build output: {full_output[:500]}..." if len(full_output) > 500 else full_output
                    ))
        else:
            # Build succeeded - store state for dependent tests
            shared_context['build_success'] = True
            shared_context['built_tag'] = tag
            
            # Add cleanup logic if requested and no runtime command provided
            if cleanup and not shared_context.get('command'):
                try:
                    cleanup_res = run(["docker", "rmi", tag])
                    if cleanup_res.returncode == 0:
                        issues.append(LintIssue(
                            "INFO",
                            f"Cleaned up Docker image: {tag}"
                        ))
                except:
                    # Cleanup failure is not critical
                    pass
            
    except FileNotFoundError:
        issues.append(LintIssue(
            "ERROR",
            "Docker CLI not found",
            "Ensure Docker Desktop/Engine is installed and docker is on PATH"
        ))
    except Exception as e:
        issues.append(LintIssue(
            "ERROR",
            f"Failed to run Docker build: {str(e)}"
        ))
    
    return issues
