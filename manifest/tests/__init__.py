"""
GenePattern Manifest Linter Test Suite

This package contains modular tests for validating GenePattern manifest files.
Each test module follows the naming convention test_*.py and implements:

- run_test(lines: List[str]) -> List[LintIssue]: Main test function
- get_test_name() -> str: Human-readable test name
- get_test_description() -> str: Test description

Available tests:
- test_basic_keyvalue.py: Basic key=value format validation
- test_duplicate_keys.py: Duplicate key detection
- test_required_keys.py: Required keys validation  
- test_lsid_format.py: LSID format validation
"""
