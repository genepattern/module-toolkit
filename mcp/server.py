#!/usr/bin/env python3
"""
MCP Server for GenePattern Module Toolkit Linters

This server exposes the GenePattern module toolkit linters as MCP (Model Context Protocol) tools.
It provides individual tools for validating various types of module files including:
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

# Import all tools and the FastMCP server instance
try:
    from tools import mcp
except ImportError as e:
    print(f"Error: Could not import tools module: {e}")
    print("Make sure you're running from the project root or mcp/ directory.")
    sys.exit(1)


def main():
    """Main entry point for the MCP server."""
    # FastMCP handles stdio server setup and async loop automatically
    mcp.run()


if __name__ == "__main__":
    main()