#!/usr/bin/env python
"""
Test for duplicate parameter flag usage.

In GenePattern manifests a parameter's flag (e.g. ``--mode``) must appear
in exactly ONE place.  There are three places a flag can live:

1. Inline in ``commandLine`` — e.g. ``... --mode <mode> ...``
2. As ``p#_prefix``             — always prepended before the value
3. As ``p#_prefix_when_specified`` — prepended only when the param has a value

Having the flag in more than one place causes it to appear twice on the
actual command line the module runs, which almost always produces an error.

Rules enforced
--------------
* If a flag appears inline in ``commandLine``, both ``p#_prefix`` and
  ``p#_prefix_when_specified`` must be blank for that parameter.
* If ``p#_prefix`` is non-empty, the flag must NOT also appear inline in
  ``commandLine``.
* If ``p#_prefix_when_specified`` is non-empty, the flag must NOT also
  appear inline in ``commandLine``.
* ``p#_prefix`` and ``p#_prefix_when_specified`` must not both be non-empty
  for the same parameter (that would also double the flag).
"""
from __future__ import annotations

import re
import sys
import os
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

PARAM_KEY_REGEX = re.compile(r"^p(\d+)_(.+)$")

# Matches an optional flag token (--flag or -f) immediately before <param_name>
_INLINE_FLAG_RE = re.compile(r"(--?[\w._-]+)\s+<([^>]+)>")


def _parse_kv(lines: List[str]) -> Dict[str, Tuple[str, int, str]]:
    """Return {key: (value, line_no, raw_line)} for every key=value pair."""
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
    return kv


def _inline_flags(command_line: str) -> Dict[str, str]:
    """Return {param_name: flag} for every '--flag <param_name>' pair in commandLine."""
    result: Dict[str, str] = {}
    for flag, param_name in _INLINE_FLAG_RE.findall(command_line):
        result[param_name] = flag
    return result


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Detect parameters whose flag appears in more than one location.

    Args:
        lines: Lines from the manifest file.

    Returns:
        List of LintIssue objects describing each violation.
    """
    issues: List[LintIssue] = []
    kv = _parse_kv(lines)

    command_line = kv.get("commandLine", ("", 0, ""))[0]
    inline = _inline_flags(command_line)
    cmd_line_no = kv.get("commandLine", ("", 0, ""))[1]
    cmd_line_text = kv.get("commandLine", ("", 0, ""))[2]

    # Collect all parameter attributes grouped by parameter number
    params: Dict[int, Dict[str, Tuple[str, int, str]]] = {}
    for key, entry in kv.items():
        m = PARAM_KEY_REGEX.match(key)
        if m:
            num = int(m.group(1))
            attr = m.group(2)
            params.setdefault(num, {})[attr] = entry

    for param_num in sorted(params):
        attrs = params[param_num]

        name_entry = attrs.get("name")
        if name_entry is None:
            continue
        param_name = name_entry[0]

        prefix_entry = attrs.get("prefix")
        prefix_ws_entry = attrs.get("prefix_when_specified")

        prefix_val = prefix_entry[0] if prefix_entry else ""
        prefix_ws_val = prefix_ws_entry[0] if prefix_ws_entry else ""

        has_inline = param_name in inline
        has_prefix = bool(prefix_val.strip())
        has_prefix_ws = bool(prefix_ws_val.strip())

        # Rule 1 & 2: inline flag + prefix both set
        if has_inline and has_prefix:
            issues.append(LintIssue(
                "ERROR",
                f"Parameter p{param_num} '{param_name}': flag '{inline[param_name]}' "
                f"appears both inline in commandLine AND in p{param_num}_prefix "
                f"('{prefix_val}'). The flag will be passed twice. "
                f"Remove it from whichever location is not intended.",
                prefix_entry[1],
                prefix_entry[2],
            ))

        # Rule 1 & 3: inline flag + prefix_when_specified both set
        if has_inline and has_prefix_ws:
            issues.append(LintIssue(
                "ERROR",
                f"Parameter p{param_num} '{param_name}': flag '{inline[param_name]}' "
                f"appears both inline in commandLine AND in "
                f"p{param_num}_prefix_when_specified ('{prefix_ws_val}'). "
                f"The flag will be passed twice. "
                f"Remove it from whichever location is not intended.",
                prefix_ws_entry[1],
                prefix_ws_entry[2],
            ))

        # Rule 4: both prefix and prefix_when_specified are set for same param
        if has_prefix and has_prefix_ws:
            issues.append(LintIssue(
                "ERROR",
                f"Parameter p{param_num} '{param_name}': both p{param_num}_prefix "
                f"('{prefix_val}') and p{param_num}_prefix_when_specified "
                f"('{prefix_ws_val}') are non-empty. Only one prefix field should "
                f"be set per parameter.",
                prefix_entry[1],
                prefix_entry[2],
            ))

    return issues
