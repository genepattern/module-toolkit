"""
GenePattern Dockerfile Linter Test Suite

This package contains modular tests for validating Dockerfiles and their build/runtime behavior.
Each test module follows the naming convention test_*.py and implements:

- run_test(dockerfile_path: str, **kwargs) -> List[LintIssue]: Main test function
- Test modules may require additional context like tag names or commands

Available tests:
- test_file_validation.py: Basic file existence and type validation
- test_docker_availability.py: Docker CLI availability check  
- test_build_validation.py: Docker image build validation
- test_runtime_validation.py: Container runtime validation (optional)
"""
