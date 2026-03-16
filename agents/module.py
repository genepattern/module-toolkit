"""
ModuleAgent — main orchestrator for GenePattern module generation.

Coordinates the research → planning → artifact-generation pipeline,
delegating to specialised sub-agents for each phase and artifact type.
"""

import json
import shutil
import subprocess
import traceback
import zipfile
import requests
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agents.config import DEFAULT_OUTPUT_DIR, MAX_ARTIFACT_LOOPS, MAX_ESCALATIONS
from agents.error_classifier import (
    classify_error, should_escalate,
    get_upstream_dependencies, _sanitize_error_line, RootCause,
)
from agents.example_data import ExampleDataItem
from agents.logger import Logger
from agents.models import ArtifactModel
from agents.planner import planner_agent, ModulePlan
from agents.researcher import researcher_agent
from agents.status import ArtifactResult, ModuleGenerationStatus
from agents.validator import validate_artifact as _validate_artifact
from dockerfile.agent import dockerfile_agent
from dockerfile.runtime import build_runtime_command as _build_runtime_command
from documentation.agent import documentation_agent
from gpunit.agent import gpunit_agent
from gpunit.linter import normalize_param_type
from manifest.agent import manifest_agent
from manifest.models import ManifestModel
from paramgroups.agent import paramgroups_agent
from paramgroups.models import ParamgroupsModel
from wrapper.agent import wrapper_agent


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
                'model': ArtifactModel,
                'filename': 'wrapper.py',
                'validate_tool': 'validate_wrapper',
                'create_method': 'create_wrapper',
                'formatter': lambda m: m.code
            },
            'manifest': {
                'agent': manifest_agent,
                'model': ManifestModel,
                'filename': 'manifest',
                'validate_tool': 'validate_manifest',
                'create_method': 'create_manifest',
                'formatter': lambda m: m.to_manifest_string()
            },
            'paramgroups': {
                'agent': paramgroups_agent,
                'model': ParamgroupsModel,
                'filename': 'paramgroups.json',
                'validate_tool': 'validate_paramgroups',
                'create_method': 'create_paramgroups',
                'formatter': lambda m: m.to_json_string()
            },
            'gpunit': {
                'agent': gpunit_agent,
                'model': ArtifactModel,
                'filename': 'test.yml',
                'validate_tool': 'validate_gpunit',
                'create_method': 'create_gpunit',
                'formatter': lambda m: m.code
            },
            'documentation': {
                'agent': documentation_agent,
                'model': ArtifactModel,
                'filename': 'README.md',
                'validate_tool': 'validate_documentation',
                'create_method': 'create_documentation',
                'formatter': lambda m: m.code
            },
            'dockerfile': {
                'agent': dockerfile_agent,
                'model': ArtifactModel,
                'filename': 'Dockerfile',
                'validate_tool': 'validate_dockerfile',
                'create_method': 'create_dockerfile',
                'formatter': lambda m: m.code
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

    def save_status(self, status: ModuleGenerationStatus):
        """Save the current status to disk as status.json"""
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

    def do_research(self, tool_info: Dict[str, str], status: ModuleGenerationStatus = None) -> Tuple[bool, Dict[str, Any]]:
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

            # Track token usage if status provided
            if status:
                status.add_usage(result)
                self.save_status(status)

            self.logger.print_status("Research phase completed successfully", "SUCCESS")
            return True, {'research': result.output}

        except Exception as e:
            error_msg = f"Research phase failed: {str(e)}"
            self.logger.print_status(error_msg, "ERROR")
            self.logger.print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return False, {'error': error_msg}

    def do_planning(self, tool_info: Dict[str, str], research_data: Dict[str, Any], status: ModuleGenerationStatus = None) -> Tuple[bool, ModulePlan]:
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

            # Track token usage if status provided
            if status:
                status.add_usage(result)
                self.save_status(status)

            self.logger.print_status("Planning phase completed successfully", "SUCCESS")
            return True, result.output

        except Exception as e:
            error_msg = f"Planning phase failed: {str(e)}"
            self.logger.print_status(error_msg, "ERROR")
            self.logger.print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return False, None

    def artifact_creation_loop(self, artifact_name: str, tool_info: Dict[str, str], planning_data: ModulePlan, module_path: Path, status: ModuleGenerationStatus, max_loops: int = MAX_ARTIFACT_LOOPS, downstream_error_context: str = "") -> ArtifactResult:
        """Generate and validate a single artifact using its dedicated agent"""
        artifact_config = self.artifact_agents[artifact_name]
        agent = artifact_config['agent']
        model_class = artifact_config.get('model', ArtifactModel)
        formatter = artifact_config.get('formatter', lambda m: m.code)
        filename = artifact_config['filename']

        # Special handling for wrapper: determine extension based on tool language
        if artifact_name == 'wrapper':
            planning_dict = planning_data.model_dump(mode='json') if planning_data else {}
            wrapper_script_from_plan = planning_dict.get('wrapper_script')

            if wrapper_script_from_plan:
                filename = wrapper_script_from_plan
                self.logger.print_status(f"Using wrapper filename from planning data: {filename}")
            else:
                tool_language = tool_info.get('language', 'python').lower()
                extension_map = {
                    'python': '.py',
                    'r': '.R',
                    'bash': '.sh',
                    'shell': '.sh',
                    'perl': '.pl',
                    'java': '.java'
                }
                extension = extension_map.get(tool_language, '.py')
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
        self.save_status(status)

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
                self.save_status(status)

                planning_data_dict = planning_data.model_dump(mode='json')
                example_data: List[ExampleDataItem] = status.example_data or []
                downstream_section = build_downstream_error_section()

                if artifact_name == 'manifest':
                    instructions_section = ""
                    if tool_info.get('instructions'):
                        instructions_section = f"\n\nAdditional Instructions (IMPORTANT):\n{tool_info['instructions']}\n"

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
                    instructions_section = ""
                    if tool_info.get('instructions'):
                        instructions_section = f"\n\nIMPORTANT - Additional Instructions:\n{tool_info['instructions']}\n"

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
                    instructions_section = ""
                    if tool_info.get('instructions'):
                        instructions_section = f"\n\nIMPORTANT - Additional Instructions:\n{tool_info['instructions']}\n"

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
                    instructions_section = ""
                    if tool_info.get('instructions'):
                        instructions_section = f"\n\nIMPORTANT - Additional Instructions:\n{tool_info['instructions']}\n"

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

                    structured_errors_section = ""
                    if error_report:
                        error_indicators = [
                            'E: Unable to locate package', 'E: Package',
                            'ERROR:', 'error:', 'No such file or directory',
                            'ModuleNotFoundError', 'ImportError', 'command not found',
                            'exit code:', 'executor failed', 'FAILED',
                            'the following arguments are required:', 'usage:',
                            'unexpected end of statement', 'failed to process',
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
                    instructions_section = ""
                    if tool_info.get('instructions'):
                        instructions_section = f"\n\nIMPORTANT - Additional Instructions:\n{tool_info['instructions']}\n"

                    error_history = build_error_history()
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

                deps_context = {
                    'tool_info': tool_info,
                    'planning_data': planning_data_dict,
                    'error_report': error_report,
                    'attempt': attempt
                }

                result = agent.run_sync(
                    prompt,
                    output_type=model_class,
                    deps=deps_context
                )
                artifact_model = result.output

                # Track token usage
                status.add_usage(result)
                self.save_status(status)

                formatted_content = formatter(artifact_model)

                with open(file_path, 'w') as f:
                    f.write(formatted_content)

                # Write the report file if the artifact has one
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
                self.save_status(status)

                # Prepare extra validation arguments based on artifact type
                extra_validation_args = None
                if artifact_name == 'dockerfile':
                    docker_tag = planning_data_dict.get('docker_image_tag', '')
                    extra_validation_args = []
                    if docker_tag:
                        extra_validation_args.extend(['-t', docker_tag])
                        self.logger.print_status(f"Using docker tag for build: {docker_tag}")

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
                    extra_validation_args = []
                    module_name = planning_data_dict.get('module_name', '')
                    if module_name:
                        extra_validation_args.extend(['--module', module_name])
                        self.logger.print_status(f"Using module name for gpunit validation: {module_name}")

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

                            param_types = [normalize_param_type(p.get('type', 'text')) for p in required_params]
                            extra_validation_args.append('--types')
                            extra_validation_args.extend(param_types)

                    if not extra_validation_args:
                        extra_validation_args = None

                validation_result = self.validate_artifact(str(file_path), validate_tool, extra_validation_args)

                if validation_result['success']:
                    status.artifacts_status[artifact_name]['validated'] = True
                    self.logger.print_status(f"✅ Successfully generated and validated {artifact_name}")
                    self.save_status(status)
                    return ArtifactResult(success=True, artifact_name=artifact_name)
                else:
                    error_report = f"Validation failed: {validation_result.get('error', 'Unknown validation error')}"
                    self.logger.print_status(f"❌ {error_report}")
                    status.artifacts_status[artifact_name]['errors'].append(error_report)
                    self.save_status(status)

                    if attempt == max_loops:
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

                tb_str = traceback.format_exc()
                self.logger.print_status(f"Full traceback:\n{tb_str}", "ERROR")

                full_error = f"{error_report}\n\nTraceback:\n{tb_str}"
                status.artifacts_status[artifact_name]['errors'].append(full_error)
                self.save_status(status)

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

    def upload_to_genepattern(self, zip_path: Path, gp_server: str, gp_user: str, gp_password: str) -> bool:
        """
        Upload a module zip file to a GenePattern server.

        Args:
            zip_path: Path to the zip file to upload
            gp_server: GenePattern server URL (e.g., http://host:port/gp)
            gp_user: GenePattern username
            gp_password: GenePattern password

        Returns:
            True if upload was successful, False otherwise
        """
        self.logger.print_section("Uploading to GenePattern")
        endpoint = f"{gp_server.rstrip('/')}/rest/v1/tasks/installModule"
        self.logger.print_status(f"Uploading {zip_path.name} to {endpoint}")

        try:
            with open(zip_path, 'rb') as f:
                response = requests.post(
                    endpoint,
                    auth=(gp_user, gp_password),
                    files={'file': (zip_path.name, f, 'application/zip')},
                    data={'privacy': '1'},
                )

            try:
                result = response.json()
            except Exception(e):
                log.error(f"Failed to parse JSON response from GenePattern installing module: {e}")
                result = {}

            status = result.get('status', '')
            message = result.get('message', response.text[:200])

            if status == 'success':
                self.logger.print_status(f"✅ {message}", "SUCCESS")
                return True
            elif status == 'failed':
                self.logger.print_status(f"Upload failed: {message}", "ERROR")
                return False
            elif response.status_code in (200, 201):
                # No JSON body but HTTP success
                self.logger.print_status(f"✅ Module uploaded successfully (HTTP {response.status_code})", "SUCCESS")
                return True
            else:
                self.logger.print_status(
                    f"Upload failed: HTTP {response.status_code} — {message}", "ERROR"
                )
                return False

        except Exception as e:
            self.logger.print_status(f"Upload failed: {str(e)}", "ERROR")
            self.logger.print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return False

    def build_runtime_command(
        self,
        planning_data: ModulePlan,
        example_data: List[ExampleDataItem],
        gpunit_params: Dict[str, Any],
        module_path: Path = None,
    ) -> Tuple[Optional[str], List[str]]:
        """Build a docker runtime command and volume list for Dockerfile runtime testing.
        Delegates to dockerfile.runtime.build_runtime_command.
        """
        return _build_runtime_command(planning_data, example_data, gpunit_params, module_path, self.logger)

    def validate_artifact(self, file_path: str, validate_tool: str, extra_args: List[str] = None) -> Dict[str, Any]:
        """Validate an artifact using its linter. Delegates to agents.validator."""
        return _validate_artifact(file_path, validate_tool, extra_args, self.logger)

    def generate_all_artifacts(self, tool_info: Dict[str, str], planning_data: ModulePlan, module_path: Path, status: ModuleGenerationStatus, skip_artifacts: List[str] = None, max_loops: int = MAX_ARTIFACT_LOOPS, max_escalations: int = MAX_ESCALATIONS, no_zip: bool = False, zip_only: bool = False, gp_server: Optional[str] = None, gp_user: Optional[str] = None, gp_password: Optional[str] = None) -> bool:
        """Run artifact generation phase with cross-artifact error escalation."""
        self.logger.print_section("Artifact Generation Phase")
        self.logger.print_status("Starting artifact generation")

        if skip_artifacts is None:
            skip_artifacts = []
        all_artifacts_successful = True

        artifact_queue: List[str] = [
            name for name in self.artifact_agents
            if name not in skip_artifacts
        ]
        if not no_zip and 'install' not in skip_artifacts:
            artifact_queue.append('install')
        escalation_pair_counts: Dict[tuple, int] = {}
        pending_downstream_context: Dict[str, str] = {}

        idx = 0
        while idx < len(artifact_queue):
            artifact_name = artifact_queue[idx]

            if artifact_name in skip_artifacts:
                self.logger.print_status(f"Skipping {artifact_name} (--skip-{artifact_name} specified)")
                idx += 1
                continue

            existing_status = status.artifacts_status.get(artifact_name, {})
            if existing_status.get('validated', False):
                self.logger.print_status(f"✓ {artifact_name} already validated, skipping")
                idx += 1
                continue

            self.logger.print_status(f"Generating {artifact_name}...")

            downstream_ctx = pending_downstream_context.pop(artifact_name, "")

            if artifact_name == 'install':
                result = self._run_install_artifact(
                    tool_info, module_path, zip_only, gp_server, gp_user, gp_password
                )
            else:
                result = self.artifact_creation_loop(
                    artifact_name, tool_info, planning_data, module_path, status,
                    max_loops,
                    downstream_error_context=downstream_ctx,
                )

            if result.success:
                idx += 1
                continue

            root_cause = result.root_cause
            escalated = False

            if root_cause and should_escalate(root_cause):
                target = root_cause.target_artifact
                pair_key = (artifact_name, target)
                current_count = escalation_pair_counts.get(pair_key, 0)

                can_escalate = (
                    current_count < max_escalations
                    and target not in skip_artifacts
                    and target in self.artifact_agents
                    and target in get_upstream_dependencies(artifact_name)
                )

                if can_escalate:
                    escalation_pair_counts[pair_key] = current_count + 1

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
                    self.save_status(status)

                    self.logger.print_section("Cross-Artifact Escalation")
                    self.logger.print_status(
                        f"🔀 Escalating: {artifact_name} failure → regenerating {target}",
                        "WARNING",
                    )
                    self.logger.print_status(f"   Reason: {root_cause.reason}", "WARNING")
                    self.logger.print_status(
                        f"   Escalation {current_count + 1}/{max_escalations} "
                        f"for {artifact_name}→{target}",
                    )

                    if target in status.artifacts_status:
                        status.artifacts_status[target]['validated'] = False
                        status.artifacts_status[target]['generated'] = False
                    self.save_status(status)

                    pending_downstream_context[target] = (
                        f"The downstream artifact '{artifact_name}' failed validation "
                        f"with the following error:\n\n"
                        f"{result.error_text[:1000]}\n\n"
                        f"Root-cause analysis: {root_cause.reason}\n\n"
                        f"You must fix the issue in THIS artifact ({target}) so that "
                        f"the downstream '{artifact_name}' step can succeed."
                    )

                    remaining = artifact_queue[idx:]
                    if target in remaining:
                        remaining.remove(target)
                    artifact_queue = (
                        artifact_queue[:idx]
                        + [target, artifact_name]
                        + [a for a in remaining if a != artifact_name]
                    )

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
        """Push the built Docker image to Docker Hub."""
        self.logger.print_section("Docker Push")

        planning_dict = planning_data.model_dump(mode='json') if planning_data else {}
        tag = planning_dict.get('docker_image_tag', '')

        if not tag:
            self.logger.print_status("No docker_image_tag found in planning data, cannot push", "ERROR")
            return False

        self.logger.print_status(f"Pushing Docker image: {tag}")

        cmd = ["docker", "push", tag]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
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

    def zip_artifacts(self, module_path: Path, tool_name: str, zip_only: bool = False) -> str:
        """Zip all artifact files into {module_name}.zip at the top level."""
        self.logger.print_section("Zipping Artifacts")
        self.logger.print_status("Creating zip archive of artifact files")

        try:
            artifact_extensions = ['.py', '.R', '.sh', '.pl', '.java']
            artifact_files = ['manifest', 'paramgroups.json', 'test.yml', 'README.md', 'Dockerfile']

            files_to_zip = []
            for file in module_path.iterdir():
                if file.is_file():
                    if any(file.name.endswith(ext) for ext in artifact_extensions):
                        files_to_zip.append(file)
                    elif file.name in artifact_files:
                        files_to_zip.append(file)

            if not files_to_zip:
                self.logger.print_status("No artifact files found to zip", "WARNING")
                return False

            zip_filename = f"{tool_name.lower().replace(' ', '_').replace('-', '_')}.zip"
            zip_path = module_path / zip_filename

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in files_to_zip:
                    zipf.write(file, arcname=file.name)
                    self.logger.print_status(f"  Added {file.name} to zip")

            zip_size = zip_path.stat().st_size
            self.logger.print_status(f"✅ Created {zip_filename} ({zip_size:,} bytes)", "SUCCESS")

            if zip_only:
                self.logger.print_status("Cleaning up artifact files (--zip-only specified)")
                for file in files_to_zip:
                    try:
                        file.unlink()
                        self.logger.print_status(f"  Deleted {file.name}")
                    except Exception as e:
                        self.logger.print_status(f"  Failed to delete {file.name}: {str(e)}", "WARNING")

            return zip_path

        except Exception as e:
            self.logger.print_status(f"Failed to create zip archive: {str(e)}", "ERROR")
            self.logger.print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return None

    def _run_install_artifact(
        self,
        tool_info: Dict[str, str],
        module_path: Path,
        zip_only: bool,
        gp_server: Optional[str],
        gp_user: Optional[str],
        gp_password: Optional[str],
    ) -> 'ArtifactResult':
        """Zip artifacts and optionally upload to GenePattern as a pseudo-artifact."""
        zip_path = self.zip_artifacts(module_path, tool_info['name'], zip_only)
        if zip_path is None:
            return ArtifactResult(
                success=False,
                artifact_name='install',
                error_text="Failed to create zip archive.",
                root_cause=RootCause(
                    target_artifact='manifest',
                    reason="Zip creation failed; manifest or paramgroups may be invalid.",
                    original_artifact='install',
                ),
            )

        if not (gp_server and gp_user):
            # No upload configured — zip success is sufficient
            return ArtifactResult(success=True, artifact_name='install')

        upload_ok = self.upload_to_genepattern(zip_path, gp_server, gp_user, gp_password)
        if upload_ok:
            return ArtifactResult(success=True, artifact_name='install')

        return ArtifactResult(
            success=False,
            artifact_name='install',
            error_text=f"GenePattern upload failed for {zip_path.name}.",
            root_cause=RootCause(
                target_artifact='manifest',
                reason="GenePattern module install failed. The manifest or paramgroups may be invalid.",
                original_artifact='install',
            ),
        )

    def print_final_report(self, status: ModuleGenerationStatus):
        """Print comprehensive final report"""
        self.logger.print_section("Final Report")

        print(f"Tool Name: {status.tool_name}")
        print(f"Module Directory: {status.module_directory}")
        print(f"Research Complete: {'✓' if status.research_complete else '❌'}")
        print(f"Planning Complete: {'✓' if status.planning_complete else '❌'}")

        print(f"\nArtifact Status:")
        for artifact_name, artifact_status in status.artifacts_status.items():
            generated = "✓" if artifact_status['generated'] else "❌"
            validated = "✓" if artifact_status['validated'] else "❌"
            attempts = artifact_status['attempts']

            print(f"  {artifact_name}:")
            print(f"    Generated: {generated} | Validated: {validated} | Attempts: {attempts}")

            if artifact_status['errors']:
                print(f"    Errors: {len(artifact_status['errors'])}")
                for error in artifact_status['errors'][:2]:
                    print(f"      - {error}")

        if status.parameters:
            print(f"\nParameters Identified: {len(status.parameters)}")
            for i, param in enumerate(status.parameters[:5]):
                name = param.name
                param_type = param.type.value if hasattr(param.type, 'value') else str(param.type)
                required = 'Required' if param.required else 'Optional'
                print(f"  - {name}: {param_type} ({required})")

            if len(status.parameters) > 5:
                print(f"  ... and {len(status.parameters) - 5} more parameters")

        module_path = Path(status.module_directory)
        if module_path.exists():
            print(f"\nGenerated Files:")
            for file in module_path.iterdir():
                if file.is_file():
                    size = file.stat().st_size
                    print(f"  - {file.name} ({size:,} bytes)")

        if status.input_tokens > 0 or status.output_tokens > 0:
            total_tokens = status.input_tokens + status.output_tokens
            estimated_cost = status.get_estimated_cost()
            print(f"\nToken Usage:")
            print(f"  Input tokens:  {status.input_tokens:,}")
            print(f"  Output tokens: {status.output_tokens:,}")
            print(f"  Total tokens:  {total_tokens:,}")
            print(f"  Estimated cost: ${estimated_cost:.4f}")

        if status.escalation_log:
            print(f"\nCross-Artifact Escalations: {len(status.escalation_log)}")
            for evt in status.escalation_log:
                print(f"  🔀 {evt['from_artifact']} → {evt['to_artifact']}: {evt['reason'][:120]}")

        all_artifacts_valid = all(
            artifact['generated'] and artifact['validated']
            for artifact in status.artifacts_status.values()
        )
        overall_success = (
            status.research_complete
            and status.planning_complete
            and all_artifacts_valid
        )

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

    def run(self, tool_info: Dict[str, str] = None, skip_artifacts: List[str] = None, resume_status: ModuleGenerationStatus = None, max_loops: int = MAX_ARTIFACT_LOOPS, no_zip: bool = False, zip_only: bool = False, docker_push: bool = False, example_data: List[ExampleDataItem] = None, max_escalations: int = MAX_ESCALATIONS, gp_server: str = None, gp_user: str = None, gp_password: str = None) -> int:
        """Run the complete module generation process"""

        if resume_status:
            self.logger.print_status(f"Resuming module generation for: {resume_status.tool_name}")
            status = resume_status
            module_path = Path(status.module_directory)

            if example_data is not None:
                status.example_data = example_data
                self.logger.print_status(f"Overriding example_data with {len(example_data)} item(s) from --data")

            if not tool_info:
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
                tool_info['example_data'] = status.example_data

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
                self.save_status(status)

        else:
            self.logger.print_status(f"Generating module for: {tool_info['name']}")
            module_path = self.create_module_directory(
                tool_info['name'],
                module_dir=tool_info.get('module_dir', ''),
            )
            status = ModuleGenerationStatus(
                tool_name=tool_info['name'],
                module_directory=str(module_path),
                example_data=example_data or [],
            )
            tool_info['example_data'] = status.example_data

            if status.example_data:
                self.download_url_data(status.example_data, module_path)

            self.save_status(status)

        # Phase 1: Research
        if status.research_complete:
            self.logger.print_section("Research Phase")
            self.logger.print_status("✓ Research already complete, using existing data", "SUCCESS")
        else:
            research_success, research_data = self.do_research(tool_info, status)
            if research_success:
                status.research_data = research_data
            else:
                status.error_messages.append(research_data.get('error', 'Research failed'))
            if status.research_data:
                with open(module_path / "research.md", "w") as f:
                    f.write(status.research_data.get('research', ''))
            self.save_status(status)

        if not status.research_complete:
            self.print_final_report(status)
            return 1

        # Phase 2: Planning
        if status.planning_complete:
            self.logger.print_section("Planning Phase")
            self.logger.print_status("✓ Planning already complete, using existing plan", "SUCCESS")
        else:
            planning_success, planning_data = self.do_planning(tool_info, status.research_data, status)
            if planning_success:
                status.planning_data = planning_data
            else:
                status.error_messages.append("Planning failed")
            if status.planning_data:
                with open(module_path / "plan.md", "w") as f:
                    f.write(status.planning_data.plan)
            self.save_status(status)

        if not status.planning_complete:
            self.print_final_report(status)
            return 1

        # Phase 3: Artifact Generation
        if skip_artifacts is None:
            skip_artifacts = []

        for artifact_name, artifact_status in status.artifacts_status.items():
            if artifact_status.get('validated', False):
                if artifact_name not in skip_artifacts:
                    skip_artifacts.append(artifact_name)
                    self.logger.print_status(f"✓ {artifact_name} already completed, skipping")

        artifacts_success = self.generate_all_artifacts(
            tool_info, status.planning_data, module_path, status,
            skip_artifacts, max_loops, max_escalations,
            no_zip=no_zip, zip_only=zip_only,
            gp_server=gp_server, gp_user=gp_user, gp_password=gp_password,
        )

        # Clean up downloaded data/ directory after successful dockerfile step
        dockerfile_validated = status.artifacts_status.get('dockerfile', {}).get('validated', False)
        if dockerfile_validated:
            self.cleanup_data_dir(module_path)

        # Phase 5: Docker push (if enabled)
        if artifacts_success and docker_push:
            self.docker_push(status.planning_data)

        self.print_final_report(status)

        return 0 if (status.research_complete and status.planning_complete and artifacts_success) else 1

