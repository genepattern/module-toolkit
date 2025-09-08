#!/usr/bin/env python
"""
GenePattern manifest linter.

Usage:
  python manifest/linter.py /path/to/manifest

Checks performed:
- File exists and is a regular file.
- Basename of the file is exactly 'manifest' (lowercase).
- Each non-empty, non-comment line is of the form key=value (value may be empty).
- Keys are non-empty and contain no whitespace.
- No duplicate keys.
- Required keys exist: LSID, name, commandLine.
- LSID value looks like a valid LSID (urn:lsid:...); accepts both escaped (urn\:lsid\:) and unescaped forms.

Outputs PASS on success, or a FAIL summary with per-issue details including line number and line text.
Exit code is 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from typing import List, Dict, Tuple


@dataclass
class LintIssue:
    severity: str  # 'ERROR' or 'WARNING'
    message: str
    line_no: int | None  # 1-based line number or None if not applicable
    line_text: str | None

    def format(self) -> str:
        line_info = f"Line {self.line_no}" if self.line_no is not None else "Line N/A"
        text = f"\n   > {self.line_text.rstrip()}" if self.line_text is not None else ""
        return f"{self.severity}: {line_info}: {self.message}{text}"


REQUIRED_KEYS = {"LSID", "name", "commandLine"}
LSID_REGEX = re.compile(r"^(urn:lsid:|urn\\:lsid\\:).+", re.IGNORECASE)
KEY_VALID_REGEX = re.compile(r"^[^\s=:#][^=:#]*$")


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="GenePattern manifest linter")
    p.add_argument("manifest_path", help="Path to the manifest file (must be named 'manifest')")
    return p.parse_args(argv)


def lint_manifest(path: str) -> Tuple[bool, List[LintIssue]]:
    issues: List[LintIssue] = []

    # Check existence
    if not os.path.exists(path):
        issues.append(LintIssue("ERROR", f"File does not exist: {path}", None, None))
        return False, issues
    if not os.path.isfile(path):
        issues.append(LintIssue("ERROR", f"Not a regular file: {path}", None, None))
        return False, issues

    # Check basename
    base = os.path.basename(path)
    if base != "manifest":
        issues.append(LintIssue(
            "ERROR",
            f"Manifest filename must be exactly 'manifest' (lowercase); found '{base}'",
            None,
            None,
        ))

    # Read file
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # Java .properties are ISO-8859-1 by spec; try latin-1.
        with open(path, "r", encoding="latin-1") as f:
            lines = f.readlines()

    # Parse
    props: Dict[str, Tuple[int, str]] = {}
    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#") or stripped.startswith("!"):
            continue

        # Basic key=value check (value can be empty)
        if "=" not in line:
            issues.append(LintIssue(
                "ERROR",
                "Expected key=value format with '=' separator",
                idx,
                line,
            ))
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        # preserve raw value including spaces; allow empty value

        if key == "":
            issues.append(LintIssue(
                "ERROR",
                "Empty key before '=' is not allowed",
                idx,
                line,
            ))
            continue

        if not KEY_VALID_REGEX.match(key):
            issues.append(LintIssue(
                "ERROR",
                "Invalid key: keys must not contain whitespace or the characters '=' ':' '#'",
                idx,
                line,
            ))
            # still record to allow duplicate detection logic to proceed predictably

        # Duplicate keys
        if key in props:
            prev_idx, prev_line = props[key]
            issues.append(LintIssue(
                "ERROR",
                f"Duplicate key '{key}' (previously defined at line {prev_idx})",
                idx,
                line,
            ))
        else:
            props[key] = (idx, line)

    # Required keys
    for req in sorted(REQUIRED_KEYS):
        if req not in props:
            issues.append(LintIssue(
                "ERROR",
                f"Missing required key '{req}'",
                None,
                None,
            ))

    # LSID format (if present)
    if "LSID" in props:
        lsid_line_no, lsid_line = props["LSID"]
        # extract value
        _, lsid_value = lsid_line.split("=", 1)
        lsid_value = lsid_value.strip()
        if not LSID_REGEX.match(lsid_value):
            issues.append(LintIssue(
                "ERROR",
                "LSID must start with 'urn:lsid:' (escaped ':' with \\: also accepted)",
                lsid_line_no,
                lsid_line,
            ))

    passed = not any(iss.severity == "ERROR" for iss in issues)
    return passed, issues


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    passed, issues = lint_manifest(args.manifest_path)

    if passed:
        print(f"PASS: Manifest '{args.manifest_path}' passed all checks.")
        return 0
    else:
        error_count = sum(1 for i in issues if i.severity == "ERROR")
        warning_count = sum(1 for i in issues if i.severity == "WARNING")
        plural_e = "s" if error_count != 1 else ""
        plural_w = "s" if warning_count != 1 else ""
        header = f"FAIL: Manifest '{args.manifest_path}' failed {error_count} check{plural_e}"
        if warning_count:
            header += f" and has {warning_count} warning{plural_w}"
        print(header + ":")
        for issue in issues:
            print(issue.format())
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
