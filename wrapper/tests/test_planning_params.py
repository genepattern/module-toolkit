#!/usr/bin/env python
"""
Test: Planning Data Parameter Names in Wrapper Script.

Verifies that every parameter name defined in the planning data appears in the
wrapper script as a CLI flag (``--param.name``).  The check is intentionally
language-agnostic: it searches the raw text for the ``--<name>`` pattern so it
works for Python (argparse), R (optparse/argparse), Bash (case/getopts), and
any other language the wrapper might be written in.

This catches the class of bug where the LLM renames a planning-data parameter
(e.g. ``tumor.bam`` → ``input.tumor.bam``, or ``reference`` → ``reference.fasta``)
when writing the wrapper, causing a manifest/wrapper consistency failure.

The test requires parameters to be passed via ``shared_context['expected_parameters']``
(populated by the linter from ``--parameters`` CLI args).  If no parameters are
provided the test is skipped with an INFO message.
"""
from __future__ import annotations

import re
import os
import sys
from dataclasses import dataclass
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Boilerplate shared across all wrapper tests
# ---------------------------------------------------------------------------
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


@dataclass
class LintIssue:
    """Represents a validation issue found during wrapper script linting."""
    severity: str  # 'ERROR' | 'WARNING' | 'INFO'
    message: str
    context: str | None = None

    def format(self) -> str:
        context_info = f" ({self.context})" if self.context else ""
        return f"{self.severity}: {self.message}{context_info}"


# ---------------------------------------------------------------------------
# Core detection logic
# ---------------------------------------------------------------------------

def _flag_patterns(param_name: str) -> List[str]:
    """Return regex patterns that match ``--<param_name>`` as a CLI flag.

    The patterns are deliberately broad so they match the flag regardless of
    which language or argument-parsing library is used:

    * Python argparse:  ``add_argument('--tumor.bam', ...)``
    * R optparse:       ``make_option(c('--tumor.bam'), ...)``
    * R argparse:       ``add_argument('--tumor.bam', ...)``
    * Bash case:        ``--tumor.bam)``
    * Bash echo/usage:  ``--tumor.bam``
    * Any free text:    ``--tumor.bam``
    """
    escaped = re.escape(param_name)
    return [
        # Quoted flag (single or double quotes), followed by anything
        rf"""['"]--{escaped}['"]""",
        # Unquoted flag at a word boundary (bash case arms, usage strings, etc.)
        rf"""--{escaped}(?=[^.\w]|$)""",
    ]


def flag_present(content: str, param_name: str) -> Tuple[bool, str]:
    """Return ``(found, match_description)`` for *param_name* in *content*.

    Searches for ``--<param_name>`` as a CLI flag using language-agnostic
    regex patterns against the raw wrapper text.
    """
    for pattern in _flag_patterns(param_name):
        m = re.search(pattern, content, re.MULTILINE)
        if m:
            # Find the line for a helpful context snippet
            start = content.rfind('\n', 0, m.start()) + 1
            end = content.find('\n', m.end())
            line_snippet = content[start:end].strip()
            return True, f"matched /{pattern}/ on: {line_snippet!r}"
    return False, ""


# ---------------------------------------------------------------------------
# Test entry point
# ---------------------------------------------------------------------------

def run_test(script_path: str, shared_context: dict) -> List[LintIssue]:
    """Verify that every planning-data parameter name appears as a CLI flag.

    Args:
        script_path:     Path to the wrapper script file.
        shared_context:  Mutable dict shared across linter tests.  Must contain
                         ``script_content`` (set by test_01_file_validation) and
                         ``expected_parameters`` (set from ``--parameters`` CLI args).

    Returns:
        List of :class:`LintIssue` objects.  One ERROR per missing parameter.
    """
    issues: List[LintIssue] = []

    # ------------------------------------------------------------------ #
    # Guard: skip if no parameters were provided                          #
    # ------------------------------------------------------------------ #
    expected_parameters: List[str] | None = shared_context.get('expected_parameters')
    if not expected_parameters:
        issues.append(LintIssue(
            "INFO",
            "Planning-data parameter check skipped — no parameters provided",
            "Pass --parameters <name1> <name2> ... to enable this test",
        ))
        return issues

    # ------------------------------------------------------------------ #
    # Guard: need script content from the file-validation test            #
    # ------------------------------------------------------------------ #
    script_content: str | None = shared_context.get('script_content')
    if script_content is None:
        issues.append(LintIssue(
            "ERROR",
            "Cannot check planning-data parameters: script content not available",
            "File validation must pass before this test runs",
        ))
        return issues

    # ------------------------------------------------------------------ #
    # Check each parameter                                                #
    # ------------------------------------------------------------------ #
    missing: List[str] = []
    found: List[str] = []

    for param_name in expected_parameters:
        ok, description = flag_present(script_content, param_name)
        if ok:
            found.append(param_name)
            issues.append(LintIssue(
                "INFO",
                f"Planning parameter '--{param_name}' found in wrapper",
                description,
            ))
        else:
            missing.append(param_name)
            issues.append(LintIssue(
                "ERROR",
                f"Planning parameter '--{param_name}' not found in wrapper script",
                (
                    f"The planning data defines a parameter named '{param_name}' but the "
                    f"wrapper does not declare '--{param_name}' as a CLI flag. "
                    f"The wrapper may have renamed it (e.g. '--input.{param_name}' or "
                    f"'--{param_name.replace('.', '-')}'). "
                    f"Wrapper flags must match planning-data parameter names exactly."
                ),
            ))

    # ------------------------------------------------------------------ #
    # Summary                                                             #
    # ------------------------------------------------------------------ #
    total = len(expected_parameters)
    if missing:
        issues.append(LintIssue(
            "INFO",
            (
                f"Planning-data parameter check: {len(found)}/{total} flags found, "
                f"{len(missing)} missing: {', '.join(f'--{n}' for n in missing)}"
            ),
        ))
    else:
        issues.append(LintIssue(
            "INFO",
            f"Planning-data parameter check: all {total} flags found in wrapper",
        ))

    return issues

