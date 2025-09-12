#!/usr/bin/env python3
"""
MCP Tools for GenePattern Module Toolkit Linters

This module contains a single unified linter tool that can validate any type of file.
"""

import io
import os
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Dict, Optional

try:
    from mcp.types import TextContent
except ImportError as e:
    print(f"Error: Could not import MCP package. Please ensure 'mcp[cli]' is installed.")
    print(f"Install with: pip install 'mcp[cli]'")
    print(f"Import error: {e}")
    sys.exit(1)

# Add the parent directory to the path so we can import the linters
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def setup_tools(server):
    """Setup the unified linter tool."""
    
    @server.call_tool()
    async def run_linter(*args, **kwargs):
        """
        Universal linter tool that can validate any type of GenePattern module file.
        
        Args:
            linter_type: Type of linter to run (dockerfile, documentation, gpunit, manifest, paramgroups, wrapper)
            path: Path to file/directory (for dockerfile, gpunit, manifest, paramgroups)
            path_or_url: Path or URL (for documentation)
            script_path: Path to script file (for wrapper)
            tag: Docker image tag (for dockerfile)
            cmd: Command to run in container (for dockerfile)
            cleanup: Clean up Docker images (for dockerfile)
            module: Expected module name (for documentation, gpunit)
            parameters: Expected parameter names (for documentation, gpunit, paramgroups, wrapper)
        """
        # Extract parameters from args (MCP framework passes tool_name, arguments_dict)
        if len(args) >= 2:
            tool_name = args[0]
            arguments = args[1]
        else:
            arguments = kwargs
        
        # Extract parameters from the arguments dictionary
        linter_type = arguments.get('linter_type')
        path = arguments.get('path')
        path_or_url = arguments.get('path_or_url')
        script_path = arguments.get('script_path')
        tag = arguments.get('tag')
        cmd = arguments.get('cmd')
        cleanup = arguments.get('cleanup', True)
        module = arguments.get('module')
        parameters = arguments.get('parameters')
        
        # Import the specific linter module and build arguments based on linter type
        if linter_type == 'dockerfile':
            import dockerfile.linter
            if not path:
                return [TextContent(type="text", text="Error: 'path' is required for dockerfile validation")]
            
            argv = [path]
            if tag:
                argv.extend(["-t", tag])
            if cmd:
                argv.extend(["-c", cmd])
            if not cleanup:
                argv.append("--no-cleanup")
            validation_name = "Dockerfile"
            linter_module = dockerfile.linter
                
        elif linter_type == 'documentation':
            import documentation.linter
            if not path_or_url:
                return [TextContent(type="text", text="Error: 'path_or_url' is required for documentation validation")]
            
            argv = [path_or_url]
            if module:
                argv.extend(["--module", module])
            if parameters and isinstance(parameters, list):
                argv.extend(["--parameters"] + parameters)
            validation_name = "Documentation"
            linter_module = documentation.linter
                
        elif linter_type == 'gpunit':
            import gpunit.linter
            if not path:
                return [TextContent(type="text", text="Error: 'path' is required for gpunit validation")]
            
            argv = [path]
            if module:
                argv.extend(["--module", module])
            if parameters and isinstance(parameters, list):
                argv.extend(["--parameters"] + parameters)
            validation_name = "GPUnit"
            linter_module = gpunit.linter
                
        elif linter_type == 'manifest':
            import manifest.linter
            if not path:
                return [TextContent(type="text", text="Error: 'path' is required for manifest validation")]
            
            argv = [path]
            validation_name = "Manifest"
            linter_module = manifest.linter
                
        elif linter_type == 'paramgroups':
            import paramgroups.linter
            if not path:
                return [TextContent(type="text", text="Error: 'path' is required for paramgroups validation")]
            
            argv = [path]
            if parameters and isinstance(parameters, list):
                argv.extend(["--parameters"] + parameters)
            validation_name = "Paramgroups"
            linter_module = paramgroups.linter
                
        elif linter_type == 'wrapper':
            import wrapper.linter
            if not script_path:
                return [TextContent(type="text", text="Error: 'script_path' is required for wrapper validation")]
            
            argv = [script_path]
            if parameters and isinstance(parameters, list):
                argv.extend(["--parameters"] + parameters)
            validation_name = "Wrapper"
            linter_module = wrapper.linter
                
        else:
            return [TextContent(type="text", text=f"Error: Unknown linter type '{linter_type}'. Valid types: dockerfile, documentation, gpunit, manifest, paramgroups, wrapper")]
        
        # Ready to call the linter
        
        # Capture stdout and stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exit_code = linter_module.main(argv)
            
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"{validation_name} validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            
            return [TextContent(type="text", text=result_text)]
            
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"{validation_name} validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return [TextContent(type="text", text=result_text)]