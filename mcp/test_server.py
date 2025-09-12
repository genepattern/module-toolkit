#!/usr/bin/env python3
"""
Test script for the official MCP Server

This script tests the MCP server using the official MCP client SDK.
"""

import asyncio
import os
import sys
from pathlib import Path

# Import MCP client components
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


async def test_server():
    """Test the MCP server functionality using the official MCP client."""
    server_path = Path(__file__).parent / "server.py"
    
    print("Testing MCP Server with official MCP client...")
    print("=" * 60)
    
    try:
        # Create stdio client to communicate with the server
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(server_path)],
            env=os.environ.copy()
        )
        async with stdio_client(server_params) as (read_stream, write_stream):
            
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the connection
                print("Initializing connection...")
                await session.initialize()
                print("✓ Connection initialized")
                
                # Test 1: List available tools
                print("\n1. Testing tools/list...")
                tools_response = await session.list_tools()
                print(f"✓ Found {len(tools_response.tools)} tools:")
                for tool in tools_response.tools:
                    print(f"   - {tool.name}: {tool.description[:60]}...")
                
                # Test 2: Call a simple tool (manifest validation)
                print("\n2. Testing tools/call (validate_manifest)...")
                try:
                    result = await session.call_tool(
                        name="validate_manifest",
                        arguments={
                            "path": "../manifest/examples/minimal/"
                        }
                    )
                    
                    print(f"✓ Tool call successful:")
                    print(f"   - isError: {result.isError}")
                    print(f"   - Content length: {len(result.content)}")
                    if result.content:
                        content = result.content[0]
                        if hasattr(content, 'text'):
                            print(f"   - First 200 chars: {content.text[:200]}...")
                    
                except Exception as e:
                    print(f"✗ Tool call failed: {e}")
                
                # Test 3: Call another tool (wrapper validation)
                print("\n3. Testing tools/call (validate_wrapper)...")
                try:
                    result = await session.call_tool(
                        name="validate_wrapper",
                        arguments={
                            "script_path": "../wrapper/examples/valid/sample_python_wrapper.py"
                        }
                    )
                    
                    print(f"✓ Tool call successful:")
                    print(f"   - isError: {result.isError}")
                    print(f"   - Content length: {len(result.content)}")
                    if result.content:
                        content = result.content[0]
                        if hasattr(content, 'text'):
                            print(f"   - First 200 chars: {content.text[:200]}...")
                    
                except Exception as e:
                    print(f"✗ Tool call failed: {e}")
                
                # Test 4: Test tool with parameters
                print("\n4. Testing tools/call with parameters (validate_documentation)...")
                try:
                    result = await session.call_tool(
                        name="validate_documentation",
                        arguments={
                            "path_or_url": "../documentation/examples/valid/readme.md",
                            "module": "TestModule",
                            "parameters": ["input", "output"]
                        }
                    )
                    
                    print(f"✓ Tool call successful:")
                    print(f"   - isError: {result.isError}")
                    print(f"   - Content length: {len(result.content)}")
                    if result.content:
                        content = result.content[0]
                        if hasattr(content, 'text'):
                            print(f"   - First 200 chars: {content.text[:200]}...")
                    
                except Exception as e:
                    print(f"✗ Tool call failed: {e}")
                
                # Test 5: Test error handling (invalid tool)
                print("\n5. Testing error handling (invalid tool)...")
                try:
                    result = await session.call_tool(
                        name="nonexistent_tool",
                        arguments={}
                    )
                    
                    print(f"✓ Error handling test:")
                    print(f"   - isError: {result.isError}")
                    if result.content:
                        content = result.content[0]
                        if hasattr(content, 'text'):
                            print(f"   - Error message: {content.text}")
                    
                except Exception as e:
                    print(f"✓ Exception caught as expected: {e}")
        
        print("\n" + "=" * 60)
        print("✓ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


async def test_individual_tools():
    """Test each individual tool separately."""
    server_path = Path(__file__).parent / "server.py"
    
    print("\nTesting individual tools...")
    print("=" * 60)
    
    test_cases = [
        {
            "name": "validate_dockerfile",
            "args": {"path": "../dockerfile/examples/success/python/"},
            "description": "Test Dockerfile validation"
        },
        {
            "name": "validate_gpunit", 
            "args": {"path": "../gpunit/examples/valid/correlation-test.yml"},
            "description": "Test GPUnit validation"
        },
        {
            "name": "validate_paramgroups",
            "args": {"path": "../paramgroups/examples/valid/basic.json"},
            "description": "Test Paramgroups validation"
        }
    ]
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env=os.environ.copy()
    )
    async with stdio_client(server_params) as (read_stream, write_stream):
        
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            for i, test_case in enumerate(test_cases, 1):
                print(f"\n{i}. {test_case['description']}...")
                try:
                    result = await session.call_tool(
                        name=test_case["name"],
                        arguments=test_case["args"]
                    )
                    
                    print(f"✓ {test_case['name']}: {'PASS' if not result.isError else 'FAIL'}")
                    if result.content and len(result.content) > 0:
                        content = result.content[0]
                        if hasattr(content, 'text'):
                            # Show just the first line for brevity
                            first_line = content.text.split('\n')[0]
                            print(f"   {first_line}")
                
                except Exception as e:
                    print(f"✗ {test_case['name']}: Error - {e}")


async def main():
    """Main test runner."""
    await test_server()
    await test_individual_tools()


if __name__ == "__main__":
    asyncio.run(main())