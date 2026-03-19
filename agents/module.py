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
                    lines.append(f"            - {item.filename} ({item.extension}) — {kind}{item.hint_label}")
                lines.append("            These are examples of data the user already has. Use them to understand typical")
                lines.append("            input formats, but do NOT restrict your research to only these formats. Document")
                lines.append("            ALL formats the tool supports so the module remains broadly useful.")
                lines.append("            Where a [hint: ...] is shown, it describes the semantic role of that file")
                lines.append("            (e.g. 'tumor_sample', 'reference', 'germline_resource').")
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

            base_image_section = ""
            if tool_info.get('base_image'):
                base_image_section = (
                    f"\n            Base Docker Image (CRITICAL - use this EXACTLY as the docker_image_tag field):\n"
                    f"            {tool_info['base_image']}\n"
                    f"            Do NOT invent or normalise a genepattern/* tag — use the value above verbatim.\n"
                )

            example_data_section = ""
            example_data = tool_info.get('example_data') or []
            if example_data:
                lines = ["", "            Example Data Provided (for reference only):"]
                for item in example_data:
                    kind = "URL" if item.is_url else "local file"
                    lines.append(f"            - {item.filename} ({item.extension}) — {kind}{item.hint_label}")
                lines.append("            The user has this format available, so the module MUST accept it. However, do")
                lines.append("            NOT restrict the file_formats field to only this extension — include every")
                lines.append("            format the tool legitimately supports. The example data tells you what to")
                lines.append("            include, not what to exclude.")
                lines.append("            Where a [hint: ...] is shown, use it to assign the file to the correct")
                lines.append("            parameter (e.g. a file hinted 'tumor_sample' maps to the tumor BAM input,")
                lines.append("            'germline_resource' maps to the germline VCF parameter, etc.).")
                lines.append("")
                example_data_section = "\n".join(lines)

            prompt = f"""
            Create a comprehensive structured plan for the GenePattern module for '{tool_info['name']}'.
            
            Tool Information:
            - Name: {tool_info['name']}
            - Version: {tool_info['version']}
            - Language: {tool_info['language']}
            - Description: {tool_info.get('description', 'Not provided')}{instructions_section}{base_image_section}{example_data_section}
            
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
                    # JVM-based tools (Java, Scala, Groovy, Kotlin) are wrapped
                    # with a bash script that invokes the tool via subprocess/gatk/java.
                    # A Java source-file wrapper is never appropriate for GenePattern.
                    'java': '.sh',
                    'scala': '.sh',
                    'groovy': '.sh',
                    'kotlin': '.sh',
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

                # Serialize planning_data here for use in prompt-building below.
                # NOTE: deps_context re-serializes immediately before the agent
                # call so that any correction made by _sync_wrapper_script (which
                # runs in generate_all_artifacts before this loop is entered) is
                # always reflected in what the LLM tool receives.
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
                            lines.append(f"- {item.filename} ({item.extension}) — {kind}{item.hint_label}")
                        lines.append("Confirm that the fileFormat field on the relevant input parameter(s) includes")
                        lines.append("this extension. Do NOT replace the full format list with only this extension —")
                        lines.append("all formats the tool legitimately supports must remain present.")
                        lines.append("Where a [hint: ...] is shown, use it to match each file to the correct")
                        lines.append("parameter (e.g. 'tumor_sample' → tumor BAM parameter, 'reference' → reference")
                        lines.append("FASTA parameter, 'germline_resource' → germline VCF parameter).")
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
                                hint_suffix = f"  # {item.hint}" if item.hint else ""
                                lines.append(f"- {item.local_path}  (use as the value for the matching file input parameter){hint_suffix}")
                            lines.append("Use these exact local paths as parameter values in the test YAML.")
                            lines.append("Where a comment shows a hint (e.g. '# tumor_sample'), use it to identify")
                            lines.append("which parameter this file corresponds to.")
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
                            lines.append(f"- {item.filename} ({item.extension}) — {kind}{item.hint_label}")
                        lines.append("These files represent distinct input roles. When grouping parameters, keep")
                        lines.append("parameters that correspond to related input files in the same logical group")
                        lines.append("(e.g., place a counts matrix and metadata file parameters together in an")
                        lines.append("'Input Files' group rather than splitting them across unrelated groups).")
                        lines.append("Where a [hint: ...] is shown, use it to understand the semantic role of each")
                        lines.append("file when deciding how to group its corresponding parameter.")
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
                            hint_suffix = f"  # role: {item.hint}" if item.hint else ""
                            lines.append(f"- {item.local_path} (will be bind-mounted into the container as /data/{item.filename}){hint_suffix}")
                        lines.append("After the image is built, a runtime command will be run using this file")
                        lines.append("bind-mounted into the container — no network access or download utilities")
                        lines.append("(wget, curl) are needed inside the image for this test. Ensure all dependencies")
                        lines.append("needed to process this file type are installed. Do NOT assume the module only")
                        lines.append("handles this format — install support for all formats the tool accepts.")
                        example_data_section = "\n".join(lines)

                    wrapper_source_section = ""
                    _wrapper_script = planning_data.wrapper_script or 'wrapper.py'
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
                            'unrecognized arguments', 'TypeError:',
                            'has no matching flag',
                            'unexpected end of statement', 'failed to process',
                            # Docker COPY source missing (BuildKit and classic)
                            'file not found in build context',
                            'file does not exist',
                            'COPY failed:',
                            'failed to solve:',
                            # GATK / Java runtime errors
                            'USER ERROR', 'A USER ERROR has occurred',
                            'Exception in thread', 'java.lang.', 'java.io.',
                            'htsjdk.', 'org.broadinstitute.',
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
                            'unrecognized arguments', 'TypeError:',
                            'has no matching flag',
                            'unexpected end of statement', 'failed to process',
                            # Docker COPY source missing (BuildKit and classic)
                            'file not found in build context',
                            'file does not exist',
                            'COPY failed:',
                            'failed to solve:',
                            # GATK / Java runtime errors
                            'USER ERROR', 'A USER ERROR has occurred',
                            'Exception in thread', 'java.lang.', 'java.io.',
                            'htsjdk.', 'org.broadinstitute.',
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
                            # ── COPY source missing ──────────────────────────────────────────
                            _copy_missing_indicators = (
                                'file not found in build context',
                                'file does not exist',
                                'COPY failed:',
                            )
                            if any(ind in e for e in extracted for ind in _copy_missing_indicators):
                                # Extract the filename Docker complained about, if present.
                                # BuildKit: "stat <name>: file does not exist"
                                # Classic:  "COPY failed: … stat <name>: no such file or directory"
                                import re as _re
                                _copy_filenames = _re.findall(
                                    r'stat\s+([\w./-]+)\s*:', error_report
                                )
                                _filename_hint = ""
                                if _copy_filenames:
                                    _copy_filenames = list(dict.fromkeys(_copy_filenames))
                                    _filename_hint = (
                                        f" Docker reported the missing file(s) as: "
                                        f"{', '.join(_copy_filenames)}."
                                    )
                                structured_errors_section += (
                                    "\n\nDOCKER BUILD FAILED — COPY SOURCE FILE NOT FOUND:"
                                    f"{_filename_hint}"
                                    "\nThe Dockerfile contains a COPY instruction that references a file"
                                    " which does not exist in the build context (the module directory)."
                                    " This is a filename mismatch, NOT a package problem."
                                    " DO NOT change apt-get install lines to fix this."
                                    "\nTo fix:"
                                    "\n  1. Check the wrapper script filename that was actually generated"
                                    " (look at the 'Wrapper Script' section above for the real filename)."
                                    "\n  2. Update the COPY instruction to use that exact filename"
                                    " (e.g. 'COPY wrapper.py /module/wrapper.py')."
                                    "\n  3. Ensure the WORKDIR and COPY destination are consistent so"
                                    " 'python wrapper.py' resolves correctly inside the container."
                                )
                            if any('the following arguments are required' in e or 'usage:' in e or 'unrecognized arguments' in e.lower() for e in extracted):
                                structured_errors_section += (
                                    "\n\nThe runtime test command failed because the manifest commandLine passes "
                                    "argument names that do not match what the wrapper's argparse declares. "
                                    "The manifest's pN_name values and commandLine template are the source of "
                                    "truth for flag names — the wrapper's add_argument() calls MUST use the "
                                    "exact same dot-notation names (e.g. '--intervals.file' not '--intervals'). "
                                    "Check the usage: line in the error for the wrapper's actual flag names, "
                                    "then either (a) fix the wrapper to accept the manifest's flag names, or "
                                    "(b) fix the manifest commandLine to use the wrapper's actual flag names."
                                )
                            if any('unexpected end of statement' in e or 'failed to process' in e for e in extracted):
                                structured_errors_section += (
                                    "\n\nDOCKERFILE SYNTAX ERROR: A RUN instruction contains an unmatched quote or "
                                    "shell metacharacter. Do NOT use double-quoted strings in RUN echo or comment "
                                    "lines. Use single quotes or no quotes. Check every RUN instruction for "
                                    "unbalanced double-quotes."
                                )
                            if any("'type' object is not subscriptable" in e for e in extracted):
                                structured_errors_section += (
                                    "\n\nPYTHON VERSION INCOMPATIBILITY: The wrapper uses built-in generic type "
                                    "annotations (e.g. list[str], dict[str, int]) that require Python 3.9+. "
                                    "The container's Python version is older. The wrapper must be fixed by "
                                    "adding 'from __future__ import annotations' as the very first import, "
                                    "OR by replacing bare built-in generics with typing module equivalents "
                                    "(e.g. List[str], Dict[str, int], Optional[str] from 'from typing import ...')."
                                )
                            if any('has no matching flag in the wrapper' in e for e in extracted):
                                structured_errors_section += (
                                    "\n\nMANIFEST/WRAPPER CONSISTENCY ERROR: The manifest declares parameter "
                                    "names (pN_name=...) that do not match any add_argument() flag in the "
                                    "wrapper script. The error lines above list the exact parameter names that "
                                    "are mismatched and what flags the wrapper actually declares. "
                                    "You MUST use the wrapper's actual flag names as the manifest pN_name "
                                    "values (e.g. if the wrapper has '--input.tumor.bam', the manifest must "
                                    "have pN_name=input.tumor.bam). Do NOT invent new parameter names. "
                                    "The wrapper's declared flags are shown in the error: "
                                    "'Wrapper declares: --flag1, --flag2, ...'. "
                                    "Every pN_name in the manifest must appear in that list."
                                )

                    _base_image_constraint = ""
                    if tool_info.get('base_image'):
                        _base_image_constraint = (
                            f"\n\n🚫 IMMUTABLE BASE IMAGE CONSTRAINT 🚫\n"
                            f"The user has explicitly specified the base Docker image:\n"
                            f"  FROM {tool_info['base_image']}\n"
                            f"You MUST use this EXACT image in the FROM instruction.\n"
                            f"Do NOT substitute a different version (e.g. do not upgrade from 4.1.4.1 to 4.6.1.0).\n"
                            f"This constraint applies to ALL retry attempts — changing the base image to fix\n"
                            f"test failures is FORBIDDEN. Fix test failures by other means (e.g. add tabix,\n"
                            f"adjust entrypoint logic, fix wrapper args) while keeping the FROM line unchanged."
                        )

                    prompt = f"""Generate the {artifact_name} artifact for the GenePattern module '{tool_info['name']}'.
{wrapper_source_section}
{error_history_section if error_history_section else ""}
{structured_errors_section}
{downstream_section}
This is attempt {attempt} of {max_loops}.{instructions_section}{example_data_section}{_base_image_constraint}

Call the {create_method} tool with the following parameters:
- wrapper_source: Pass the FULL wrapper script source shown above in the "Wrapper Script" section (pass an empty string if no wrapper source was shown).
- error_report: {repr(error_report)}
- attempt: {attempt}.
The tool will parse the wrapper's import statements programmatically to determine the correct pip/R packages to install.
Make sure the generated artifact follows all guidelines, key requirements and critical rules and edit what the tool gave you as needed."""

                elif artifact_name == 'wrapper':
                    instructions_section = ""
                    if tool_info.get('instructions'):
                        instructions_section = f"\n\nIMPORTANT - Additional Instructions:\n{tool_info['instructions']}\n"

                    # Determine the wrapper language explicitly so the LLM cannot
                    # oscillate between bash and Python across retry attempts.
                    _tool_lang = tool_info.get('language', 'python').lower()
                    _jvm_langs = {'java', 'scala', 'groovy', 'kotlin'}
                    if _tool_lang in _jvm_langs:
                        _wrapper_lang = 'bash'
                        _wrapper_lang_rationale = (
                            f"The tool is implemented in {tool_info.get('language', 'Java')}. "
                            "GenePattern wrappers for JVM-based tools MUST be written as bash scripts "
                            "that invoke the tool via its command-line interface (e.g. `gatk`, `java -jar`). "
                            "Do NOT write a Java, Python, or any other language wrapper."
                        )
                    elif _tool_lang == 'r':
                        _wrapper_lang = 'R'
                        _wrapper_lang_rationale = "The tool is R-based; write an R wrapper script."
                    elif _tool_lang in ('bash', 'shell'):
                        _wrapper_lang = 'bash'
                        _wrapper_lang_rationale = "The tool is shell-based; write a bash wrapper script."
                    else:
                        _wrapper_lang = 'python'
                        _wrapper_lang_rationale = "Write a Python wrapper script using argparse and subprocess."

                    _wrapper_script_name = planning_data_dict.get('wrapper_script', filename)
                    wrapper_language_section = (
                        f"\n\n🔒 WRAPPER LANGUAGE IS FIXED — DO NOT CHANGE THIS 🔒\n"
                        f"You MUST write this wrapper as a {_wrapper_lang.upper()} script.\n"
                        f"Rationale: {_wrapper_lang_rationale}\n"
                        f"The output file will be saved as '{_wrapper_script_name}'. "
                        f"Its shebang line and syntax MUST match {_wrapper_lang.upper()}.\n"
                        f"This constraint applies to ALL retry attempts — do not switch languages to fix errors.\n"
                    )

                    # Build an explicit list of parameter names from planning data so the
                    # LLM cannot silently substitute its own names.
                    param_names_section = ""
                    planned_params = planning_data_dict.get('parameters', [])
                    if planned_params:
                        param_lines_list = []
                        for p in planned_params:
                            pname = p.get('name', '?') if isinstance(p, dict) else getattr(p, 'name', '?')
                            ptype = p.get('type', 'text') if isinstance(p, dict) else getattr(p, 'type', 'text')
                            preq  = p.get('required', False) if isinstance(p, dict) else getattr(p, 'required', False)
                            req_label = 'required' if preq else 'optional'
                            param_lines_list.append(f"  - {pname} ({ptype}, {req_label})")
                        param_names_section = (
                            "\n\n⚠️  PARAMETER NAMES ARE FIXED — DO NOT RENAME THEM ⚠️\n"
                            "The wrapper MUST use EXACTLY the following parameter names as CLI flags "
                            "(e.g. --tumor.bam, not --input.tumor.bam; --reference, not --reference.fasta). "
                            "These names come from the planning data and must match the manifest exactly:\n"
                            + "\n".join(param_lines_list)
                            + "\n\nDo NOT add a prefix like 'input.' or rename any parameter for any reason. "
                            "The create_wrapper tool will generate a scaffold using these exact names — "
                            "preserve them as-is in the final wrapper.\n"
                        )

                    error_history = build_error_history()
                    prompt = f"""Generate the wrapper artifact for the GenePattern module '{tool_info['name']}'.
{wrapper_language_section}
{param_names_section}
{error_history if error_history else ""}
{downstream_section}
This is attempt {attempt} of {max_loops}.{instructions_section}

Call the {create_method} tool with the following parameters:
- tool_info: Use the tool information provided
- planning_data: Use the planning data provided
- error_report: {repr(error_report)}
- attempt: {attempt}.
The tool generates a scaffold using the exact parameter names listed above. You may extend the
scaffold with better validation, logging, and error handling, but you MUST NOT rename any
parameter — every --flag in the final wrapper must exactly match the names listed above."""

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
                    'planning_data': planning_data.model_dump(mode='json'),
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
                if artifact_name == 'wrapper':
                    # Pass planning-data parameter names so the wrapper linter can
                    # verify that every planned parameter appears as a --flag in
                    # the generated wrapper script.
                    planned_params = planning_data_dict.get('parameters', [])
                    if planned_params:
                        param_names_for_lint = [
                            p['name'] for p in planned_params
                            if isinstance(p, dict) and p.get('name')
                        ]
                        if param_names_for_lint:
                            extra_validation_args = ['--parameters'] + param_names_for_lint
                            self.logger.print_status(
                                f"Passing {len(param_names_for_lint)} planning-data parameter names to wrapper linter"
                            )

                elif artifact_name == 'manifest':
                    # Pass the wrapper script path so the consistency linter can
                    # cross-check manifest parameter names against add_argument() flags.
                    wrapper_script = planning_data_dict.get('wrapper_script') or 'wrapper.py'
                    wrapper_path = module_path / wrapper_script
                    if wrapper_path.exists():
                        extra_validation_args = ['--wrapper', str(wrapper_path)]
                        self.logger.print_status(f"Passing wrapper to manifest linter: {wrapper_path.name}")

                elif artifact_name == 'dockerfile':
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

    def _sync_wrapper_script(
        self,
        planning_data: 'ModulePlan',
        module_path: Path,
        status: 'ModuleGenerationStatus',
        *,
        context: str = "",
    ) -> None:
        """Ensure planning_data.wrapper_script points to a file that actually exists.

        After wrapper generation the LLM may have written a file whose name
        differs from what planning_data.wrapper_script says (e.g. the plan said
        ``run_mutect2.py`` but the file on disk is ``wrapper.py``).  This method:

        1. Checks whether ``module_path / planning_data.wrapper_script`` exists.
        2. If it does not, scans *module_path* for the most likely wrapper
           candidate (a ``.py``, ``.R``, or ``.sh`` file that is not a known
           non-wrapper name) and updates ``planning_data.wrapper_script`` to
           match.
        3. Persists the updated status to disk so all downstream steps pick up
           the corrected name.
        """
        expected_name = planning_data.wrapper_script or "wrapper.py"
        expected_path = module_path / expected_name

        ctx_prefix = f"[{context}] " if context else ""

        if expected_path.exists():
            self.logger.print_status(
                f"{ctx_prefix}wrapper_script '{expected_name}' confirmed on disk ✓"
            )
            return

        # The expected file is missing — scan for a real wrapper candidate.
        self.logger.print_status(
            f"{ctx_prefix}⚠️  wrapper_script '{expected_name}' not found in {module_path} "
            f"— scanning for actual wrapper file",
            "WARNING",
        )

        # Non-wrapper filenames that share extensions with wrappers
        _NON_WRAPPER_NAMES = frozenset({
            "manage.py", "setup.py", "setup.cfg", "conftest.py",
        })

        wrapper_extensions = (".py", ".R", ".r", ".sh", ".bash", ".pl")
        candidates = []
        for p in module_path.iterdir():
            if (
                p.is_file()
                and p.suffix.lower() in wrapper_extensions
                and p.name not in _NON_WRAPPER_NAMES
            ):
                candidates.append(p)

        if not candidates:
            self.logger.print_status(
                f"{ctx_prefix}No wrapper-like file found in {module_path}; "
                f"keeping planning_data.wrapper_script='{expected_name}' unchanged",
                "WARNING",
            )
            return

        # Prefer files whose names start with "wrapper" or match common patterns;
        # fall back to the first candidate sorted by name.
        def _score(p: Path) -> int:
            n = p.name.lower()
            if n.startswith("wrapper"):
                return 0
            if n.startswith("run_"):
                return 1
            return 2

        candidates.sort(key=_score)
        chosen = candidates[0]
        old_name = planning_data.wrapper_script
        planning_data.wrapper_script = chosen.name

        # Reflect the correction in status.planning_data if it is the same object
        if status.planning_data is planning_data:
            pass  # already updated via the shared reference
        elif status.planning_data is not None:
            status.planning_data.wrapper_script = chosen.name

        self.logger.print_status(
            f"{ctx_prefix}✅ Corrected wrapper_script: '{old_name}' → '{chosen.name}'",
            "WARNING",
        )
        self.save_status(status)

    def _get_manifest_docker_image(self, module_path: Path) -> Optional[str]:
        """Read job.docker.image from the manifest file, unescaping colons."""
        manifest_path = module_path / 'manifest'
        if not manifest_path.exists():
            return None
        try:
            for line in manifest_path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line.startswith('job.docker.image='):
                    value = line[len('job.docker.image='):]
                    return value.replace('\\:', ':')
        except Exception:
            pass
        return None

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
                    tool_info, planning_data, module_path, zip_only, gp_server, gp_user, gp_password
                )
            else:
                # Before starting the dockerfile step, make absolutely sure
                # planning_data.wrapper_script points to a file that exists on
                # disk.  This guards against cases where the wrapper was skipped
                # (--skip-wrapper), resumed from a prior run, or the sync above
                # was not triggered (e.g. wrapper generation failed but the run
                # is being resumed with the file already present).
                if artifact_name == 'dockerfile':
                    # Skip Dockerfile generation when the user supplied a base
                    # image AND the manifest already points to that same image —
                    # the existing image will be used directly, so no build is needed.
                    user_base_image = tool_info.get('base_image', '').strip()
                    if user_base_image:
                        manifest_image = self._get_manifest_docker_image(module_path)
                        if manifest_image and manifest_image == user_base_image:
                            self.logger.print_status(
                                f"⏭  Skipping Dockerfile generation — manifest already uses "
                                f"base image '{user_base_image}' as job.docker.image"
                            )
                            status.artifacts_status['dockerfile'] = {
                                'generated': True, 'validated': True, 'skipped': True,
                                'attempts': 0, 'errors': [],
                            }
                            self.save_status(status)
                            idx += 1
                            continue

                    self._sync_wrapper_script(
                        planning_data, module_path, status,
                        context="pre-dockerfile assertion",
                    )
                result = self.artifact_creation_loop(
                    artifact_name, tool_info, planning_data, module_path, status,
                    max_loops,
                    downstream_error_context=downstream_ctx,
                )

            if result.success:
                # After the wrapper is written to disk, verify planning_data.wrapper_script
                # matches the actual filename.  The LLM sometimes saves a file with a
                # different name than what the plan specified (e.g. wrapper.py vs
                # run_mutect2.py), which would cause the Dockerfile COPY to fail later.
                if artifact_name == 'wrapper':
                    self._sync_wrapper_script(
                        planning_data, module_path, status,
                        context="post-wrapper sync",
                    )
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

                    # Build an enriched context message for manifest/wrapper escalations
                    # that includes wrapper flag details to guide alignment.
                    extra_context = ""
                    if target in ('manifest', 'wrapper'):
                        planning_dict_esc = planning_data.model_dump(mode='json') if planning_data else {}
                        wrapper_script_esc = planning_dict_esc.get('wrapper_script') or 'wrapper.py'
                        wrapper_path_esc = module_path / wrapper_script_esc
                        if wrapper_path_esc.exists():
                            try:
                                import ast as _ast
                                wrapper_src = wrapper_path_esc.read_text(encoding='utf-8', errors='replace')
                                # Extract declared flags for the context message
                                declared_flags = []
                                try:
                                    tree = _ast.parse(wrapper_src)
                                    for node in _ast.walk(tree):
                                        if isinstance(node, _ast.Call):
                                            func = node.func
                                            is_add_arg = (
                                                (isinstance(func, _ast.Attribute) and func.attr == 'add_argument')
                                                or (isinstance(func, _ast.Name) and func.id == 'add_argument')
                                            )
                                            if is_add_arg:
                                                for a in node.args:
                                                    if isinstance(a, _ast.Constant) and isinstance(a.value, str) and a.value.startswith('--'):
                                                        declared_flags.append(a.value)
                                except Exception:
                                    pass
                                if declared_flags:
                                    extra_context = (
                                        f"\n\nWrapper script '{wrapper_script_esc}' currently declares these "
                                        f"add_argument() flags:\n"
                                        + "\n".join(f"  {f}" for f in sorted(declared_flags))
                                        + "\n\nThe manifest pN_name values and commandLine placeholders MUST "
                                        "use these exact flag names (or the wrapper must be updated to match "
                                        "the manifest's parameter names — they must be consistent)."
                                    )
                            except Exception:
                                pass

                    pending_downstream_context[target] = (
                        f"The downstream artifact '{artifact_name}' failed validation "
                        f"with the following error:\n\n"
                        f"{result.error_text[:1500]}\n\n"
                        f"Root-cause analysis: {root_cause.reason}"
                        f"{extra_context}\n\n"
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

                # When manifest or wrapper fails, pre-warn the dockerfile agent
                # because the runtime validation command is built from the on-disk
                # manifest — if the manifest is broken the dockerfile test will also
                # fail for the wrong reason (mismatched arg names, not a Docker issue).
                if artifact_name in ('manifest', 'wrapper'):
                    failure_summary = result.error_text[:1500] if result.error_text else ""
                    existing_ctx = pending_downstream_context.get('dockerfile', '')
                    new_ctx = (
                        f"WARNING: The '{artifact_name}' artifact failed validation. "
                        f"The dockerfile runtime test command is derived from the manifest "
                        f"commandLine — if the manifest has wrong parameter names the "
                        f"runtime test will fail with 'unrecognized arguments' even if the "
                        f"Dockerfile itself is correct. "
                        f"DO NOT attempt to fix this by changing the Dockerfile. "
                        f"The wrapper's add_argument() flags and the manifest pN_name values "
                        f"must be made consistent first.\n\n"
                        f"{artifact_name} failure details:\n{failure_summary}"
                    )
                    if existing_ctx:
                        pending_downstream_context['dockerfile'] = existing_ctx + "\n\n" + new_ctx
                    else:
                        pending_downstream_context['dockerfile'] = new_ctx

                # Abort the remaining pipeline — there is no point generating further
                # artifacts when one has permanently failed, because downstream artifacts
                # depend on this one (or the module is simply incomplete).
                # Zipping, upload, and install are also skipped.
                remaining_queue = artifact_queue[idx + 1:]
                if remaining_queue:
                    skipped_names = ', '.join(remaining_queue)
                    self.logger.print_status(
                        f"⛔ Aborting pipeline: skipping remaining artifact(s): {skipped_names}",
                        "WARNING",
                    )
                break

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

    def zip_artifacts(self, module_path: Path, tool_name: str, planning_data: 'ModulePlan', zip_only: bool = False) -> str:
        """Zip all artifact files into {module_name}.zip at the top level."""
        self.logger.print_section("Zipping Artifacts")
        self.logger.print_status("Creating zip archive of artifact files")

        try:
            artifact_files = ['manifest', 'paramgroups.json', 'test.yml', 'README.md', 'Dockerfile']
            wrapper_script = planning_data.wrapper_script if planning_data else None

            files_to_zip = []
            for file in module_path.iterdir():
                if file.is_file():
                    if wrapper_script and file.name == wrapper_script:
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
        planning_data: 'ModulePlan',
        module_path: Path,
        zip_only: bool,
        gp_server: Optional[str],
        gp_user: Optional[str],
        gp_password: Optional[str],
    ) -> 'ArtifactResult':
        """Zip artifacts and optionally upload to GenePattern as a pseudo-artifact."""
        zip_path = self.zip_artifacts(module_path, tool_info['name'], planning_data, zip_only)
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
            generated = "✓" if artifact_status.get('generated') else "❌"
            validated = "✓" if artifact_status.get('validated') else "❌"
            attempts = artifact_status.get('attempts', 0)
            skipped = " (skipped)" if artifact_status.get('skipped') else ""

            print(f"  {artifact_name}:")
            print(f"    Generated: {generated} | Validated: {validated} | Attempts: {attempts}{skipped}")

            if artifact_status.get('errors'):
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
                self.save_status(status)  # persist hints immediately so they survive any mid-run crash

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

