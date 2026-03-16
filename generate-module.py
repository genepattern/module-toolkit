#!/usr/bin/env python
"""
GenePattern Module Generator

A multi-agent system for automatically generating GenePattern modules from bioinformatics tools.
Uses Pydantic AI to orchestrate research, planning, and artifact generation.
"""

import sys
import traceback
import argparse
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from agents.config import DEFAULT_OUTPUT_DIR, MAX_ARTIFACT_LOOPS, MAX_ESCALATIONS, configure_telemetry
from agents.example_data import ExampleDataItem, ExampleDataResolver
from agents.logger import Logger
from agents.module import ModuleAgent
from agents.status import ModuleGenerationStatus

# Enable telemetry with Logfire
configure_telemetry()



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

        # Example data (optional)
        data_input = input("Example data files or URLs (space-separated, optional): ").strip()
        if data_input:
            raw_items = data_input.split()
            resolver = ExampleDataResolver(self.logger)
            tool_info['example_data'] = resolver.resolve(raw_items)
        else:
            tool_info['example_data'] = []

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


        # Resume from previous run
        parser.add_argument('--resume', type=str, metavar='MODULE_DIR', help='Resume generation from a previous run using the specified module directory')

        # Max loops configuration
        parser.add_argument('--max-loops', type=int, metavar='X', default=MAX_ARTIFACT_LOOPS, help=f'Maximum number of generation attempts per artifact (default: {MAX_ARTIFACT_LOOPS})')

        # Max escalations configuration
        parser.add_argument('--max-escalations', type=int, metavar='N', default=MAX_ESCALATIONS, help=f'Maximum cross-artifact escalation attempts per artifact pair (default: {MAX_ESCALATIONS})')

        # Output directory
        parser.add_argument('--output-dir', default=DEFAULT_OUTPUT_DIR, type=str, help=f'Output directory for generated modules (default: {DEFAULT_OUTPUT_DIR})')

        # Pre-created module directory (used by the web UI to guarantee name consistency)
        parser.add_argument('--module-dir', type=str, metavar='PATH',
                            help='Use this pre-created directory as the module output directory instead of '
                                 'generating a new timestamped name under --output-dir.')

        # Zip options
        parser.add_argument('--no-zip', action='store_true', help='Skip creating a zip archive of artifact files')
        parser.add_argument('--zip-only', action='store_true', help='After creating zip archive, delete the individual artifact files (keeps only the zip)')

        # Docker push
        parser.add_argument('--docker-push', action='store_true', help='Push the Docker image to Docker Hub after building')

        # Example data
        parser.add_argument('--data', nargs='+', metavar='PATH_OR_URL',
                            help='Example data files (local paths or HTTP/HTTPS URLs). URLs are downloaded '
                                 'before planning so their contents can inform the LLM. Local files are '
                                 'used directly. All files are bind-mounted during the Dockerfile runtime test.')

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
            'instructions': self.args.instructions or "",
            'example_data': [],
            'module_dir': self.args.module_dir or "",
        }
        # Resolve --data items if provided
        if self.args.data:
            resolver = ExampleDataResolver(self.logger)
            self.tool_info['example_data'] = resolver.resolve(self.args.data)

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

                # Resolve fresh --data override if provided on resume
                resume_example_data = None
                if self.args.data:
                    resolver = ExampleDataResolver(self.logger)
                    resume_example_data = resolver.resolve(self.args.data)
                    self.logger.print_status(f"--data override: {len(resume_example_data)} item(s) will replace persisted example_data")

                return self.module_agent.run(
                    skip_artifacts=self.skip_artifacts,
                    resume_status=status,
                    max_loops=self.args.max_loops,
                    no_zip=self.args.no_zip,
                    zip_only=self.args.zip_only,
                    docker_push=self.args.docker_push,
                    example_data=resume_example_data,
                    max_escalations=self.args.max_escalations,
                )
            else:
                # Get tool information from args or user input
                if self.args.name:
                    self.tool_info_from_args()
                else:
                    self.tool_info = self.get_user_input()

                example_data = self.tool_info.pop('example_data', []) or []

                # Run the generation process
                return self.module_agent.run(
                    self.tool_info,
                    self.skip_artifacts,
                    max_loops=self.args.max_loops,
                    no_zip=self.args.no_zip,
                    zip_only=self.args.zip_only,
                    docker_push=self.args.docker_push,
                    example_data=example_data,
                    max_escalations=self.args.max_escalations,
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