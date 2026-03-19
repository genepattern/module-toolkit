#!/usr/bin/env python
"""
Test for Docker image build validation.

This test validates that a Dockerfile can be successfully built
into a Docker image.
"""
from __future__ import annotations

import json
import platform as _platform
import re
import subprocess
import sys
import os
import time
from typing import List, Optional
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


def _parse_from_image(dockerfile_path: str) -> Optional[str]:
    """Return the base image name from the first FROM instruction."""
    try:
        with open(dockerfile_path) as f:
            for line in f:
                m = re.match(r'^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)', line, re.IGNORECASE)
                if m and m.group(1).lower() != 'scratch':
                    return m.group(1)
    except Exception:
        pass
    return None


def _detect_required_platform(from_image: str) -> Optional[str]:
    """Return the --platform value needed to build from_image on this host, or None.

    Uses `docker manifest inspect` to find what platforms the image supports.
    If the host is ARM64 and the image only offers linux/amd64, returns 'linux/amd64'
    so Docker doesn't hang trying to emulate the wrong architecture silently.
    Falls back gracefully if manifest inspection fails.
    """
    machine = _platform.machine().lower()
    host_is_arm = 'arm' in machine or 'aarch' in machine
    host_platform = 'linux/arm64' if host_is_arm else 'linux/amd64'

    try:
        result = subprocess.run(
            ['docker', 'manifest', 'inspect', from_image],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return None
        manifest = json.loads(result.stdout)
        supported = set()
        for entry in manifest.get('manifests', []):
            p = entry.get('platform', {})
            arch = p.get('architecture', '')
            os_ = p.get('os', 'linux')
            if arch == 'amd64':
                supported.add('linux/amd64')
            elif arch in ('arm64', 'arm'):
                supported.add('linux/arm64')
        if not supported:
            return None
        if host_platform not in supported and 'linux/amd64' in supported:
            return 'linux/amd64'
    except Exception:
        pass
    return None


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
    
    # Determine --platform: use explicit CLI value, otherwise auto-detect
    platform = shared_context.get('platform')
    if not platform:
        from_image = _parse_from_image(dockerfile_path)
        if from_image:
            platform = _detect_required_platform(from_image)
            if platform:
                print(f"  Auto-detected platform mismatch: building with --platform {platform} for {from_image}")
    if platform:
        shared_context['platform'] = platform  # pass to runtime test

    # Build command
    cmd = ["docker", "build", "-t", tag, "-f", dockerfile_path]
    if platform:
        cmd += ["--platform", platform]
    cmd.append(context_dir)

    try:
        res = run(cmd, cwd=context_dir)
        
        if res.returncode != 0:
            # Combine stdout and stderr; docker build mixes them
            combined_build = (res.stdout + "\n" + res.stderr).strip()

            # Always print the last 50 lines to the console so the user can follow along,
            # but don't flood the terminal with the full package-install transcript.
            if combined_build:
                tail = combined_build.splitlines()[-50:]
                print("\n--- Docker build output (last 50 lines) ---")
                print("\n".join(tail))
                print("--- End build output ---\n")

            # Extract key error lines for the LintIssue context (used by the LLM on retry).
            build_error_keywords = [
                'error', 'failed', 'exception',
                'no such file', 'not found', 'unable to locate',
                'executor failed', 'exit code',
                'COPY failed', 'failed to solve',
            ]
            key_lines = []
            for line in combined_build.splitlines():
                if any(kw in line.lower() for kw in build_error_keywords):
                    stripped = line.strip()
                    if stripped and stripped not in key_lines:
                        key_lines.append(stripped)

            tail_lines = combined_build.splitlines()[-50:]
            parts = []
            if key_lines:
                parts.append("KEY ERRORS:\n" + "\n".join(f"  {l}" for l in key_lines[:20]))
            parts.append("LAST 50 LINES OF BUILD OUTPUT:\n" + "\n".join(tail_lines))
            build_summary = "\n\n".join(parts) if parts else "(no output captured)"

            issues.append(LintIssue(
                "ERROR",
                f"Docker build failed for {dockerfile_path}",
                f"Build command: {res.cmd}\n\n{build_summary}"
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
