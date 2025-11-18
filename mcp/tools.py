#!/usr/bin/env python3
"""
MCP Tools for GenePattern Module Toolkit Linters

This module contains individual MCP tools for each linter type.
Each tool is a thin wrapper that calls the respective linter directly.
"""

import sys
import os
from typing import Optional, List

try:
    from mcp.server.fastmcp import FastMCP  # pyright: ignore[reportMissingImports]
except ImportError as e:
    print(f"Error: Could not import MCP package. Please ensure 'mcp[cli]' is installed.")
    print(f"Install with: pip install 'mcp[cli]'")
    print(f"Import error: {e}")
    sys.exit(1)

# Add the parent directory to the path so we can import the linters
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Create the FastMCP server instance
mcp = FastMCP("GenePattern-Module-Toolkit")


@mcp.tool()
def validate_manifest(path: str) -> str:
    """
    Validate GenePattern manifest files.
    
    This tool validates GenePattern module manifest files to ensure they conform
    to the required format and contain all necessary metadata for module execution.
    
    Args:
        path: Path to the manifest file or directory containing a manifest file.
              Can be a specific manifest.json file or a directory that contains one.
    
    Returns:
        A string containing the validation results, indicating whether the manifest 
        passed or failed validation along with detailed error messages if applicable.
    """
    try:
        import io
        import traceback
        from contextlib import redirect_stderr, redirect_stdout
        import manifest.linter

        argv = [path]
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exit_code = manifest.linter.main(argv)

            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Manifest validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Manifest validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
    except Exception as e:
        return f"Error running manifest linter: {str(e)}\n{traceback.format_exc()}"


@mcp.tool()
def validate_dockerfile(
    path: str, 
    tag: Optional[str] = None, 
    cmd: Optional[str] = None, 
    cleanup: bool = True
) -> str:
    """
    Validate Dockerfiles for GenePattern modules.
    
    This tool validates Dockerfile syntax and structure, optionally builds and tests
    the Docker image to ensure it can be used for GenePattern module execution.
    
    Args:
        path: Path to the Dockerfile or directory containing a Dockerfile.
              If a directory is provided, looks for 'Dockerfile' in that directory.
        tag: Optional Docker image tag to use when building the image for testing.
             If not provided, a default tag will be generated.
        cmd: Optional command to run inside the container for testing.
             If provided, the tool will start a container and execute this command
             to verify the image works correctly.
        cleanup: Whether to clean up Docker images after validation (default: True).
                Setting to False will leave test images on the system for debugging.
    
    Returns:
        A string containing the validation results, including build output, 
        test results, and any error messages.
    """
    try:
        import io
        import traceback
        from contextlib import redirect_stderr, redirect_stdout
        import dockerfile.linter

        argv = [path]
        if tag:
            argv.extend(["-t", tag])
        if cmd:
            argv.extend(["-c", cmd])
        if not cleanup:
            argv.append("--no-cleanup")

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exit_code = dockerfile.linter.main(argv)

            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Dockerfile validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Dockerfile validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
    except Exception as e:
        return f"Error running dockerfile linter: {str(e)}\n{traceback.format_exc()}"


@mcp.tool()
def validate_documentation(
    path_or_url: str, 
    module: Optional[str] = None, 
    parameters: Optional[list[str]] = None
) -> str:
    """
    Validate GenePattern module documentation files or URLs.
    
    This tool validates documentation to ensure it contains proper descriptions,
    parameter documentation, and usage instructions for GenePattern modules.
    It can validate local files or remote documentation URLs.
    
    Args:
        path_or_url: Path to a local documentation file (e.g., README.md) or a URL
                    pointing to online documentation. Supports Markdown, plain text,
                    and HTML formats.
        module: Optional expected module name that should be documented.
               If provided, the tool will verify that the documentation properly
               references this module name.
        parameters: Optional list of parameter names that should be documented.
                   If provided, the tool will verify that each parameter is
                   properly described in the documentation with usage examples.
    
    Returns:
        A string containing the validation results, indicating whether the 
        documentation is complete and properly formatted, along with details 
        about any missing or incorrect content.
    """
    try:
        import io
        import traceback
        from contextlib import redirect_stderr, redirect_stdout
        import documentation.linter

        argv = [path_or_url]
        if module:
            argv.extend(["--module", module])
        if parameters and isinstance(parameters, list):
            argv.extend(["--parameters"] + parameters)

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exit_code = documentation.linter.main(argv)

            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Documentation validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Documentation validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
    except Exception as e:
        return f"Error running documentation linter: {str(e)}\n{traceback.format_exc()}"


@mcp.tool()
def validate_gpunit(
    path: str, 
    module: Optional[str] = None, 
    parameters: Optional[list[str]] = None
) -> str:
    """
    Validate GPUnit test definition YAML files.
    
    This tool validates GPUnit YAML files that define automated tests for GenePattern
    modules. GPUnit tests ensure modules work correctly by running them with known
    inputs and verifying expected outputs.
    
    Args:
        path: Path to the GPUnit YAML file to validate. The file should contain
              test definitions with input parameters, expected outputs, and
              validation criteria.
        module: Optional expected module name that the GPUnit test should target.
               If provided, validates that the test file correctly references
               this module and its interface.
        parameters: Optional list of parameter names that should be tested.
                   If provided, validates that the GPUnit test covers all
                   specified parameters with appropriate test cases.
    
    Returns:
        A string containing the validation results, indicating whether the GPUnit 
        test file is properly structured and contains valid test definitions, 
        along with any syntax or logic errors.
    """
    try:
        import io
        import traceback
        from contextlib import redirect_stderr, redirect_stdout
        import gpunit.linter

        argv = [path]
        if module:
            argv.extend(["--module", module])
        if parameters and isinstance(parameters, list):
            argv.extend(["--parameters"] + parameters)

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exit_code = gpunit.linter.main(argv)

            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"GPUnit validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"GPUnit validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
    except Exception as e:
        return f"Error running gpunit linter: {str(e)}\n{traceback.format_exc()}"


@mcp.tool()
def validate_paramgroups(
    path: str, 
    parameters: Optional[list[str]] = None
) -> str:
    """
    Validate GenePattern paramgroups.json files.
    
    This tool validates paramgroups.json files that define parameter groupings
    and UI layout for GenePattern modules. These files control how parameters
    are organized and displayed in the GenePattern web interface.
    
    Args:
        path: Path to the paramgroups.json file to validate. The file should
              contain valid JSON with parameter group definitions, including
              group names, descriptions, and parameter memberships.
        parameters: Optional list of parameter names that should be included
                   in the parameter groups. If provided, validates that all
                   specified parameters are properly assigned to groups and
                   that no orphaned parameters exist.
    
    Returns:
        A string containing the validation results, indicating whether the 
        paramgroups.json file is properly formatted and contains valid parameter 
        groupings, along with any JSON syntax errors or logical inconsistencies.
    """
    try:
        import io
        import traceback
        from contextlib import redirect_stderr, redirect_stdout
        import paramgroups.linter

        argv = [path]
        if parameters and isinstance(parameters, list):
            argv.extend(["--parameters"] + parameters)

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exit_code = paramgroups.linter.main(argv)

            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Paramgroups validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Paramgroups validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
    except Exception as e:
        return f"Error running paramgroups linter: {str(e)}\n{traceback.format_exc()}"


@mcp.tool()
def validate_wrapper(
    script_path: str, 
    parameters: Optional[list[str]] = None
) -> str:
    """
    Validate GenePattern wrapper scripts.
    
    This tool validates wrapper scripts that serve as the interface between
    GenePattern and the underlying analysis tools. Wrapper scripts handle
    parameter parsing, input validation, tool execution, and output formatting.
    
    Args:
        script_path: Path to the wrapper script file to validate. Can be Python,
                    R, shell script, or other executable formats. The script should
                    follow GenePattern wrapper conventions for parameter handling
                    and output generation.
        parameters: Optional list of parameter names that the wrapper script
                   should handle. If provided, validates that the script properly
                   processes all specified parameters, including required parameter
                   validation and optional parameter defaults.
    
    Returns:
        A string containing the validation results, indicating whether the wrapper 
        script follows proper conventions, handles parameters correctly, and includes 
        necessary error handling, along with any syntax errors or missing functionality.
    """
    try:
        import io
        import traceback
        from contextlib import redirect_stderr, redirect_stdout
        import wrapper.linter

        argv = [script_path]
        if parameters and isinstance(parameters, list):
            argv.extend(["--parameters"] + parameters)

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exit_code = wrapper.linter.main(argv)

            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Wrapper validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Wrapper validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
    except Exception as e:
        return f"Error running wrapper linter: {str(e)}\n{traceback.format_exc()}"
