#!/usr/bin/env python
"""
GenePattern Wrapper Script linter - Production version.

This tool validates wrapper scripts through a series of modular tests including
file validation, syntax validation (for Python), and parameter validation.

Usage:
  python wrapper/linter.py /path/to/script.py                           # Validate Python script
  python wrapper/linter.py /path/to/script.sh                           # Validate Bash script
  python wrapper/linter.py /path/to/script.R                            # Validate R script
  python wrapper/linter.py /path/to/script.py --parameters param1 param2 # Include parameter validation

Supported script types:
- Python (.py) - Full syntax validation using AST parsing
- Bash (.sh, .bash) - Syntax validation using bash -n (if bash available)
- R (.r, .R) - Syntax validation using Rscript (if R available)
- Other types - Basic file validation and parameter search

Script type detection:
- File extension analysis
- Shebang line parsing  
- Content pattern recognition

Validation tests performed:
- File existence and readability validation
- Script type detection and basic file analysis
- Syntax validation (Python always, others if tools available)
- Parameter presence validation (if parameters provided)

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
from typing import List, Optional


@dataclass
class LintIssue:
    """Represents a validation issue found during wrapper script linting."""
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
        description="GenePattern wrapper script linter - Production version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported script types: Python, Bash, R, and others
Script type detection: File extension, shebang analysis, content patterns

Examples:
  %(prog)s /path/to/wrapper.py                                # Validate Python wrapper
  %(prog)s /path/to/wrapper.sh                                # Validate Bash wrapper
  %(prog)s /path/to/wrapper.R                                 # Validate R wrapper
  %(prog)s /path/to/wrapper.py --parameters input output      # Include parameter validation
  
Validation features:
  - File existence and permissions check
  - Python syntax validation (using AST)
  - Bash syntax validation (using bash -n, if available)
  - R syntax validation (using Rscript, if available)
  - Parameter presence detection (language-specific patterns)
  
Dependencies (optional):
  - bash: For Bash script syntax validation
  - Rscript: For R script syntax validation
  - Python: Always available for Python script validation
"""
    )
    p.add_argument(
        "script_path", 
        help="Path to wrapper script file"
    )
    p.add_argument(
        "--parameters", 
        nargs="*",
        help="List of expected parameter names for validation (optional)"
    )
    return p.parse_args(argv)


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


def run_modular_tests(script_path: str, **test_kwargs) -> tuple[bool, List[LintIssue]]:
    """Run all discovered test modules against a wrapper script.
    
    Args:
        script_path: Path to wrapper script file
        **test_kwargs: Additional context for tests (expected_parameters, etc.)
        
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
                    test_issues = test_module.run_test(script_path, shared_context)
                    all_issues.extend(test_issues)
                    tests_run += 1
                    
                    # Tests can modify shared_context to pass data to subsequent tests
                    # This allows file validation to pass script content and type to other tests
                    
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
    """Main entry point for the wrapper script linter.
    
    Args:
        argv: Command line arguments (excluding script name)
        
    Returns:
        Exit code: 0 for success, 1 for failure
    """
    args = parse_args(argv)
    
    script_path = args.script_path
    
    # Basic path validation
    if not script_path:
        print("ERROR: No script path provided")
        return 1
    
    # Convert to absolute path for consistent handling
    script_path = os.path.abspath(script_path)
    
    # Prepare test context - pass all CLI arguments to tests
    test_kwargs = {
        'expected_parameters': args.parameters,  # May be None or empty list
    }
    
    # Run modular tests
    print(f"Running modular tests on wrapper script: {script_path}")
    passed, issues = run_modular_tests(script_path, **test_kwargs)
    
    # Output results
    if passed:
        print(f"\nPASS: Wrapper script '{script_path}' passed all validation checks.")
        return 0
    else:
        error_count = sum(1 for i in issues if i.severity == "ERROR")
        warning_count = sum(1 for i in issues if i.severity == "WARNING")
        plural_e = "s" if error_count != 1 else ""
        plural_w = "s" if warning_count != 1 else ""
        
        header = f"\nFAIL: Wrapper script '{script_path}' failed {error_count} check{plural_e}"
        if warning_count:
            header += f" and has {warning_count} warning{plural_w}"
        print(header + ":")
        
        for issue in issues:
            print(issue.format())
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
