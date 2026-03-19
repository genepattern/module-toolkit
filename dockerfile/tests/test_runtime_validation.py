#!/usr/bin/env python
"""
Test for Docker container runtime validation.

This test validates that a built Docker image can successfully
run commands in a container environment.
"""
from __future__ import annotations

import sys
import os
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


def _detect_wrapper_help_command(command: str) -> str | None:
    """Infer a cheap --help invocation from a full runtime command string.

    Returns a shell one-liner that runs the wrapper with --help (or an
    equivalent flag for languages that don't support --help), or None when
    no suitable pre-check can be constructed.

    Supported patterns
    ------------------
    * ``python wrapper.py ...``   → ``python wrapper.py --help``
    * ``Rscript wrapper.R ...``   → ``Rscript wrapper.R --help``
    * ``bash wrapper.sh ...``     → skipped (bash scripts rarely support --help)
    * ``perl wrapper.pl ...``     → ``perl wrapper.pl --help``
    * ``julia wrapper.jl ...``    → skipped (no universal --help convention)
    * bare script (./wrapper.py)  → ``./wrapper.py --help``
    """
    import shlex

    try:
        tokens = shlex.split(command)
    except ValueError:
        return None

    if not tokens:
        return None

    interpreter = tokens[0].lower()

    # Python wrapper
    if interpreter in ("python", "python3", "python2"):
        if len(tokens) >= 2:
            script = tokens[1]
            return f"{tokens[0]} {script} --help"
        return None

    # Rscript wrapper
    if interpreter == "rscript":
        if len(tokens) >= 2:
            script = tokens[1]
            return f"Rscript {script} --help"
        return None

    # Perl wrapper
    if interpreter == "perl":
        if len(tokens) >= 2:
            script = tokens[1]
            return f"perl {script} --help"
        return None

    # Bare script invocation (e.g. ./wrapper.py or /module/wrapper.py)
    script_path = tokens[0]
    if script_path.endswith(".py"):
        return f"python {script_path} --help"
    if script_path.endswith((".R", ".r")):
        return f"Rscript {script_path} --help"
    if script_path.endswith(".pl"):
        return f"perl {script_path} --help"

    # bash / shell scripts and unknown languages: no universal --help convention
    return None


def _run_wrapper_help_check(tag: str, volume_flags: List[str], help_cmd: str, platform: Optional[str] = None) -> List[LintIssue]:
    """Run ``help_cmd`` inside the container as a cheap import/syntax check.

    A non-zero exit is treated as an ERROR only when the failure output
    contains unmistakable import/syntax error keywords.  Exit-code 1 from
    argparse --help (which is normal for many scripts that exit 1 after
    printing help) is **not** considered a failure.
    """
    issues: List[LintIssue] = []

    platform_flags = ["--platform", platform] if platform else []
    cmd = [
        "docker", "run", "--rm",
        *platform_flags,
        *volume_flags,
        "--entrypoint", "sh", tag, "-lc", help_cmd,
    ]

    try:
        res = run(cmd)

        combined = (res.stdout + "\n" + res.stderr).strip()

        # Hard import/syntax errors that always indicate a broken wrapper
        fatal_keywords = [
            "ModuleNotFoundError",
            "ImportError",
            "SyntaxError",
            "cannot open file",           # Python: script not found
            "No such file or directory",  # generic
            "Error in library(",          # R: missing library
            "Error in source(",           # R: script not found
            "there is no package called", # R: missing package
            "Cannot find the specified file",  # Perl/generic
        ]

        fatal_lines = [
            line.strip()
            for line in combined.splitlines()
            if any(kw.lower() in line.lower() for kw in fatal_keywords)
        ]

        if fatal_lines:
            issues.append(LintIssue(
                "ERROR",
                f"Wrapper --help pre-check detected import/syntax error: {fatal_lines[0]}",
                f"Pre-check command: {help_cmd}"
            ))
            for line in fatal_lines[1:4]:  # at most 3 additional detail lines
                issues.append(LintIssue("ERROR", line))
        else:
            # Success (exit 0) or argparse-style exit 1 with usage output — both are fine
            issues.append(LintIssue(
                "INFO",
                "Wrapper --help pre-check passed (imports resolved, argparse initialised)",
                f"Pre-check command: {help_cmd}"
            ))

    except FileNotFoundError:
        # Docker not available — already reported elsewhere; skip silently
        pass
    except Exception as exc:
        issues.append(LintIssue(
            "WARNING",
            f"Wrapper --help pre-check could not run: {exc}",
            f"Pre-check command: {help_cmd}"
        ))

    return issues


def run_test(dockerfile_path: str, shared_context: dict) -> List[LintIssue]:
    """
    Test Docker container runtime validation.

    Runs two checks when a command is provided via --cmd:
      1. A cheap ``--help`` pre-check to verify the wrapper's imports resolve
         and argparse initialises correctly (skipped gracefully for languages
         that don't support --help, such as bash).
      2. The full runtime command with example data bound into the container.

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
        # Build likely failed — that error is already reported by test_build_validation.
        # Emit a WARNING here so the build ERROR remains the only actionable failure.
        issues.append(LintIssue(
            "WARNING",
            "Skipping runtime test: no Docker tag available (build likely failed)",
            "Fix the build errors above first"
        ))
        return issues

    # Collect bind-mount volumes from shared_context (host:container strings)
    volumes = shared_context.get('volumes', [])

    # Run command inside a shell for broader command compatibility.
    # We set entrypoint to 'sh' to avoid image CMD/ENTRYPOINT interference.
    # Note: If the image does not include a POSIX shell, this will fail and report accordingly.
    volume_flags = []
    for vol in volumes:
        volume_flags.extend(["-v", vol])

    # ---------------------------------------------------------------------- #
    # Wrapper --help pre-check: cheaper than the full runtime command and     #
    # catches import errors / missing packages early.  We attempt this for    #
    # Python, R, and Perl wrappers; languages without a --help convention are #
    # silently skipped.                                                        #
    # ---------------------------------------------------------------------- #
    platform = shared_context.get('platform')

    help_cmd = _detect_wrapper_help_command(command)
    if help_cmd:
        help_issues = _run_wrapper_help_check(tag, volume_flags, help_cmd, platform=platform)
        issues.extend(help_issues)
        # If the pre-check found a hard import error, abort — no point running
        # the full command when the wrapper can't even be imported.
        if any(iss.severity == "ERROR" for iss in help_issues):
            issues.append(LintIssue(
                "INFO",
                "Full runtime test skipped because wrapper --help pre-check failed",
                "Fix the import/syntax errors above and rebuild the image"
            ))
            return issues

    platform_flags = ["--platform", platform] if platform else []
    cmd = [
        "docker", "run", "--rm",
        *platform_flags,
        *volume_flags,
        "--entrypoint", "sh", tag, "-lc", command,
    ]

    try:
        res = run(cmd)
        
        # Always print the full container output so the user can follow along.
        combined_output = (res.stdout + "\n" + res.stderr).strip()
        if combined_output:
            print("\n--- Container output ---")
            print(combined_output)
            print("--- End container output ---\n")

        if res.returncode != 0:

            # Extract the most actionable lines using a broad set of error keywords,
            # including GATK/Java-specific patterns the generic filter would miss.
            error_keywords = [
                # Generic
                'error', 'failed', 'exception', 'traceback', 'fatal',
                # Java / GATK
                'user error', 'a user error has occurred', 'exception in thread',
                'java.lang.', 'java.io.', 'htsjdk.', 'org.broadinstitute.',
                # Python
                'modulenotfounderror', 'importerror', 'syntaxerror',
                # Shell / OS
                'command not found', 'no such file', 'permission denied',
            ]
            key_lines = []
            for line in combined_output.splitlines():
                if any(kw in line.lower() for kw in error_keywords):
                    stripped = line.strip()
                    if stripped and stripped not in key_lines:
                        key_lines.append(stripped)

            # Always include the last 30 lines of combined output so the LLM
            # has full context even when errors don't match the keyword list.
            tail_lines = combined_output.splitlines()[-30:]

            parts = []
            if key_lines:
                parts.append("KEY ERRORS:\n" + "\n".join(f"  {l}" for l in key_lines[:20]))
            parts.append("LAST 30 LINES OF OUTPUT:\n" + "\n".join(tail_lines))
            output_summary = "\n\n".join(parts) if parts else "(no output captured)"

            issues.append(LintIssue(
                "ERROR",
                f"Container runtime failed for command: {command}",
                f"Run command: {res.cmd}\n\n{output_summary}"
            ))

            # If container can't find shell, suggest alternative
            if 'executable file not found' in res.stderr.lower() and 'sh' in res.stderr:
                issues.append(LintIssue(
                    "ERROR",
                    "Container does not have POSIX shell (sh)",
                    "Image may be based on scratch or distroless - cannot run shell commands"
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
