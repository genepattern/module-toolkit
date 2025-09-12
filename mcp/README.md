# GenePattern Module Toolkit MCP Server

This directory contains an MCP (Model Context Protocol) server that exposes the project's linters as tools. The server allows MCP-compatible clients to validate GenePattern module components through a unified interface.

## Requirements

- Python 3.10+ (Required for official MCP Python SDK)
- All dependencies for the individual linters
- MCP Python SDK: `pip install "mcp[cli]"`

## Available Tools

The server exposes the following validation tools:

### 1. `validate_dockerfile`
Validates Dockerfiles through file validation, Docker availability checks, build validation, and optional runtime testing.

**Parameters:**
- `path` (required): Path to Dockerfile or directory containing Dockerfile
- `tag` (optional): Name:tag for the built image
- `cmd` (optional): Command to run in the built container for runtime testing
- `cleanup` (optional): Clean up built images after testing (default: true)

### 2. `validate_documentation`
Validates documentation files through content retrieval, module validation, and parameter validation. Supports HTML, Markdown, PDF, TXT files and HTTP/HTTPS URLs.

**Parameters:**
- `path_or_url` (required): Path to documentation file or URL to documentation
- `module` (optional): Expected module name for validation
- `parameters` (optional): List of expected parameter names for validation

### 3. `validate_gpunit`
Validates GPUnit YAML files through file validation, structure validation, and optional module/parameter validation.

**Parameters:**
- `path` (required): Path to GPUnit .yml file or directory containing .yml files
- `module` (optional): Expected module name or LSID for validation
- `parameters` (optional): List of expected parameter names for validation

### 4. `validate_manifest`
Validates GenePattern module manifest files for compliance with the manifest specification.

**Parameters:**
- `path` (required): Path to manifest file or directory containing manifest file

### 5. `validate_paramgroups`
Validates paramgroups.json files through file validation, structure validation, and optional parameter validation.

**Parameters:**
- `path` (required): Path to paramgroups.json file or directory containing paramgroups.json file
- `parameters` (optional): List of expected parameter names for validation

### 6. `validate_wrapper`
Validates wrapper scripts through file validation, syntax validation, and parameter validation. Supports Python, Bash, R, and other script types.

**Parameters:**
- `script_path` (required): Path to wrapper script file
- `parameters` (optional): List of expected parameter names for validation

## Usage

### Installation

First, ensure you have Python 3.10+ and install the MCP framework:

```bash
pip install "mcp[cli]"
```

### Running the Server

To start the MCP server using stdio transport:

```bash
cd mcp/
python server.py
```

The server communicates via JSON-RPC over stdin/stdout, following the MCP protocol.

**Note**: Make sure to activate the correct Python environment that has the MCP framework installed.

### Testing the Server

A test script is provided to verify the server functionality:

```bash
cd mcp/
python test_server.py
```

### Example MCP Requests

#### Initialize
```json
{
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "my-client",
      "version": "1.0.0"
    }
  }
}
```

#### List Available Tools
```json
{
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

#### Call a Tool
```json
{
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "validate_manifest",
    "arguments": {
      "path": "/path/to/manifest"
    }
  }
}
```

#### Call a Tool with Options
```json
{
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "validate_dockerfile",
    "arguments": {
      "path": "/path/to/Dockerfile",
      "tag": "myimage:latest",
      "cmd": "echo 'test'"
    }
  }
}
```

## Integration with MCP Clients

This server can be used with any MCP-compatible client. Popular options include:

- [Claude Desktop](https://claude.ai/desktop) - Configure in MCP settings
- [MCP Inspector](https://github.com/modelcontextprotocol/inspector) - For debugging and testing
- Custom MCP clients using the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

### Claude Desktop Configuration

Add the following to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "genepattern-linters": {
      "command": "python",
      "args": ["/path/to/module-toolkit/mcp/server.py"],
      "cwd": "/path/to/module-toolkit/mcp"
    }
  }
}
```

## Notes

- This implementation uses the official MCP Python SDK for full protocol compliance
- All linter output is captured and returned in the tool responses
- The server handles both successful validation and error cases appropriately
- Tool responses include the full output from the linters, making it easy to understand validation results
- The server requires Python 3.10+ due to MCP SDK requirements

## Files

- `server.py` - Main MCP server implementation
- `test_server.py` - Test script for server functionality
- `README.md` - This documentation file
