# GenePattern Wrapper Script Linter

A production-ready linter for validating wrapper scripts across multiple programming languages with syntax and parameter validation.

## Overview

The wrapper script linter validates wrapper scripts through comprehensive checks including file validation, script type detection, syntax validation, and optional parameter presence validation. It supports Python, Bash, R, and other scripting languages with intelligent detection and language-specific validation.

## Usage

```bash
python wrapper/linter.py [SCRIPT_PATH] [OPTIONS]
```

### Arguments

- `SCRIPT_PATH` - Path to wrapper script file

### Options

- `--parameters PARAM1 PARAM2 ...` - List of expected parameter names for validation (optional)

### Examples

```bash
# Basic wrapper script validation
python wrapper/linter.py /path/to/wrapper.py

# Validate different script types
python wrapper/linter.py /path/to/wrapper.sh
python wrapper/linter.py /path/to/wrapper.R
python wrapper/linter.py /path/to/wrapper.pl

# Include parameter validation
python wrapper/linter.py wrapper.py --parameters input output method threshold

# Complex parameter validation
python wrapper/linter.py wrapper.sh --parameters input.file gene.sets.database permutations random.seed window.size
```

## Supported Script Types

### Full Support (Syntax + Parameter Validation)
- **Python** (`.py`) - AST-based syntax validation, comprehensive parameter detection
- **Bash** (`.sh`, `.bash`) - External bash syntax validation, shell-specific patterns
- **R** (`.r`, `.R`) - External R syntax validation, R-specific patterns

### Basic Support (File + Parameter Validation)
- **Perl** (`.pl`, `.perl`) - Pattern-based parameter detection
- **JavaScript** (`.js`) - Basic validation and parameter search
- **Ruby** (`.rb`, `.ruby`) - Basic validation and parameter search
- **Other** - Generic parameter search patterns

## Script Type Detection

The linter intelligently detects script types using multiple strategies:

### 1. File Extension Analysis
- `.py` → Python
- `.sh`, `.bash` → Bash
- `.r`, `.R` → R
- `.pl`, `.perl` → Perl
- `.js` → JavaScript
- `.rb` → Ruby

### 2. Shebang Line Analysis
- `#!/usr/bin/env python` → Python
- `#!/bin/bash`, `#!/bin/sh` → Bash
- `#!/usr/bin/env Rscript` → R
- `#!/usr/bin/env perl` → Perl

### 3. Content Pattern Recognition
- Python: `import`, `def`, `class`, `if __name__`
- Bash: `echo`, `$1`, `${var}`, `do/fi`
- R: `library()`, `<-`, `args <-`

## Validation Tests

The linter runs the following modular tests:

### 1. File Validation (`test_file_validation.py`)
- **Purpose**: Validates script file properties and detects type
- **Checks**:
  - File exists and is readable
  - File is a regular file (not directory)
  - Script type detection and classification
  - File permissions and executability
  - Shebang line presence and format
  - Basic file statistics (line counts)

### 2. Syntax Validation (`test_syntax_validation.py`)
- **Purpose**: Validates script syntax using language-specific tools
- **Python Checks**:
  - AST (Abstract Syntax Tree) parsing
  - Comprehensive syntax error detection
  - Line-level error reporting
- **Bash Checks**:
  - External `bash -n` validation (if available)
  - Shell syntax error detection
- **R Checks**:
  - External `Rscript` parsing validation (if available)
  - R syntax error detection
- **Other Languages**:
  - Basic syntax pattern checking
  - Common syntax error detection (unmatched quotes, brackets)

### 3. Parameter Validation (`test_parameter_validation.py`)
- **Purpose**: Validates parameter presence using language-specific patterns (conditional)
- **Python Patterns**:
  - `argparse`: `add_argument('--param')`
  - Argument access: `args.param`, `options.param`
  - Dictionary access: `config['param']`
  - Environment variables: `os.environ.get('param')`
  - Click decorators: `@click.option('--param')`
- **Bash Patterns**:
  - Positional parameters: `$1`, `$2`, `${param}`
  - Command line options: `--param`, `-p`
  - Variable assignments: `param="$2"`
  - getopts parsing: `getopts "p:o:" opt`
- **R Patterns**:
  - optparse: `make_option('--param')`
  - Variable assignments: `param <- args$param`
  - Command line args: `commandArgs()`
  - List access: `options$param`
- **Requirements**: Requires `--parameters` argument

## Exit Codes

- `0` - All validation checks passed
- `1` - One or more validation checks failed

## Output Examples

### Success (Python Script)
```
Running modular tests on wrapper script: /path/to/wrapper.py
  Test 'Test File Validation': 4 info message(s)
  Test 'Test Syntax Validation': 1 info message(s)
  Test 'Test Parameter Validation': 5 info message(s)
Ran 3 test module(s)

PASS: Wrapper script '/path/to/wrapper.py' passed all validation checks.
```

### Success (Bash Script)
```
Running modular tests on wrapper script: /path/to/wrapper.sh
  Test 'Test File Validation': 4 info message(s)
  Test 'Test Syntax Validation': 1 info message(s)
  Test 'Test Parameter Validation': 5 info message(s)
Ran 3 test module(s)

PASS: Wrapper script '/path/to/wrapper.sh' passed all validation checks.
```

### Failure (Syntax Error)
```
Running modular tests on wrapper script: /path/to/wrapper.py
  Test 'Test File Validation': 1 warning(s) found
  Test 'Test Syntax Validation': 1 error(s) found
  Test 'Test Parameter Validation': 1 info message(s)
Ran 3 test module(s)

FAIL: Wrapper script '/path/to/wrapper.py' failed 1 check and has 1 warning:
INFO: Detected script type: PYTHON
WARNING: Script file is not executable (Permissions: 644) (Consider setting execute permissions with: chmod +x /path/to/wrapper.py)
INFO: Script contains 89 lines (67 non-empty)
INFO: Found shebang: #!/usr/bin/env python
ERROR: Python syntax error: Line 14: invalid syntax ('print("unclosed string)
INFO: Parameter validation skipped - no expected parameters provided (Use --parameters to enable parameter validation)
```

### Failure (Missing Parameters)
```
Running modular tests on wrapper script: /path/to/wrapper.py
  Test 'Test File Validation': 4 info message(s)
  Test 'Test Syntax Validation': 1 info message(s)
  Test 'Test Parameter Validation': 3 error(s) found
Ran 3 test module(s)

FAIL: Wrapper script '/path/to/wrapper.py' failed 3 checks:
INFO: Detected script type: PYTHON
INFO: Script file is executable (Permissions: 755)
INFO: Script contains 89 lines (67 non-empty)
INFO: Found shebang: #!/usr/bin/env python
INFO: Python syntax is valid
ERROR: Parameter 'missing.param' not found in PYTHON script (Expected parameter should appear in script)
ERROR: Parameter 'another.missing' not found in PYTHON script (Expected parameter should appear in script)
ERROR: Parameter validation summary: 1/3 parameters found, 2 missing
```

### Warning (Missing Dependencies)
```
Running modular tests on wrapper script: /path/to/wrapper.sh
  Test 'Test File Validation': 4 info message(s)
  Test 'Test Syntax Validation': 1 warning(s) found
  Test 'Test Parameter Validation': 1 info message(s)
Ran 3 test module(s)

PASS: Wrapper script '/path/to/wrapper.sh' passed all validation checks.

INFO: Detected script type: BASH
INFO: Script file is executable (Permissions: 755)
INFO: Script contains 45 lines (38 non-empty)
INFO: Found shebang: #!/bin/bash
WARNING: Could not validate bash syntax: bash command not found - cannot validate bash syntax
INFO: Parameter validation skipped - no expected parameters provided (Use --parameters to enable parameter validation)
```

## Dependencies

### Required
- Python 3.7+ (uses standard library only)

### Optional (for enhanced validation)
- **bash**: For Bash script syntax validation
- **Rscript** (R): For R script syntax validation

### No External Python Packages Required
All functionality uses Python standard library:
- `ast` for Python syntax validation
- `subprocess` for external tool integration
- `re` for pattern matching
- `os` for file operations

## Use Cases

### Wrapper Development
- Validate wrapper scripts during development
- Ensure syntax correctness across languages
- Verify parameter handling implementation

### CI/CD Integration
- Include in build pipelines to catch wrapper issues
- Automated validation of script syntax and parameters
- Prevent deployment of broken wrapper scripts

### Parameter Auditing
- Check that wrapper scripts handle all expected parameters
- Identify missing parameter implementations
- Ensure parameter naming consistency

### Multi-Language Projects
- Consistent validation across Python, Bash, and R wrappers
- Language-appropriate syntax checking
- Unified parameter validation approach

## Architecture

The linter uses a modular architecture with language-aware processing:

- File validation provides script type detection for subsequent tests
- Syntax validation uses language-specific tools and fallbacks
- Parameter validation employs language-appropriate search patterns
- Shared context allows script content and type to be passed between tests
- Graceful degradation when external tools (bash, R) are unavailable

## Performance Notes

- **Python Syntax**: Very fast using built-in AST parsing
- **Bash Syntax**: Quick external validation (if bash available)
- **R Syntax**: May take longer depending on R startup time
- **Parameter Search**: Efficient regex-based pattern matching
- **Large Files**: Handles large wrapper scripts efficiently

## Security Considerations

- No script execution during validation
- External syntax tools run in safe mode (parse-only)
- No persistent changes to system
- Safe handling of malformed scripts

## Language-Specific Features

### Python Support
- Full AST-based syntax validation
- Comprehensive argument parsing pattern detection
- Support for argparse, click, optparse patterns
- Environment variable detection

### Bash Support
- External bash validation for accuracy
- Shell-specific variable pattern detection
- getopts and manual parsing support
- Positional parameter detection

### R Support
- External R parsing validation
- optparse and argparse pattern detection
- R-specific assignment operators
- Command line argument handling patterns

### Generic Support
- Basic syntax error detection for any language
- Generic parameter search patterns
- File validation regardless of language
- Extensible pattern matching system
