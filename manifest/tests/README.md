# Manifest Linter Test Suite

This directory contains a comprehensive suite of tests for validating GenePattern module manifest files.

## Test Files

Each test is implemented in a separate Python file following the naming convention `test_*.py`. All tests follow a consistent pattern:

1. Import the `LintIssue` class from the parent linter module
2. Implement a `run_test(lines: List[str]) -> List[LintIssue]` function
3. Return a list of validation issues found

### Available Tests

#### Core Format Tests
- **test_basic_keyvalue.py** - Validates basic key=value format for all non-comment lines
- **test_duplicate_keys.py** - Ensures no key appears more than once in the manifest
- **test_required_keys.py** - Verifies that required keys (LSID, name, commandLine) are present

#### LSID and Naming Tests
- **test_lsid_format.py** - Validates LSID follows proper format (urn:lsid: or urn\:lsid\:)
- **test_module_name.py** - Ensures module name contains only valid characters

#### Metadata Field Tests
- **test_author_field.py** - Warns if author field is empty
- **test_version_field.py** - Warns if version field is empty
- **test_description_field.py** - Warns if description field is empty
- **test_quality_level.py** - Validates quality field (development, preproduction, production, deprecated)
- **test_privacy_level.py** - Validates privacy field (public, private)
- **test_task_type.py** - Validates taskType field (informational only)

#### Environment Tests
- **test_os_field.py** - Validates OS field (any, Linux, Windows, Mac, Unix, Solaris)
- **test_cpu_type.py** - Validates cpuType field (any, Intel, PowerPC, Alpha)
- **test_language_field.py** - Validates language field (informational only)
- **test_jvm_level.py** - Validates JVMLevel format if specified

#### Docker and Resources Tests
- **test_docker_image.py** - Validates Docker image name format
- **test_memory_spec.py** - Validates job.memory format (e.g., 8Gb, 4Mb)

#### URL and File Format Tests
- **test_url_fields.py** - Validates URL format for src.repo, documentationUrl, etc.
- **test_file_format.py** - Validates fileFormat fields (no leading dots, semicolon-separated)

#### Command Line Tests
- **test_commandline.py** - Validates commandLine field is present and contains parameters

#### Parameter Tests
- **test_parameter_numbering.py** - Ensures parameters are numbered sequentially (p1, p2, p3, ...)
- **test_parameter_attributes.py** - Validates parameter attributes and consistency

## Adding New Tests

To add a new test:

1. Create a new file in this directory named `test_<description>.py`
2. Import the required modules:
   ```python
   import sys
   import os
   sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
   from linter import LintIssue
   ```
3. Implement the `run_test(lines: List[str]) -> List[LintIssue]` function
4. Return a list of `LintIssue` objects for any violations found

### LintIssue Format

```python
LintIssue(
    severity,    # "ERROR" or "WARNING"
    message,     # Human-readable description
    line_no,     # 1-based line number or None
    line_text    # The actual line content or None
)
```

## Running Tests

The linter automatically discovers and runs all tests when executed:

```bash
# Validate a specific manifest file
python manifest/linter.py /path/to/manifest

# Validate manifest in a directory
python manifest/linter.py /path/to/module/directory
```

## Test Examples

### Valid Manifest
See `manifest/examples/valid/manifest` for a properly formatted manifest that passes all tests.

### Invalid Manifests
The `manifest/examples/invalid/` directory contains examples of common errors:
- `manifest_missing_lsid` - Missing required LSID field
- `manifest_invalid_lsid` - Invalid LSID format
- `manifest_duplicate_keys` - Duplicate key definitions
- `manifest_param_gap` - Non-sequential parameter numbering

## Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed

## Severity Levels

- **ERROR** - Critical issues that prevent the manifest from being valid
- **WARNING** - Potential issues or unusual patterns that should be reviewed

