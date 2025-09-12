# GenePattern Dockerfile Linter

A production-ready linter for validating Dockerfiles with build and runtime testing capabilities.

## Overview

The Dockerfile linter validates Dockerfiles through comprehensive checks including file validation, Docker availability, build testing, and optional runtime validation. It's designed specifically for GenePattern module Dockerfiles.

## Usage

```bash
python dockerfile/linter.py [PATH] [OPTIONS]
```

### Arguments

- `PATH` - Path to a Dockerfile OR directory containing a Dockerfile

### Options

- `--tag TAG` - Docker tag to use for build testing (optional)
- `--cmd COMMAND` - Command to test during runtime validation (optional)

### Examples

```bash
# Basic Dockerfile validation
python dockerfile/linter.py /path/to/Dockerfile

# Validate Dockerfile in a directory
python dockerfile/linter.py /path/to/module/directory/

# Include build testing with custom tag
python dockerfile/linter.py /path/to/Dockerfile --tag my-test-image:latest

# Include runtime testing with command
python dockerfile/linter.py /path/to/Dockerfile --cmd "python --version"

# Full validation with build and runtime testing
python dockerfile/linter.py /path/to/Dockerfile --tag my-image:test --cmd "ls /app"
```

## Validation Tests

The linter runs the following modular tests:

### 1. File Validation (`test_file_validation.py`)
- **Purpose**: Validates Dockerfile existence and basic format
- **Checks**:
  - File exists and is readable
  - File basename is 'Dockerfile' (case-sensitive)
  - File contains valid Docker instructions
  - Basic Dockerfile format validation

### 2. Docker Availability (`test_docker_availability.py`)
- **Purpose**: Ensures Docker CLI is available and functional
- **Checks**:
  - Docker command is available in PATH
  - Docker daemon is running and accessible
  - User has permissions to run Docker commands
  - Docker version information

### 3. Build Validation (`test_build_validation.py`)
- **Purpose**: Tests actual Docker image building
- **Checks**:
  - Dockerfile can be successfully built into an image
  - No build errors or failures
  - Generates a tagged image for runtime testing
  - Build process completes within reasonable time

### 4. Runtime Validation (`test_runtime_validation.py`)
- **Purpose**: Tests container runtime behavior (conditional)
- **Checks**:
  - Container can be created and started
  - Specified command executes successfully
  - Container environment is functional
  - Proper cleanup after testing
- **Requirements**: Requires `--cmd` argument and successful build

## Expected Input Format

Standard Dockerfile format:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "app.py"]
```

## Exit Codes

- `0` - All validation checks passed
- `1` - One or more validation checks failed

## Output Examples

### Success (Basic Validation)
```
Running modular tests on Dockerfile: /path/to/Dockerfile
  Test 'Test File Validation': PASSED
  Test 'Test Docker Availability': PASSED
  Test 'Test Build Validation': PASSED
  Test 'Test Runtime Validation': 1 info message(s)
Ran 4 test module(s)

PASS: Dockerfile '/path/to/Dockerfile' passed all validation checks.
```

### Success (With Runtime Testing)
```
Running modular tests on Dockerfile: /path/to/Dockerfile
  Test 'Test File Validation': PASSED
  Test 'Test Docker Availability': PASSED
  Test 'Test Build Validation': PASSED
  Test 'Test Runtime Validation': PASSED
Ran 4 test module(s)

PASS: Dockerfile '/path/to/Dockerfile' passed all validation checks.
```

### Failure (Build Error)
```
Running modular tests on Dockerfile: /path/to/Dockerfile
  Test 'Test File Validation': PASSED
  Test 'Test Docker Availability': PASSED
  Test 'Test Build Validation': 1 error(s) found
  Test 'Test Runtime Validation': 1 error(s) found
Ran 4 test module(s)

FAIL: Dockerfile '/path/to/Dockerfile' failed 2 checks:
ERROR: Docker build failed: Step 3/5 : RUN pip install invalid-package
ERROR: Cannot test runtime: No Docker tag available
```

## Dependencies

- Python 3.7+ (uses standard library only)
- Docker CLI and daemon (required for build/runtime testing)
- No external Python packages required

## Performance Notes

- **Build Testing**: Can take several minutes depending on Dockerfile complexity
- **Runtime Testing**: Adds additional time for container startup and command execution
- **Cleanup**: Automatically removes test containers and optionally test images
- **Timeouts**: Built-in timeouts prevent hanging on problematic builds

## Security Considerations

- Tests run in isolated containers
- Automatic cleanup of test artifacts
- No persistent changes to system
- Safe handling of build failures

## Architecture

The linter uses a modular architecture with shared context between tests:

- File validation provides basic Dockerfile analysis
- Docker availability ensures prerequisites are met
- Build validation creates tagged images for runtime testing
- Runtime validation uses built images from previous test
- Shared context allows tests to pass data between stages

Each test can gracefully skip if prerequisites aren't met (e.g., runtime testing skips if no command provided).
