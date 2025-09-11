"""
GenePattern Wrapper Script Linter Test Suite

This package contains modular tests for validating wrapper scripts.
Each test module follows the naming convention test_*.py and implements:

- run_test(script_path: str, shared_context: dict) -> List[LintIssue]: Main test function

Available tests:
- test_file_validation.py: Script existence and readability validation
- test_syntax_validation.py: Python syntax validation (conditional on script type)
- test_parameter_validation.py: Parameter presence validation (conditional)

Supported script types: Python (.py), Bash (.sh, .bash), R (.r, .R), and others
Script type detection: File extension, shebang analysis, content inspection
"""
