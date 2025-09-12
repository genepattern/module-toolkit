# GenePattern Manifest Linter

A production-ready linter for validating GenePattern module manifest files.

## Overview

The manifest linter validates GenePattern module manifest files for compliance with the manifest specification. It performs comprehensive checks on file format, required keys, key formats, and LSID validation.

## Usage

```bash
python manifest/linter.py [PATH]
```

### Arguments

- `PATH` - Path to a manifest file OR directory containing a manifest file

### Examples

```bash
# Validate a specific manifest file
python manifest/linter.py /path/to/manifest

# Validate manifest in a module directory
python manifest/linter.py /path/to/module/directory/

# The linter will automatically find 'manifest' file in the directory
python manifest/linter.py ./my_module/
```

## Validation Tests

The linter runs the following modular tests:

### 1. File Validation (`test_file_validation.py`)
- **Purpose**: Validates file existence and basic properties
- **Checks**:
  - File exists and is readable
  - File basename is exactly 'manifest' (case-sensitive)
  - File is a regular file (not directory or symlink)

### 2. Key-Value Format (`test_key_value_format.py`)
- **Purpose**: Validates manifest key-value format
- **Checks**:
  - Each non-empty, non-comment line follows `key=value` format
  - Keys are non-empty and contain only valid characters
  - Values can be empty but must be present after `=`
  - Handles comments (lines starting with `#`)

### 3. Duplicate Keys (`test_duplicate_keys.py`)
- **Purpose**: Ensures no duplicate keys exist
- **Checks**:
  - No key appears more than once in the manifest
  - Case-sensitive key comparison
  - Reports all duplicate occurrences

### 4. Required Keys (`test_required_keys.py`)
- **Purpose**: Validates presence of required manifest keys
- **Checks**:
  - `LSID` - Life Science Identifier (required)
  - `name` - Module name (required)
  - `commandLine` - Command line template (required)

### 5. LSID Format (`test_lsid_format.py`)
- **Purpose**: Validates LSID format compliance
- **Checks**:
  - LSID follows proper format: `urn:lsid:authority:namespace:object:revision`
  - Supports both standard and escaped formats
  - Validates each component of the LSID

## Expected Input Format

Manifest files should follow this format:

```
# Comments are allowed
LSID=urn:lsid:genepattern.org:module.analysis:00001:1
name=MyModule
description=Module description
commandLine=<java> -jar mymodule.jar <input.file> <output.file>
version=1.0
```

## Exit Codes

- `0` - All validation checks passed
- `1` - One or more validation checks failed

## Output Examples

### Success
```
Running modular tests on manifest file: /path/to/manifest
  Test 'Test File Validation': PASSED
  Test 'Test Key Value Format': PASSED
  Test 'Test Duplicate Keys': PASSED
  Test 'Test Required Keys': PASSED
  Test 'Test Lsid Format': PASSED
Ran 5 test module(s)

PASS: Manifest file '/path/to/manifest' passed all validation checks.
```

### Failure
```
Running modular tests on manifest file: /path/to/manifest
  Test 'Test File Validation': PASSED
  Test 'Test Key Value Format': 1 error(s) found
  Test 'Test Required Keys': 1 error(s) found
Ran 5 test module(s)

FAIL: Manifest file '/path/to/manifest' failed 2 checks:
ERROR: Line 5: Invalid key-value format: 'invalid line without equals'
ERROR: Required key 'LSID' is missing
```

## Dependencies

- Python 3.7+ (uses standard library only)
- No external dependencies required

## Architecture

The linter follows a modular architecture where each validation concern is implemented as a separate test module. This allows for:

- Easy maintenance and updates
- Clear separation of concerns
- Extensible validation framework
- Consistent error reporting

Each test module implements a `run_test()` function that returns a list of `LintIssue` objects describing any problems found.
