#!/usr/bin/env python3
"""
MCP Tools for GenePattern Module Toolkit Linters

This module contains individual MCP tools for each linter type.
Each tool is defined separately to avoid closure issues.
"""

import io
import os
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP  # pyright: ignore[reportMissingImports]
    from mcp.types import TextContent  # pyright: ignore[reportMissingImports]
except ImportError as e:
    print(f"Error: Could not import MCP package. Please ensure 'mcp[cli]' is installed.")
    print(f"Install with: pip install 'mcp[cli]'")
    print(f"Import error: {e}")
    sys.exit(1)

# Add the parent directory to the path so we can import the linters
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Create the FastMCP server instance
mcp = FastMCP("GenePattern-Module-Toolkit")


def _run_linter_with_capture(linter_module, argv, linter_name):
    """Helper function to run a linter and capture output."""
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            exit_code = linter_module.main(argv)
        
        output = stdout_capture.getvalue()
        errors = stderr_capture.getvalue()
        result_text = f"{linter_name} validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
        if errors:
            result_text += f"\nErrors:\n{errors}"
        return [TextContent(type="text", text=result_text)]
    except SystemExit as e:
        exit_code = e.code if e.code is not None else 0
        output = stdout_capture.getvalue()
        errors = stderr_capture.getvalue()
        result_text = f"{linter_name} validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
        if errors:
            result_text += f"\nErrors:\n{errors}"
        return [TextContent(type="text", text=result_text)]


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
        import manifest.linter
        result = _run_linter_with_capture(manifest.linter, [path], "Manifest")
        return result[0].text  # Extract text from TextContent
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
        import dockerfile.linter
        
        argv = [path]
        if tag:
            argv.extend(["-t", tag])
        if cmd:
            argv.extend(["-c", cmd])
        if not cleanup:
            argv.append("--no-cleanup")
        
        result = _run_linter_with_capture(dockerfile.linter, argv, "Dockerfile")
        return result[0].text  # Extract text from TextContent
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
        import documentation.linter
        
        argv = [path_or_url]
        if module:
            argv.extend(["--module", module])
        if parameters and isinstance(parameters, list):
            argv.extend(["--parameters"] + parameters)
        
        result = _run_linter_with_capture(documentation.linter, argv, "Documentation")
        return result[0].text  # Extract text from TextContent
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
        import gpunit.linter
        
        argv = [path]
        if module:
            argv.extend(["--module", module])
        if parameters and isinstance(parameters, list):
            argv.extend(["--parameters"] + parameters)
        
        result = _run_linter_with_capture(gpunit.linter, argv, "GPUnit")
        return result[0].text  # Extract text from TextContent
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
        import paramgroups.linter
        
        argv = [path]
        if parameters and isinstance(parameters, list):
            argv.extend(["--parameters"] + parameters)
        
        result = _run_linter_with_capture(paramgroups.linter, argv, "Paramgroups")
        return result[0].text  # Extract text from TextContent
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
        import wrapper.linter
        
        argv = [script_path]
        if parameters and isinstance(parameters, list):
            argv.extend(["--parameters"] + parameters)
        
        result = _run_linter_with_capture(wrapper.linter, argv, "Wrapper")
        return result[0].text  # Extract text from TextContent
    except Exception as e:
        return f"Error running wrapper linter: {str(e)}\n{traceback.format_exc()}"


@mcp.tool()
def create_module_file(
    module_directory: str,
    filename: str, 
    content: str
) -> str:
    """
    Write a file to a GenePattern module directory.
    
    This tool creates or overwrites a file in the specified module directory with
    the provided content. It's useful for generating module files programmatically,
    such as creating configuration files, documentation, or code files as part of
    module development workflows.
    
    Args:
        module_directory: Path to the module directory where the file should be created.
                         The directory must exist or the operation will fail.
        filename: Name of the file to create or overwrite. Should include the file
                 extension (e.g., "manifest.json", "README.md", "wrapper.py").
        content: The text content to write to the file. Will be written as UTF-8 text.
    
    Returns:
        A string indicating the success or failure of the file write operation,
        including the full path of the created file and any error messages if
        the operation fails.
    """
    try:
        import os
        from pathlib import Path
        
        # Validate module directory exists
        module_path = Path(module_directory)
        if not module_path.exists():
            return f"Error: Module directory '{module_directory}' does not exist"
        
        if not module_path.is_dir():
            return f"Error: '{module_directory}' is not a directory"
        
        # Validate filename is safe (no path traversal)
        if os.path.sep in filename or ".." in filename:
            return f"Error: Invalid filename '{filename}'. Filename cannot contain path separators or '..' sequences"
        
        # Create full file path
        file_path = module_path / filename
        
        # Write the content to the file
        try:
            file_path.write_text(content, encoding='utf-8')
            file_size = len(content.encode('utf-8'))
            return f"Successfully wrote file '{filename}' to module directory '{module_directory}'\nFile path: {file_path}\nContent size: {file_size} bytes"
        except PermissionError:
            return f"Error: Permission denied when writing to '{file_path}'"
        except OSError as e:
            return f"Error: Failed to write file '{file_path}': {str(e)}"
            
    except Exception as e:
        return f"Error writing module file: {str(e)}\n{traceback.format_exc()}"
