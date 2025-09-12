#!/usr/bin/env python3
"""
MCP Server for GenePattern Module Toolkit Linters

This MCP server exposes the project's linters as tools that can be called 
by MCP-compatible clients. Each linter is exposed as a separate tool.

Uses the official MCP Python SDK to provide proper MCP protocol support.
The tools are defined in tools.py and automatically registered.

Available tools:
- validate_dockerfile: Validates Dockerfiles
- validate_documentation: Validates documentation files/URLs  
- validate_gpunit: Validates GPUnit YAML files
- validate_manifest: Validates GenePattern manifest files
- validate_paramgroups: Validates paramgroups.json files
- validate_wrapper: Validates wrapper scripts
"""

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

# Import tools module to register all tools
from tools import setup_tools

# Create the server instance
server = Server("genepattern-linter-server")

# Setup all tools with the server
setup_tools(server)


@server.list_tools()
async def handle_list_tools():
    """List available tools - MCP framework requires this handler."""
    # The framework should automatically detect tools, but we need this handler
    # to enable the tools capability. Return empty list since tools are auto-detected.
    from mcp.types import Tool
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