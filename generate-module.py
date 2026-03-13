#!/usr/bin/env python
"""
GenePattern Module Generator

A multi-agent system for automatically generating GenePattern modules from bioinformatics tools.
Uses Pydantic AI to orchestrate research, planning, and artifact generation.
"""

import os
import re
import sys
import shutil
import traceback
import argparse
import logfire
import json
import socket
import zipfile
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
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
from agents.error_classifier import classify_error, should_escalate, RootCause


_VALID_GPUNIT_TYPES = {'text', 'number', 'file'}


def _normalize_param_type(raw_type) -> str:
    """Map any planning-data parameter type to a valid gpunit --types value.

    The gpunit validator only accepts 'text', 'number', or 'file'.
    GenePattern-specific types like 'choice', 'password', etc. are all
    functionally text at the test level, so they map to 'text'.
    """
    raw = str(raw_type).lower().strip()
    return raw if raw in _VALID_GPUNIT_TYPES else 'text'


def _sanitize_error_line(line: str) -> str:
    """Strip shell metacharacters and quotes from an error line.

    Prevents extracted error text from being copied verbatim into a generated
    Dockerfile RUN instruction and breaking the Docker BuildKit parser (e.g.
    an unmatched double-quote causing 'unexpected end of statement').
    """
    line = line.strip()
    for ch in ('"', "'", '`', '$', '\\'):
        line = line.replace(ch, '')
    return line


def enable_telemetry(host="localhost", port=4318):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0

# Enable telemetry with Logfire
if enable_telemetry():
    logfire.configure(send_to_logfire=False, service_name="module-toolkit")
    logfire.instrument_pydantic_ai()


# Configuration
MAX_ARTIFACT_LOOPS = int(os.getenv('MAX_ARTIFACT_LOOPS', '5'))
DEFAULT_OUTPUT_DIR = os.getenv('MODULE_OUTPUT_DIR', './generated-modules')

# Token cost configuration (cost per 1000 tokens)
INPUT_TOKEN_COST_PER_1000 = float(os.getenv('INPUT_TOKEN_COST_PER_1000', '0.003'))
OUTPUT_TOKEN_COST_PER_1000 = float(os.getenv('OUTPUT_TOKEN_COST_PER_1000', '0.015'))

# Cross-artifact escalation configuration
MAX_ESCALATIONS = int(os.getenv('MAX_ESCALATIONS', '2'))

# Artifact dependency graph: when a downstream artifact fails, these are the
# upstream artifacts that *could* be the root cause (in priority order).
ARTIFACT_DEPENDENCIES = {
    'dockerfile': ['wrapper', 'manifest', 'gpunit'],
    'gpunit': ['wrapper', 'manifest'],
    'manifest': ['wrapper'],
    'paramgroups': ['wrapper', 'manifest'],
    'documentation': [],
    'wrapper': [],
}


@dataclass
class ArtifactResult:
    """Structured result from an artifact_creation_loop call."""
    success: bool
    artifact_name: str
    error_text: str = ""          # raw validation error from the last failed attempt
    root_cause: Optional[RootCause] = None  # populated when classification is available


@dataclass
class ExampleDataItem:
    """Represents a single example data file (local path or URL)."""
    original: str           # Original value as supplied by the user
    resolved: str           # Resolved value: absolute path for local files, original URL for URLs
    is_url: bool            # True if this item came from a URL
    extension: str          # File extension, e.g. '.bam'
    filename: str           # Basename, e.g. 'sample.bam'
    local_path: Optional[str] = None  # Absolute local filesystem path; set after download for URLs

    @property
    def has_local(self) -> bool:
        """Return True if a local file path is available."""
        return self.local_path is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'original': self.original,
            'resolved': self.resolved,
            'is_url': self.is_url,
            'extension': self.extension,
            'filename': self.filename,
            'local_path': self.local_path,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ExampleDataItem':
        return cls(
            original=d['original'],
            resolved=d['resolved'],
            is_url=d['is_url'],
            extension=d['extension'],
            filename=d['filename'],
            local_path=d.get('local_path'),
        )


class ExampleDataResolver:
    """Validates and normalises --data items into ExampleDataItem objects."""

    def __init__(self, logger: 'Logger'):
        self.logger = logger

    def resolve(self, items: List[str]) -> List[ExampleDataItem]:
        """Validate and normalise a list of paths/URLs into ExampleDataItem objects."""
        result = []
        for item in items:
            if item.startswith('http://') or item.startswith('https://'):
                resolved = self._resolve_url(item)
            else:
                resolved = self._resolve_local(item)
            if resolved:
                result.append(resolved)
        return result

    def _resolve_url(self, url: str) -> Optional[ExampleDataItem]:
        filename = url.split('?')[0].rstrip('/').split('/')[-1] or 'data'
        ext = Path(filename).suffix.lower()
        try:
            resp = requests.head(url, timeout=10, allow_redirects=True)
            if resp.status_code >= 400:
                self.logger.print_status(
                    f"URL returned HTTP {resp.status_code}: {url} — continuing without this item",
                    "WARNING"
                )
                return None
        except Exception as e:
            self.logger.print_status(
                f"Could not reach URL {url} ({e}) — continuing without this item",
                "WARNING"
            )
            return None
        return ExampleDataItem(
            original=url, resolved=url, is_url=True,
            extension=ext, filename=filename, local_path=None
        )

    def _resolve_local(self, path: str) -> Optional[ExampleDataItem]:
        p = Path(path).resolve()
        if not p.exists():
            print(f"Error: Example data file not found: {path}")
            sys.exit(1)
        return ExampleDataItem(
            original=path, resolved=str(p), is_url=False,
            extension=p.suffix.lower(), filename=p.name, local_path=str(p)
        )


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
    example_data: List[ExampleDataItem] = None
    # Token tracking fields
    input_tokens: int = 0
    output_tokens: int = 0
    # Cross-artifact escalation tracking: artifact_name -> count
    escalation_counts: Dict[str, int] = None
    # Log of escalation events for debugging / reporting
    escalation_log: List[Dict[str, str]] = None

    def __post_init__(self):
        if self.artifacts_status is None: self.artifacts_status = {}
        if self.error_messages is None: self.error_messages = []
        if self.research_data is None: self.research_data = {}
        if self.example_data is None: self.example_data = []
        if self.escalation_counts is None: self.escalation_counts = {}
        if self.escalation_log is None: self.escalation_log = []

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
                self.input_tokens += usage.input_tokens or 0
                self.output_tokens += usage.outputTokens or 0
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
            'example_data': [item.to_dict() for item in (self.example_data or [])],
            'escalation_counts': self.escalation_counts or {},
            'escalation_log': self.escalation_log or [],
        }

        # Serialize planning_data if present (it's a Pydantic model)
        if self.planning_data:
            data['planning_data'] = self.planning_data.model_dump(mode='json')
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
    
    def create_module_directory(self, tool_name: str, module_dir: str = "") -> Path:
        """Create and return the module directory path.

        If *module_dir* is a non-empty absolute (or relative) path it is used
        directly, allowing the caller (e.g. the web UI) to guarantee that
        uploaded files and generated artifacts share the same directory.
        """
        if module_dir:
            module_path = Path(module_dir)
            self.logger.print_status(f"Creating module directory: {module_path}")
            module_path.mkdir(parents=True, exist_ok=True)
            return module_path

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tool_name_clean = tool_name.lower().replace(' ', '_').replace('-', '_')
        module_dir_name = f"{tool_name_clean}_{timestamp}"
        module_path = Path(self.output_dir) / module_dir_name

        self.logger.print_status(f"Creating module directory: {module_path}")
        module_path.mkdir(parents=True, exist_ok=True)
        return module_path

    def download_url_data(self, example_data: List[ExampleDataItem], module_path: Path) -> None:
        """Download URL-based example data items into {module_path}/data/ before planning.

        Sets item.local_path on each downloaded item so all downstream steps can
        use item.local_path uniformly without checking is_url.
        """
        url_items = [item for item in example_data if item.is_url]
        if not url_items:
            return

        data_dir = module_path / "data"
        data_dir.mkdir(exist_ok=True)

        # Track filenames used in this session to handle collisions
        used_names: set = set()

        for item in url_items:
            # Resolve filename collisions
            filename = item.filename
            if filename in used_names:
                stem = Path(filename).stem
                suffix = Path(filename).suffix
                counter = 1
                while filename in used_names:
                    filename = f"{stem}_{counter}{suffix}"
                    counter += 1
            used_names.add(filename)

            dest = data_dir / filename
            self.logger.print_status(f"Downloading {item.original} → {dest}")
            try:
                with requests.get(item.original, stream=True, timeout=60) as resp:
                    resp.raise_for_status()
                    with open(dest, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                item.local_path = str(dest.resolve())
                self.logger.print_status(f"Downloaded {filename} ({dest.stat().st_size:,} bytes)", "SUCCESS")
            except Exception as e:
                self.logger.print_status(
                    f"Failed to download {item.original}: {e} — skipping this item",
                    "WARNING"
                )
                # Clean up partial file if it exists
                if dest.exists():
                    try:
                        dest.unlink()
                    except Exception:
                        pass
                # local_path remains None — downstream steps will skip this item

    def cleanup_data_dir(self, module_path: Path) -> None:
        """Remove the data/ subdirectory after a successful dockerfile step."""
        data_dir = module_path / "data"
        if not data_dir.exists():
            return
        try:
            shutil.rmtree(data_dir)
            self.logger.print_status(f"Cleaned up data directory: {data_dir}")
        except Exception as e:
            self.logger.print_status(
                f"Could not remove data directory {data_dir}: {e}",
                "WARNING"
            )

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
                output_tokens=data.get('output_tokens', 0),
                example_data=[ExampleDataItem.from_dict(d) for d in data.get('example_data', [])],
                escalation_counts=data.get('escalation_counts', {}),
                escalation_log=data.get('escalation_log', []),
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

            example_data_section = ""
            example_data = tool_info.get('example_data') or []
            if example_data:
                lines = ["", "            Example Data Provided (for reference only):"]
                for item in example_data:
                    kind = "URL" if item.is_url else "local file"
                    lines.append(f"            - {item.filename} ({item.extension}) — {kind}")
                lines.append("            These are examples of data the user already has. Use them to understand typical")
                lines.append("            input formats, but do NOT restrict your research to only these formats. Document")
                lines.append("            ALL formats the tool supports so the module remains broadly useful.")
                lines.append("")
                example_data_section = "\n".join(lines)

            prompt = f"""
            Research the bioinformatics tool '{tool_info['name']}' and provide comprehensive information.
            
            Known Information:
            - Name: {tool_info['name']}
            - Version: {tool_info['version']}
            - Language: {tool_info['language']}
            - Description: {tool_info.get('description', 'Not provided')}
            - Repository: {tool_info.get('repository_url', 'Not provided')}
            - Documentation: {tool_info.get('documentation_url', 'Not provided')}{instructions_section}{example_data_section}
            
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

            example_data_section = ""
            example_data = tool_info.get('example_data') or []
            if example_data:
                lines = ["", "            Example Data Provided (for reference only):"]
                for item in example_data:
                    kind = "URL" if item.is_url else "local file"
                    lines.append(f"            - {item.filename} ({item.extension}) — {kind}")
                lines.append("            The user has this format available, so the module MUST accept it. However, do")
                lines.append("            NOT restrict the file_formats field to only this extension — include every")
                lines.append("            format the tool legitimately supports. The example data tells you what to")
                lines.append("            include, not what to exclude.")
                lines.append("")
                example_data_section = "\n".join(lines)

            prompt = f"""
            Create a comprehensive structured plan for the GenePattern module for '{tool_info['name']}'.
            
            Tool Information:
            - Name: {tool_info['name']}
            - Version: {tool_info['version']}
            - Language: {tool_info['language']}
            - Description: {tool_info.get('description', 'Not provided')}{instructions_section}{example_data_section}
            
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

    def artifact_creation_loop(self, artifact_name: str, tool_info: Dict[str, str], planning_data: ModulePlan, module_path: Path, status: ModuleGenerationStatus, max_loops: int = MAX_ARTIFACT_LOOPS, dev_mode: bool = False, downstream_error_context: str = "") -> ArtifactResult:
        """Generate and validate a single artifact using its dedicated agent"""
        artifact_config = self.artifact_agents[artifact_name]
        agent = artifact_config['agent']
        model_class = artifact_config.get('model', ArtifactModel)  # Get the Pydantic model
        formatter = artifact_config.get('formatter', lambda m: m.code)  # Get formatter function
        filename = artifact_config['filename']

        # Special handling for wrapper: determine extension based on tool language
        if artifact_name == 'wrapper':
            # First, check if planning_data has a wrapper_script specified
            planning_dict = planning_data.model_dump(mode='json') if planning_data else {}
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

        # Initialize artifact status (preserve errors from previous runs during escalation)
        existing_errors = []
        if artifact_name in status.artifacts_status:
            existing_errors = status.artifacts_status[artifact_name].get('errors', [])
        status.artifacts_status[artifact_name] = {
            'generated': False,
            'validated': False,
            'attempts': 0,
            'errors': existing_errors if downstream_error_context else []
        }
        self.save_status(status, dev_mode)

        def build_error_history() -> str:
            """Build a numbered history of all previous errors for this artifact."""
            errors = status.artifacts_status[artifact_name].get('errors', [])
            if not errors:
                return ""
            lines = ["Previous attempt errors (avoid repeating these mistakes):"]
            for i, err in enumerate(errors, 1):
                lines.append(f"\nAttempt {i} error:\n{err}")
            return "\n".join(lines)

        def build_downstream_error_section() -> str:
            """Build a prompt section explaining why this artifact is being re-generated
            due to a downstream failure (cross-artifact escalation)."""
            if not downstream_error_context:
                return ""
            return (
                "\n\n⚠️  CROSS-ARTIFACT ESCALATION — READ CAREFULLY ⚠️\n"
                "This artifact is being RE-GENERATED because a DOWNSTREAM artifact failed "
                "with an error that was traced back to THIS artifact as the root cause.\n\n"
                f"{downstream_error_context}\n\n"
                "You MUST address the issue described above in your new version of this artifact. "
                "Do NOT simply reproduce the previous version — make targeted changes to fix "
                "the downstream failure.\n"
            )

        for attempt in range(1, max_loops + 1):
            try:
                self.logger.print_status(f"Generating {artifact_name} (attempt {attempt}/{max_loops})")
                status.artifacts_status[artifact_name]['attempts'] = attempt
                self.save_status(status, dev_mode)

                # Convert ModulePlan to a serializable format for the prompt
                planning_data_dict = planning_data.model_dump(mode='json')

                # Call the agent with appropriate prompt based on artifact type
                # Build example-data context snippets (used by several artifact types)
                example_data: List[ExampleDataItem] = status.example_data or []

                # Build cross-artifact escalation context (non-empty only during backtracking)
                downstream_section = build_downstream_error_section()

                if artifact_name == 'manifest':
                    # Build instructions section if provided
                    instructions_section = ""
                    if tool_info.get('instructions'):
                        instructions_section = f"\n\nAdditional Instructions (IMPORTANT):\n{tool_info['instructions']}\n"

                    # Build example data cross-check block
                    example_data_section = ""
                    if example_data:
                        lines = ["\nExample Data Provided (for cross-check only):"]
                        for item in example_data:
                            kind = "URL" if item.is_url else "local file"
                            lines.append(f"- {item.filename} ({item.extension}) — {kind}")
                        lines.append("Confirm that the fileFormat field on the relevant input parameter(s) includes")
                        lines.append("this extension. Do NOT replace the full format list with only this extension —")
                        lines.append("all formats the tool legitimately supports must remain present.")
                        example_data_section = "\n".join(lines)

                    # For manifest, use a direct prompt that doesn't mention tool names
                    error_history = build_error_history()
                    prompt = f"""Generate a complete GenePattern module manifest for {tool_info['name']}.

Tool Information:
- Name: {tool_info['name']}
- Version: {tool_info.get('version', '1.0')}
- Language: {tool_info.get('language', 'unknown')}
- Description: {tool_info.get('description', 'Bioinformatics analysis tool')}
- Repository: {tool_info.get('repository_url', '')}{instructions_section}

Planning Data:
{planning_data_dict}

{error_history if error_history else ""}
{downstream_section}
This is attempt {attempt} of {max_loops}.
{example_data_section}
Generate a complete, valid manifest file in key=value format."""

                elif artifact_name == 'gpunit':
                    # Build instructions section if provided
                    instructions_section = ""
                    if tool_info.get('instructions'):
                        instructions_section = f"\n\nIMPORTANT - Additional Instructions:\n{tool_info['instructions']}\n"

                    # Build concrete file values block
                    example_data_section = ""
                    if example_data:
                        local_items = [item for item in example_data if item.has_local]
                        if local_items:
                            lines = ["\nExample Data for Test Parameters:"]
                            for item in local_items:
                                lines.append(f"- {item.local_path}  (use as the value for the matching file input parameter)")
                            lines.append("Use these exact local paths as parameter values in the test YAML.")
                            lines.append("For all other parameters (numeric, text, choice), use sensible default or")
                            lines.append("representative values. Do not invent placeholder strings like '<path_to_input>'.")
                            example_data_section = "\n".join(lines)

                    error_history = build_error_history()
                    prompt = f"""Generate the {artifact_name} artifact for the GenePattern module '{tool_info['name']}'.

{error_history if error_history else ""}
{downstream_section}
This is attempt {attempt} of {max_loops}.{instructions_section}{example_data_section}

Call the {create_method} tool with the following parameters:
- tool_info: Use the tool information provided
- planning_data: Use the planning data provided
- error_report: {repr(error_report)}
- attempt: {attempt}.
Make sure the generated artifact follows all guidelines, key requirements and critical rules and edit what the tool gave you as needed."""

                elif artifact_name == 'paramgroups':
                    # Build instructions section if provided
                    instructions_section = ""
                    if tool_info.get('instructions'):
                        instructions_section = f"\n\nIMPORTANT - Additional Instructions:\n{tool_info['instructions']}\n"

                    # Build grouping hint when two or more distinct extensions are provided
                    example_data_section = ""
                    distinct_exts = list(dict.fromkeys(
                        item.extension for item in example_data if item.extension
                    ))
                    if len(distinct_exts) >= 2:
                        lines = ["\nExample Data Provided:"]
                        for item in example_data:
                            kind = "URL" if item.is_url else "local file"
                            lines.append(f"- {item.filename} ({item.extension}) — {kind}")
                        lines.append("These files represent distinct input roles. When grouping parameters, keep")
                        lines.append("parameters that correspond to related input files in the same logical group")
                        lines.append("(e.g., place a counts matrix and metadata file parameters together in an")
                        lines.append("'Input Files' group rather than splitting them across unrelated groups).")
                        example_data_section = "\n".join(lines)

                    error_history = build_error_history()
                    prompt = f"""Generate the {artifact_name} artifact for the GenePattern module '{tool_info['name']}'.

{error_history if error_history else ""}
{downstream_section}
This is attempt {attempt} of {max_loops}.{instructions_section}{example_data_section}

Call the {create_method} tool with the following parameters:
- tool_info: Use the tool information provided
- planning_data: Use the planning data provided
- error_report: {repr(error_report)}
- attempt: {attempt}.
Make sure the generated artifact follows all guidelines, key requirements and critical rules and edit what the tool gave you as needed."""

                elif artifact_name == 'dockerfile':
                    # Build instructions section if provided
                    instructions_section = ""
                    if tool_info.get('instructions'):
                        instructions_section = f"\n\nIMPORTANT - Additional Instructions:\n{tool_info['instructions']}\n"

                    # Build bind-mount runtime note
                    example_data_section = ""
                    local_items = [item for item in example_data if item.has_local]
                    if local_items:
                        lines = ["\nExample Data for Runtime Validation:"]
                        for item in local_items:
                            lines.append(f"- {item.local_path} (will be bind-mounted into the container as /data/{item.filename})")
                        lines.append("After the image is built, a runtime command will be run using this file")
                        lines.append("bind-mounted into the container — no network access or download utilities")
                        lines.append("(wget, curl) are needed inside the image for this test. Ensure all dependencies")
                        lines.append("needed to process this file type are installed. Do NOT assume the module only")
                        lines.append("handles this format — install support for all formats the tool accepts.")
                        example_data_section = "\n".join(lines)

                    # Improvement 1: Read wrapper source and expose it so the LLM can
                    # infer the correct pip/CRAN/apt packages to install.
                    wrapper_source_section = ""
                    _wrapper_script = planning_data_dict.get('wrapper_script') or 'wrapper.py'
                    _wrapper_path = module_path / _wrapper_script
                    if _wrapper_path.exists():
                        try:
                            _wrapper_src = _wrapper_path.read_text(encoding='utf-8', errors='replace')
                            wrapper_source_section = (
                                f"\n\nWrapper Script ({_wrapper_script}) — use this to determine "
                                f"which packages must be installed in the image:\n"
                                f"```\n{_wrapper_src}\n```"
                            )
                        except Exception as _we:
                            self.logger.print_status(f"Could not read wrapper for dockerfile prompt: {_we}", "WARNING")

                    # Improvement 2 & 3: Build error history from ALL previous attempts,
                    # and truncate each raw log to structured errors + last 50 lines.
                    def _truncate_error_report(raw: str, max_tail: int = 50) -> str:
                        """Return structured error lines + last `max_tail` lines of raw output."""
                        error_indicators = [
                            'E: Unable to locate package', 'E: Package',
                            'ERROR:', 'error:', 'No such file or directory',
                            'ModuleNotFoundError', 'ImportError', 'command not found',
                            'exit code:', 'executor failed', 'FAILED',
                            'the following arguments are required:', 'usage:',
                            'unexpected end of statement', 'failed to process',
                        ]
                        extracted = []
                        for ln in raw.splitlines():
                            if any(ind in ln for ind in error_indicators):
                                sanitized = _sanitize_error_line(ln)
                                if sanitized and sanitized not in extracted:
                                    extracted.append(sanitized)
                        tail_lines = raw.splitlines()[-max_tail:]
                        parts = []
                        if extracted:
                            parts.append("KEY ERRORS:\n" + "\n".join(f"  - {e}" for e in extracted))
                        parts.append("LAST 50 LINES OF OUTPUT:\n" + "\n".join(tail_lines))
                        return "\n\n".join(parts)

                    all_errors = status.artifacts_status[artifact_name].get('errors', [])
                    error_history_section = ""
                    if all_errors:
                        history_parts = ["Previous attempt errors (do NOT repeat these mistakes):"]
                        for i, prev_err in enumerate(all_errors, 1):
                            truncated = _truncate_error_report(prev_err)
                            history_parts.append(f"\n--- Attempt {i} error ---\n{truncated}")
                        error_history_section = "\n".join(history_parts)

                    # Build per-attempt structured guidance from the latest error
                    structured_errors_section = ""
                    if error_report:
                        error_indicators = [
                            'E: Unable to locate package',
                            'E: Package',
                            'ERROR:',
                            'error:',
                            'No such file or directory',
                            'ModuleNotFoundError',
                            'ImportError',
                            'command not found',
                            'exit code:',
                            'executor failed',
                            'FAILED',
                            'the following arguments are required:',
                            'usage:',
                            'unexpected end of statement',
                            'failed to process',
                        ]
                        extracted = []
                        for line in error_report.splitlines():
                            if any(ind in line for ind in error_indicators):
                                sanitized = _sanitize_error_line(line)
                                if sanitized and sanitized not in extracted:
                                    extracted.append(sanitized)
                        if extracted:
                            structured_errors_section = "\n\nKEY ERRORS FROM MOST RECENT ATTEMPT (fix these specifically):\n"
                            structured_errors_section += "\n".join(f"  - {e}" for e in extracted)
                            structured_errors_section += (
                                "\n\nBefore writing apt-get install commands, use the verify_apt_packages tool "
                                "to confirm every package name is valid. If a package is not found, search for "
                                "the correct name before using it."
                            )
                            if any('the following arguments are required' in e or 'usage:' in e for e in extracted):
                                structured_errors_section += (
                                    "\n\nThe runtime test command failed because arguments were passed in the wrong style. "
                                    "The wrapper uses named --flag style arguments (e.g. --input-file, --command). "
                                    "Check the usage: line in the error above for the exact flag names required."
                                )
                            if any('unexpected end of statement' in e or 'failed to process' in e for e in extracted):
                                structured_errors_section += (
                                    "\n\nDOCKERFILE SYNTAX ERROR: A RUN instruction contains an unmatched quote or "
                                    "shell metacharacter. Do NOT use double-quoted strings in RUN echo or comment "
                                    "lines. Use single quotes or no quotes. Check every RUN instruction for "
                                    "unbalanced double-quotes."
                                )

                    prompt = f"""Generate the {artifact_name} artifact for the GenePattern module '{tool_info['name']}'.
{wrapper_source_section}
{error_history_section if error_history_section else ""}
{structured_errors_section}
{downstream_section}
This is attempt {attempt} of {max_loops}.{instructions_section}{example_data_section}

Call the {create_method} tool with the following parameters:
- wrapper_source: Pass the FULL wrapper script source shown above in the "Wrapper Script" section (pass an empty string if no wrapper source was shown).
- planning_data: Pass the planning data as a dictionary with keys: wrapper_script, parameters, input_file_formats, cpu_cores, memory, docker_image_tag.
- error_report: {repr(error_report)}
- attempt: {attempt}.
The tool will parse the wrapper's import statements programmatically to determine the correct pip/R packages to install.
Make sure the generated artifact follows all guidelines, key requirements and critical rules and edit what the tool gave you as needed."""

                else:
                    # Build instructions section if provided
                    instructions_section = ""
                    if tool_info.get('instructions'):
                        instructions_section = f"\n\nIMPORTANT - Additional Instructions:\n{tool_info['instructions']}\n"

                    error_history = build_error_history()
                    # For other artifacts, use a simpler prompt that instructs the LLM to call the tool
                    prompt = f"""Generate the {artifact_name} artifact for the GenePattern module '{tool_info['name']}'.

{error_history if error_history else ""}
{downstream_section}
This is attempt {attempt} of {max_loops}.{instructions_section}

Call the {create_method} tool with the following parameters:
- tool_info: Use the tool information provided
- planning_data: Use the planning data provided
- error_report: {repr(error_report)}
- attempt: {attempt}.
Make sure the generated artifact follows all guidelines, key requirements and critical rules and edit what the tool gave you as needed."""

                # Create a dependency context that includes tool_info and planning_data
                # This makes them automatically available to tool functions via RunContext
                deps_context = {
                    'tool_info': tool_info,
                    'planning_data': planning_data_dict,
                    'error_report': error_report,
                    'attempt': attempt
                }

                # Use the specific model type for this artifact
                # Pass tool_info and planning_data as deps so they're automatically available to tools
                result = agent.run_sync(
                    prompt,
                    output_type=model_class,
                    deps=deps_context
                )
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
                    extra_validation_args = []
                    if docker_tag:
                        extra_validation_args.extend(['-t', docker_tag])
                        self.logger.print_status(f"Using docker tag for build: {docker_tag}")

                    # Build runtime command from example data (Step 7)
                    # gpunit runs before dockerfile (insertion-order guarantee), so test.yml is readable
                    if example_data:
                        gpunit_params: Dict[str, Any] = {}
                        test_yml_path = module_path / "test.yml"
                        if test_yml_path.exists():
                            try:
                                import yaml
                                with open(test_yml_path) as yf:
                                    gpunit_doc = yaml.safe_load(yf)
                                if isinstance(gpunit_doc, dict):
                                    gpunit_params = gpunit_doc.get('params', {}) or {}
                            except Exception as e:
                                self.logger.print_status(f"Could not parse test.yml for runtime params: {e}", "WARNING")

                        runtime_cmd, volumes = self.build_runtime_command(
                            planning_data, example_data, gpunit_params, module_path
                        )
                        if runtime_cmd:
                            extra_validation_args.extend(['-c', runtime_cmd])
                            self.logger.print_status(f"Runtime command for dockerfile test: {runtime_cmd}")
                        for vol in volumes:
                            extra_validation_args.extend(['-v', vol])
                            self.logger.print_status(f"Volume mount: {vol}")

                    if not extra_validation_args:
                        extra_validation_args = None
                elif artifact_name == 'gpunit':
                    # Pass the module name and parameters to the gpunit linter for validation
                    extra_validation_args = []
                    module_name = planning_data_dict.get('module_name', '')
                    if module_name:
                        extra_validation_args.extend(['--module', module_name])
                        self.logger.print_status(f"Using module name for gpunit validation: {module_name}")

                    # Extract ONLY REQUIRED parameter names (and their types) from planning data.
                    # Optional parameters don't need to be in every GPUnit test.
                    parameters = planning_data_dict.get('parameters', [])
                    if parameters:
                        required_params = [
                            p for p in parameters
                            if p.get('name') and p.get('required', False)
                        ]
                        if required_params:
                            required_param_names = [p['name'] for p in required_params]
                            extra_validation_args.append('--parameters')
                            extra_validation_args.extend(required_param_names)
                            self.logger.print_status(f"Using {len(required_param_names)} required parameters for gpunit validation")

                            # Wire --types co-ordered with --parameters so the gpunit linter
                            # can verify file-typed parameters reference existing files.
                            param_types = [_normalize_param_type(p.get('type', 'text')) for p in required_params]
                            extra_validation_args.append('--types')
                            extra_validation_args.extend(param_types)

                    # Only set extra_validation_args if we have something to pass
                    if not extra_validation_args:
                        extra_validation_args = None

                # Validate using linter
                validation_result = self.validate_artifact(str(file_path), validate_tool, extra_validation_args)

                if validation_result['success']:
                    status.artifacts_status[artifact_name]['validated'] = True
                    self.logger.print_status(f"✅ Successfully generated and validated {artifact_name}")
                    self.save_status(status, dev_mode)
                    return ArtifactResult(success=True, artifact_name=artifact_name)
                else:
                    error_report = f"Validation failed: {validation_result.get('error', 'Unknown validation error')}"
                    self.logger.print_status(f"❌ {error_report}")
                    status.artifacts_status[artifact_name]['errors'].append(error_report)
                    self.save_status(status, dev_mode)

                    if attempt == max_loops:
                        # Classify the error to determine root cause
                        root_cause = classify_error(error_report, artifact_name)
                        return ArtifactResult(
                            success=False,
                            artifact_name=artifact_name,
                            error_text=error_report,
                            root_cause=root_cause,
                        )

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
                    root_cause = classify_error(full_error, artifact_name)
                    return ArtifactResult(
                        success=False,
                        artifact_name=artifact_name,
                        error_text=full_error,
                        root_cause=root_cause,
                    )

        # Fallback (should not normally reach here)
        root_cause = classify_error(error_report, artifact_name)
        return ArtifactResult(
            success=False,
            artifact_name=artifact_name,
            error_text=error_report,
            root_cause=root_cause,
        )

    def build_runtime_command(
        self,
        planning_data: ModulePlan,
        example_data: List[ExampleDataItem],
        gpunit_params: Dict[str, Any],
        module_path: Path = None,
    ) -> Tuple[Optional[str], List[str]]:
        """Build a docker runtime command and volume list for Dockerfile runtime testing.

        Tries two strategies in order:
        1. Wrapper introspection: reads the generated wrapper script and parses its
           argparse flags so the command uses --flag value style arguments.
        2. Placeholder substitution: falls back to substituting <param.name> tokens
           in planning_data.command_line (original behaviour).

        Returns:
            (command_str, volume_list) where volume_list entries are "host_path:container_path".
            Returns (None, []) when no substitution is possible.
        """
        from agents.models import ParameterType

        parameters = {p.name: p for p in planning_data.parameters}

        # Build extension → item mapping for file matching (first match wins)
        ext_to_item: Dict[str, ExampleDataItem] = {}
        positional_files: List[ExampleDataItem] = []
        for item in (example_data or []):
            if item.has_local:
                if item.extension and item.extension not in ext_to_item:
                    ext_to_item[item.extension] = item
                positional_files.append(item)

        volume_list: List[str] = []

        # ------------------------------------------------------------------ #
        # Strategy 1: introspect the wrapper script for argparse flag names  #
        # ------------------------------------------------------------------ #
        wrapper_flags = None  # dict: param_name -> '--flag-name' or None (positional)
        if module_path is not None:
            wrapper_script = planning_data.wrapper_script or 'wrapper.py'
            wrapper_path = module_path / wrapper_script
            if wrapper_path.exists():
                try:
                    wrapper_flags = self._parse_wrapper_flags(wrapper_path)
                    self.logger.print_status(
                        f"Introspected {len(wrapper_flags)} argument(s) from {wrapper_script}"
                    )
                except Exception as e:
                    self.logger.print_status(
                        f"Could not introspect wrapper flags, falling back to placeholder substitution: {e}",
                        "WARNING"
                    )

        if wrapper_flags is not None:
            # Build command using --flag value style derived from wrapper source
            wrapper_script = planning_data.wrapper_script or 'wrapper.py'
            # Determine interpreter prefix
            if wrapper_script.endswith('.py'):
                prefix = f"python {wrapper_script}"
            elif wrapper_script.endswith(('.R', '.r')):
                prefix = f"Rscript {wrapper_script}"
            elif wrapper_script.endswith('.sh'):
                prefix = f"bash {wrapper_script}"
            else:
                prefix = wrapper_script

            parts = [prefix]
            positional_file_idx = 0

            for param in planning_data.parameters:
                flag = wrapper_flags.get(param.name)
                # Skip parameters that have no corresponding flag and aren't positional
                if flag is None and param.name not in wrapper_flags:
                    continue

                if param.type == ParameterType.FILE:
                    item = None
                    if param.file_formats:
                        for fmt in param.file_formats:
                            ext = fmt if fmt.startswith('.') else f'.{fmt}'
                            if ext.lower() in ext_to_item:
                                item = ext_to_item[ext.lower()]
                                break
                    if item is None and positional_file_idx < len(positional_files):
                        item = positional_files[positional_file_idx]
                        positional_file_idx += 1

                    if item is None or not item.has_local:
                        self.logger.print_status(
                            f"No local example data for FILE parameter '{param.name}' — skipping runtime command",
                            "WARNING"
                        )
                        return None, []

                    container_path = f"/data/{item.filename}"
                    volume_entry = f"{item.local_path}:{container_path}"
                    if volume_entry not in volume_list:
                        volume_list.append(volume_entry)

                    if flag:
                        parts.append(f"{flag} {container_path}")
                    else:
                        parts.append(container_path)

                elif not param.required and param.type not in (ParameterType.INTEGER, ParameterType.FLOAT):
                    # Skip optional non-numeric parameters to keep the command minimal
                    continue

                else:
                    value = gpunit_params.get(param.name)
                    if value is None:
                        value = param.default_value
                    if value is None:
                        if param.type == ParameterType.INTEGER:
                            value = "1"
                        elif param.type == ParameterType.FLOAT:
                            value = "1.0"
                        elif param.type == ParameterType.CHOICE and param.choices:
                            value = param.choices[0].value
                        else:
                            value = "output"

                    if flag:
                        parts.append(f"{flag} {value}")
                    else:
                        parts.append(str(value))

            return " ".join(parts), volume_list

        # ------------------------------------------------------------------ #
        # Strategy 2: placeholder substitution in command_line (fallback)    #
        # ------------------------------------------------------------------ #
        command_line = planning_data.command_line
        placeholders = re.findall(r'<([^>]+)>', command_line)

        if not placeholders:
            return None, []

        result_cmd = command_line
        positional_file_idx = 0

        for placeholder in placeholders:
            param = parameters.get(placeholder)
            if param is None:
                continue

            if param.type == ParameterType.FILE:
                item = None
                if param.file_formats:
                    for fmt in param.file_formats:
                        ext = fmt if fmt.startswith('.') else f'.{fmt}'
                        if ext.lower() in ext_to_item:
                            item = ext_to_item[ext.lower()]
                            break
                if item is None and positional_file_idx < len(positional_files):
                    item = positional_files[positional_file_idx]
                    positional_file_idx += 1

                if item is None or not item.has_local:
                    self.logger.print_status(
                        f"No local example data available for FILE parameter '{placeholder}' — skipping runtime command",
                        "WARNING"
                    )
                    return None, []

                container_path = f"/data/{item.filename}"
                volume_entry = f"{item.local_path}:{container_path}"
                if volume_entry not in volume_list:
                    volume_list.append(volume_entry)
                result_cmd = result_cmd.replace(f'<{placeholder}>', container_path, 1)

            else:
                value = gpunit_params.get(placeholder)
                if value is None:
                    value = param.default_value
                if value is None:
                    if param.type == ParameterType.INTEGER:
                        value = "1"
                    elif param.type == ParameterType.FLOAT:
                        value = "1.0"
                    elif param.type == ParameterType.CHOICE and param.choices:
                        value = param.choices[0].value
                    else:
                        value = "output"
                result_cmd = result_cmd.replace(f'<{placeholder}>', str(value), 1)

        return result_cmd, volume_list

    def _parse_wrapper_flags(self, wrapper_path: Path) -> Dict[str, Optional[str]]:
        """Parse a wrapper script's argparse add_argument calls to extract flag names.

        Reads the wrapper source and finds lines like:
            parser.add_argument('--input-file', ...)
            parser.add_argument('input_file', ...)   # positional

        Returns a dict mapping GenePattern parameter name (dashes→underscores stripped
        to canonical form) to the flag string (e.g. '--input-file') or None for positional.
        Only includes arguments that have a long-form flag or are positional.
        """
        import ast

        source = wrapper_path.read_text(encoding='utf-8')
        flags: Dict[str, Optional[str]] = {}

        try:
            tree = ast.parse(source)
        except SyntaxError:
            # Fall back to regex if AST parse fails
            return self._parse_wrapper_flags_regex(source)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            # Match parser.add_argument(...) calls
            func = node.func
            is_add_argument = (
                (isinstance(func, ast.Attribute) and func.attr == 'add_argument') or
                (isinstance(func, ast.Name) and func.id == 'add_argument')
            )
            if not is_add_argument:
                continue
            if not node.args:
                continue

            # Collect string args (flag names like '--input-file' or 'input_file')
            str_args = [
                a.value if isinstance(a, ast.Constant) and isinstance(a.value, str)
                else None
                for a in node.args
            ]
            str_args = [s for s in str_args if s is not None]

            # Find the long flag (prefer --xxx over -x)
            long_flag = next((s for s in str_args if s.startswith('--')), None)
            positional = next((s for s in str_args if not s.startswith('-')), None)

            if long_flag:
                # Canonical name: '--input-file' → 'input.file' and 'input_file'
                canon = long_flag.lstrip('-').replace('-', '.').replace('_', '.')
                flags[canon] = long_flag
                # Also store with underscore/hyphen variants for looser matching
                flags[long_flag.lstrip('-').replace('-', '_')] = long_flag
                flags[long_flag.lstrip('-').replace('-', '.')] = long_flag
            elif positional:
                canon = positional.replace('-', '.').replace('_', '.')
                flags[canon] = None  # positional — no flag prefix
                flags[positional.replace('-', '_')] = None
                flags[positional.replace('-', '.')] = None

        return flags

    def _parse_wrapper_flags_regex(self, source: str) -> Dict[str, Optional[str]]:
        """Regex fallback for _parse_wrapper_flags when AST parsing fails."""
        flags: Dict[str, Optional[str]] = {}
        pattern = re.compile(r"""add_argument\s*\(\s*(['"])(--?[\w-]+)\1""")
        for match in pattern.finditer(source):
            flag = match.group(2)
            if flag.startswith('--'):
                canon = flag.lstrip('-').replace('-', '.')
                flags[canon] = flag
                flags[flag.lstrip('-').replace('-', '_')] = flag
        return flags


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

    def generate_all_artifacts(self, tool_info: Dict[str, str], planning_data: ModulePlan, module_path: Path, status: ModuleGenerationStatus, skip_artifacts: List[str] = None, max_loops: int = MAX_ARTIFACT_LOOPS, dev_mode: bool = False, max_escalations: int = MAX_ESCALATIONS) -> bool:
        """Run artifact generation phase with cross-artifact error escalation.

        Instead of a simple linear pass, this method implements a dependency-aware
        loop with backtracking.  When a downstream artifact (e.g. ``dockerfile``)
        fails validation and the error classifier determines the root cause lies
        in an upstream artifact (e.g. ``wrapper``), the upstream artifact is
        invalidated and regenerated with the downstream error context injected
        into its prompt.  The downstream artifact is then retried.

        Escalation is capped at ``MAX_ESCALATIONS`` per artifact pair to prevent
        infinite loops.
        """
        self.logger.print_section("Artifact Generation Phase")
        self.logger.print_status("Starting artifact generation")

        # Initialize skip list and success flag
        if skip_artifacts is None:
            skip_artifacts = []
        all_artifacts_successful = True

        # Build the ordered list of artifacts to process (insertion order).
        # gpunit intentionally comes before dockerfile so test.yml is available
        # when build_runtime_command reads it during the dockerfile step.
        artifact_queue: List[str] = [
            name for name in self.artifact_agents
            if name not in skip_artifacts
        ]
        # Track per-pair escalation counts to enforce the cap.
        # Key: (failing_artifact, target_artifact) -> int
        escalation_pair_counts: Dict[tuple, int] = {}

        # Track downstream error context to inject when re-generating an
        # upstream artifact due to escalation.  Key: artifact_name -> str
        pending_downstream_context: Dict[str, str] = {}

        idx = 0
        while idx < len(artifact_queue):
            artifact_name = artifact_queue[idx]

            if artifact_name in skip_artifacts:
                self.logger.print_status(f"Skipping {artifact_name} (--skip-{artifact_name} specified)")
                idx += 1
                continue

            # Check if already validated (e.g. from a previous resumed run)
            existing_status = status.artifacts_status.get(artifact_name, {})
            if existing_status.get('validated', False):
                self.logger.print_status(f"✓ {artifact_name} already validated, skipping")
                idx += 1
                continue

            self.logger.print_status(f"Generating {artifact_name}...")

            # Pop any pending downstream error context for this artifact
            downstream_ctx = pending_downstream_context.pop(artifact_name, "")

            result: ArtifactResult = self.artifact_creation_loop(
                artifact_name, tool_info, planning_data, module_path, status,
                max_loops, dev_mode,
                downstream_error_context=downstream_ctx,
            )

            if result.success:
                idx += 1
                continue

            # -----------------------------------------------------------
            # Artifact failed — attempt cross-artifact escalation
            # -----------------------------------------------------------
            root_cause = result.root_cause
            escalated = False

            if root_cause and should_escalate(root_cause):
                target = root_cause.target_artifact
                pair_key = (artifact_name, target)
                current_count = escalation_pair_counts.get(pair_key, 0)

                # Only escalate if:
                #  1. We haven't exceeded the per-pair escalation cap
                #  2. The target artifact is in our queue (not skipped)
                #  3. The target is upstream of the current artifact
                can_escalate = (
                    current_count < max_escalations
                    and target not in skip_artifacts
                    and target in self.artifact_agents
                    and target in ARTIFACT_DEPENDENCIES.get(artifact_name, [])
                )

                if can_escalate:
                    escalation_pair_counts[pair_key] = current_count + 1

                    # Record escalation in status for persistence / reporting
                    status.escalation_counts[pair_key[0]] = (
                        status.escalation_counts.get(pair_key[0], 0) + 1
                    )
                    escalation_event = {
                        'from_artifact': artifact_name,
                        'to_artifact': target,
                        'reason': root_cause.reason,
                        'error_snippet': result.error_text[:500],
                    }
                    status.escalation_log.append(escalation_event)
                    self.save_status(status, dev_mode)

                    self.logger.print_section("Cross-Artifact Escalation")
                    self.logger.print_status(
                        f"🔀 Escalating: {artifact_name} failure → regenerating {target}",
                        "WARNING",
                    )
                    self.logger.print_status(
                        f"   Reason: {root_cause.reason}",
                        "WARNING",
                    )
                    self.logger.print_status(
                        f"   Escalation {current_count + 1}/{max_escalations} "
                        f"for {artifact_name}→{target}",
                    )

                    # Invalidate the upstream artifact so it gets regenerated
                    if target in status.artifacts_status:
                        status.artifacts_status[target]['validated'] = False
                        status.artifacts_status[target]['generated'] = False
                    self.save_status(status, dev_mode)

                    # Build context string for the upstream regeneration prompt
                    pending_downstream_context[target] = (
                        f"The downstream artifact '{artifact_name}' failed validation "
                        f"with the following error:\n\n"
                        f"{result.error_text[:1000]}\n\n"
                        f"Root-cause analysis: {root_cause.reason}\n\n"
                        f"You must fix the issue in THIS artifact ({target}) so that "
                        f"the downstream '{artifact_name}' step can succeed."
                    )

                    # Insert the upstream artifact back into the queue right
                    # before the current position so it runs next, followed
                    # by a retry of the current artifact.
                    # First, remove any prior occurrence of target in the
                    # remaining queue to avoid duplicates.
                    remaining = artifact_queue[idx:]
                    if target in remaining:
                        remaining.remove(target)
                    # Rebuild: everything before idx + [target, current, rest…]
                    artifact_queue = (
                        artifact_queue[:idx]
                        + [target, artifact_name]
                        + [a for a in remaining if a != artifact_name]
                    )
                    # Don't increment idx — the next iteration picks up target

                    escalated = True

                else:
                    if current_count >= max_escalations:
                        self.logger.print_status(
                            f"⚠️  Escalation cap reached for {artifact_name}→{target} "
                            f"({max_escalations} attempts). Marking {artifact_name} as failed.",
                            "WARNING",
                        )

            if not escalated:
                self.logger.print_status(
                    f"❌ Failed to generate {artifact_name} after {max_loops} attempts"
                )
                all_artifacts_successful = False
                idx += 1

        return all_artifacts_successful
    
    def docker_push(self, planning_data: ModulePlan) -> bool:
        """Push the built Docker image to Docker Hub.

        Args:
            planning_data: The ModulePlan containing the docker_image_tag

        Returns:
            True if the push succeeded, False otherwise
        """
        self.logger.print_section("Docker Push")

        planning_dict = planning_data.model_dump(mode='json') if planning_data else {}
        tag = planning_dict.get('docker_image_tag', '')

        if not tag:
            self.logger.print_status("No docker_image_tag found in planning data, cannot push", "ERROR")
            return False

        self.logger.print_status(f"Pushing Docker image: {tag}")

        import subprocess
        cmd = ["docker", "push", tag]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            # Stream output line-by-line so the user can see progress
            for line in proc.stdout:
                print(line, end="")
            proc.wait()

            if proc.returncode == 0:
                self.logger.print_status(f"✅ Successfully pushed {tag}", "SUCCESS")
                return True
            else:
                self.logger.print_status(f"❌ Docker push failed for {tag} (exit code {proc.returncode})", "ERROR")
                return False
        except FileNotFoundError:
            self.logger.print_status("Docker CLI not found; ensure Docker is installed and on PATH", "ERROR")
            return False
        except Exception as e:
            self.logger.print_status(f"Docker push error: {str(e)}", "ERROR")
            self.logger.print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return False

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

        # Print cross-artifact escalation summary (if any occurred)
        if status.escalation_log:
            print(f"\nCross-Artifact Escalations: {len(status.escalation_log)}")
            for evt in status.escalation_log:
                print(f"  🔀 {evt['from_artifact']} → {evt['to_artifact']}: {evt['reason'][:120]}")

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

    def run(self, tool_info: Dict[str, str] = None, skip_artifacts: List[str] = None, dev_mode: bool = False, resume_status: ModuleGenerationStatus = None, max_loops: int = MAX_ARTIFACT_LOOPS, no_zip: bool = False, zip_only: bool = False, docker_push: bool = False, example_data: List[ExampleDataItem] = None, max_escalations: int = MAX_ESCALATIONS) -> int:
        """Run the complete module generation process"""

        # Handle resume mode
        if resume_status:
            self.logger.print_status(f"Resuming module generation for: {resume_status.tool_name}")
            status = resume_status
            module_path = Path(status.module_directory)

            # If --data was passed on resume, override the persisted example_data
            if example_data is not None:
                status.example_data = example_data
                self.logger.print_status(f"Overriding example_data with {len(example_data)} item(s) from --data")

            # Extract tool_info from status if not provided
            if not tool_info:
                # Try to extract language from research_data or planning_data
                language = 'unknown'
                if status.research_data and isinstance(status.research_data, dict):
                    research_text = str(status.research_data.get('research', ''))
                    if 'bioconductor' in research_text.lower() or ' r package' in research_text.lower() or 'cran' in research_text.lower():
                        language = 'r'
                    elif 'python' in research_text.lower() and 'pypi' in research_text.lower():
                        language = 'python'

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
                    'documentation_url': '',
                    'example_data': status.example_data,
                }
                self.logger.print_status(f"Detected tool language from existing data: {language}")
            else:
                # Ensure tool_info carries the (possibly overridden) example_data
                tool_info['example_data'] = status.example_data

            # Re-download any URL items whose local_path was not persisted
            url_items_missing_local = [
                item for item in (status.example_data or [])
                if item.is_url and not item.has_local
            ]
            if url_items_missing_local:
                self.logger.print_status(
                    f"Re-downloading {len(url_items_missing_local)} URL item(s) whose local_path was not recorded"
                )
                self.download_url_data(status.example_data, module_path)
                tool_info['example_data'] = status.example_data
                self.save_status(status, dev_mode)

        else:
            self.logger.print_status(f"Generating module for: {tool_info['name']}")
            # Create module directory (use pre-created path from web UI if supplied)
            module_path = self.create_module_directory(
                tool_info['name'],
                module_dir=tool_info.get('module_dir', ''),
            )
            # Initialize status tracking
            status = ModuleGenerationStatus(
                tool_name=tool_info['name'],
                module_directory=str(module_path),
                example_data=example_data or [],
            )
            # Propagate example_data into tool_info so prompt builders can read it
            tool_info['example_data'] = status.example_data

            # Step 1b: Download URL items before research/planning
            if status.example_data:
                self.download_url_data(status.example_data, module_path)

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

        artifacts_success = self.generate_all_artifacts(tool_info, status.planning_data, module_path, status, skip_artifacts, max_loops, dev_mode, max_escalations)

        # Step 1c: Clean up downloaded data/ directory after successful dockerfile step
        dockerfile_validated = status.artifacts_status.get('dockerfile', {}).get('validated', False)
        if dockerfile_validated:
            self.cleanup_data_dir(module_path)

        # Phase 4: Zip artifacts (if successful and not disabled)
        if artifacts_success and not no_zip:
            self.zip_artifacts(module_path, tool_info['name'], zip_only)

        # Phase 5: Docker push (if enabled)
        if artifacts_success and docker_push:
            self.docker_push(status.planning_data)

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

        # Development mode
        parser.add_argument('--dev-mode', action='store_true', help='Enable development mode, saves intermediate files')

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
                    dev_mode=self.args.dev_mode,
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
                    self.args.dev_mode,
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