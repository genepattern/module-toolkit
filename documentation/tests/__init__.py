"""
GenePattern Documentation Linter Test Suite

This package contains modular tests for validating documentation files.
Each test module follows the naming convention test_*.py and implements:

- run_test(doc_path_or_url: str, shared_context: dict) -> List[LintIssue]: Main test function

Available tests:
- test_content_retrieval.py: Content existence and retrieval validation (file/URL, format support)
- test_module_validation.py: Module name presence validation (conditional)
- test_parameter_validation.py: Parameter names presence validation (conditional)

Supported formats: HTML, Markdown (.md), PDF, TXT
Supported sources: Local files, HTTP/HTTPS URLs
"""
