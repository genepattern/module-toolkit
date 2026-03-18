#!/usr/bin/env python
"""
Test for command line field validation.

This test ensures that the commandLine field is present and non-empty,
and checks for common issues in command line syntax including:
- Empty commandLine
- Missing parameter references
- Missing <libdir> prefix before wrapper scripts

The <libdir> substitution is required so GenePattern can locate the
wrapper script inside the module's installation directory at runtime.

Good:  python <libdir>wrapper.py ...
Good:  Rscript <libdir>wrapper.R ...
Bad:   python wrapper.py ...       (bare script name — will fail at runtime)
"""
from __future__ import annotations

import re
import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Script extensions/invocations that indicate a wrapper script reference
_SCRIPT_INVOCATION_RE = re.compile(
    r"""
    (?:
        python\s+        |   # python  wrapper.py
        Rscript\s+       |   # Rscript wrapper.R
        bash\s+          |   # bash    wrapper.sh
        perl\s+          |   # perl    wrapper.pl
        ruby\s+              # ruby    wrapper.rb
    )
    (?!<libdir>)             # NOT already prefixed with <libdir>
    ([\w./\\-]+              # capture the bare script filename
     \.(?:py|R|sh|pl|rb|r))  # that has a recognised script extension
    """,
    re.VERBOSE,
)


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test command line field validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any command line violations
    """
    issues: List[LintIssue] = []
    commandline_found = False
    commandline_value = ""
    commandline_line_no = 0
    commandline_line_text = ""

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        # Skip empty lines and comments
        if stripped == "" or stripped.startswith("#") or stripped.startswith("!"):
            continue

        # Skip lines that don't have = separator
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Skip empty keys
        if key == "":
            continue

        # Check for commandLine field
        if key == "commandLine":
            commandline_found = True
            commandline_value = value
            commandline_line_no = idx
            commandline_line_text = line

    # Validate commandLine
    if commandline_found:
        # Check if commandLine is empty (this is also caught by required_keys but we can be more specific)
        if not commandline_value:
            issues.append(LintIssue(
                "ERROR",
                "commandLine field is present but empty",
                commandline_line_no,
                commandline_line_text,
            ))
        else:
            # Check for potential issues in commandLine
            # Look for parameter references like <param.name>
            if "<" in commandline_value and ">" in commandline_value:
                # This is expected - parameters are referenced with < >
                pass
            elif commandline_value and not any(c in commandline_value for c in ["<", ">", " "]):
                # CommandLine exists but has no parameters and no spaces - might be wrong
                issues.append(LintIssue(
                    "WARNING",
                    "commandLine does not contain any parameter references (<param.name>) or spaces. This may be incorrect.",
                    commandline_line_no,
                    commandline_line_text,
                ))

            # Check that wrapper scripts are referenced with <libdir> prefix.
            # A bare script name (e.g. "python wrapper.py") will fail at runtime
            # because GenePattern won't know where the script lives.
            # The correct form is "python <libdir>wrapper.py".
            m = _SCRIPT_INVOCATION_RE.search(commandline_value)
            if m:
                bare_script = m.group(1)
                issues.append(LintIssue(
                    "ERROR",
                    (
                        f"commandLine references wrapper script '{bare_script}' without the "
                        f"<libdir> substitution. GenePattern cannot locate the script at runtime. "
                        f"Use '<libdir>{bare_script}' instead "
                        f"(e.g. 'python <libdir>{bare_script} ...')."
                    ),
                    commandline_line_no,
                    commandline_line_text,
                ))

    return issues

