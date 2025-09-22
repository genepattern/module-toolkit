import os
import sys
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerStdio
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


system_prompt = """
You are an expert software architect and DevOps specialist with deep expertise in 
creating robust wrapper scripts for bioinformatics pipelines and GenePattern modules. 
Your task is to create production-ready wrapper scripts that provide seamless 
integration between GenePattern's interface and underlying bioinformatics tools.

Key requirements for GenePattern wrapper scripts:
- Create clean, maintainable code that handles parameter passing efficiently
- Implement comprehensive error handling and input validation
- Design for reliability with proper exit codes and error reporting
- Support multiple programming languages (Python, Bash, R) as appropriate
- Follow best practices for argument parsing and data handling
- Ensure robust file I/O operations with proper path handling
- Include logging and debugging capabilities for troubleshooting

Wrapper Script Design Principles:
- Use appropriate scripting language based on tool requirements and ecosystem
- Implement clear separation between parameter parsing, validation, and execution
- Provide informative error messages that help users diagnose issues
- Handle edge cases gracefully (missing files, invalid parameters, etc.)
- Ensure scripts are portable across different environments
- Support both required and optional parameters with sensible defaults
- Include proper shebang lines and execute permissions

Language-Specific Best Practices:
- Python: Use argparse for argument parsing, subprocess for tool execution
- Bash: Use getopts or manual parsing, proper variable quoting and error checking
- R: Use optparse or argparse, proper error handling with tryCatch
- General: Follow language conventions and idioms for maintainability

Error Handling Strategy:
- Validate all input parameters before tool execution
- Check file existence and permissions before processing
- Capture and report tool execution errors with context
- Use appropriate exit codes (0 for success, non-zero for failures)
- Provide clear error messages that guide users toward solutions
- Log intermediate steps for debugging complex workflows

Output Management:
- Ensure predictable output file naming and locations
- Handle temporary files properly with cleanup
- Provide progress indicators for long-running operations
- Validate output files are created successfully
- Support different output formats as specified by parameters

Always generate complete, production-ready wrapper scripts that provide reliable
integration between GenePattern and bioinformatics tools with excellent user experience.
"""

# Use DEFAULT_LLM_MODEL from environment, fallback to a reasonable default
DEFAULT_LLM_MODEL = os.getenv('DEFAULT_LLM_MODEL', 'bedrock:us.anthropic.claude-sonnet-4-20250514-v1:0')

mcp_tools = MCPServerStdio('python', args=['mcp/server.py'], timeout=10)

# Create agent 
wrapper_agent = Agent(DEFAULT_LLM_MODEL, system_prompt=system_prompt, toolsets=[mcp_tools])


@wrapper_agent.tool
def analyze_wrapper_requirements(context: RunContext[str], tool_info: Dict[str, Any], parameters: List[Dict[str, Any]] = None, execution_environment: str = "container") -> str:
    """
    Analyze tool information to determine optimal wrapper script requirements and implementation strategy.
    
    Args:
        tool_info: Dictionary with tool information (name, description, language, etc.)
        parameters: List of parameter definitions for the module
        execution_environment: Target execution environment ('container', 'local', 'cluster')
    
    Returns:
        Analysis of wrapper requirements with language recommendations and implementation strategy
    """
    print(f"🔧 WRAPPER TOOL: Running analyze_wrapper_requirements for '{tool_info.get('name', 'unknown')}' with {len(parameters or [])} parameters (env: {execution_environment})")
    
    tool_name = tool_info.get('name', 'Unknown Tool')
    description = tool_info.get('description', '')
    language = tool_info.get('language', 'unknown').lower()
    version = tool_info.get('version', 'latest')
    
    analysis = f"Wrapper Script Requirements Analysis for {tool_name}:\n"
    analysis += "=" * 55 + "\n\n"
    
    # Analyze tool characteristics for wrapper design
    tool_characteristics = []
    complexity_score = 0
    
    if language in ['python', 'r', 'java', 'scala']:
        tool_characteristics.append("Interpreted/VM-based tool")
        complexity_score += 1
    elif language in ['c', 'c++', 'fortran']:
        tool_characteristics.append("Compiled binary tool")
        complexity_score += 2
    elif language == 'unknown':
        tool_characteristics.append("Unknown implementation language")
        complexity_score += 1
    
    if parameters:
        param_count = len(parameters)
        file_params = [p for p in parameters if p.get('type') == 'File']
        choice_params = [p for p in parameters if p.get('type') == 'Choice']
        required_params = [p for p in parameters if p.get('required', False)]
        
        if param_count > 10:
            tool_characteristics.append("Many parameters (>10)")
            complexity_score += 2
        if len(file_params) > 3:
            tool_characteristics.append("Complex file handling")
            complexity_score += 1
        if len(choice_params) > 2:
            tool_characteristics.append("Multiple choice parameters")
            complexity_score += 1
        if len(required_params) > 5:
            tool_characteristics.append("Many required parameters")
            complexity_score += 1
    
    analysis += f"**Tool Analysis:**\n"
    analysis += f"- Tool name: {tool_name}\n"
    analysis += f"- Implementation language: {language.title()}\n"
    analysis += f"- Execution environment: {execution_environment}\n"
    analysis += f"- Complexity score: {complexity_score}/7\n"
    
    if tool_characteristics:
        analysis += f"- Characteristics: {', '.join(tool_characteristics)}\n"
    analysis += "\n"
    
    # Recommend wrapper language
    wrapper_language = "python"  # Default
    wrapper_rationale = []
    
    if language == 'python':
        wrapper_language = "python"
        wrapper_rationale.append("Native Python tool - Python wrapper for seamless integration")
    elif language == 'r':
        wrapper_language = "r"
        wrapper_rationale.append("R tool - R wrapper for direct library integration")
    elif language in ['bash', 'shell']:
        wrapper_language = "bash"
        wrapper_rationale.append("Shell-based tool - Bash wrapper for native execution")
    elif execution_environment == 'container':
        wrapper_language = "python"
        wrapper_rationale.append("Container environment - Python wrapper for robust container integration")
    elif complexity_score >= 4:
        wrapper_language = "python"
        wrapper_rationale.append("High complexity - Python wrapper for advanced error handling")
    else:
        wrapper_language = "bash"
        wrapper_rationale.append("Simple tool - Bash wrapper for lightweight execution")
    
    analysis += f"**Wrapper Language Recommendation: {wrapper_language.upper()}**\n"
    analysis += f"- Rationale: {'; '.join(wrapper_rationale)}\n\n"
    
    # Parameter handling strategy
    if parameters:
        analysis += f"**Parameter Handling Strategy:**\n"
        analysis += f"- Total parameters: {len(parameters)}\n"
        
        param_categories = {
            'file_inputs': [p for p in parameters if p.get('type') == 'File' and 'input' in p.get('name', '').lower()],
            'file_outputs': [p for p in parameters if p.get('type') == 'File' and 'output' in p.get('name', '').lower()],
            'choices': [p for p in parameters if p.get('type') == 'Choice'],
            'numeric': [p for p in parameters if p.get('type') in ['Integer', 'Float']],
            'flags': [p for p in parameters if p.get('type') == 'Boolean'],
            'text': [p for p in parameters if p.get('type') in ['Text', 'String']]
        }
        
        for category, params in param_categories.items():
            if params:
                analysis += f"- {category.replace('_', ' ').title()}: {len(params)} parameters\n"
        
        # Special handling requirements
        special_handling = []
        if param_categories['file_inputs']:
            special_handling.append("Input file validation and existence checking")
        if param_categories['file_outputs']:
            special_handling.append("Output directory creation and write permissions")
        if param_categories['choices']:
            special_handling.append("Choice parameter validation against allowed values")
        if any('path' in p.get('name', '').lower() for p in parameters):
            special_handling.append("Path handling and normalization")
        
        if special_handling:
            analysis += f"\n**Special Handling Requirements:**\n"
            for requirement in special_handling:
                analysis += f"- {requirement}\n"
    
    # Execution strategy recommendations
    analysis += f"\n**Execution Strategy:**\n"
    
    if execution_environment == 'container':
        analysis += "- Container-optimized execution with proper signal handling\n"
        analysis += "- Path mapping between host and container filesystem\n"
        analysis += "- Environment variable propagation\n"
    elif execution_environment == 'cluster':
        analysis += "- Cluster-aware resource management\n"
        analysis += "- Job scheduling and monitoring integration\n"
        analysis += "- Distributed file system handling\n"
    else:
        analysis += "- Local execution with resource monitoring\n"
        analysis += "- Standard file system operations\n"
        analysis += "- Process management and cleanup\n"
    
    if language == 'python':
        analysis += "- Use subprocess for Python tool execution with proper error handling\n"
    elif language == 'r':
        analysis += "- Direct R library calls or Rscript execution\n"
    elif language in ['c', 'c++']:
        analysis += "- Direct binary execution with argument passing\n"
    else:
        analysis += "- Generic command-line tool execution\n"
    
    # Error handling recommendations
    analysis += f"\n**Error Handling Requirements:**\n"
    analysis += "- Comprehensive input validation before tool execution\n"
    analysis += "- Clear error messages with actionable guidance\n"
    analysis += "- Proper exit codes (0=success, 1=user error, 2=system error)\n"
    analysis += "- Tool output capture and error reporting\n"
    analysis += "- Graceful handling of interrupted execution\n"
    
    # Development recommendations
    analysis += f"\n**Development Recommendations:**\n"
    
    if wrapper_language == 'python':
        analysis += "- Use argparse for robust argument parsing\n"
        analysis += "- Implement comprehensive logging with configurable levels\n"
        analysis += "- Use pathlib for cross-platform path handling\n"
        analysis += "- Include type hints for better code documentation\n"
    elif wrapper_language == 'bash':
        analysis += "- Use getopts for argument parsing or manual validation\n"
        analysis += "- Implement proper variable quoting and error checking\n"
        analysis += "- Use 'set -euo pipefail' for strict error handling\n"
        analysis += "- Include comprehensive usage documentation\n"
    elif wrapper_language == 'r':
        analysis += "- Use optparse or argparse for argument handling\n"
        analysis += "- Implement tryCatch for comprehensive error handling\n"
        analysis += "- Use proper R logging mechanisms\n"
        analysis += "- Include session info for reproducibility\n"
    
    analysis += f"\n**Testing Strategy:**\n"
    analysis += "- Unit tests for parameter validation functions\n"
    analysis += "- Integration tests with sample data\n"
    analysis += "- Error condition testing (missing files, invalid parameters)\n"
    analysis += "- Performance testing with representative datasets\n"
    analysis += "- Cross-platform compatibility testing\n"
    
    print("✅ WRAPPER TOOL: analyze_wrapper_requirements completed successfully")
    return analysis


@wrapper_agent.tool
def generate_wrapper_structure(context: RunContext[str], language: str, parameters: List[Dict[str, Any]], tool_command: str) -> str:
    """
    Generate the basic structure and key components for a wrapper script in the specified language.
    
    Args:
        language: Programming language for the wrapper ('python', 'bash', 'r')
        parameters: List of parameter definitions for argument parsing
        tool_command: Base command to execute the underlying tool
    
    Returns:
        Detailed wrapper script structure with key functions and implementation guidelines
    """
    print(f"🏗️ WRAPPER TOOL: Running generate_wrapper_structure for {language} with {len(parameters)} parameters")
    
    if not parameters:
        print("❌ WRAPPER TOOL: generate_wrapper_structure failed - no parameters provided")
        return "Error: No parameters provided for wrapper structure generation"
    
    language = language.lower()
    if language not in ['python', 'bash', 'r']:
        print(f"❌ WRAPPER TOOL: generate_wrapper_structure failed - unsupported language: {language}")
        return f"Error: Unsupported wrapper language: {language}. Supported: python, bash, r"
    
    structure = f"Wrapper Script Structure for {language.upper()}:\n"
    structure += "=" * 45 + "\n\n"
    
    # Language-specific structure
    if language == 'python':
        structure += "**Python Wrapper Structure:**\n\n"
        structure += "```python\n"
        structure += "#!/usr/bin/env python\n"
        structure += '"""\nWrapper script for [TOOL_NAME] - [DESCRIPTION]\n"""\n\n'
        structure += "import argparse\nimport os\nimport sys\nimport subprocess\nimport logging\nfrom pathlib import Path\n\n"
        
        structure += "def setup_logging(verbose=False):\n"
        structure += '    """Configure logging for the wrapper."""\n'
        structure += "    level = logging.DEBUG if verbose else logging.INFO\n"
        structure += "    logging.basicConfig(level=level, format='%(levelname)s: %(message)s')\n\n"
        
        structure += "def parse_arguments():\n"
        structure += '    """Parse and validate command line arguments."""\n'
        structure += '    parser = argparse.ArgumentParser(description="[TOOL_NAME] wrapper")\n\n'
        
        # Generate parameter parsing
        for param in parameters[:5]:  # Show first 5 as example
            param_name = param.get('name', 'unknown')
            param_type = param.get('type', 'Text')
            required = param.get('required', False)
            description = param.get('description', f'{param_name} parameter')
            
            structure += f"    parser.add_argument('--{param_name.replace('_', '-')}',\n"
            if required:
                structure += "                       required=True,\n"
            if param_type == 'Choice':
                structure += "                       choices=['option1', 'option2'],\n"
            elif param_type in ['Integer', 'Float']:
                structure += f"                       type={param_type.lower()},\n"
            elif param_type == 'Boolean':
                structure += "                       action='store_true',\n"
            structure += f"                       help='{description}')\n\n"
        
        if len(parameters) > 5:
            structure += f"    # ... ({len(parameters) - 5} more parameters)\n\n"
        
        structure += "    return parser.parse_args()\n\n"
        
        structure += "def validate_inputs(args):\n"
        structure += '    """Validate input parameters and files."""\n'
        structure += "    # Add input validation logic here\n"
        structure += "    pass\n\n"
        
        structure += "def run_tool(args):\n"
        structure += '    """Execute the underlying tool with validated parameters."""\n'
        structure += f"    cmd = ['{tool_command}']\n"
        structure += "    # Add parameter-to-command mapping here\n"
        structure += "    \n"
        structure += "    try:\n"
        structure += "        result = subprocess.run(cmd, check=True, capture_output=True, text=True)\n"
        structure += "        return True\n"
        structure += "    except subprocess.CalledProcessError as e:\n"
        structure += "        logging.error(f'Tool execution failed: {e}')\n"
        structure += "        return False\n\n"
        
        structure += "def main():\n"
        structure += "    args = parse_arguments()\n"
        structure += "    setup_logging(getattr(args, 'verbose', False))\n"
        structure += "    validate_inputs(args)\n"
        structure += "    success = run_tool(args)\n"
        structure += "    sys.exit(0 if success else 1)\n\n"
        structure += "if __name__ == '__main__':\n"
        structure += "    main()\n"
        structure += "```\n\n"
    
    elif language == 'bash':
        structure += "**Bash Wrapper Structure:**\n\n"
        structure += "```bash\n"
        structure += "#!/bin/bash\n"
        structure += "set -euo pipefail  # Exit on error, undefined vars, pipe failures\n\n"
        structure += "# Tool information\n"
        structure += "TOOL_NAME=\"[TOOL_NAME]\"\n"
        structure += f"TOOL_COMMAND=\"{tool_command}\"\n\n"
        
        structure += "# Default parameter values\n"
        for param in parameters[:3]:
            param_name = param.get('name', 'unknown').upper()
            default_value = param.get('default', '""')
            structure += f"{param_name}={default_value}\n"
        structure += "\n"
        
        structure += "usage() {\n"
        structure += '    echo "Usage: $0 [OPTIONS]"\n'
        structure += '    echo "Options:"\n'
        for param in parameters[:3]:
            param_name = param.get('name', 'unknown')
            description = param.get('description', f'{param_name} parameter')
            structure += f'    echo "  --{param_name.replace("_", "-")} VALUE    {description}"\n'
        structure += '    exit 1\n'
        structure += "}\n\n"
        
        structure += "parse_arguments() {\n"
        structure += "    while [[ $# -gt 0 ]]; do\n"
        structure += "        case $1 in\n"
        for param in parameters[:3]:
            param_name = param.get('name', 'unknown')
            param_var = param_name.upper()
            structure += f"            --{param_name.replace('_', '-')})\n"
            structure += f"                {param_var}=\"$2\"\n"
            structure += "                shift 2\n"
            structure += "                ;;\n"
        structure += "            -h|--help)\n"
        structure += "                usage\n"
        structure += "                ;;\n"
        structure += "            *)\n"
        structure += '                echo "Unknown option: $1"\n'
        structure += "                usage\n"
        structure += "                ;;\n"
        structure += "        esac\n"
        structure += "    done\n"
        structure += "}\n\n"
        
        structure += "validate_inputs() {\n"
        structure += "    # Add input validation logic here\n"
        structure += "    return 0\n"
        structure += "}\n\n"
        
        structure += "run_tool() {\n"
        structure += f"    $TOOL_COMMAND \\\n"
        for param in parameters[:3]:
            param_name = param.get('name', 'unknown')
            param_var = param_name.upper()
            structure += f"        --{param_name.replace('_', '-')} \"${param_var}\" \\\n"
        structure += "        # Add more parameters as needed\n"
        structure += "}\n\n"
        
        structure += "main() {\n"
        structure += "    parse_arguments \"$@\"\n"
        structure += "    validate_inputs\n"
        structure += "    run_tool\n"
        structure += "}\n\n"
        structure += "main \"$@\"\n"
        structure += "```\n\n"
    
    elif language == 'r':
        structure += "**R Wrapper Structure:**\n\n"
        structure += "```r\n"
        structure += "#!/usr/bin/env Rscript\n\n"
        structure += "# Load required libraries\n"
        structure += "suppressMessages({\n"
        structure += "  library(optparse)\n"
        structure += "  library(futile.logger)\n"
        structure += "})\n\n"
        
        structure += "# Define command line options\n"
        structure += "option_list <- list(\n"
        for i, param in enumerate(parameters[:3]):
            param_name = param.get('name', 'unknown')
            param_type = param.get('type', 'character')
            description = param.get('description', f'{param_name} parameter')
            r_type = 'character' if param_type in ['Text', 'File', 'Choice'] else 'numeric'
            
            structure += f"  make_option(c('--{param_name.replace('_', '-')}'), type='{r_type}',\n"
            structure += f"              help='{description}')"
            if i < min(len(parameters), 3) - 1:
                structure += ","
            structure += "\n"
        structure += ")\n\n"
        
        structure += "# Parse arguments\n"
        structure += "opt_parser <- OptionParser(option_list=option_list)\n"
        structure += "opt <- parse_args(opt_parser)\n\n"
        
        structure += "validate_inputs <- function(opt) {\n"
        structure += "  # Add input validation logic here\n"
        structure += "  return(TRUE)\n"
        structure += "}\n\n"
        
        structure += "run_tool <- function(opt) {\n"
        structure += "  tryCatch({\n"
        structure += f"    cmd <- paste('{tool_command}',\n"
        for param in parameters[:3]:
            param_name = param.get('name', 'unknown')
            structure += f"                 '--{param_name.replace('_', '-')}', opt${param_name.replace('-', '_')},\n"
        structure += "                 collapse=' ')\n"
        structure += "    \n"
        structure += "    result <- system(cmd, intern=TRUE)\n"
        structure += "    return(TRUE)\n"
        structure += "  }, error = function(e) {\n"
        structure += "    flog.error('Tool execution failed: %s', e$message)\n"
        structure += "    return(FALSE)\n"
        structure += "  })\n"
        structure += "}\n\n"
        
        structure += "# Main execution\n"
        structure += "main <- function() {\n"
        structure += "  if (!validate_inputs(opt)) {\n"
        structure += "    quit(status=1)\n"
        structure += "  }\n"
        structure += "  \n"
        structure += "  success <- run_tool(opt)\n"
        structure += "  quit(status=if(success) 0 else 1)\n"
        structure += "}\n\n"
        structure += "main()\n"
        structure += "```\n\n"
    
    # Implementation guidelines
    structure += f"**Implementation Guidelines:**\n\n"
    
    structure += f"**Parameter Mapping:**\n"
    for param in parameters:
        param_name = param.get('name', 'unknown')
        param_type = param.get('type', 'Text')
        required = 'Required' if param.get('required', False) else 'Optional'
        structure += f"- {param_name}: {param_type} ({required})\n"
    
    structure += f"\n**Validation Requirements:**\n"
    file_params = [p for p in parameters if p.get('type') == 'File']
    choice_params = [p for p in parameters if p.get('type') == 'Choice']
    
    if file_params:
        structure += "- File existence and readability checks\n"
    if choice_params:
        structure += "- Choice parameter validation against allowed values\n"
    structure += "- Required parameter presence validation\n"
    structure += "- Parameter type and format validation\n"
    
    structure += f"\n**Error Handling:**\n"
    structure += "- Return exit code 0 for success\n"
    structure += "- Return exit code 1 for user/input errors\n"
    structure += "- Return exit code 2 for system/tool errors\n"
    structure += "- Provide clear, actionable error messages\n"
    structure += "- Log intermediate steps for debugging\n"
    
    print("✅ WRAPPER TOOL: generate_wrapper_structure completed successfully")
    return structure


@wrapper_agent.tool
def optimize_wrapper_performance(context: RunContext[str], wrapper_content: str, performance_goals: List[str] = None) -> str:
    """
    Analyze wrapper script content and suggest performance optimizations and best practices.
    
    Args:
        wrapper_content: Current wrapper script content to analyze
        performance_goals: List of performance goals ('speed', 'memory', 'reliability', 'maintainability')
    
    Returns:
        Analysis with specific optimization recommendations and implementation improvements
    """
    print(f"⚡ WRAPPER TOOL: Running optimize_wrapper_performance (content length: {len(wrapper_content)} chars)")
    
    if performance_goals is None:
        performance_goals = ['reliability', 'speed']
    
    if not wrapper_content.strip():
        print("❌ WRAPPER TOOL: optimize_wrapper_performance failed - no content provided")
        return "Error: No wrapper content provided for performance analysis"
    
    analysis = "Wrapper Performance Optimization:\n"
    analysis += "=" * 40 + "\n\n"
    
    # Detect wrapper language
    wrapper_language = "unknown"
    if wrapper_content.startswith("#!/usr/bin/env python") or "import " in wrapper_content:
        wrapper_language = "python"
    elif wrapper_content.startswith("#!/bin/bash") or "#!/bin/sh" in wrapper_content:
        wrapper_language = "bash"
    elif wrapper_content.startswith("#!/usr/bin/env Rscript") or "library(" in wrapper_content:
        wrapper_language = "r"
    
    analysis += f"**Wrapper Analysis:**\n"
    analysis += f"- Detected language: {wrapper_language.upper()}\n"
    analysis += f"- Content size: {len(wrapper_content)} characters\n"
    analysis += f"- Lines of code: {len(wrapper_content.splitlines())}\n"
    analysis += f"- Optimization goals: {', '.join(performance_goals)}\n\n"
    
    # Analyze current implementation
    optimizations = []
    
    # Performance goal-specific analysis
    if 'speed' in performance_goals:
        speed_optimizations = []
        
        if wrapper_language == "python":
            if "subprocess.run" in wrapper_content and "capture_output=True" in wrapper_content:
                speed_optimizations.append("Consider streaming output for large datasets instead of capturing all at once")
            if "import " in wrapper_content and len(re.findall(r'import \w+', wrapper_content)) > 10:
                speed_optimizations.append("Reduce import overhead by importing only needed modules")
            
        elif wrapper_language == "bash":
            if "$(command)" in wrapper_content or "`command`" in wrapper_content:
                speed_optimizations.append("Minimize subshell usage - store command results in variables")
            if wrapper_content.count("grep") > 3:
                speed_optimizations.append("Combine multiple grep operations or use more efficient text processing")
        
        if speed_optimizations:
            optimizations.append(("Speed Optimizations", speed_optimizations))
    
    if 'memory' in performance_goals:
        memory_optimizations = []
        
        if wrapper_language == "python":
            if "capture_output=True" in wrapper_content:
                memory_optimizations.append("Stream large tool outputs instead of loading into memory")
            if ".read()" in wrapper_content:
                memory_optimizations.append("Use generators or chunked reading for large files")
        
        elif wrapper_language == "r":
            if "read.csv" in wrapper_content or "read.table" in wrapper_content:
                memory_optimizations.append("Use data.table::fread() for faster, memory-efficient file reading")
        
        if memory_optimizations:
            optimizations.append(("Memory Optimizations", memory_optimizations))
    
    if 'reliability' in performance_goals:
        reliability_optimizations = []
        
        # Common reliability issues
        if "try:" not in wrapper_content and "tryCatch" not in wrapper_content:
            reliability_optimizations.append("Add comprehensive error handling with try/catch blocks")
        
        if wrapper_language == "bash" and "set -e" not in wrapper_content:
            reliability_optimizations.append("Add 'set -euo pipefail' for strict error handling")
        
        if wrapper_language == "python" and "logging" not in wrapper_content:
            reliability_optimizations.append("Add logging for better debugging and monitoring")
        
        # File handling checks
        if "os.path.exists" not in wrapper_content and "file.exists" not in wrapper_content and "[ -f " not in wrapper_content:
            reliability_optimizations.append("Add file existence checks before processing")
        
        if reliability_optimizations:
            optimizations.append(("Reliability Improvements", reliability_optimizations))
    
    if 'maintainability' in performance_goals:
        maintainability_optimizations = []
        
        # Code organization
        lines = wrapper_content.splitlines()
        if len(lines) > 100 and "def " not in wrapper_content and "function " not in wrapper_content:
            maintainability_optimizations.append("Break down into smaller, reusable functions")
        
        # Documentation
        if '"""' not in wrapper_content and "#" not in wrapper_content[:200]:
            maintainability_optimizations.append("Add comprehensive docstrings and comments")
        
        # Constants and configuration
        if wrapper_content.count('"') > 20 and "CONFIG" not in wrapper_content:
            maintainability_optimizations.append("Extract configuration constants to top of file")
        
        if maintainability_optimizations:
            optimizations.append(("Maintainability Improvements", maintainability_optimizations))
    
    # Report optimizations
    if optimizations:
        analysis += f"**Optimization Recommendations:**\n\n"
        for category, items in optimizations:
            analysis += f"### {category}:\n"
            for item in items:
                analysis += f"- {item}\n"
            analysis += "\n"
    else:
        analysis += f"**Result:** Wrapper appears well-optimized for specified goals!\n\n"
    
    # Language-specific best practices
    analysis += f"**{wrapper_language.upper()}-Specific Best Practices:**\n"
    
    if wrapper_language == "python":
        analysis += "- Use argparse for robust argument parsing\n"
        analysis += "- Implement proper logging with configurable levels\n"
        analysis += "- Use pathlib for cross-platform path operations\n"
        analysis += "- Add type hints for better code documentation\n"
        analysis += "- Use context managers for file operations\n"
        analysis += "- Handle subprocess errors with proper exception catching\n"
    
    elif wrapper_language == "bash":
        analysis += "- Use 'set -euo pipefail' for strict error handling\n"
        analysis += "- Quote all variable expansions: \"${var}\"\n"
        analysis += "- Use [[ ]] for test conditions instead of [ ]\n"
        analysis += "- Implement proper function error checking\n"
        analysis += "- Use local variables in functions\n"
        analysis += "- Add comprehensive usage documentation\n"
    
    elif wrapper_language == "r":
        analysis += "- Use optparse or argparse for argument handling\n"
        analysis += "- Implement tryCatch for comprehensive error handling\n"
        analysis += "- Use appropriate data.table operations for performance\n"
        analysis += "- Add session info logging for reproducibility\n"
        analysis += "- Use appropriate R logging mechanisms\n"
        analysis += "- Handle missing packages gracefully\n"
    
    else:
        analysis += "- Add clear documentation for the wrapper language\n"
        analysis += "- Implement proper error handling mechanisms\n"
        analysis += "- Use consistent coding style and conventions\n"
        analysis += "- Add input validation and error reporting\n"
    
    # Performance metrics and monitoring
    analysis += f"\n**Performance Monitoring Recommendations:**\n"
    analysis += "- Add execution time logging for performance tracking\n"
    analysis += "- Monitor memory usage for large dataset processing\n"
    analysis += "- Log file sizes and processing statistics\n"
    analysis += "- Implement progress reporting for long-running operations\n"
    analysis += "- Add resource usage warnings for resource-intensive operations\n"
    
    # Testing recommendations
    analysis += f"\n**Testing and Validation:**\n"
    analysis += "- Unit tests for parameter validation functions\n"
    analysis += "- Integration tests with various input sizes\n"
    analysis += "- Performance benchmarks with representative data\n"
    analysis += "- Error condition testing (missing files, invalid inputs)\n"
    analysis += "- Cross-platform compatibility validation\n"
    
    print("✅ WRAPPER TOOL: optimize_wrapper_performance completed successfully")
    return analysis
