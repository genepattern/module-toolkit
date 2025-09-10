"""
GenePattern Paramgroups Linter Test Suite

This package contains modular tests for validating paramgroups.json files.
Each test module follows the naming convention test_*.py and implements:

- run_test(paramgroups_path: str, shared_context: dict) -> List[LintIssue]: Main test function

Available tests:
- test_file_validation.py: File existence and JSON parsing validation
- test_structure_validation.py: Correct array/object structure validation
- test_parameter_coverage.py: Verify all provided parameters are represented
- test_parameter_completeness.py: Verify no extra parameters in file
- test_group_validation.py: Verify groups have non-zero parameters
"""
