#!/usr/bin/env python
"""
GenePattern GPUnit linter - Production version.

This tool validates GPUnit YAML files through a series of modular tests including
file validation, structure validation, and optional module/parameter validation.

Usage:
  python gpunit/linter.py /path/to/test.yml                              # Validate specific GPUnit file
  python gpunit/linter.py /path/to/gpunit/directory                      # Validate all .yml files in directory
  python gpunit/linter.py /path/to/test.yml --module ModuleName          # Include module validation
  python gpunit/linter.py /path/to/test.yml --parameters param1 param2   # Include parameter validation

Validation tests performed:
- File existence and YAML parsing validation
- Structure validation (required fields: name, module, params, assertions)
- Module name/LSID matching validation (if module provided)
- Parameter validation against expected list (if parameters provided)

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
    """Represents a validation issue found during GPUnit linting."""
    severity: str  # 'ERROR' or 'WARNING' or 'INFO'
    message: str
    context: str | None = None

    def format(self) -> str:
        """Format the issue for human-readable output."""
        context_info = f" ({self.context})" if self.context else ""
        return f"{self.severity}: {self.message}{context_info}"


def parse_args(argv: List[str]) -> argparse.Namespace:
    """Parse command line arguments.
    
    Args:
        argv: Command line arguments (excluding script name)
        
    Returns:
        Parsed arguments namespace
    """
    p = argparse.ArgumentParser(
        description="GenePattern GPUnit linter - Production version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/test.yml                                        # Validate specific GPUnit file
  %(prog)s /path/to/gpunit/directory                                # Validate all .yml files in directory
  %(prog)s /path/to/test.yml --module ModuleName                    # Include module validation
  %(prog)s /path/to/test.yml --module urn:lsid:...                  # Include LSID validation
  %(prog)s /path/to/test.yml --parameters param1 param2             # Include parameter validation
  %(prog)s /path/to/test.yml --module MyModule --parameters p1 p2   # Full validation
"""
    )
    p.add_argument(
        "path", 
        help="Path to GPUnit .yml file or directory containing .yml files"
    )
    p.add_argument(
        "--module", 
        help="Expected module name or LSID for validation (optional)"
    )
    p.add_argument(
        "--parameters", 
        nargs="*",
        help="List of expected parameter names for validation (optional)"
    )
    p.add_argument(
        "--types",
        nargs="*",
        choices=["text", "number", "file"],
        help="List of parameter types corresponding to --parameters (text, number, file)"
    )

    return p.parse_args(argv)


def find_gpunit_files(path: str) -> List[str]:
    """Find GPUnit files (.yml) in a path.
    
    If path is a file, return it if it's a .yml file.
    If path is a directory, find all .yml files within it.
    
    Args:
        path: File or directory path
        
    Returns:
        List of .yml file paths
    """
    if os.path.isfile(path):
        if path.endswith('.yml'):
            return [path]
        else:
            return []
    elif os.path.isdir(path):
        yml_files = glob.glob(os.path.join(path, "*.yml"))
        return sorted(yml_files)
    else:
        return []


def discover_tests() -> List[str]:
    """Discover test modules in the tests directory.
    
    Returns:
        List of test module file paths that match the test_*.py pattern
    """
    tests_dir = os.path.join(os.path.dirname(__file__), "tests")
    if not os.path.exists(tests_dir):
        return []
    
    test_files = glob.glob(os.path.join(tests_dir, "test_*.py"))
    
    # Priority order (based off of GPUnit README)
    priority_filenames = ["test_file_validation.py","test_structure_validation.py", 
                          "test_module_validation.py","test_parameter_validation.py"]
    def sort_key(filepath):
        filename = os.path.basename(filepath)
        if filename in priority_filenames:
            return priority_filenames.index(filename)
        return len(priority_filenames) + 1
    return sorted(test_files, key=sort_key)


def run_modular_tests(gpunit_path: str, **test_kwargs) -> Tuple[bool, List[LintIssue]]:
    """Run all discovered test modules against a GPUnit file.
    
    Args:
        gpunit_path: Path to the GPUnit file to test
        **test_kwargs: Additional context for tests (expected_module, expected_parameters, etc.)
        
    Returns:
        Tuple of (all_tests_passed, list_of_all_issues)
    """
    all_issues: List[LintIssue] = []
    
    # Discover and run tests
    test_files = discover_tests()
    if not test_files:
        all_issues.append(LintIssue(
            "WARNING", 
            "No test modules found in tests/ directory", 
            None
        ))
        return True, all_issues
    
    tests_run = 0
    shared_context = test_kwargs.copy()  # Shared context between tests
    
    for test_file in test_files:
        try:
            # Use a simpler approach - add test directory to path temporarily
            test_dir = os.path.dirname(test_file)
            test_filename = os.path.basename(test_file)
            module_name = test_filename[:-3]  # Remove .py extension
            
            # Temporarily add tests directory to Python path
            tests_dir_added = False
            if test_dir not in sys.path:
                sys.path.insert(0, test_dir)
                tests_dir_added = True
            
            try:
                # Import the module using standard import
                test_module = __import__(module_name)
                
                # Run the test if it has the required function
                if hasattr(test_module, "run_test"):
                    # Pass the shared context as a mutable dict that tests can modify
                    test_issues = test_module.run_test(gpunit_path, shared_context)
                    all_issues.extend(test_issues)
                    tests_run += 1
                    
                    # Tests can modify shared_context to pass data to subsequent tests
                    # This allows file tests to pass parsed data to structure tests, etc.
                    
                    # Add test info for verbose output
                    test_name = os.path.basename(test_file).replace('.py', '').replace('_', ' ').title()
                    if test_issues:
                        error_count = sum(1 for issue in test_issues if issue.severity == "ERROR")
                        warning_count = sum(1 for issue in test_issues if issue.severity == "WARNING")
                        info_count = sum(1 for issue in test_issues if issue.severity == "INFO")
                        
                        if error_count > 0:
                            print(f"  Test '{test_name}': {error_count} error(s) found")
                        elif warning_count > 0:
                            print(f"  Test '{test_name}': {warning_count} warning(s) found")
                        elif info_count > 0:
                            print(f"  Test '{test_name}': {info_count} info message(s)")
                        else:
                            print(f"  Test '{test_name}': {len(test_issues)} issue(s) found")
                    else:
                        print(f"  Test '{test_name}': PASSED")
                        
            finally:
                # Clean up: remove tests directory from path
                if tests_dir_added and test_dir in sys.path:
                    sys.path.remove(test_dir)
                    
                # Clean up: remove module from sys.modules to avoid conflicts
                if module_name in sys.modules:
                    del sys.modules[module_name]
            
        except Exception as e:
            all_issues.append(LintIssue(
                "ERROR", 
                f"Failed to run test {os.path.basename(test_file)}: {str(e)}", 
                None
            ))
    
    print(f"Ran {tests_run} test module(s)")
    passed = not any(iss.severity == "ERROR" for iss in all_issues)
    return passed, all_issues


def main(argv: List[str]) -> int:
    """Main entry point for the GPUnit linter.
    
    Args:
        argv: Command line arguments (excluding script name)
        
    Returns:
        Exit code: 0 for success, 1 for failure
    """
    args = parse_args(argv)
    
    # Find GPUnit files to validate
    gpunit_files = find_gpunit_files(args.path)
    if not gpunit_files:
        if os.path.isdir(args.path):
            print(f"ERROR: No .yml files found in directory '{args.path}'")
        elif os.path.isfile(args.path):
            print(f"ERROR: File '{args.path}' is not a .yml file")
        else:
            print(f"ERROR: File or directory does not exist: '{args.path}'")
        return 1
    
    # Validate that types match parameters if provided
    expected_param_types = {}
    if args.types:
        if not args.parameters:
            print("ERROR: --types argument requires --parameters argument")
            return 1
        if len(args.parameters) != len(args.types):
            print(f"ERROR: Number of --types ({len(args.types)}) must match number of --parameters ({len(args.parameters)})")
            return 1
        # Map parameters to types
        expected_param_types = dict(zip(args.parameters, args.types))
    
    # Prepare test context - pass all CLI arguments to tests
    test_kwargs = {
        'expected_module': args.module,  # May be None
        'expected_parameters': args.parameters,  # May be None or empty list
        'expected_param_types': expected_param_types
    }
    
    # Process each GPUnit file
    overall_passed = True
    total_files = len(gpunit_files)
    file_results = []  # Track results to avoid re-running tests
    
    for i, gpunit_file in enumerate(gpunit_files):
        if total_files > 1:
            print(f"\n{'='*60}")
            print(f"Validating GPUnit file {i+1}/{total_files}: {gpunit_file}")
            print('='*60)
        else:
            print(f"Running modular tests on GPUnit file: {gpunit_file}")
        
        # Run modular tests on this file
        passed, issues = run_modular_tests(gpunit_file, **test_kwargs)
        file_results.append((gpunit_file, passed, issues))
        
        if not passed:
            overall_passed = False
        
        # Output results for this file
        if passed:
            print(f"\nPASS: GPUnit file '{gpunit_file}' passed all validation checks.")
        else:
            error_count = sum(1 for i in issues if i.severity == "ERROR")
            warning_count = sum(1 for i in issues if i.severity == "WARNING")
            plural_e = "s" if error_count != 1 else ""
            plural_w = "s" if warning_count != 1 else ""
            
            header = f"\nFAIL: GPUnit file '{gpunit_file}' failed {error_count} check{plural_e}"
            if warning_count:
                header += f" and has {warning_count} warning{plural_w}"
            print(header + ":")
            
            for issue in issues:
                print(issue.format())
    
    # Final summary for multiple files
    if total_files > 1:
        passed_count = sum(1 for _, passed, _ in file_results if passed)
        failed_count = total_files - passed_count
        
        print(f"\n{'='*60}")
        print(f"SUMMARY: {passed_count}/{total_files} GPUnit files passed")
        if failed_count > 0:
            print(f"         {failed_count} file(s) failed validation")
        print('='*60)
    
    return 0 if overall_passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
