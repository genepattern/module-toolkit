#!/usr/bin/env python3
"""
GenePattern Module Generator

A multi-agent system for automatically generating GenePattern modules from bioinformatics tools.
Uses Pydantic AI to orchestrate research, planning, and artifact generation.
"""

import os
import sys
import traceback
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

from pydantic_ai import Agent
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


class Logger:
    """Logging and display utilities for the module generation process."""

    @staticmethod
    def print_status(message: str, level: str = "INFO"):
        """Print status message with timestamp and level"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    @staticmethod
    def print_section(title: str):
        """Print a section header"""
        print("\n" + "=" * 60)
        print(f" {title}")
        print("=" * 60)


# Status tracking
@dataclass
class ModuleGenerationStatus:
    """Track the status of module generation process"""
    tool_name: str
    module_directory: str
    research_data: Dict[str, Any] = None
    planning_data: Dict[str, Any] = None
    artifacts_status: Dict[str, Dict[str, Any]] = None
    parameters: List[Dict[str, Any]] = None
    error_messages: List[str] = None

    def __post_init__(self):
        if self.artifacts_status is None: self.artifacts_status = {}
        if self.parameters is None: self.parameters = []
        if self.error_messages is None: self.error_messages = []
        if self.research_data is None: self.research_data = {}
        if self.planning_data is None: self.planning_data = {}

    @property
    def research_complete(self) -> bool:
        """Return True if research data is present"""
        return bool(self.research_data)

    @property
    def planning_complete(self) -> bool:
        """Return True if planning data is present"""
        return bool(self.planning_data)


class ModuleAgent:
    """
    Main orchestrator agent for GenePattern module generation.
    Groups all methods for calling other agents, validation, and reporting.
    """
    
    def __init__(self, logger: Logger = None, output_dir: str = DEFAULT_OUTPUT_DIR):
        """Initialize the module agent with MCP server for validation"""
        self.logger = logger or Logger()
        self.output_dir = output_dir

        # Define artifact agents mapping
        self.artifact_agents = {
            'wrapper': {
                'agent': wrapper_agent,
                'filename': 'wrapper.py',
                'validate_tool': 'validate_wrapper',
                'create_method': 'create_wrapper'
            },
            'manifest': {
                'agent': manifest_agent,
                'filename': 'manifest',
                'validate_tool': 'validate_manifest',
                'create_method': 'create_manifest'
            },
            'paramgroups': {
                'agent': paramgroups_agent,
                'filename': 'paramgroups.json',
                'validate_tool': 'validate_paramgroups',
                'create_method': 'create_paramgroups'
            },
            'gpunit': {
                'agent': gpunit_agent,
                'filename': 'test.yml',
                'validate_tool': 'validate_gpunit',
                'create_method': 'create_gpunit'
            },
            'documentation': {
                'agent': documentation_agent,
                'filename': 'README.md',
                'validate_tool': 'validate_documentation',
                'create_method': 'create_documentation'
            },
            'dockerfile': {
                'agent': dockerfile_agent,
                'filename': 'Dockerfile',
                'validate_tool': 'validate_dockerfile',
                'create_method': 'create_dockerfile'
            }
        }
    
    def create_module_directory(self, tool_name: str) -> Path:
        """Create and return the module directory path"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tool_name_clean = tool_name.lower().replace(' ', '_').replace('-', '_')
        module_dir_name = f"{tool_name_clean}_{timestamp}"
        module_path = Path(self.output_dir) / module_dir_name

        self.logger.print_status(f"Creating module directory: {module_path}")
        module_path.mkdir(parents=True, exist_ok=True)
        return module_path
    
    def do_research(self, tool_info: Dict[str, str]) -> Tuple[bool, Dict[str, Any]]:
        """Run research phase using researcher agent"""
        self.logger.print_section("Research Phase")
        self.logger.print_status("Starting research on tool information")
        
        try:
            prompt = f"""
            Research the bioinformatics tool '{tool_info['name']}' and provide comprehensive information.
            
            Known Information:
            - Name: {tool_info['name']}
            - Version: {tool_info['version']}
            - Language: {tool_info['language']}
            - Description: {tool_info.get('description', 'Not provided')}
            - Repository: {tool_info.get('repository_url', 'Not provided')}
            - Documentation: {tool_info.get('documentation_url', 'Not provided')}
            
            Please provide detailed research including:
            1. Tool purpose and scientific applications
            2. Input/output formats and requirements
            3. Parameter analysis and usage patterns
            4. Installation and dependency requirements
            5. Common workflows and use cases
            6. Integration considerations for GenePattern
            
            Focus on information that will help create a complete GenePattern module.
            """
            
            result = researcher_agent.run_sync(prompt)
            self.logger.print_status("Research phase completed successfully", "SUCCESS")
            return True, {'research': result.output}
            
        except Exception as e:
            error_msg = f"Research phase failed: {str(e)}"
            self.logger.print_status(error_msg, "ERROR")
            self.logger.print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return False, {'error': error_msg}
    
    def do_planning(self, tool_info: Dict[str, str], research_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Run planning phase using planner agent"""
        self.logger.print_section("Planning Phase")
        self.logger.print_status("Starting module planning and parameter analysis")
        
        try:
            prompt = f"""
            Create a comprehensive plan for the GenePattern module for '{tool_info['name']}'.
            
            Tool Information:
            - Name: {tool_info['name']}
            - Version: {tool_info['version']}
            - Language: {tool_info['language']}
            - Description: {tool_info.get('description', 'Not provided')}
            
            Research Results:
            {research_data.get('research', 'No research data available')}
            
            Please create:
            1. Detailed parameter definitions with types and descriptions
            2. Module architecture recommendations
            3. Integration strategy for GenePattern
            4. Validation and testing approach
            5. Implementation roadmap
            
            Focus on creating actionable specifications for module development.
            """
            
            result = planner_agent.run_sync(prompt)
            self.logger.print_status("Planning phase completed successfully", "SUCCESS")
            return True, {'plan': result.output, 'parameters': []}  # Parameters would be extracted from plan
            
        except Exception as e:
            error_msg = f"Planning phase failed: {str(e)}"
            self.logger.print_status(error_msg, "ERROR")
            self.logger.print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return False, {'error': error_msg}
    
    def artifact_creation_loop(self, artifact_name: str, tool_info: Dict[str, str], planning_data: Dict[str, Any], module_path: Path, status: ModuleGenerationStatus) -> bool:
        """Generate and validate a single artifact using its dedicated agent"""
        artifact_config = self.artifact_agents[artifact_name]
        agent = artifact_config['agent']
        filename = artifact_config['filename']
        validate_tool = artifact_config['validate_tool']
        create_method = artifact_config['create_method']
        file_path = module_path / filename
        error_report = ""

        # Initialize artifact status
        status.artifacts_status[artifact_name] = {
            'generated': False,
            'validated': False,
            'attempts': 0,
            'errors': []
        }

        for attempt in range(1, MAX_ARTIFACT_LOOPS + 1):
            try:
                self.logger.print_status(f"Generating {artifact_name} (attempt {attempt}/{MAX_ARTIFACT_LOOPS})")
                status.artifacts_status[artifact_name]['attempts'] = attempt

                # Call the agent's create method with proper parameters
                prompt = f"""Use the {create_method} tool with the following parameters:
                - tool_info: {tool_info}
                - planning_data: {planning_data}
                - error_report: {error_report}
                - attempt: {attempt}

                Generate the {artifact_name} artifact for {tool_info['name']}."""
                result = agent.run_sync(prompt)

                # Write content to file
                with open(file_path, 'w') as f:
                    f.write(result.output)

                status.artifacts_status[artifact_name]['generated'] = True
                self.logger.print_status(f"Generated {filename}")

                # Validate using MCP server
                validation_result = self.validate_artifact(str(file_path), validate_tool)

                if validation_result['success']:
                    status.artifacts_status[artifact_name]['validated'] = True
                    self.logger.print_status(f"✅ Successfully generated and validated {artifact_name}")
                    return True
                else:
                    error_report = f"Validation failed: {validation_result.get('error', 'Unknown validation error')}"
                    self.logger.print_status(f"❌ {error_report}")
                    status.artifacts_status[artifact_name]['errors'].append(error_report)

                    if attempt == MAX_ARTIFACT_LOOPS:
                        return False

            except Exception as e:
                error_report = f"Error generating {artifact_name}: {str(e)}"
                self.logger.print_status(error_report, "ERROR")
                status.artifacts_status[artifact_name]['errors'].append(error_report)

                if attempt == MAX_ARTIFACT_LOOPS:
                    return False

        return False

    def validate_artifact(self, file_path: str, validate_tool: str) -> Dict[str, Any]:
        """Validate an artifact using the MCP server"""
        try:
            self.logger.print_status(f"Validating with {validate_tool}")

            # Create a temporary agent with MCP tools to run validation
            validation_agent = Agent(
                model='bedrock:us.anthropic.claude-sonnet-4-20250514-v1:0',
                toolsets=[MCPServerStdio('python', args=['mcp/server.py'], timeout=10)]
            )

            # Use the agent to call the validation tool
            prompt = f"Use the {validate_tool} tool to validate the file at path: {file_path}"
            result = validation_agent.run_sync(prompt)

            # Parse the validation output more carefully
            output = result.output
            self.logger.print_status(f"Validation output: {output[:200]}...")  # Log first 200 chars for debugging

            # Look for explicit PASS/FAIL indicators from the linter
            output_lower = output.lower()

            # Check for explicit failure indicators
            if any(indicator in output_lower for indicator in [
                "fail:", "failed", "error:", "invalid json", "validation failed"
            ]):
                return {'success': False, 'error': output}

            # Check for explicit success indicators
            elif any(indicator in output_lower for indicator in [
                "pass:", "passed all validation", "validation passed"
            ]):
                return {'success': True, 'result': output}

            # If we can't determine success/failure clearly, default to failure for safety
            else:
                self.logger.print_status(f"Ambiguous validation result, defaulting to failure", "WARNING")
                return {'success': False, 'error': f"Ambiguous validation result: {output}"}

        except Exception as e:
            return {'success': False, 'error': f"Validation error: {str(e)}"}

    def generate_all_artifacts(self, tool_info: Dict[str, str], planning_data: Dict[str, Any], module_path: Path, status: ModuleGenerationStatus, skip_artifacts: List[str] = None) -> bool:
        """Run artifact generation phase using artifact agents"""
        self.logger.print_section("Artifact Generation Phase")
        self.logger.print_status("Starting artifact generation")
        
        # Initialize skip list and success flag
        if skip_artifacts is None: skip_artifacts = []
        all_artifacts_successful = True
        
        for artifact_name, artifact_config in self.artifact_agents.items():
            if artifact_name in skip_artifacts:  # Check if this artifact should be skipped
                self.logger.print_status(f"Skipping {artifact_name} (--skip-{artifact_name} specified)")
                continue
            
            self.logger.print_status(f"Generating {artifact_name}...")
            success = self.artifact_creation_loop(artifact_name, tool_info, planning_data, module_path, status)
            
            if not success:
                self.logger.print_status(f"❌ Failed to generate {artifact_name} after {MAX_ARTIFACT_LOOPS} attempts")
                all_artifacts_successful = False
        
        return all_artifacts_successful
    
    def print_final_report(self, status: ModuleGenerationStatus):
        """Print comprehensive final report"""
        self.logger.print_section("Final Report")
        
        print(f"Tool Name: {status.tool_name}")
        print(f"Module Directory: {status.module_directory}")
        print(f"Research Complete: {'✓' if status.research_complete else '❌'}")
        print(f"Planning Complete: {'✓' if status.planning_complete else '❌'}")
        
        # Print artifact status
        print(f"\nArtifact Status:")
        for artifact_name, artifact_status in status.artifacts_status.items():
            generated = "✓" if artifact_status['generated'] else "❌"
            validated = "✓" if artifact_status['validated'] else "❌"
            attempts = artifact_status['attempts']
            
            print(f"  {artifact_name}:")
            print(f"    Generated: {generated} | Validated: {validated} | Attempts: {attempts}")
            
            if artifact_status['errors']:
                print(f"    Errors: {len(artifact_status['errors'])}")
                for error in artifact_status['errors'][:2]:  # Show first 2 errors
                    print(f"      - {error}")
        
        # Print parameters if available
        if status.parameters:
            print(f"\nParameters Identified: {len(status.parameters)}")
            for i, param in enumerate(status.parameters[:5]):  # Show first 5
                name = param.get('name', 'unknown')
                param_type = param.get('type', 'unknown')
                required = 'Required' if param.get('required', False) else 'Optional'
                print(f"  - {name}: {param_type} ({required})")
            
            if len(status.parameters) > 5:
                print(f"  ... and {len(status.parameters) - 5} more parameters")
        
        # Print generated files
        module_path = Path(status.module_directory)
        if module_path.exists():
            print(f"\nGenerated Files:")
            for file in module_path.iterdir():
                if file.is_file():
                    size = file.stat().st_size
                    print(f"  - {file.name} ({size:,} bytes)")
        
        # Overall success status
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

    def run(self, tool_info: Dict[str, str], skip_artifacts: List[str] = None, dev_mode: bool = False) -> int:
        """Run the complete module generation process"""
        self.logger.print_status(f"Generating module for: {tool_info['name']}")

        # Create module directory
        module_path = self.create_module_directory(tool_info['name'])

        # Initialize status tracking
        status = ModuleGenerationStatus(tool_name=tool_info['name'], module_directory=str(module_path))

        # Phase 1: Research
        research_success, research_data = self.do_research(tool_info)
        if research_success: status.research_data = research_data
        else: status.error_messages.append(research_data.get('error', 'Research failed'))
        if dev_mode:
            with open(module_path / "research.md", "w") as f:
                f.write(status.research_data.get('research', ''))

        if not status.research_complete:
            self.print_final_report(status)
            return 1

        # Phase 2: Planning
        planning_success, planning_data = self.do_planning(tool_info, status.research_data)
        if planning_success: status.planning_data = planning_data
        else: status.error_messages.append(planning_data.get('error', 'Planning failed'))
        if dev_mode:
            with open(module_path / "plan.md", "w") as f:
                f.write(status.planning_data.get('plan', ''))

        if not status.planning_complete:
            self.print_final_report(status)
            return 1

        # Extract parameters from planning data
        status.parameters = status.planning_data.get('parameters', [])

        # Phase 3: Artifact Generation
        artifacts_success = self.generate_all_artifacts(tool_info, status.planning_data, module_path, status, skip_artifacts)

        # Final report
        self.print_final_report(status)

        return 0 if (research_success and planning_success and artifacts_success) else 1


class GenerationScript:
    """
    Main script orchestration class for GenePattern module generation.
    Handles user input, argument parsing, and overall script coordination.
    """
    
    def __init__(self):
        """Initialize the generation script"""
        self.logger = Logger()
        self.args = None
        self.tool_info = None
        self.module_agent = None
        self.skip_artifacts = None

    def get_user_input(self) -> Dict[str, str]:
        """Prompt user for bioinformatics tool information"""
        self.logger.print_section("GenePattern Module Generator")
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
        
        return tool_info

    def parse_arguments(self):
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
        
        # Tool information
        parser.add_argument('--name', type=str, help='Tool name (e.g., "samtools")')
        parser.add_argument('--version', type=str, help='Tool version')
        parser.add_argument('--language', type=str, help='Primary language (e.g., "python")')
        parser.add_argument('--description', type=str, help='Brief description of the tool')
        parser.add_argument('--repository-url', type=str, help='URL of the source code repository')
        parser.add_argument('--documentation-url', type=str, help='URL of the tool documentation')

        # Artifact skip flags
        parser.add_argument('--skip-wrapper', action='store_true', help='Skip generating wrapper script')
        parser.add_argument('--skip-manifest', action='store_true', help='Skip generating manifest file')
        parser.add_argument('--skip-paramgroups', action='store_true', help='Skip generating paramgroups.json file')
        parser.add_argument('--skip-gpunit', action='store_true', help='Skip generating GPUnit test file')
        parser.add_argument('--skip-documentation', action='store_true', help='Skip generating README.md documentation')
        parser.add_argument('--skip-dockerfile', action='store_true', help='Skip generating Dockerfile')
        
        # Alternative: specify only artifacts to generate
        parser.add_argument('--artifacts', nargs='+', choices=['wrapper', 'manifest', 'paramgroups', 'gpunit', 'documentation', 'dockerfile', 'none'], help="Generate only specified artifacts, or 'none' to skip all (alternative to --skip-* flags)")

        # Development mode
        parser.add_argument('--dev-mode', action='store_true', help='Enable development mode, saves intermediate files')

        # Output directory
        parser.add_argument('--output-dir', default=DEFAULT_OUTPUT_DIR, type=str, help=f'Output directory for generated modules (default: {DEFAULT_OUTPUT_DIR})')
        
        self.args = parser.parse_args()

    def tool_info_from_args(self):
        """Extract tool information from command line arguments"""
        self.tool_info = {
            'name': self.args.name,
            'version': self.args.version or "latest",
            'language': self.args.language or "unknown",
            'description': self.args.description or "",
            'repository_url': self.args.repository_url or "",
            'documentation_url': self.args.documentation_url or ""
        }

    def parse_skip_artifacts(self):
        """Determine which artifacts to skip based on command line arguments"""
        self.skip_artifacts = []
        all_artifacts = ['wrapper', 'manifest', 'paramgroups', 'gpunit', 'documentation', 'dockerfile']

        # If --artifacts specified, skip everything not in the list
        if self.args.artifacts:
            if 'none' in self.args.artifacts:
                self.skip_artifacts = all_artifacts
                self.logger.print_status("Skipping all artifact generation as '--artifacts none' was specified.")
            else:
                self.skip_artifacts = [artifact for artifact in all_artifacts if artifact not in self.args.artifacts]
                self.logger.print_status(f"Generating only: {', '.join(self.args.artifacts)}")
        else:
            # Use individual skip flags
            if self.args.skip_wrapper:       self.skip_artifacts.append('wrapper')
            if self.args.skip_manifest:      self.skip_artifacts.append('manifest')
            if self.args.skip_paramgroups:   self.skip_artifacts.append('paramgroups')
            if self.args.skip_gpunit:        self.skip_artifacts.append('gpunit')
            if self.args.skip_documentation: self.skip_artifacts.append('documentation')
            if self.args.skip_dockerfile:    self.skip_artifacts.append('dockerfile')

            if self.skip_artifacts:          self.logger.print_status(f"Skipping: {', '.join(self.skip_artifacts)}")

    def main(self):
        """Main entry point for module generation"""
        try:
            # Parse command line arguments
            self.parse_arguments()
            self.parse_skip_artifacts()

            # Get tool information from args or user input
            if self.args.name: self.tool_info_from_args()
            else: self.tool_info = self.get_user_input()

            # Initialize ModuleAgent with logger and module directory
            self.module_agent = ModuleAgent(self.logger, self.args.output_dir)

            # Run the generation process
            return self.module_agent.run(self.tool_info, self.skip_artifacts, self.args.dev_mode)

        except KeyboardInterrupt:
            self.logger.print_status("\nGeneration interrupted by user", "WARNING")
            return 1
        except Exception as e:
            self.logger.print_status(f"Unexpected error: {str(e)}", "ERROR")
            self.logger.print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return 1

if __name__ == "__main__":
    script = GenerationScript()
    sys.exit(script.main())
