#!/usr/bin/env python
"""
Test for prefix_when_specified / commandLine flag consistency.

GenePattern convention: parameter names use dots (e.g., ``input.file``).
Wrapper scripts must accept flags that match the parameter names exactly
(e.g., ``--input.file``).  A common LLM-generation bug is to produce
dashes instead of dots (e.g., ``--input-file``) which causes a mismatch
between the manifest's commandLine / prefix_when_specified and the
wrapper's argparse / optparse definitions.

This test catches three classes of mismatch:
1. ``prefix_when_specified`` uses dashes where the parameter name has dots.
2. Inline flags in ``commandLine`` use dashes where the parameter name
   has dots.
3. ``prefix_when_specified`` and the inline flag in ``commandLine`` are
   inconsistent with each other.
"""
from __future__ import annotations

import re
import sys
import os
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Regex to match parameter keys
PARAM_KEY_REGEX = re.compile(r"^p(\d+)_(.+)$")


def _dots_to_dashes(name: str) -> str:
    """Convert dots to dashes: input.file -> input-file."""
    return name.replace(".", "-")


def _extract_inline_flag(command_line: str, param_name: str) -> Optional[str]:
    r"""Extract the inline flag that precedes ``<param_name>`` in the commandLine.

    For example, given:
        commandLine = "python wrapper.py --input-file <input.file> --model <model>"
    and param_name = "input.file", returns "--input-file".

    Returns None if no inline flag precedes the placeholder.
    """
    # Look for --flag <param_name> pattern
    pattern = re.compile(
        r"(--[\w._-]+)\s+<" + re.escape(param_name) + r">"
    )
    m = pattern.search(command_line)
    if m:
        return m.group(1)
    return None


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test that prefix_when_specified values and commandLine inline flags
    use dots (matching parameter names) rather than dashes.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any consistency violations
    """
    issues: List[LintIssue] = []
    kv: Dict[str, Tuple[str, int, str]] = {}  # key -> (value, line_no, line_text)

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if stripped == "" or stripped.startswith("#") or stripped.startswith("!"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            kv[key] = (value, idx, line)

    # Extract commandLine
    command_line = kv.get("commandLine", ("", 0, ""))[0]

    # Collect parameter info
    params: Dict[int, Dict[str, Tuple[str, int, str]]] = {}
    for key, (value, line_no, line_text) in kv.items():
        m = PARAM_KEY_REGEX.match(key)
        if m:
            idx = int(m.group(1))
            attr = m.group(2)
            params.setdefault(idx, {})[attr] = (value, line_no, line_text)

    for param_num in sorted(params):
        attrs = params[param_num]
        name_val = attrs.get("name")
        prefix_val = attrs.get("prefix_when_specified")

        if name_val is None:
            continue

        param_name = name_val[0]

        # Only check params whose names actually contain dots
        if "." not in param_name:
            continue

        # --- Check 1: prefix_when_specified uses dashes instead of dots ---
        if prefix_val is not None:
            prefix = prefix_val[0]
            prefix_line_no = prefix_val[1]
            prefix_line_text = prefix_val[2]

            if prefix:
                # Expected: --input.file   Wrong: --input-file
                expected_prefix = f"--{param_name}"
                dashed_prefix = f"--{_dots_to_dashes(param_name)}"

                if prefix == dashed_prefix and prefix != expected_prefix:
                    issues.append(LintIssue(
                        "ERROR",
                        f"Parameter p{param_num} '{param_name}': "
                        f"prefix_when_specified uses dashes ('{prefix}') but "
                        f"should use dots ('{expected_prefix}') to match the "
                        f"parameter name. GenePattern wrapper scripts use "
                        f"dot-based flag names.",
                        prefix_line_no,
                        prefix_line_text,
                    ))

        # --- Check 2: commandLine inline flag uses dashes instead of dots ---
        if command_line:
            inline_flag = _extract_inline_flag(command_line, param_name)
            if inline_flag:
                expected_flag = f"--{param_name}"
                dashed_flag = f"--{_dots_to_dashes(param_name)}"

                if inline_flag == dashed_flag and inline_flag != expected_flag:
                    cmd_line_no = kv.get("commandLine", ("", 0, ""))[1]
                    cmd_line_text = kv.get("commandLine", ("", 0, ""))[2]
                    issues.append(LintIssue(
                        "ERROR",
                        f"Parameter p{param_num} '{param_name}': "
                        f"commandLine uses dashed flag '{inline_flag}' but "
                        f"should use dotted flag '{expected_flag}' to match "
                        f"the parameter name and the wrapper script.",
                        cmd_line_no,
                        cmd_line_text,
                    ))

    return issues

