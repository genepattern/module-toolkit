# GenePattern GPUnit Linter

A production-ready linter for validating GPUnit test files used in GenePattern module testing.

## Overview

The GPUnit linter validates GPUnit YAML test files through comprehensive checks including YAML format validation, structure validation, and optional module/parameter validation. GPUnit files define automated tests for GenePattern modules.

## Usage

```bash
python gpunit/linter.py [PATH] [OPTIONS]
```

### Arguments

- `PATH` - Path to a GPUnit .yml file OR directory containing GPUnit .yml files

### Options

- `--module MODULE` - Expected module name or LSID for validation (optional)
- `--parameters PARAM1 PARAM2 ...` - List of expected parameter names for validation (optional)

### Examples

```bash
# Basic GPUnit validation (single file)
python gpunit/linter.py /path/to/test.yml

# Validate all GPUnit files in a directory
python gpunit/linter.py /path/to/gpunit/directory/

# Include module validation
python gpunit/linter.py test.yml --module CorrelationMatrix

# Include module validation with LSID
python gpunit/linter.py test.yml --module "urn:lsid:genepattern.org:module.analysis:00474"

# Include parameter validation
python gpunit/linter.py test.yml --parameters input method dimension output

# Full validation with module and parameters
python gpunit/linter.py test.yml --module spatialGE.STenrich --parameters input.file gene.sets.database permutations random.seed
```

## Validation Tests

The linter runs the following modular tests:

### 1. File Validation (`test_file_validation.py`)
- **Purpose**: Validates file existence and YAML format
- **Checks**:
  - File exists and is readable
  - File has .yml extension
  - File contains valid YAML syntax
  - YAML can be parsed successfully
  - File is not empty

### 2. Structure Validation (`test_structure_validation.py`)
- **Purpose**: Validates GPUnit YAML structure
- **Checks**:
  - Required top-level fields: `name`, `module`, `params`, `assertions`
  - Field types are correct:
    - `name`: string
    - `module`: string  
    - `params`: object/dictionary
    - `assertions`: object/dictionary
  - Structure follows GPUnit specification

### 3. Module Validation (`test_module_validation.py`)
- **Purpose**: Validates module name/LSID matching (conditional)
- **Checks**:
  - Module field matches expected module name
  - Supports both simple names and LSID formats
  - Case-sensitive and case-insensitive matching
  - LSID component matching for complex identifiers
- **Requirements**: Requires `--module` argument

### 4. Parameter Validation (`test_parameter_validation.py`)
- **Purpose**: Validates parameter presence (conditional)
- **Checks**:
  - All expected parameters are present in `params` section
  - No expected parameters are missing
  - Identifies which parameters are found/missing
- **Requirements**: Requires `--parameters` argument

## Expected Input Format

GPUnit files should follow this YAML format:

```yaml
# Comments are allowed
name: "CorrelationMatrix - Basic test"
module: urn:lsid:genepattern.org:module.analysis:00474
params:
  input: "data/example_input.gct"
  method: "pearson"
  dimension: "column"
  output: "output.gct"
assertions:
  diffCmd: diff <%gpunit.diffStripTrailingCR%> -q
  files:
    "output.gct":
      diff: "data/example_output.gct"
```

### Field Descriptions

- **name** (required): Human-readable test name
- **module** (required): Module name or LSID being tested
- **params** (required): Dictionary of parameter values for the test
- **assertions** (required): Test assertions and expected outcomes

## Exit Codes

- `0` - All validation checks passed
- `1` - One or more validation checks failed

## Output Examples

### Success (Basic Validation)
```
Running modular tests on GPUnit file: /path/to/test.yml
  Test 'Test File Validation': PASSED
  Test 'Test Structure Validation': PASSED  
  Test 'Test Module Validation': 1 info message(s)
  Test 'Test Parameter Validation': 1 info message(s)
Ran 4 test module(s)

PASS: GPUnit file '/path/to/test.yml' passed all validation checks.
```

### Success (Directory of Files)
```
Running modular tests on GPUnit files in directory: /path/to/tests/
Found 3 GPUnit files: correlation-test.yml, tfsites-test.yml, stenrich-test.yml

=== correlation-test.yml ===
  Test 'Test File Validation': PASSED
  Test 'Test Structure Validation': PASSED
  Test 'Test Module Validation': PASSED
  Test 'Test Parameter Validation': PASSED
Ran 4 test module(s)
PASS: correlation-test.yml passed all validation checks.

=== tfsites-test.yml ===
  Test 'Test File Validation': PASSED
  Test 'Test Structure Validation': PASSED
  Test 'Test Module Validation': PASSED
  Test 'Test Parameter Validation': PASSED  
Ran 4 test module(s)
PASS: tfsites-test.yml passed all validation checks.

=== stenrich-test.yml ===
  Test 'Test File Validation': PASSED
  Test 'Test Structure Validation': PASSED
  Test 'Test Module Validation': PASSED
  Test 'Test Parameter Validation': PASSED
Ran 4 test module(s)
PASS: stenrich-test.yml passed all validation checks.

Overall result: All 3 GPUnit files passed validation.
```

### Failure (Structure Issues)
```
Running modular tests on GPUnit file: /path/to/test.yml
  Test 'Test File Validation': PASSED
  Test 'Test Structure Validation': 2 error(s) found
  Test 'Test Module Validation': 1 error(s) found
Ran 4 test module(s)

FAIL: GPUnit file '/path/to/test.yml' failed 3 checks:
ERROR: Missing required field: 'name'
ERROR: Field 'params' must be a dictionary/object
ERROR: Cannot validate module: document content not available
```

### Failure (Module/Parameter Mismatch)
```
Running modular tests on GPUnit file: /path/to/test.yml
  Test 'Test Module Validation': 1 error(s) found
  Test 'Test Parameter Validation': 2 error(s) found
Ran 4 test module(s)

FAIL: GPUnit file '/path/to/test.yml' failed 3 checks:
ERROR: Module name 'ExpectedModule' does not match GPUnit module 'ActualModule'
ERROR: Expected parameter 'missing.param' not found in GPUnit params
ERROR: Expected parameter 'another.missing' not found in GPUnit params
```

## Dependencies

- **PyYAML** (required): For YAML file parsing
- Python 3.7+

Install dependencies:
```bash
pip install PyYAML>=6.0
```

## Use Cases

### Test Development
- Validate GPUnit test files during development
- Ensure test structure compliance with GPUnit specification
- Verify test parameters match module expectations

### CI/CD Integration
- Include in build pipelines to catch test definition issues
- Automated validation of test suites
- Prevent deployment of modules with invalid tests

### Test Auditing
- Check that GPUnit tests cover expected module parameters
- Identify missing parameter coverage in test suites
- Ensure test module references are correct

## Architecture

The linter uses a modular architecture with conditional testing:

- File validation ensures basic YAML validity and .yml extension
- Structure validation checks GPUnit-specific format requirements
- Module validation only runs when expected module provided
- Parameter validation only runs when expected parameters provided
- Shared context allows tests to pass parsed YAML data between stages

Support for both single files and directories makes it suitable for validating individual test files or entire test suites.

## PyYAML Integration

The linter includes automatic PyYAML availability checking:

- Graceful handling when PyYAML is not installed
- Clear error messages with installation instructions
- Fallback behavior for missing dependencies
- Version compatibility with PyYAML 6.0+
