#!/usr/bin/env python
"""
Test: manifest parameter names vs wrapper script argument consistency.

For every parameter declared in the manifest (pN_name=...) this test
verifies that the wrapper script exposes a matching add_argument() flag.
The wrapper path is supplied via the shared ``context`` dict under the
key ``wrapper_path`` (populated by the manifest linter when --wrapper is
passed on the CLI).

If no wrapper path is provided the test is skipped (PASS with INFO).
"""
from __future__ import annotations

import ast
import re
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from linter import LintIssue


# ---------------------------------------------------------------------------
# Helpers: extract parameter names from the manifest lines
# ---------------------------------------------------------------------------

_PARAM_NAME_RE = re.compile(r"^p(\d+)_name\s*=\s*(.+)$")


def _extract_manifest_params(lines: List[str]) -> List[Tuple[int, str]]:
    """Return [(param_number, param_name), ...] from manifest lines."""
    params: List[Tuple[int, str]] = []
    for raw in lines:
        line = raw.rstrip("\n").strip()
        if line.startswith("#") or line.startswith("!") or "=" not in line:
            continue
        m = _PARAM_NAME_RE.match(line)
        if m:
            params.append((int(m.group(1)), m.group(2).strip()))
    return sorted(params, key=lambda t: t[0])


# ---------------------------------------------------------------------------
# Helpers: extract declared flags from a Python wrapper via AST
# ---------------------------------------------------------------------------

def _python_add_argument_flags(source: str) -> Set[str]:
    """Return the set of long-flag strings (e.g. '--input.tumor.bam')
    declared by add_argument() calls in a Python wrapper."""
    flags: Set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _python_flags_regex(source)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_add_arg = (
            (isinstance(func, ast.Attribute) and func.attr == "add_argument")
            or (isinstance(func, ast.Name) and func.id == "add_argument")
        )
        if not is_add_arg:
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if arg.value.startswith("--"):
                    flags.add(arg.value)
    return flags


def _python_flags_regex(source: str) -> Set[str]:
    """Regex fallback when AST parsing fails."""
    flags: Set[str] = set()
    for m in re.finditer(r"""add_argument\s*\(\s*['"](-{1,2}[\w.\-]+)['"]""", source):
        if m.group(1).startswith("--"):
            flags.add(m.group(1))
    return flags


# ---------------------------------------------------------------------------
# Helpers: extract declared flags from an R wrapper (optparse / argparse)
# ---------------------------------------------------------------------------

def _r_flags(source: str) -> Set[str]:
    """Return long-flag strings from make_option / add_argument calls in R."""
    flags: Set[str] = set()
    # optparse: make_option(c("--foo", "-f"), ...)  or  make_option("--foo", ...)
    for m in re.finditer(r"""make_option\s*\(\s*(?:c\s*\()?['"](-{1,2}[\w.\-]+)['"]""", source):
        if m.group(1).startswith("--"):
            flags.add(m.group(1))
    # argparse R package: parser$add_argument("--foo", ...)
    for m in re.finditer(r"""add_argument\s*\(\s*['"](-{1,2}[\w.\-]+)['"]""", source):
        if m.group(1).startswith("--"):
            flags.add(m.group(1))
    return flags


# ---------------------------------------------------------------------------
# Normalisation: map a manifest param name → candidate flag strings
# ---------------------------------------------------------------------------

def _candidate_flags(param_name: str) -> Set[str]:
    """Generate plausible flag variants for a manifest parameter name.

    GenePattern param names use dot-notation (e.g. 'input.tumor.bam').
    Wrappers may declare them as:
      --input.tumor.bam   (dots preserved — preferred)
      --input-tumor-bam   (dashes)
      --input_tumor_bam   (underscores, via dest= only — NOT a flag)
    We check the dot and dash variants as valid flag names.
    """
    base = param_name.strip()
    candidates: Set[str] = {
        f"--{base}",                              # --input.tumor.bam  (dots)
        f"--{base.replace('.', '-')}",            # --input-tumor-bam  (dashes)
    }
    return candidates


# ---------------------------------------------------------------------------
# Main test entry point
# ---------------------------------------------------------------------------

def run_test(lines: List[str], context: Optional[dict] = None) -> List[LintIssue]:
    """Cross-check manifest parameter names against wrapper add_argument flags.

    Args:
        lines:   Lines of the manifest file.
        context: Shared linter context dict; must contain 'wrapper_path' to
                 enable the check.  If absent or empty the test is skipped.

    Returns:
        List of LintIssue objects.
    """
    issues: List[LintIssue] = []

    # ------------------------------------------------------------------
    # Retrieve wrapper path from context
    # ------------------------------------------------------------------
    wrapper_path: Optional[str] = None
    if context and context.get("wrapper_path"):
        wrapper_path = context["wrapper_path"]

    if not wrapper_path:
        issues.append(LintIssue(
            "INFO",
            "Wrapper consistency check skipped: no wrapper path provided "
            "(pass --wrapper <path> to the manifest linter to enable this check).",
            None, None,
        ))
        return issues

    wrapper_file = Path(wrapper_path)
    if not wrapper_file.is_file():
        issues.append(LintIssue(
            "WARNING",
            f"Wrapper consistency check skipped: wrapper file not found at '{wrapper_path}'.",
            None, None,
        ))
        return issues

    # ------------------------------------------------------------------
    # Read wrapper source and detect language
    # ------------------------------------------------------------------
    try:
        wrapper_source = wrapper_file.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        issues.append(LintIssue(
            "WARNING",
            f"Wrapper consistency check skipped: could not read wrapper: {exc}",
            None, None,
        ))
        return issues

    ext = wrapper_file.suffix.lower()
    if ext == ".py":
        declared_flags = _python_add_argument_flags(wrapper_source)
    elif ext in (".r",):
        declared_flags = _r_flags(wrapper_source)
    else:
        # Bash / other — skip structural check
        issues.append(LintIssue(
            "INFO",
            f"Wrapper consistency check skipped: unsupported wrapper language ({ext}).",
            None, None,
        ))
        return issues

    if not declared_flags:
        issues.append(LintIssue(
            "WARNING",
            "Wrapper consistency check: no add_argument() flags found in wrapper. "
            "Skipping parameter cross-check.",
            None, None,
        ))
        return issues

    # ------------------------------------------------------------------
    # Extract manifest parameter names
    # ------------------------------------------------------------------
    manifest_params = _extract_manifest_params(lines)
    if not manifest_params:
        return issues  # nothing to check

    # ------------------------------------------------------------------
    # Cross-check each manifest param against wrapper flags
    # ------------------------------------------------------------------
    # Normalise declared flags to lowercase for comparison
    declared_lower: Dict[str, str] = {f.lower(): f for f in declared_flags}

    missing: List[str] = []
    for _num, param_name in manifest_params:
        candidates = _candidate_flags(param_name)
        # Check if any candidate matches (case-insensitive)
        found = any(c.lower() in declared_lower for c in candidates)
        if not found:
            missing.append(param_name)

    if missing:
        # Build a human-readable list of what the wrapper actually has
        sorted_flags = sorted(declared_flags)
        wrapper_flags_str = ", ".join(sorted_flags[:20])
        if len(sorted_flags) > 20:
            wrapper_flags_str += f" … ({len(sorted_flags)} total)"

        for param_name in missing:
            candidates_str = " or ".join(sorted(_candidate_flags(param_name)))
            issues.append(LintIssue(
                "ERROR",
                f"Manifest parameter '{param_name}' has no matching flag in the wrapper script. "
                f"Expected one of: {candidates_str}. "
                f"Wrapper declares: {wrapper_flags_str}.",
                None, None,
            ))

    if not missing:
        issues.append(LintIssue(
            "INFO",
            f"Wrapper consistency check passed: all {len(manifest_params)} manifest "
            f"parameter(s) have matching flags in the wrapper script.",
            None, None,
        ))

    return issues



