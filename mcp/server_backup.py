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

# Import tools module to register all tools
from tools import setup_tools

# Create the server instance
server = Server("genepattern-linter-server")

# Setup all tools with the server
setup_tools(server)


# The list_tools handler is automatically provided by the framework
# based on the registered @server.call_tool() decorated functions


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