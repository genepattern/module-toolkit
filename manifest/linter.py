#!/usr/bin/env python
"""
GenePattern manifest linter - Production version.

This tool validates GenePattern module manifest files for compliance with
the manifest specification. It can validate individual manifest files or
find and validate manifest files within directories.

Usage:
  python manifest/linter.py /path/to/manifest           # Validate specific file
  python manifest/linter.py /path/to/module/directory   # Find and validate manifest in directory

Validation checks performed:
- File exists and is a regular file
- Basename of the file is exactly 'manifest' (lowercase)
- Each non-empty, non-comment line follows key=value format (value may be empty)
- Keys are non-empty and contain no whitespace or special characters
- No duplicate keys exist
- Required keys are present: LSID, name, commandLine
- LSID value follows proper format (urn:lsid:... or urn\:lsid\:...)

Outputs PASS on success, or a FAIL summary with detailed issue descriptions.
Exit code is 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class LintIssue:
    """Represents a validation issue found during manifest linting.
    
    Attributes:
        severity: Issue severity level ('ERROR' or 'WARNING')
        message: Human-readable description of the issue
        line_no: 1-based line number where issue occurred (None if not applicable)
        line_text: The actual line content that caused the issue (None if not applicable)
    """
    severity: str  # 'ERROR' or 'WARNING'
    message: str
    line_no: int | None  # 1-based line number or None if not applicable
    line_text: str | None

    def format(self) -> str:
        """Format the issue for human-readable output.
        
        Returns:
            Formatted string representation of the issue
        """
        line_info = f"Line {self.line_no}" if self.line_no is not None else "Line N/A"
        text = f"\n   > {self.line_text.rstrip()}" if self.line_text is not None else ""
        return f"{self.severity}: {line_info}: {self.message}{text}"




def parse_args(argv: List[str]) -> argparse.Namespace:
    """Parse command line arguments.
    
    Args:
        argv: Command line arguments (excluding script name)
        
    Returns:
        Parsed arguments namespace
    """
    p = argparse.ArgumentParser(
        description="GenePattern manifest linter - Production version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/manifest               # Validate specific manifest file
  %(prog)s /path/to/module/directory       # Find and validate manifest in directory
"""
    )
    p.add_argument(
        "path", 
        help="Path to manifest file or directory containing manifest file"
    )
    return p.parse_args(argv)


def resolve_manifest_path(path: str) -> Optional[str]:
    """Resolve the path to a manifest file.
    
    If path is a file named 'manifest', return it.
    If path is a directory, look for a file named 'manifest' within it.
    
    Args:
        path: File or directory path
        
    Returns:
        Path to manifest file, or None if not found
    """
    if os.path.isfile(path):
        return path
    elif os.path.isdir(path):
        manifest_path = os.path.join(path, "manifest")
        if os.path.isfile(manifest_path):
            return manifest_path
        else:
            return None
    else:
        return None




def discover_tests() -> List[str]:
    """Discover test modules in the tests directory.
    
    Returns:
        List of test module file paths that match the test_*.py pattern
    """
    tests_dir = os.path.join(os.path.dirname(__file__), "tests")
    if not os.path.exists(tests_dir):
        return []
    
    test_files = glob.glob(os.path.join(tests_dir, "test_*.py"))
    return sorted(test_files)


def run_modular_tests(manifest_path: str) -> Tuple[bool, List[LintIssue]]:
    """Run all discovered test modules against the manifest.
    
    Args:
        manifest_path: Path to the manifest file to test
        
    Returns:
        Tuple of (all_tests_passed, list_of_all_issues)
    """
    all_issues: List[LintIssue] = []
    
    # Basic file validation
    if not os.path.exists(manifest_path):
        all_issues.append(LintIssue("ERROR", f"File does not exist: {manifest_path}", None, None))
        return False, all_issues
    if not os.path.isfile(manifest_path):
        all_issues.append(LintIssue("ERROR", f"Not a regular file: {manifest_path}", None, None))
        return False, all_issues
    
    # Filename validation
    base = os.path.basename(manifest_path)
    if base != "manifest":
        all_issues.append(LintIssue(
            "ERROR",
            f"Manifest filename must be exactly 'manifest' (lowercase); found '{base}'",
            None,
            None,
        ))
    
    # Read the manifest file
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # Java .properties are ISO-8859-1 by spec; try latin-1
        with open(manifest_path, "r", encoding="latin-1") as f:
            lines = f.readlines()
    except FileNotFoundError:
        all_issues.append(LintIssue("ERROR", f"File not found: {manifest_path}", None, None))
        return False, all_issues
    
    # Discover and run tests
    test_files = discover_tests()
    if not test_files:
        all_issues.append(LintIssue(
            "WARNING", 
            "No test modules found in tests/ directory", 
            None, 
            None
        ))
        return True, all_issues
    
    tests_run = 0
    for test_file in test_files:
        try:
            # Load the test module dynamically
            spec = importlib.util.spec_from_file_location("test_module", test_file)
            if spec is None or spec.loader is None:
                continue
                
            test_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(test_module)
            
            # Run the test if it has the required function
            if hasattr(test_module, "run_test"):
                test_issues = test_module.run_test(lines)
                all_issues.extend(test_issues)
                tests_run += 1
                
                # Add test info for verbose output
                test_name = os.path.basename(test_file).replace('.py', '').replace('_', ' ').title()
                if test_issues:
                    print(f"  Test '{test_name}': {len(test_issues)} issue(s) found")
                else:
                    print(f"  Test '{test_name}': PASSED")
            
        except Exception as e:
            all_issues.append(LintIssue(
                "ERROR", 
                f"Failed to run test {os.path.basename(test_file)}: {str(e)}", 
                None, 
                None
            ))
    
    print(f"\nRan {tests_run} test module(s)")
    passed = not any(iss.severity == "ERROR" for iss in all_issues)
    return passed, all_issues


def main(argv: List[str]) -> int:
    """Main entry point for the manifest linter.
    
    Args:
        argv: Command line arguments (excluding script name)
        
    Returns:
        Exit code: 0 for success, 1 for failure
    """
    args = parse_args(argv)
    
    # Resolve the manifest path
    manifest_path = resolve_manifest_path(args.path)
    if manifest_path is None:
        if os.path.isdir(args.path):
            print(f"ERROR: No manifest file found in directory '{args.path}'")
        else:
            print(f"ERROR: File or directory does not exist: '{args.path}'")
        return 1
    
    # Run modular tests (this is now the only validation method)
    print(f"Running modular tests on manifest: {manifest_path}")
    passed, issues = run_modular_tests(manifest_path)
    
    # Output results
    if passed:
        print(f"\nPASS: Manifest '{manifest_path}' passed all validation checks.")
        return 0
    else:
        error_count = sum(1 for i in issues if i.severity == "ERROR")
        warning_count = sum(1 for i in issues if i.severity == "WARNING")
        plural_e = "s" if error_count != 1 else ""
        plural_w = "s" if warning_count != 1 else ""
        
        header = f"\nFAIL: Manifest '{manifest_path}' failed {error_count} check{plural_e}"
        if warning_count:
            header += f" and has {warning_count} warning{plural_w}"
        print(header + ":")
        
        for issue in issues:
            print(issue.format())
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
