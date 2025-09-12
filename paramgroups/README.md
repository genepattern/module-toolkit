# GenePattern Paramgroups Linter

A production-ready linter for validating paramgroups.json files used in GenePattern modules.

## Overview

The paramgroups linter validates paramgroups.json files through comprehensive checks including JSON format validation, structure validation, and optional parameter coverage analysis. Paramgroups files define how module parameters are organized into logical groups in the GenePattern interface.

## Usage

```bash
python paramgroups/linter.py [PATH] [OPTIONS]
```

### Arguments

- `PATH` - Path to a paramgroups.json file OR directory containing a paramgroups.json file

### Options

- `--parameters PARAM1 PARAM2 ...` - List of expected parameter names for validation (optional)

### Examples

```bash
# Basic paramgroups.json validation
python paramgroups/linter.py /path/to/paramgroups.json

# Validate paramgroups.json in a module directory
python paramgroups/linter.py /path/to/module/directory/

# Include parameter coverage validation
python paramgroups/linter.py /path/to/paramgroups.json --parameters input.file output.file method threshold

# Validate with comprehensive parameter list
python paramgroups/linter.py paramgroups.json --parameters dataset.file chip.platform collapse.mode omit.features.with.no.symbol.match
```

## Validation Tests

The linter runs the following modular tests:

### 1. File Validation (`test_file_validation.py`)
- **Purpose**: Validates file existence and JSON format
- **Checks**:
  - File exists and is readable
  - File contains valid JSON syntax
  - JSON can be parsed successfully
  - File is not empty

### 2. Structure Validation (`test_structure_validation.py`)
- **Purpose**: Validates paramgroups JSON structure
- **Checks**:
  - Root element is an array
  - Each group is an object with required fields
  - Required fields: `name`, `parameters`
  - Optional fields: `description`, `hidden`
  - Field types are correct (strings, arrays, booleans)

### 3. Parameter Coverage (`test_parameter_coverage.py`)
- **Purpose**: Validates parameter coverage (conditional)
- **Checks**:
  - All expected parameters are represented in groups
  - No expected parameters are missing from paramgroups
  - Identifies which groups contain which parameters
- **Requirements**: Requires `--parameters` argument

### 4. Parameter Completeness (`test_parameter_completeness.py`)
- **Purpose**: Validates parameter completeness (conditional)
- **Checks**:
  - No extra parameters in paramgroups that weren't expected
  - All parameters in paramgroups are in the expected list
  - Identifies unexpected parameters by group
- **Requirements**: Requires `--parameters` argument

### 5. Group Validation (`test_group_validation.py`)
- **Purpose**: Validates individual group properties
- **Checks**:
  - Each group has a non-empty name
  - Each group has at least one parameter
  - No duplicate parameter names within groups
  - Parameter names are valid strings

## Expected Input Format

Paramgroups files should follow this JSON format:

```json
[
  {
    "name": "Basic Parameters",
    "description": "Essential parameters for module operation",
    "hidden": false,
    "parameters": ["input.file", "output.file", "method"]
  },
  {
    "name": "Advanced Parameters", 
    "description": "Optional parameters with defaults",
    "hidden": true,
    "parameters": ["threshold", "max.iterations", "debug.mode"]
  }
]
```

### Field Descriptions

- **name** (required): Display name for the parameter group
- **description** (optional): Human-readable description of the group
- **hidden** (optional): Whether group is initially collapsed in UI
- **parameters** (required): Array of parameter names in this group

## Exit Codes

- `0` - All validation checks passed
- `1` - One or more validation checks failed

## Output Examples

### Success (Basic Validation)
```
Running modular tests on paramgroups file: /path/to/paramgroups.json
  Test 'Test File Validation': PASSED
  Test 'Test Structure Validation': PASSED
  Test 'Test Parameter Coverage': 1 info message(s)
  Test 'Test Parameter Completeness': 1 info message(s)
  Test 'Test Group Validation': PASSED
Ran 5 test module(s)

PASS: Paramgroups file '/path/to/paramgroups.json' passed all validation checks.
```

### Success (With Parameter Validation)
```
Running modular tests on paramgroups file: /path/to/paramgroups.json
  Test 'Test File Validation': PASSED
  Test 'Test Structure Validation': PASSED
  Test 'Test Parameter Coverage': PASSED
  Test 'Test Parameter Completeness': PASSED
  Test 'Test Group Validation': PASSED
Ran 5 test module(s)

PASS: Paramgroups file '/path/to/paramgroups.json' passed all validation checks.
```

### Failure (Structure Issues)
```
Running modular tests on paramgroups file: /path/to/paramgroups.json
  Test 'Test File Validation': PASSED
  Test 'Test Structure Validation': 2 error(s) found
  Test 'Test Group Validation': 1 error(s) found
Ran 5 test module(s)

FAIL: Paramgroups file '/path/to/paramgroups.json' failed 3 checks:
ERROR: Group 1: Missing required field 'name'
ERROR: Group 2: Field 'parameters' must be an array
ERROR: Group 'Advanced': Group has no parameters
```

### Failure (Parameter Coverage)
```
Running modular tests on paramgroups file: /path/to/paramgroups.json
  Test 'Test Parameter Coverage': 2 error(s) found
  Test 'Test Parameter Completeness': 1 error(s) found
Ran 5 test module(s)

FAIL: Paramgroups file '/path/to/paramgroups.json' failed 3 checks:
ERROR: Expected parameter 'input.file' not found in any group
ERROR: Expected parameter 'threshold' not found in any group  
ERROR: Unexpected parameter 'extra.param' found in group 'Advanced'
```

## Dependencies

- Python 3.7+ (uses standard library only)
- No external dependencies required

## Use Cases

### Module Development
- Validate paramgroups.json during module development
- Ensure all module parameters are properly grouped
- Verify JSON structure compliance

### CI/CD Integration
- Include in build pipelines to catch paramgroups issues early
- Automated validation of parameter organization
- Prevent deployment of modules with invalid parameter groupings

### Parameter Auditing
- Check that paramgroups match actual module parameters
- Identify missing or extra parameter definitions
- Ensure UI grouping matches module expectations

## Architecture

The linter uses a modular architecture with conditional testing:

- File validation ensures basic JSON validity
- Structure validation checks paramgroups-specific format
- Parameter coverage/completeness tests only run when expected parameters provided
- Group validation ensures individual group integrity
- Shared context allows tests to pass parsed data between stages

This design allows the linter to be useful both for basic format validation and comprehensive parameter analysis.
