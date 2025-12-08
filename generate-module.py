#!/usr/bin/env python
"""
GenePattern Module Generator

A multi-agent system for automatically generating GenePattern modules from bioinformatics tools.
Uses Pydantic AI to orchestrate research, planning, and artifact generation.
"""

import os
import sys
import traceback
import argparse
import json
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from pydantic_ai import Agent
# from pydantic_ai.mcp import MCPServerStdio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import models and agents
from agents.models import ArtifactModel, configured_llm_model
from agents.researcher import researcher_agent
from agents.planner import planner_agent, ModulePlan
from dockerfile.agent import dockerfile_agent
from wrapper.agent import wrapper_agent
from manifest.agent import manifest_agent
from manifest.models import ManifestModel
from paramgroups.agent import paramgroups_agent
from paramgroups.models import ParamgroupsModel
from documentation.agent import documentation_agent
from gpunit.agent import gpunit_agent


# Configuration
MAX_ARTIFACT_LOOPS = int(os.getenv('MAX_ARTIFACT_LOOPS', '5'))
DEFAULT_OUTPUT_DIR = os.getenv('MODULE_OUTPUT_DIR', './generated-modules')

# Token cost configuration (cost per 1000 tokens)
INPUT_TOKEN_COST_PER_1000 = float(os.getenv('INPUT_TOKEN_COST_PER_1000', '0.003'))
OUTPUT_TOKEN_COST_PER_1000 = float(os.getenv('OUTPUT_TOKEN_COST_PER_1000', '0.015'))


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
    planning_data: ModulePlan = None
    artifacts_status: Dict[str, Dict[str, Any]] = None
    error_messages: List[str] = None
    # Token tracking fields
    input_tokens: int = 0
    output_tokens: int = 0

    def __post_init__(self):
        if self.artifacts_status is None: self.artifacts_status = {}
        if self.error_messages is None: self.error_messages = []
        if self.research_data is None: self.research_data = {}

    @property
    def research_complete(self) -> bool:
        """Return True if research data is present"""
        return bool(self.research_data)

    @property
    def planning_complete(self) -> bool:
        """Return True if planning data is present"""
        return self.planning_data is not None

    @property
    def parameters(self):
        """Return parameters from planning_data if available"""
        return self.planning_data.parameters if self.planning_data else []

    def add_usage(self, result) -> None:
        """Add token usage from an agent result to the running totals"""
        try:
            usage = result.usage()
            if usage:
                self.input_tokens += usage.request_tokens or 0
                self.output_tokens += usage.response_tokens or 0
        except Exception:
            # If usage tracking fails, continue without crashing
            pass

    def get_estimated_cost(self) -> float:
        """Calculate estimated cost based on token usage"""
        input_cost = (self.input_tokens / 1000) * INPUT_TOKEN_COST_PER_1000
        output_cost = (self.output_tokens / 1000) * OUTPUT_TOKEN_COST_PER_1000
        return input_cost + output_cost

    def to_dict(self) -> Dict[str, Any]:
        """Convert status to a JSON-serializable dictionary"""
        data: Dict[str, Any] = {
            'tool_name': self.tool_name,
            'module_directory': self.module_directory,
            'research_complete': self.research_complete,
            'planning_complete': self.planning_complete,
            'research_data': self.research_data,
            'artifacts_status': self.artifacts_status,
            'error_messages': self.error_messages,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'estimated_cost': self.get_estimated_cost(),
        }

        # Serialize planning_data if present (it's a Pydantic model)
        if self.planning_data:
            data['planning_data'] = self.planning_data.model_dump()
        else:
            data['planning_data'] = {}

        return data


class ModuleAgent:
    """
    Main orchestrator agent for GenePattern module generation.
    Groups all methods for calling other agents, validation, and reporting.
    """
    
    def __init__(self, logger: Logger = None, output_dir: str = DEFAULT_OUTPUT_DIR):
        """Initialize the module agent with MCP server for validation"""
        self.logger = logger or Logger()
        self.output_dir = output_dir

        # Define artifact agents mapping with models and formatters
        self.artifact_agents = {
            'wrapper': {
                'agent': wrapper_agent,
                'model': ArtifactModel,  # Use ArtifactModel as placeholder
                'filename': 'wrapper.py',
                'validate_tool': 'validate_wrapper',
                'create_method': 'create_wrapper',
                'formatter': lambda m: m.code  # Extract code from ArtifactModel
            },
            'manifest': {
                'agent': manifest_agent,
                'model': ManifestModel,  # Use specific ManifestModel
                'filename': 'manifest',
                'validate_tool': 'validate_manifest',
                'create_method': 'create_manifest',
                'formatter': lambda m: m.to_manifest_string()  # Use ManifestModel's formatter
            },
            'paramgroups': {
                'agent': paramgroups_agent,
                'model': ParamgroupsModel,  # Use specific ParamgroupsModel
                'filename': 'paramgroups.json',
                'validate_tool': 'validate_paramgroups',
                'create_method': 'create_paramgroups',
                'formatter': lambda m: m.to_json_string()  # Use ParamgroupsModel's JSON formatter
            },
            'gpunit': {
                'agent': gpunit_agent,
                'model': ArtifactModel,  # Use ArtifactModel as placeholder
                'filename': 'test.yml',
                'validate_tool': 'validate_gpunit',
                'create_method': 'create_gpunit',
                'formatter': lambda m: m.code  # Extract code from ArtifactModel
            },
            'documentation': {
                'agent': documentation_agent,
                'model': ArtifactModel,  # Use ArtifactModel as placeholder
                'filename': 'README.md',
                'validate_tool': 'validate_documentation',
                'create_method': 'create_documentation',
                'formatter': lambda m: m.code  # Extract code from ArtifactModel
            },
            'dockerfile': {
                'agent': dockerfile_agent,
                'model': ArtifactModel,  # Use ArtifactModel as placeholder
                'filename': 'Dockerfile',
                'validate_tool': 'validate_dockerfile',
                'create_method': 'create_dockerfile',
                'formatter': lambda m: m.code  # Extract code from ArtifactModel
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
    
    def save_status(self, status: ModuleGenerationStatus, dev_mode: bool = False):
        """Save the status to disk as status.json if in dev mode"""
        if not dev_mode:
            return

        try:
            status_path = Path(status.module_directory) / "status.json"
            with open(status_path, 'w') as f:
                json.dump(status.to_dict(), f, indent=2)
        except Exception as e:
            self.logger.print_status(f"Failed to save status.json: {str(e)}", "WARNING")

    def load_status(self, module_directory: str) -> ModuleGenerationStatus:
        """Load status from status.json file for resuming generation"""
        status_path = Path(module_directory) / "status.json"

        if not status_path.exists():
            raise FileNotFoundError(f"No status.json found in {module_directory}")

        try:
            with open(status_path, 'r') as f:
                data = json.load(f)

            # Reconstruct ModulePlan from dict if present
            planning_data = None
            if data.get('planning_data') and data['planning_data']:
                planning_data = ModulePlan(**data['planning_data'])

            # Create status object with token counts
            status = ModuleGenerationStatus(
                tool_name=data['tool_name'],
                module_directory=data['module_directory'],
                research_data=data.get('research_data'),
                planning_data=planning_data,
                artifacts_status=data.get('artifacts_status', {}),
                error_messages=data.get('error_messages', []),
                input_tokens=data.get('input_tokens', 0),
                output_tokens=data.get('output_tokens', 0)
            )

            self.logger.print_status(f"Loaded status from {status_path}")
            return status

        except Exception as e:
            raise ValueError(f"Failed to load status.json: {str(e)}")

    def do_research(self, tool_info: Dict[str, str], status: ModuleGenerationStatus = None, dev_mode: bool = False) -> Tuple[bool, Dict[str, Any]]:
        """Run research phase using researcher agent"""
        self.logger.print_section("Research Phase")
        self.logger.print_status("Starting research on tool information")
        
        try:
            instructions_section = ""
            if tool_info.get('instructions'):
                instructions_section = f"\n            Additional Instructions:\n            {tool_info['instructions']}\n"

            prompt = f"""
            Research the bioinformatics tool '{tool_info['name']}' and provide comprehensive information.
            
            Known Information:
            - Name: {tool_info['name']}
            - Version: {tool_info['version']}
            - Language: {tool_info['language']}
            - Description: {tool_info.get('description', 'Not provided')}
            - Repository: {tool_info.get('repository_url', 'Not provided')}
            - Documentation: {tool_info.get('documentation_url', 'Not provided')}{instructions_section}
            
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

            # Track token usage if status provided and in dev mode
            if status and dev_mode:
                status.add_usage(result)
                self.save_status(status, dev_mode)

            self.logger.print_status("Research phase completed successfully", "SUCCESS")
            return True, {'research': result.output}
            
        except Exception as e:
            error_msg = f"Research phase failed: {str(e)}"
            self.logger.print_status(error_msg, "ERROR")
            self.logger.print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return False, {'error': error_msg}
    
    def do_planning(self, tool_info: Dict[str, str], research_data: Dict[str, Any], status: ModuleGenerationStatus = None, dev_mode: bool = False) -> Tuple[bool, ModulePlan]:
        """Run planning phase using planner agent"""
        self.logger.print_section("Planning Phase")
        self.logger.print_status("Starting module planning and parameter analysis")
        
        try:
            instructions_section = ""
            if tool_info.get('instructions'):
                instructions_section = f"\n            Additional Instructions (IMPORTANT - Pay close attention to these):\n            {tool_info['instructions']}\n"

            prompt = f"""
            Create a comprehensive structured plan for the GenePattern module for '{tool_info['name']}'.
            
            Tool Information:
            - Name: {tool_info['name']}
            - Version: {tool_info['version']}
            - Language: {tool_info['language']}
            - Description: {tool_info.get('description', 'Not provided')}{instructions_section}
            
            Research Results:
            {research_data.get('research', 'No research data available')}
            
            Please create a structured ModulePlan with:
            1. Detailed parameter definitions with types and descriptions
            2. Module architecture recommendations
            3. Integration strategy for GenePattern
            4. Validation and testing approach
            5. Implementation roadmap
            
            If an author name is not provided, use 'GenePattern Team'.
            
            Focus on creating actionable specifications for module development.
            """
            
            result = planner_agent.run_sync(prompt)

            # Track token usage if status provided and in dev mode
            if status and dev_mode:
                status.add_usage(result)
                self.save_status(status, dev_mode)

            self.logger.print_status("Planning phase completed successfully", "SUCCESS")
            return True, result.output

        except Exception as e:
            error_msg = f"Planning phase failed: {str(e)}"
            self.logger.print_status(error_msg, "ERROR")
            self.logger.print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return False, None

    def artifact_creation_loop(self, artifact_name: str, tool_info: Dict[str, str], planning_data: ModulePlan, module_path: Path, status: ModuleGenerationStatus, max_loops: int = MAX_ARTIFACT_LOOPS, dev_mode: bool = False) -> bool:
        """Generate and validate a single artifact using its dedicated agent"""
        artifact_config = self.artifact_agents[artifact_name]
        agent = artifact_config['agent']
        model_class = artifact_config.get('model', ArtifactModel)  # Get the Pydantic model
        formatter = artifact_config.get('formatter', lambda m: m.code)  # Get formatter function
        filename = artifact_config['filename']

        # Special handling for wrapper: determine extension based on tool language
        if artifact_name == 'wrapper':
            # First, check if planning_data has a wrapper_script specified
            planning_dict = planning_data.model_dump() if planning_data else {}
            wrapper_script_from_plan = planning_dict.get('wrapper_script')

            if wrapper_script_from_plan:
                # Use the wrapper script name from planning data
                filename = wrapper_script_from_plan
                self.logger.print_status(f"Using wrapper filename from planning data: {filename}")
            else:
                # Fallback to language-based naming
                tool_language = tool_info.get('language', 'python').lower()
                # Map language to file extension
                extension_map = {
                    'python': '.py',
                    'r': '.R',
                    'bash': '.sh',
                    'shell': '.sh',
                    'perl': '.pl',
                    'java': '.java'
                }
                extension = extension_map.get(tool_language, '.py')  # Default to .py
                filename = f'wrapper{extension}'
                self.logger.print_status(f"Using default wrapper filename: {filename}")

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
        self.save_status(status, dev_mode)

        for attempt in range(1, max_loops + 1):
            try:
                self.logger.print_status(f"Generating {artifact_name} (attempt {attempt}/{max_loops})")
                status.artifacts_status[artifact_name]['attempts'] = attempt
                self.save_status(status, dev_mode)

                # Convert ModulePlan to a serializable format for the prompt
                planning_data_dict = planning_data.model_dump()

                # Call the agent with appropriate prompt based on artifact type
                if artifact_name == 'manifest':
                    # Build instructions section if provided
                    instructions_section = ""
                    if tool_info.get('instructions'):
                        instructions_section = f"\n\nAdditional Instructions (IMPORTANT):\n{tool_info['instructions']}\n"

                    # For manifest, use a direct prompt that doesn't mention tool names
                    prompt = f"""Generate a complete GenePattern module manifest for {tool_info['name']}.

Tool Information:
- Name: {tool_info['name']}
- Version: {tool_info.get('version', '1.0')}
- Language: {tool_info.get('language', 'unknown')}
- Description: {tool_info.get('description', 'Bioinformatics analysis tool')}
- Repository: {tool_info.get('repository_url', '')}{instructions_section}

Planning Data:
{planning_data_dict}

{"Previous attempt failed with error: " + error_report if error_report else ""}

This is attempt {attempt} of {max_loops}.

Generate a complete, valid manifest file in key=value format."""
                else:
                    # Build instructions section if provided
                    instructions_section = ""
                    if tool_info.get('instructions'):
                        instructions_section = f"\n\nIMPORTANT - Additional Instructions:\n{tool_info['instructions']}\n"

                    # For other artifacts, use the tool-based prompt
                    prompt = f"""Use the {create_method} tool with the following parameters:
                - tool_info: {tool_info}
                - planning_data: {planning_data_dict}
                - error_report: {error_report}
                - attempt: {attempt}{instructions_section}

                Generate the {artifact_name} artifact for {tool_info['name']}."""

                # Use the specific model type for this artifact
                result = agent.run_sync(prompt, output_type=model_class)
                artifact_model = result.output

                # Track token usage if in dev mode
                if dev_mode:
                    status.add_usage(result)
                    self.save_status(status, dev_mode)

                # Format the artifact using the configured formatter
                formatted_content = formatter(artifact_model)

                # Write the formatted content to the main artifact file
                with open(file_path, 'w') as f:
                    f.write(formatted_content)

                # Write the report file if dev mode is enabled and artifact has report
                if dev_mode:
                    # Check if model has artifact_report (ManifestModel) or report (ArtifactModel)
                    report_content = None
                    if hasattr(artifact_model, 'artifact_report') and artifact_model.artifact_report:
                        report_content = artifact_model.artifact_report

                    if report_content:
                        report_path = module_path / f"report-{artifact_name}.md"
                        with open(report_path, 'w') as f:
                            f.write(report_content)
                        self.logger.print_status(f"Generated {artifact_name} report: {report_path.name}")

                status.artifacts_status[artifact_name]['generated'] = True
                self.logger.print_status(f"Generated {filename}")
                self.save_status(status, dev_mode)

                # Prepare extra validation arguments based on artifact type
                extra_validation_args = None
                if artifact_name == 'dockerfile':
                    # Pass the docker image tag from planning data to the dockerfile linter
                    docker_tag = planning_data_dict.get('docker_image_tag', '')
                    if docker_tag:
                        extra_validation_args = ['-t', docker_tag]
                        self.logger.print_status(f"Using docker tag for build: {docker_tag}")
                elif artifact_name == 'gpunit':
                    # Pass the module name and parameters to the gpunit linter for validation
                    extra_validation_args = []
                    module_name = planning_data_dict.get('module_name', '')
                    if module_name:
                        extra_validation_args.extend(['--module', module_name])
                        self.logger.print_status(f"Using module name for gpunit validation: {module_name}")
                    
                    # Extract parameter names from planning data
                    parameters = planning_data_dict.get('parameters', [])
                    if parameters:
                        param_names = [p.get('name', '') for p in parameters if p.get('name')]
                        if param_names:
                            extra_validation_args.append('--parameters')
                            extra_validation_args.extend(param_names)
                            self.logger.print_status(f"Using {len(param_names)} parameters for gpunit validation")
                    
                    # Only set extra_validation_args if we have something to pass
                    if not extra_validation_args:
                        extra_validation_args = None

                # Validate using linter
                validation_result = self.validate_artifact(str(file_path), validate_tool, extra_validation_args)

                if validation_result['success']:
                    status.artifacts_status[artifact_name]['validated'] = True
                    self.logger.print_status(f"✅ Successfully generated and validated {artifact_name}")
                    self.save_status(status, dev_mode)
                    return True
                else:
                    error_report = f"Validation failed: {validation_result.get('error', 'Unknown validation error')}"
                    self.logger.print_status(f"❌ {error_report}")
                    status.artifacts_status[artifact_name]['errors'].append(error_report)
                    self.save_status(status, dev_mode)

                    if attempt == max_loops:
                        return False

            except Exception as e:
                error_report = f"Error generating {artifact_name}: {str(e)}"
                self.logger.print_status(error_report, "ERROR")

                # Print full traceback for debugging
                tb_str = traceback.format_exc()
                self.logger.print_status(f"Full traceback:\n{tb_str}", "ERROR")

                # Store both error message and traceback
                full_error = f"{error_report}\n\nTraceback:\n{tb_str}"
                status.artifacts_status[artifact_name]['errors'].append(full_error)
                self.save_status(status, dev_mode)

                if attempt == max_loops:
                    return False

        return False

    def validate_artifact(self, file_path: str, validate_tool: str, extra_args: List[str] = None) -> Dict[str, Any]:
        """Validate an artifact using its linter directly

        Args:
            file_path: Path to the artifact file to validate
            validate_tool: Name of the validation tool to use
            extra_args: Additional command line arguments to pass to the linter
        """
        try:
            self.logger.print_status(f"Validating with {validate_tool}")

            # Map validate_tool names to their linter modules
            linter_map = {
                'validate_manifest': 'manifest.linter',
                'validate_dockerfile': 'dockerfile.linter',
                'validate_documentation': 'documentation.linter',
                'validate_gpunit': 'gpunit.linter',
                'validate_paramgroups': 'paramgroups.linter',
                'validate_wrapper': 'wrapper.linter',
            }

            if validate_tool not in linter_map:
                return {'success': False, 'error': f"Unknown validation tool: {validate_tool}"}

            linter_module_name = linter_map[validate_tool]

            # Import the linter module and call it directly
            import importlib
            import io
            from contextlib import redirect_stdout, redirect_stderr

            linter_module = importlib.import_module(linter_module_name)

            # Capture stdout and stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            try:
                # Build argument list - file path plus any extra args
                linter_args = [file_path]
                if extra_args:
                    linter_args.extend(extra_args)

                # Call the linter's main function with the arguments
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exit_code = linter_module.main(linter_args)

                output = stdout_capture.getvalue()
                errors = stderr_capture.getvalue()
                full_output = output
                if errors:
                    full_output += f"\nErrors:\n{errors}"

            except SystemExit as e:
                # Some linters call sys.exit()
                exit_code = e.code if e.code is not None else 0
                output = stdout_capture.getvalue()
                errors = stderr_capture.getvalue()
                full_output = output
                if errors:
                    full_output += f"\nErrors:\n{errors}"

            # Look for explicit PASS/FAIL indicators from the linter
            output_lower = full_output.lower()

            # Check for explicit failure indicators first
            if exit_code != 0 or any(indicator in output_lower for indicator in [
                "fail:", "failed", "error:", "invalid json", "validation failed"
            ]):
                # Print the full validation output for debugging
                self.logger.print_status("Validation failed. Full validation output:", "ERROR")
                print(full_output)
                return {'success': False, 'error': full_output}

            # Check for explicit success indicators
            elif any(indicator in output_lower for indicator in [
                "pass:", "passed", "validation passed", "has passed", "**passed**",
                "successfully", "validation successful", "all checks passed"
            ]):
                self.logger.print_status("✅ Validation passed", "SUCCESS")
                return {'success': True, 'result': full_output}

            # If we can't determine success/failure clearly, default to failure for safety
            else:
                self.logger.print_status(f"Ambiguous validation result, defaulting to failure", "WARNING")
                self.logger.print_status("Full validation output:", "WARNING")
                print(full_output)
                return {'success': False, 'error': f"Ambiguous validation result: {full_output}"}

        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            self.logger.print_status(error_msg, "ERROR")
            self.logger.print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return {'success': False, 'error': error_msg}

    def generate_all_artifacts(self, tool_info: Dict[str, str], planning_data: ModulePlan, module_path: Path, status: ModuleGenerationStatus, skip_artifacts: List[str] = None, max_loops: int = MAX_ARTIFACT_LOOPS, dev_mode: bool = False) -> bool:
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
            success = self.artifact_creation_loop(artifact_name, tool_info, planning_data, module_path, status, max_loops, dev_mode)

            if not success:
                self.logger.print_status(f"❌ Failed to generate {artifact_name} after {max_loops} attempts")
                all_artifacts_successful = False
        
        return all_artifacts_successful
    
    def zip_artifacts(self, module_path: Path, tool_name: str, zip_only: bool = False) -> bool:
        """
        Zip all artifact files into {module_name}.zip at the top level

        Args:
            module_path: Path to the module directory
            tool_name: Name of the tool/module
            zip_only: If True, delete artifact files after zipping

        Returns:
            True if zipping was successful, False otherwise
        """
        self.logger.print_section("Zipping Artifacts")
        self.logger.print_status("Creating zip archive of artifact files")

        try:
            # Define artifact filenames to include (not dev mode files)
            artifact_extensions = ['.py', '.R', '.sh', '.pl', '.java']  # Wrapper extensions
            artifact_files = ['manifest', 'paramgroups.json', 'test.yml', 'README.md', 'Dockerfile']

            # Collect all files to zip
            files_to_zip = []
            for file in module_path.iterdir():
                if file.is_file():
                    # Include wrapper files (files starting with 'wrapper' OR ending with wrapper extensions)
                    if file.name.startswith('wrapper') and any(file.name.endswith(ext) for ext in artifact_extensions):
                        files_to_zip.append(file)
                    # Also include files ending with wrapper extensions (catches custom wrapper names like geoquery_wrapper.R)
                    elif any(file.name.endswith(ext) for ext in artifact_extensions) and '_wrapper' in file.name.lower():
                        files_to_zip.append(file)
                    # Include other artifact files
                    elif file.name in artifact_files:
                        files_to_zip.append(file)

            if not files_to_zip:
                self.logger.print_status("No artifact files found to zip", "WARNING")
                return False

            # Create zip file
            zip_filename = f"{tool_name.lower().replace(' ', '_').replace('-', '_')}.zip"
            zip_path = module_path / zip_filename

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in files_to_zip:
                    # Add file at top level (arcname is just the filename)
                    zipf.write(file, arcname=file.name)
                    self.logger.print_status(f"  Added {file.name} to zip")

            zip_size = zip_path.stat().st_size
            self.logger.print_status(f"✅ Created {zip_filename} ({zip_size:,} bytes)", "SUCCESS")

            # If zip_only is True, delete the artifact files
            if zip_only:
                self.logger.print_status("Cleaning up artifact files (--zip-only specified)")
                for file in files_to_zip:
                    try:
                        file.unlink()
                        self.logger.print_status(f"  Deleted {file.name}")
                    except Exception as e:
                        self.logger.print_status(f"  Failed to delete {file.name}: {str(e)}", "WARNING")

            return True

        except Exception as e:
            self.logger.print_status(f"Failed to create zip archive: {str(e)}", "ERROR")
            self.logger.print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return False

    def print_final_report(self, status: ModuleGenerationStatus, dev_mode: bool = False):
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
                # Handle structured Parameter objects
                name = param.name
                param_type = param.type.value if hasattr(param.type, 'value') else str(param.type)
                required = 'Required' if param.required else 'Optional'
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
        
        # Print token usage and cost (only in dev mode)
        if status.input_tokens > 0 or status.output_tokens > 0:
            total_tokens = status.input_tokens + status.output_tokens
            estimated_cost = status.get_estimated_cost()
            print(f"\nToken Usage (dev mode):")
            print(f"  Input tokens:  {status.input_tokens:,}")
            print(f"  Output tokens: {status.output_tokens:,}")
            print(f"  Total tokens:  {total_tokens:,}")
            print(f"  Estimated cost: ${estimated_cost:.4f}")

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

    def run(self, tool_info: Dict[str, str] = None, skip_artifacts: List[str] = None, dev_mode: bool = False, resume_status: ModuleGenerationStatus = None, max_loops: int = MAX_ARTIFACT_LOOPS, no_zip: bool = False, zip_only: bool = False) -> int:
        """Run the complete module generation process"""

        # Handle resume mode
        if resume_status:
            self.logger.print_status(f"Resuming module generation for: {resume_status.tool_name}")
            status = resume_status
            module_path = Path(status.module_directory)

            # Extract tool_info from status if not provided
            if not tool_info:
                # Try to extract language from research_data or planning_data
                language = 'unknown'
                if status.research_data and isinstance(status.research_data, dict):
                    # Try to find language info in research data
                    research_text = str(status.research_data.get('research', ''))
                    # Look for common language indicators
                    if 'bioconductor' in research_text.lower() or ' r package' in research_text.lower() or 'cran' in research_text.lower():
                        language = 'r'
                    elif 'python' in research_text.lower() and 'pypi' in research_text.lower():
                        language = 'python'
                
                # Also check planning data if available
                if language == 'unknown' and status.planning_data:
                    plan_text = str(status.planning_data.plan if hasattr(status.planning_data, 'plan') else '')
                    if 'bioconductor' in plan_text.lower() or ' r package' in plan_text.lower():
                        language = 'r'
                    elif 'python' in plan_text.lower():
                        language = 'python'
                
                tool_info = {
                    'name': status.tool_name,
                    'version': 'latest',
                    'language': language,
                    'description': '',
                    'repository_url': '',
                    'documentation_url': ''
                }
                self.logger.print_status(f"Detected tool language from existing data: {language}")
        else:
            self.logger.print_status(f"Generating module for: {tool_info['name']}")
            # Create module directory
            module_path = self.create_module_directory(tool_info['name'])
            # Initialize status tracking
            status = ModuleGenerationStatus(tool_name=tool_info['name'], module_directory=str(module_path))
            self.save_status(status, dev_mode)

        # Phase 1: Research
        if status.research_complete:
            self.logger.print_section("Research Phase")
            self.logger.print_status("✓ Research already complete, using existing data", "SUCCESS")
            research_success = True
        else:
            research_success, research_data = self.do_research(tool_info, status, dev_mode)
            if research_success:
                status.research_data = research_data
            else:
                status.error_messages.append(research_data.get('error', 'Research failed'))
            if dev_mode and status.research_data:
                with open(module_path / "research.md", "w") as f:
                    f.write(status.research_data.get('research', ''))
            self.save_status(status, dev_mode)

        if not status.research_complete:
            self.print_final_report(status, dev_mode)
            return 1

        # Phase 2: Planning
        if status.planning_complete:
            self.logger.print_section("Planning Phase")
            self.logger.print_status("✓ Planning already complete, using existing plan", "SUCCESS")
            planning_success = True
        else:
            planning_success, planning_data = self.do_planning(tool_info, status.research_data, status, dev_mode)
            if planning_success:
                status.planning_data = planning_data
            else:
                status.error_messages.append("Planning failed")
            if dev_mode and status.planning_data:
                with open(module_path / "plan.md", "w") as f:
                    f.write(status.planning_data.plan)
            self.save_status(status, dev_mode)

        if not status.planning_complete:
            self.print_final_report(status, dev_mode)
            return 1

        # Phase 3: Artifact Generation
        # Add completed artifacts to skip list
        if skip_artifacts is None:
            skip_artifacts = []

        # Skip artifacts that are already validated
        for artifact_name, artifact_status in status.artifacts_status.items():
            if artifact_status.get('validated', False):
                if artifact_name not in skip_artifacts:
                    skip_artifacts.append(artifact_name)
                    self.logger.print_status(f"✓ {artifact_name} already completed, skipping")

        artifacts_success = self.generate_all_artifacts(tool_info, status.planning_data, module_path, status, skip_artifacts, max_loops, dev_mode)

        # Phase 4: Zip artifacts (if successful and not disabled)
        if artifacts_success and not no_zip:
            self.zip_artifacts(module_path, tool_info['name'], zip_only)

        # Final report
        self.print_final_report(status, dev_mode)

        return 0 if (status.research_complete and status.planning_complete and artifacts_success) else 1


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
        tool_info['instructions'] = input("Additional instructions/context (optional): ").strip()

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
        parser.add_argument('--instructions', type=str, help='Additional instructions and context for module generation (e.g., which features to expose, which function to call)')

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

        # Resume from previous run
        parser.add_argument('--resume', type=str, metavar='MODULE_DIR', help='Resume generation from a previous run using the specified module directory')

        # Max loops configuration
        parser.add_argument('--max-loops', type=int, metavar='X', default=MAX_ARTIFACT_LOOPS, help=f'Maximum number of generation attempts per artifact (default: {MAX_ARTIFACT_LOOPS})')

        # Output directory
        parser.add_argument('--output-dir', default=DEFAULT_OUTPUT_DIR, type=str, help=f'Output directory for generated modules (default: {DEFAULT_OUTPUT_DIR})')
        
        # Zip options
        parser.add_argument('--no-zip', action='store_true', help='Skip creating a zip archive of artifact files')
        parser.add_argument('--zip-only', action='store_true', help='After creating zip archive, delete the individual artifact files (keeps only the zip)')

        self.args = parser.parse_args()

    def tool_info_from_args(self):
        """Extract tool information from command line arguments"""
        self.tool_info = {
            'name': self.args.name,
            'version': self.args.version or "latest",
            'language': self.args.language or "unknown",
            'description': self.args.description or "",
            'repository_url': self.args.repository_url or "",
            'documentation_url': self.args.documentation_url or "",
            'instructions': self.args.instructions or ""
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

            # Initialize ModuleAgent with logger and module directory
            self.module_agent = ModuleAgent(self.logger, self.args.output_dir)

            # Check if resuming from a previous run
            if self.args.resume:
                self.logger.print_status(f"Resuming from previous run in directory: {self.args.resume}")
                status = self.module_agent.load_status(self.args.resume)
                return self.module_agent.run(
                    skip_artifacts=self.skip_artifacts,
                    dev_mode=self.args.dev_mode,
                    resume_status=status,
                    max_loops=self.args.max_loops,
                    no_zip=self.args.no_zip,
                    zip_only=self.args.zip_only
                )
            else:
                # Get tool information from args or user input
                if self.args.name:
                    self.tool_info_from_args()
                else:
                    self.tool_info = self.get_user_input()

                # Run the generation process
                return self.module_agent.run(
                    self.tool_info,
                    self.skip_artifacts,
                    self.args.dev_mode,
                    max_loops=self.args.max_loops,
                    no_zip=self.args.no_zip,
                    zip_only=self.args.zip_only
                )

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