"""
GenePattern GPUnit Linter Test Suite

This package contains modular tests for validating GPUnit YAML files.
Each test module follows the naming convention test_*.py and implements:

- run_test(gpunit_path: str, shared_context: dict) -> List[LintIssue]: Main test function

Available tests:
- test_file_validation.py: File existence and YAML parsing validation
- test_structure_validation.py: Required fields validation (name, module, params, assertions)
- test_module_validation.py: Module name/LSID matching validation (conditional)
- test_parameter_validation.py: Parameter validation against expected list (conditional)
"""
