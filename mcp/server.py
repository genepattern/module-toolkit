#!/usr/bin/env python3
"""
MCP Server for GenePattern Module Toolkit Linters

This server exposes the GenePattern module toolkit linters as MCP (Model Context Protocol) tools.
It provides a unified interface for validating various types of module files including:
- Dockerfiles
- Documentation files
- GPUnit YAML files  
- Manifest files
- Paramgroups JSON files
- Wrapper scripts

The server uses the official Python MCP SDK and requires Python 3.10+.

Usage:
    python server.py
    # or from parent directory:
    python mcp/server.py

The server will start and listen for MCP connections over stdio.
"""

import asyncio
import sys
import os

# Add current directory to path to support running from both . and ./mcp/
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server  # pyright: ignore[reportMissingImports]
    from mcp.types import Tool  # pyright: ignore[reportMissingImports]
except ImportError as e:
    print(f"Error: Could not import MCP package. Please ensure 'mcp[cli]' is installed.")
    print(f"Install with: pip install 'mcp[cli]'")
    print(f"Import error: {e}")
    sys.exit(1)

# Import tools module to register all tools
# Handle running from different directories
setup_tools = None

# First try importing from current directory (when running from mcp/)
try:
    from tools import setup_tools
except ImportError:
    pass

# If that didn't work, try importing as a relative module from parent directory
if setup_tools is None:
    try:
        import importlib.util
        tools_path = os.path.join(current_dir, "tools.py")
        spec = importlib.util.spec_from_file_location("tools", tools_path)
        tools_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tools_module)
        setup_tools = tools_module.setup_tools
    except Exception as e:
        print(f"Error: Could not import tools module: {e}")
        print("Make sure you're running from the project root or mcp/ directory.")
        sys.exit(1)

if setup_tools is None:
    print("Error: Could not load tools module")
    sys.exit(1)

# Create the server instance
server = Server("genepattern-linter-server")

# Setup all tools with the server
setup_tools(server)


@server.list_tools()
async def handle_list_tools():
    """List available tools - MCP framework requires this handler."""
    # The framework should automatically detect tools, but we need this handler
    # to enable the tools capability.
    return [
        Tool(
            name="run_linter",
            description="Universal linter tool that can validate any type of GenePattern module file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "linter_type": {
                        "type": "string", 
                        "description": "Type of linter to run",
                        "enum": ["dockerfile", "documentation", "gpunit", "manifest", "paramgroups", "wrapper"]
                    },
                    "path": {"type": "string", "description": "Path to file/directory (for dockerfile, gpunit, manifest, paramgroups)"},
                    "path_or_url": {"type": "string", "description": "Path or URL (for documentation)"},
                    "script_path": {"type": "string", "description": "Path to script file (for wrapper)"},
                    "tag": {"type": "string", "description": "Docker image tag (for dockerfile)"},
                    "cmd": {"type": "string", "description": "Command to run in container (for dockerfile)"},
                    "cleanup": {"type": "boolean", "description": "Clean up Docker images (for dockerfile)", "default": True},
                    "module": {"type": "string", "description": "Expected module name (for documentation, gpunit)"},
                    "parameters": {"type": "array", "items": {"type": "string"}, "description": "Expected parameter names (for documentation, gpunit, paramgroups, wrapper)"}
                },
                "required": ["linter_type"]
            }
        )
    ]


async def main():
    """Main entry point for the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())