#!/usr/bin/env python
"""
GenePattern Documentation linter - Production version.

This tool validates documentation files through a series of modular tests including
content retrieval, module validation, and parameter validation.

Usage:
  python documentation/linter.py /path/to/doc.html                           # Validate local file
  python documentation/linter.py https://example.com/docs/module.html        # Validate URL
  python documentation/linter.py /path/to/doc.pdf --module ModuleName        # Include module validation
  python documentation/linter.py /path/to/doc.md --parameters param1 param2  # Include parameter validation

Supported formats:
- HTML (.html, .htm) - requires beautifulsoup4 for best parsing
- Markdown (.md, .markdown) - parsed as plain text
- PDF (.pdf) - requires PyPDF2 for text extraction
- Plain text (.txt) - parsed directly

Supported sources:
- Local files - any supported format
- HTTP/HTTPS URLs - requires requests library

Validation tests performed:
- Content retrieval and format parsing
- Module name presence validation (if module provided)
- Parameter names presence validation (if parameters provided)

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
from urllib.parse import urlparse


@dataclass
class LintIssue:
    """Represents a validation issue found during documentation linting."""
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
        description="GenePattern documentation linter - Production version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported formats: HTML, Markdown, PDF, TXT
Supported sources: Local files, HTTP/HTTPS URLs

Examples:
  %(prog)s /path/to/documentation.html                                # Validate local HTML file
  %(prog)s https://example.com/docs/module.html                       # Validate URL
  %(prog)s /path/to/docs.pdf --module ModuleName                      # Include module validation
  %(prog)s /path/to/readme.md --parameters param1 param2              # Include parameter validation
  %(prog)s https://docs.site.com/api.html --module MyModule --parameters input output  # Full validation

Dependencies:
  - requests: Required for URL validation
  - beautifulsoup4: Recommended for HTML parsing (optional, fallback available)
  - PyPDF2: Required for PDF parsing

Install dependencies: pip install requests beautifulsoup4 PyPDF2
"""
    )
    p.add_argument(
        "path_or_url", 
        help="Path to documentation file or URL to documentation"
    )
    p.add_argument(
        "--module", 
        help="Expected module name for validation (optional)"
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


def run_modular_tests(doc_path_or_url: str, **test_kwargs) -> tuple[bool, List[LintIssue]]:
    """Run all discovered test modules against a documentation source.
    
    Args:
        doc_path_or_url: Path to documentation file or URL
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
                    test_issues = test_module.run_test(doc_path_or_url, shared_context)
                    all_issues.extend(test_issues)
                    tests_run += 1
                    
                    # Tests can modify shared_context to pass data to subsequent tests
                    # This allows content retrieval to pass extracted text to validation tests
                    
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
    """Main entry point for the documentation linter.
    
    Args:
        argv: Command line arguments (excluding script name)
        
    Returns:
        Exit code: 0 for success, 1 for failure
    """
    args = parse_args(argv)
    
    # Validate input - check if it's a URL or file
    doc_input = args.path_or_url
    parsed_url = urlparse(doc_input)
    
    is_url = parsed_url.scheme in ('http', 'https')
    
    if not is_url:
        # For local files, check if path exists
        if not os.path.exists(doc_input):
            print(f"ERROR: File does not exist: '{doc_input}'")
            return 1
    
    # Prepare test context - pass all CLI arguments to tests
    test_kwargs = {
        'expected_module': args.module,  # May be None
        'expected_parameters': args.parameters,  # May be None or empty list
    }
    
    # Determine input type for display
    input_type = "URL" if is_url else "file"
    
    # Run modular tests
    print(f"Running modular tests on documentation {input_type}: {doc_input}")
    passed, issues = run_modular_tests(doc_input, **test_kwargs)
    
    # Output results
    if passed:
        print(f"\nPASS: Documentation '{doc_input}' passed all validation checks.")
        return 0
    else:
        error_count = sum(1 for i in issues if i.severity == "ERROR")
        warning_count = sum(1 for i in issues if i.severity == "WARNING")
        plural_e = "s" if error_count != 1 else ""
        plural_w = "s" if warning_count != 1 else ""
        
        header = f"\nFAIL: Documentation '{doc_input}' failed {error_count} check{plural_e}"
        if warning_count:
            header += f" and has {warning_count} warning{plural_w}"
        print(header + ":")
        
        for issue in issues:
            print(issue.format())
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
