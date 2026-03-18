#!/usr/bin/env python
"""
Cross-validation: manifest flags vs wrapper script accepted flags.

The manifest's ``commandLine`` and per-parameter ``prefix`` /
``prefix_when_specified`` values specify the flags that will be passed to the
wrapper script at runtime.  The wrapper script must actually accept every flag
that the manifest sends — otherwise the module will fail immediately when run.

A common LLM-generation bug is a mismatch between the two, for example:

    Manifest commandLine:   bash <libdir>run.sh -I <input.file>
    Wrapper parse_arguments: case --input.bam)  ...

This test:
1. Locates the wrapper script in the same directory as the manifest (any
   .py / .R / .sh / .r / .bash file that is not named ``manifest``).
2. Extracts the flags the wrapper actually accepts:
   - Bash/sh:  ``case`` patterns like ``--flag)`` or ``-f)``, and getopts strings
   - Python:   ``add_argument("--flag", ...)`` / ``add_argument("-f", ...)``
   - R:        ``make_option(c("--flag", "-f"), ...)`` / ``add_argument``
3. Collects every flag the manifest sends:
   - Inline flags in ``commandLine``  (``--flag <param>`` or ``-f <param>``)
   - ``p#_prefix``
   - ``p#_prefix_when_specified``
4. Reports an ERROR for any manifest flag that is not found in the wrapper.

The test is skipped (produces no issues) when no wrapper script is present
alongside the manifest — for example when linting a bare manifest file.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

PARAM_KEY_RE = re.compile(r"^p(\d+)_(.+)$")

# Inline flag before a GenePattern placeholder: --flag <param> or -f <param>
INLINE_FLAG_RE = re.compile(r"(--?[\w._-]+)\s+<([^>]+)>")

# ---------------------------------------------------------------------------
# Wrapper flag extraction
# ---------------------------------------------------------------------------

def _extract_flags_bash(content: str) -> Set[str]:
    """Extract flags from a bash/sh wrapper script.

    Handles:
    - ``case`` arm patterns: ``--flag)``, ``-f)``, ``--flag|--alias)``
    - ``getopts`` option strings (short flags only)
    """
    flags: Set[str] = set()

    # case arms: look for lines like "    --input.bam)" or "--flag|-f)"
    # Also handles leading whitespace and trailing ;; or )
    case_arm_re = re.compile(r"""
        (?:^|\s)                     # start-of-line or whitespace
        (                            # capture group: one or more flag alternatives
            -[-\w._]+                # long flag  --foo or -foo
            (?:\|-[-\w._]+)*         # optional | alternatives
        )
        \s*\)                        # closing paren of case arm
    """, re.VERBOSE | re.MULTILINE)

    for m in case_arm_re.finditer(content):
        for alt in m.group(1).split("|"):
            alt = alt.strip()
            if alt.startswith("-"):
                flags.add(alt)

    # getopts: getopts "abc:d:" opt  -> adds -a -b -c -d
    getopts_re = re.compile(r'\bgetopts\s+["\']([^"\']+)["\']')
    for m in getopts_re.finditer(content):
        optstring = m.group(1).lstrip(":")
        for ch in optstring:
            if ch != ":":
                flags.add(f"-{ch}")

    return flags


def _extract_flags_python(content: str) -> Set[str]:
    """Extract flags from a Python wrapper using argparse/optparse patterns."""
    flags: Set[str] = set()

    # add_argument("--flag", ...) or add_argument('-f', '--flag', ...)
    # Also handles dest= style long options
    add_arg_re = re.compile(
        r"""add_argument\s*\(
            \s*(                      # capture the argument list
                (?:["'][^"']+["']\s*,?\s*)+  # one or more quoted strings
            )
        """,
        re.VERBOSE,
    )
    quoted_re = re.compile(r"""["'](--?[\w._-]+)["']""")

    for m in add_arg_re.finditer(content):
        for flag in quoted_re.findall(m.group(1)):
            flags.add(flag)

    # Fallback: any add_argument call with a -- string anywhere on the line
    for line in content.splitlines():
        if "add_argument" in line:
            for flag in quoted_re.findall(line):
                flags.add(flag)

    return flags


def _extract_flags_r(content: str) -> Set[str]:
    """Extract flags from an R wrapper using optparse/argparse patterns."""
    flags: Set[str] = set()

    # make_option(c("--flag", "-f"), ...) or make_option("--flag", ...)
    # add_argument("--flag", ...)
    quoted_re = re.compile(r"""["'](--?[\w._-]+)["']""")

    for line in content.splitlines():
        if any(kw in line for kw in ("make_option", "add_argument", "add_option")):
            for flag in quoted_re.findall(line):
                flags.add(flag)

    return flags


def _extract_wrapper_flags(script_path: str) -> Optional[Set[str]]:
    """Read *script_path* and return the set of flags it accepts, or None on error."""
    try:
        with open(script_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        return None

    ext = os.path.splitext(script_path)[1].lower()
    if ext == ".py":
        return _extract_flags_python(content)
    if ext in (".r",):
        return _extract_flags_r(content)
    if ext in (".sh", ".bash"):
        return _extract_flags_bash(content)

    # Unknown extension: try to detect from shebang / content
    first_line = content.split("\n", 1)[0]
    if "python" in first_line:
        return _extract_flags_python(content)
    if "Rscript" in first_line or "Rscript" in content[:200]:
        return _extract_flags_r(content)
    # Default: try bash heuristics
    return _extract_flags_bash(content)


# ---------------------------------------------------------------------------
# Manifest flag collection
# ---------------------------------------------------------------------------

def _collect_manifest_flags(
    kv: Dict[str, Tuple[str, int, str]],
) -> List[Tuple[str, str, int, str]]:
    """Return list of (flag, source_description, line_no, line_text) for all
    flags the manifest will pass to the wrapper."""

    results: List[Tuple[str, str, int, str]] = []

    command_line, cmd_line_no, cmd_line_text = kv.get("commandLine", ("", 0, ""))

    # Inline flags in commandLine
    for flag, _param in INLINE_FLAG_RE.findall(command_line):
        results.append((flag, "commandLine inline flag", cmd_line_no, cmd_line_text))

    # Per-parameter prefix / prefix_when_specified
    params: Dict[int, Dict[str, Tuple[str, int, str]]] = {}
    for key, entry in kv.items():
        m = PARAM_KEY_RE.match(key)
        if m:
            num = int(m.group(1))
            attr = m.group(2)
            params.setdefault(num, {})[attr] = entry

    for param_num in sorted(params):
        attrs = params[param_num]
        param_name = attrs.get("name", ("", 0, ""))[0]

        for attr_name in ("prefix", "prefix_when_specified"):
            entry = attrs.get(attr_name)
            if entry is None:
                continue
            value, line_no, line_text = entry
            value = value.strip()
            if not value:
                continue
            # Extract the flag token(s) — value may be "--flag " (with trailing space)
            tokens = value.split()
            for tok in tokens:
                if tok.startswith("-"):
                    results.append((
                        tok,
                        f"p{param_num}_{attr_name} (param '{param_name}')",
                        line_no,
                        line_text,
                    ))
                    break  # only the first flag token matters

    return results


# ---------------------------------------------------------------------------
# Helper: find wrapper script next to the manifest
# ---------------------------------------------------------------------------

_WRAPPER_EXTENSIONS = {".py", ".R", ".r", ".sh", ".bash", ".pl", ".rb"}


def _find_wrapper_script(manifest_path: str) -> Optional[str]:
    """Return the path of the wrapper script in the same directory, or None."""
    module_dir = os.path.dirname(os.path.abspath(manifest_path))
    candidates = []
    try:
        for fname in os.listdir(module_dir):
            fpath = os.path.join(module_dir, fname)
            if not os.path.isfile(fpath):
                continue
            if fname == "manifest":
                continue
            _, ext = os.path.splitext(fname)
            if ext.lower() in _WRAPPER_EXTENSIONS:
                candidates.append(fpath)
    except OSError:
        return None

    if not candidates:
        return None
    # Prefer files whose names contain "wrapper" or "run_"
    for c in candidates:
        base = os.path.basename(c).lower()
        if "wrapper" in base or base.startswith("run_") or base.startswith("run"):
            return c
    return candidates[0]


# ---------------------------------------------------------------------------
# Main run_test entry point
# ---------------------------------------------------------------------------

def run_test(lines: List[str], context: dict = None) -> List[LintIssue]:
    """
    Cross-check manifest flags against wrapper script accepted flags.

    Args:
        lines: Lines from the manifest file.
        context: Shared context dict from the linter.  Must contain
                 'manifest_path' (str) so the test can locate sibling files.
                 When absent or empty the test is skipped silently.

    Returns:
        List of LintIssue objects for any mismatches found.
    """
    issues: List[LintIssue] = []

    # Extract manifest_path from context; skip if not available
    if not context or not isinstance(context, dict):
        return issues
    manifest_path = context.get("manifest_path")
    if not manifest_path or not isinstance(manifest_path, str):
        return issues

    wrapper_path = _find_wrapper_script(manifest_path)
    if wrapper_path is None:
        # No wrapper script found — nothing to check
        return issues

    wrapper_flags = _extract_wrapper_flags(wrapper_path)
    if wrapper_flags is None:
        issues.append(LintIssue(
            "WARNING",
            f"Could not read wrapper script '{os.path.basename(wrapper_path)}' "
            "to validate flag consistency.",
            None,
            None,
        ))
        return issues

    # If we couldn't extract any flags at all it may mean the extractor
    # failed silently — warn rather than false-positive.
    if not wrapper_flags:
        issues.append(LintIssue(
            "WARNING",
            f"No flags extracted from wrapper script "
            f"'{os.path.basename(wrapper_path)}'. "
            "Cannot validate manifest flag consistency. "
            "Ensure the wrapper uses standard flag parsing (argparse / optparse / case).",
            None,
            None,
        ))
        return issues

    # Parse manifest key-value pairs
    kv: Dict[str, Tuple[str, int, str]] = {}
    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("!"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            kv[key] = (value.strip(), idx, line)

    manifest_flags = _collect_manifest_flags(kv)

    wrapper_basename = os.path.basename(wrapper_path)

    for flag, source, line_no, line_text in manifest_flags:
        if flag not in wrapper_flags:
            issues.append(LintIssue(
                "ERROR",
                f"Manifest {source} passes flag '{flag}' to the wrapper, "
                f"but '{wrapper_basename}' does not appear to accept that flag. "
                f"Accepted flags: {', '.join(sorted(wrapper_flags))}. "
                f"Fix the manifest flag or add '{flag}' handling to the wrapper.",
                line_no,
                line_text,
            ))

    return issues

