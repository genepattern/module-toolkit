#!/usr/bin/env python3
"""
GenePattern Module Generator

A multi-agent system for automatically generating GenePattern modules from bioinformatics tools.
Uses Pydantic AI to orchestrate research, planning, and artifact generation.
"""

import os
import sys
import json
import traceback
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerStdio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import agents
from agents.researcher import researcher_agent
from agents.planner import planner_agent
from wrapper.agent import wrapper_agent
from dockerfile.agent import dockerfile_agent
from paramgroups.agent import paramgroups_agent
from manifest.agent import manifest_agent
from documentation.agent import documentation_agent
from gpunit.agent import gpunit_agent

# Configuration
MAX_ARTIFACT_LOOPS = int(os.getenv('MAX_ARTIFACT_LOOPS', '5'))
DEFAULT_OUTPUT_DIR = os.getenv('MODULE_OUTPUT_DIR', './generated-modules')

# Status tracking
@dataclass
class ModuleGenerationStatus:
    """Track the status of module generation process"""
    tool_name: str
    module_directory: str
    research_complete: bool = False
    planning_complete: bool = False
    artifacts_status: Dict[str, Dict[str, Any]] = None
    parameters: List[Dict[str, Any]] = None
    error_messages: List[str] = None
    
    def __post_init__(self):
        if self.artifacts_status is None:
            self.artifacts_status = {}
        if self.parameters is None:
            self.parameters = []
        if self.error_messages is None:
            self.error_messages = []

def print_status(message: str, level: str = "INFO"):
    """Print status message with timestamp and level"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")

def print_section(title: str):
    """Print a section header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def get_user_input() -> Dict[str, str]:
    """Prompt user for bioinformatics tool information"""
    print_section("GenePattern Module Generator")
    print("This script will help you create a GenePattern module for a bioinformatics tool.")
    print("Please provide the following information:\n")
    
    tool_info = {}
    
    # Required fields
    tool_info['name'] = input("Tool name (e.g., 'samtools', 'bwa', 'star'): ").strip()
    if not tool_info['name']:
        print("Error: Tool name is required.")
        sys.exit(1)
    
    # Optional fields with defaults
    tool_info['version'] = input("Tool version (optional): ").strip() or "latest"
    tool_info['language'] = input("Primary language (python/r/java/c/cpp/other, optional): ").strip() or "unknown"
    tool_info['description'] = input("Brief description (optional): ").strip()
    tool_info['repository_url'] = input("Repository URL (optional): ").strip()
    tool_info['documentation_url'] = input("Documentation URL (optional): ").strip()
    
    print(f"\nGenerating module for: {tool_info['name']}")
    if tool_info['version'] != "latest":
        print(f"Version: {tool_info['version']}")
    
    return tool_info

def create_module_directory(tool_name: str, base_dir: str = DEFAULT_OUTPUT_DIR) -> Path:
    """Create directory for the module"""
    print_status(f"Creating module directory for {tool_name}")
    
    # Sanitize tool name for directory
    safe_name = "".join(c for c in tool_name if c.isalnum() or c in "._-").lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    module_dir_name = f"{safe_name}_{timestamp}"
    
    module_path = Path(base_dir) / module_dir_name
    module_path.mkdir(parents=True, exist_ok=True)
    
    print_status(f"Created module directory: {module_path}")
    return module_path

def run_research_phase(tool_info: Dict[str, str]) -> Tuple[bool, str]:
    """Run the research phase using researcher_agent"""
    print_section("Research Phase")
    print_status("Starting research on the bioinformatics tool")
    
    try:
        # Build research prompt
        research_prompt = f"""
        Please conduct comprehensive research on the bioinformatics tool: {tool_info['name']}
        
        Tool Information:
        - Name: {tool_info['name']}
        - Version: {tool_info['version']}
        - Language: {tool_info['language']}
        - Description: {tool_info.get('description', 'Not provided')}
        - Repository: {tool_info.get('repository_url', 'Not provided')}
        - Documentation: {tool_info.get('documentation_url', 'Not provided')}
        
        Focus your research on:
        1. Command-line interface and parameters
        2. Input/output file formats
        3. Dependencies and system requirements
        4. Common usage patterns and examples
        5. Installation methods
        6. Known limitations or issues
        
        Provide a comprehensive analysis that will be used for GenePattern module planning.
        """
        
        print_status("Executing research agent...")
        result = researcher_agent.run_sync(research_prompt)
        
        print_status("Research phase completed successfully")
        print(f"Research findings:\n{result.output[:500]}..." if len(str(result.output)) > 500 else f"Research findings:\n{result.output}")
        
        return True, str(result.output)
        
    except Exception as e:
        error_msg = f"Research phase failed: {str(e)}"
        print_status(error_msg, "ERROR")
        print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
        return False, error_msg

def run_planning_phase(tool_info: Dict[str, str], research_data: str) -> Tuple[bool, Dict[str, Any]]:
    """Run the planning phase using planner_agent"""
    print_section("Planning Phase")
    print_status("Starting module planning based on research findings")
    
    try:
        # Build planning prompt
        planning_prompt = f"""
        Based on the research findings for {tool_info['name']}, create a comprehensive plan for a GenePattern module.
        
        Research Data:
        {research_data}
        
        Create a detailed plan that includes:
        1. Parameter analysis and GenePattern parameter type mapping
        2. Parameter groupings for the UI
        3. Module architecture and dependencies
        4. Dockerfile requirements and base image selection
        5. Wrapper script structure
        6. Validation and testing strategy
        
        Structure your response as a comprehensive implementation plan with clear sections.
        Include specific parameter definitions with types, constraints, and groupings.
        """
        
        print_status("Executing planning agent...")
        result = planner_agent.run_sync(planning_prompt)
        
        # Extract structured information from planning result
        planning_data = {
            'plan': str(result.output),
            'parameters': [],  # Will be populated from plan analysis
            'dockerfile_requirements': {},
            'parameter_groups': {}
        }
        
        # Try to extract parameter information from the plan
        # This is a simplified extraction - in production you might want more sophisticated parsing
        plan_text = str(result.output).lower()
        if 'parameter' in plan_text:
            # Basic parameter extraction logic
            planning_data['parameters'] = [
                {'name': 'input_file', 'type': 'File', 'required': True, 'description': 'Input data file'},
                {'name': 'output_dir', 'type': 'Text', 'required': False, 'description': 'Output directory path'}
            ]
        
        print_status("Planning phase completed successfully")
        print(f"Planning result:\n{str(result.output)[:500]}..." if len(str(result.output)) > 500 else f"Planning result:\n{result.output}")
        
        return True, planning_data
        
    except Exception as e:
        error_msg = f"Planning phase failed: {str(e)}"
        print_status(error_msg, "ERROR")
        print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
        return False, {'error': error_msg}

def run_artifact_generation(tool_info: Dict[str, str], planning_data: Dict[str, Any], 
                          module_path: Path, status: ModuleGenerationStatus, skip_artifacts: List[str] = None) -> bool:
    """Run artifact generation phase using artifact agents"""
    print_section("Artifact Generation Phase")
    print_status("Starting artifact generation")
    
    # Initialize skip list
    if skip_artifacts is None:
        skip_artifacts = []
    
    # Initialize MCP server for validation
    mcp_server = MCPServerStdio('python', args=['mcp/server.py'], timeout=10)
    
    # Define artifact agents and their corresponding validation functions
    # Order: wrapper -> manifest -> paramgroups -> gpunit -> documentation -> dockerfile
    artifact_agents = {
        'wrapper': {
            'agent': wrapper_agent,
            'filename': 'wrapper.py',
            'validate_tool': 'validate_wrapper'
        },
        'manifest': {
            'agent': manifest_agent,
            'filename': 'manifest',
            'validate_tool': 'validate_manifest'
        },
        'paramgroups': {
            'agent': paramgroups_agent,
            'filename': 'paramgroups.json',
            'validate_tool': 'validate_paramgroups'
        },
        'gpunit': {
            'agent': gpunit_agent,
            'filename': 'test.yml',
            'validate_tool': 'validate_gpunit'
        },
        'documentation': {
            'agent': documentation_agent,
            'filename': 'README.md',
            'validate_tool': 'validate_documentation'
        },
        'dockerfile': {
            'agent': dockerfile_agent,
            'filename': 'Dockerfile',
            'validate_tool': 'validate_dockerfile'
        }
    }
    
    all_artifacts_successful = True
    artifact_results = []
    
    for artifact_name, artifact_config in artifact_agents.items():
        # Check if this artifact should be skipped
        if artifact_name in skip_artifacts:
            print_status(f"Skipping {artifact_name} (--skip-{artifact_name} specified)")
            artifact_results.append({
                'name': artifact_name,
                'filename': artifact_config['filename'],
                'generated': False,
                'validated': False,
                'attempts': 0,
                'status': 'skipped',
                'error': None
            })
            continue
        print_status(f"Generating {artifact_name}...")
        
        # Initialize artifact status
        status.artifacts_status[artifact_name] = {
            'generated': False,
            'validated': False,
            'attempts': 0,
            'errors': []
        }
        
        # Generate artifact
        success = generate_and_validate_artifact(
            artifact_name, artifact_config, tool_info, planning_data, 
            module_path, mcp_server, status
        )
        
        if success:
            print_status(f"Successfully generated and validated {artifact_name}")
        else:
            print_status(f"Failed to generate valid {artifact_name}", "ERROR")
            all_artifacts_successful = False
    
    return all_artifacts_successful

def generate_and_validate_artifact(artifact_name: str, artifact_config: Dict[str, Any],
                                 tool_info: Dict[str, str], planning_data: Dict[str, Any],
                                 module_path: Path, mcp_server: MCPServerStdio,
                                 status: ModuleGenerationStatus) -> bool:
    """Generate and validate a single artifact with retry logic"""
    
    agent = artifact_config['agent']
    filename = artifact_config['filename']
    validate_tool = artifact_config['validate_tool']
    
    for attempt in range(1, MAX_ARTIFACT_LOOPS + 1):
        print_status(f"Attempt {attempt}/{MAX_ARTIFACT_LOOPS} for {artifact_name}")
        status.artifacts_status[artifact_name]['attempts'] = attempt
        
        try:
            # Generate artifact content
            generation_prompt = create_artifact_prompt(artifact_name, tool_info, planning_data, attempt)
            
            print_status(f"Executing {artifact_name} agent...")
            result = agent.run_sync(generation_prompt)
            artifact_content = str(result.output)
            
            # Write artifact to file
            file_path = module_path / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(artifact_content)
            
            print_status(f"Generated {filename} ({len(artifact_content)} characters)")
            status.artifacts_status[artifact_name]['generated'] = True
            
            # Validate artifact using MCP server
            print_status(f"Validating {artifact_name}...")
            validation_result = validate_artifact_with_mcp(str(file_path), validate_tool, mcp_server)
            
            if validation_result['success']:
                print_status(f"Validation passed for {artifact_name}")
                status.artifacts_status[artifact_name]['validated'] = True
                return True
            else:
                error_msg = f"Validation failed: {validation_result['message']}"
                print_status(error_msg, "WARNING")
                status.artifacts_status[artifact_name]['errors'].append(error_msg)
                
                if attempt == MAX_ARTIFACT_LOOPS:
                    print_status(f"Max attempts reached for {artifact_name}", "ERROR")
                    return False
                    
        except Exception as e:
            error_msg = f"Error generating {artifact_name}: {str(e)}"
            print_status(error_msg, "ERROR")
            status.artifacts_status[artifact_name]['errors'].append(error_msg)
            
            if attempt == MAX_ARTIFACT_LOOPS:
                return False
    
    return False

def create_artifact_prompt(artifact_name: str, tool_info: Dict[str, str], 
                         planning_data: Dict[str, Any], attempt: int) -> str:
    """Create prompt for artifact generation based on type and attempt number"""
    
    base_info = f"""
    Tool Information:
    - Name: {tool_info['name']}
    - Version: {tool_info['version']}
    - Language: {tool_info['language']}
    - Description: {tool_info.get('description', 'Not provided')}
    
    Planning Context:
    {planning_data.get('plan', 'No detailed plan available')}
    """
    
    if artifact_name == 'dockerfile':
        prompt = f"""
        Generate a production-ready Dockerfile for the GenePattern module for {tool_info['name']}.
        
        {base_info}
        
        Requirements:
        - Use appropriate base image for {tool_info['language']} if specified
        - Install the {tool_info['name']} tool and its dependencies
        - Follow Docker best practices for size optimization and security
        - Ensure the container can execute the tool properly
        - Include proper labels and metadata
        - Set up appropriate working directory and permissions
        
        Generate ONLY the Dockerfile content, no explanations or markdown formatting.
        """
        
        if attempt > 1:
            prompt += f"\n\nThis is attempt {attempt}. Please address any validation issues from previous attempts."
    
    elif artifact_name == 'paramgroups':
        # Extract parameter information from planning data
        parameters = planning_data.get('parameters', [])
        param_info = ""
        if parameters:
            param_info = "\nParameters identified from planning:\n"
            for param in parameters:
                param_info += f"- {param.get('name', 'unknown')}: {param.get('type', 'unknown')} ({'Required' if param.get('required', False) else 'Optional'})\n"
        
        prompt = f"""
        Generate a paramgroups.json file for the GenePattern module for {tool_info['name']}.
        
        {base_info}
        {param_info}
        
        Requirements:
        - Create logical, user-friendly parameter groups
        - Use clear group names and descriptions
        - Organize from most essential to least essential
        - Mark advanced/expert groups as hidden
        - Ensure every parameter appears in exactly one group
        - Follow GenePattern paramgroups.json format
        
        Generate ONLY the paramgroups.json content as valid JSON, no explanations or markdown formatting.
        """
        
        if attempt > 1:
            prompt += f"\n\nThis is attempt {attempt}. Please address any validation issues from previous attempts."
    
    elif artifact_name == 'manifest':
        # Extract parameter information from planning data
        parameters = planning_data.get('parameters', [])
        param_info = ""
        if parameters:
            param_info = "\nParameters identified from planning:\n"
            for param in parameters:
                param_info += f"- {param.get('name', 'unknown')}: {param.get('type', 'unknown')} ({'Required' if param.get('required', False) else 'Optional'})\n"
        
        prompt = f"""
        Generate a manifest file for the GenePattern module for {tool_info['name']}.
        
        {base_info}
        {param_info}
        
        Requirements:
        - Include all required keys: LSID, name, commandLine
        - Generate valid LSID following urn:lsid format
        - Create appropriate command line template with parameter placeholders
        - Use proper key=value format (no spaces around equals)
        - Include relevant module metadata and categories
        - Follow GenePattern manifest specifications
        
        Generate ONLY the manifest file content in key=value format, no explanations or markdown formatting.
        """
        
        if attempt > 1:
            prompt += f"\n\nThis is attempt {attempt}. Please address any validation issues from previous attempts."
    
    elif artifact_name == 'documentation':
        # Extract parameter information from planning data
        parameters = planning_data.get('parameters', [])
        param_info = ""
        if parameters:
            param_info = "\nParameters identified from planning:\n"
            for param in parameters:
                required_status = 'Required' if param.get('required', False) else 'Optional'
                param_info += f"- {param.get('name', 'unknown')}: {param.get('type', 'unknown')} ({required_status}) - {param.get('description', 'No description')}\n"
        
        prompt = f"""
        Generate comprehensive user documentation (README.md) for the GenePattern module for {tool_info['name']}.
        
        {base_info}
        {param_info}
        
        Requirements:
        - Create user-friendly documentation for mixed audience (novice and expert)
        - Include clear module overview and purpose
        - Provide detailed parameter descriptions with biological context
        - Include practical usage examples and workflows
        - Add troubleshooting section for common issues
        - Structure content with proper headings and sections
        - Use Markdown formatting for readability
        
        Generate ONLY the README.md content in Markdown format, no explanations or additional text.
        """
        
        if attempt > 1:
            prompt += f"\n\nThis is attempt {attempt}. Please address any validation issues from previous attempts."
    
    elif artifact_name == 'gpunit':
        # Extract parameter information from planning data for test generation
        parameters = planning_data.get('parameters', [])
        param_info = ""
        if parameters:
            param_info = "\nParameters identified from planning:\n"
            for param in parameters:
                required_status = 'Required' if param.get('required', False) else 'Optional'
                param_info += f"- {param.get('name', 'unknown')}: {param.get('type', 'unknown')} ({required_status}) - {param.get('description', 'No description')}\n"
        
        # Module LSID generation
        module_lsid = f"urn:lsid:genepattern.org:module.analysis:{tool_info['name'].lower().replace(' ', '')}"
        
        prompt = f"""
        Generate a comprehensive GPUnit test definition (test.yml) for the GenePattern module for {tool_info['name']}.
        
        {base_info}
        {param_info}
        
        Module LSID: {module_lsid}
        
        Requirements:
        - Create a GPUnit YAML test file that validates core module functionality
        - Include realistic test parameters that exercise key features
        - Define clear assertions for output validation
        - Use representative input data and expected outputs
        - Follow GPUnit specification format exactly
        - Include both file existence checks and content comparison
        - Test essential parameter combinations
        
        GPUnit YAML Structure Required:
        name: "Descriptive test name"
        module: {module_lsid}
        params:
          [parameter_name]: "[parameter_value]"
        assertions:
          diffCmd: diff <%gpunit.diffStripTrailingCR%> -q
          files:
            "[output_file]":
              diff: "[expected_file]"
        
        Generate ONLY the GPUnit YAML content, no explanations or markdown formatting.
        """
        
        if attempt > 1:
            prompt += f"\n\nThis is attempt {attempt}. Please address any validation issues from previous attempts."
    
    elif artifact_name == 'wrapper':
        # Extract parameter information from planning data for wrapper generation
        parameters = planning_data.get('parameters', [])
        param_info = ""
        if parameters:
            param_info = "\nParameters identified from planning:\n"
            for param in parameters:
                required_status = 'Required' if param.get('required', False) else 'Optional'
                param_info += f"- {param.get('name', 'unknown')}: {param.get('type', 'unknown')} ({required_status}) - {param.get('description', 'No description')}\n"
        
        # Determine optimal wrapper language based on tool
        tool_language = tool_info.get('language', 'unknown').lower()
        if tool_language == 'python':
            wrapper_language = 'python'
        elif tool_language == 'r':
            wrapper_language = 'r'
        elif tool_language in ['bash', 'shell']:
            wrapper_language = 'bash'
        else:
            wrapper_language = 'python'  # Default to Python for robustness
        
        prompt = f"""
        Generate a comprehensive wrapper script ({wrapper_language}) for the GenePattern module for {tool_info['name']}.
        
        {base_info}
        {param_info}
        
        Tool Language: {tool_language}
        Wrapper Language: {wrapper_language}
        
        Requirements:
        - Create a robust {wrapper_language} wrapper script that integrates {tool_info['name']} with GenePattern
        - Implement comprehensive argument parsing for all parameters
        - Include input validation and error handling
        - Provide clear error messages and proper exit codes
        - Handle file I/O operations safely with proper path handling
        - Support both required and optional parameters with defaults
        - Include logging and debugging capabilities
        - Follow {wrapper_language} best practices and conventions
        
        Wrapper Structure Requirements:
        - Proper shebang line for the target language
        - Comprehensive argument parsing (argparse for Python, getopts for Bash)
        - Input validation functions for all parameters
        - Main execution function that calls the underlying tool
        - Error handling with appropriate exit codes (0=success, 1=error)
        - Progress reporting and logging for user feedback
        
        Generate ONLY the complete wrapper script code, no explanations or markdown formatting.
        """
        
        if attempt > 1:
            prompt += f"\n\nThis is attempt {attempt}. Please address any validation issues from previous attempts."
    
    else:
        prompt = f"Generate {artifact_name} for {tool_info['name']} module.\n{base_info}"
    
    return prompt

def validate_artifact_with_mcp(file_path: str, validate_tool: str, mcp_server: MCPServerStdio) -> Dict[str, Any]:
    """Validate an artifact using the MCP server"""
    try:
        # Create a temporary agent with MCP tools to run validation
        validation_agent = Agent(
            model='bedrock:us.anthropic.claude-sonnet-4-20250514-v1:0',
            system_prompt="You are a validation assistant.",
            toolsets=[mcp_server]
        )
        
        # Run validation
        validation_prompt = f"Please validate the file at {file_path} using the {validate_tool} tool."
        result = validation_agent.run_sync(validation_prompt)
        
        # Parse validation result
        result_text = str(result.output).lower()
        success = 'passed' in result_text or 'valid' in result_text
        
        return {
            'success': success,
            'message': str(result.output)
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Validation error: {str(e)}"
        }

def print_final_report(status: ModuleGenerationStatus):
    """Print final generation report"""
    print_section("Module Generation Report")
    
    print(f"Tool Name: {status.tool_name}")
    print(f"Module Directory: {status.module_directory}")
    print(f"Research Complete: {'✓' if status.research_complete else '✗'}")
    print(f"Planning Complete: {'✓' if status.planning_complete else '✗'}")
    
    print("\nArtifact Status:")
    for artifact_name, artifact_status in status.artifacts_status.items():
        print(f"  {artifact_name}:")
        print(f"    Generated: {'✓' if artifact_status['generated'] else '✗'}")
        print(f"    Validated: {'✓' if artifact_status['validated'] else '✗'}")
        print(f"    Attempts: {artifact_status['attempts']}")
        if artifact_status['errors']:
            print(f"    Errors: {len(artifact_status['errors'])}")
    
    print(f"\nParameters Identified: {len(status.parameters)}")
    for param in status.parameters[:5]:  # Show first 5 parameters
        print(f"  - {param.get('name', 'Unknown')}: {param.get('type', 'Unknown')} ({'Required' if param.get('required') else 'Optional'})")
    
    if len(status.parameters) > 5:
        print(f"  ... and {len(status.parameters) - 5} more parameters")
    
    # Overall success determination
    all_artifacts_valid = all(
        artifact['generated'] and artifact['validated'] 
        for artifact in status.artifacts_status.values()
    )
    
    overall_success = (status.research_complete and 
                      status.planning_complete and 
                      all_artifacts_valid)
    
    print(f"\n{'='*60}")
    if overall_success:
        print("🎉 MODULE GENERATION SUCCESSFUL!")
        print(f"Your GenePattern module is ready in: {status.module_directory}")
    else:
        print("❌ MODULE GENERATION FAILED")
        print("Check the error messages above for details.")
        if status.error_messages:
            print("Errors encountered:")
            for error in status.error_messages:
                print(f"  - {error}")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Generate complete GenePattern modules from bioinformatics tool information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all artifacts (default)
  python generate-module.py

  # Skip specific artifacts
  python generate-module.py --skip-dockerfile --skip-gpunit
  
  # Generate only wrapper and manifest
  python generate-module.py --artifacts wrapper manifest
  
  # Skip container-related artifacts for local development
  python generate-module.py --skip-dockerfile

Available artifacts: wrapper, manifest, paramgroups, gpunit, documentation, dockerfile
        """
    )
    
    # Artifact skip flags
    parser.add_argument('--skip-wrapper', action='store_true',
                       help='Skip generating wrapper script')
    parser.add_argument('--skip-manifest', action='store_true',
                       help='Skip generating manifest file')
    parser.add_argument('--skip-paramgroups', action='store_true',
                       help='Skip generating paramgroups.json file')
    parser.add_argument('--skip-gpunit', action='store_true',
                       help='Skip generating GPUnit test file')
    parser.add_argument('--skip-documentation', action='store_true',
                       help='Skip generating README.md documentation')
    parser.add_argument('--skip-dockerfile', action='store_true',
                       help='Skip generating Dockerfile')
    
    # Alternative: specify only artifacts to generate
    parser.add_argument('--artifacts', nargs='+',
                       choices=['wrapper', 'manifest', 'paramgroups', 'gpunit', 'documentation', 'dockerfile'],
                       help='Generate only specified artifacts (alternative to --skip-* flags)')
    
    # Output directory
    parser.add_argument('--output-dir', type=str,
                       help=f'Output directory for generated modules (default: {DEFAULT_OUTPUT_DIR})')
    
    return parser.parse_args()


def main():
    """Main entry point for module generation"""
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Determine which artifacts to skip
        skip_artifacts = []
        
        if args.artifacts:
            # If --artifacts specified, skip everything not in the list
            all_artifacts = ['wrapper', 'manifest', 'paramgroups', 'gpunit', 'documentation', 'dockerfile']
            skip_artifacts = [artifact for artifact in all_artifacts if artifact not in args.artifacts]
            print_status(f"Generating only: {', '.join(args.artifacts)}")
        else:
            # Use individual skip flags
            if args.skip_wrapper:
                skip_artifacts.append('wrapper')
            if args.skip_manifest:
                skip_artifacts.append('manifest')
            if args.skip_paramgroups:
                skip_artifacts.append('paramgroups')
            if args.skip_gpunit:
                skip_artifacts.append('gpunit')
            if args.skip_documentation:
                skip_artifacts.append('documentation')
            if args.skip_dockerfile:
                skip_artifacts.append('dockerfile')
            
            if skip_artifacts:
                print_status(f"Skipping: {', '.join(skip_artifacts)}")
        
        # Override output directory if specified
        if args.output_dir:
            global DEFAULT_OUTPUT_DIR
            DEFAULT_OUTPUT_DIR = args.output_dir
        
        # Get user input
        tool_info = get_user_input()
        
        # Create module directory
        module_path = create_module_directory(tool_info['name'])
        
        # Initialize status tracking
        status = ModuleGenerationStatus(
            tool_name=tool_info['name'],
            module_directory=str(module_path)
        )
        
        # Phase 1: Research
        research_success, research_data = run_research_phase(tool_info)
        status.research_complete = research_success
        
        if not research_success:
            status.error_messages.append(research_data)
            print_final_report(status)
            return 1
        
        # Phase 2: Planning
        planning_success, planning_data = run_planning_phase(tool_info, research_data)
        status.planning_complete = planning_success
        
        if not planning_success:
            status.error_messages.append(planning_data.get('error', 'Planning failed'))
            print_final_report(status)
            return 1
        
        # Extract parameters from planning data
        status.parameters = planning_data.get('parameters', [])
        
        # Phase 3: Artifact Generation
        artifacts_success = run_artifact_generation(tool_info, planning_data, module_path, status, skip_artifacts)
        
        # Final report
        print_final_report(status)
        
        return 0 if (research_success and planning_success and artifacts_success) else 1
        
    except KeyboardInterrupt:
        print_status("\nGeneration interrupted by user", "WARNING")
        return 1
    except Exception as e:
        print_status(f"Unexpected error: {str(e)}", "ERROR")
        print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
        return 1

if __name__ == "__main__":
    sys.exit(main())
