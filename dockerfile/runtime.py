"""
Dockerfile runtime command builder.

Constructs the docker runtime test command (and associated volume mounts)
used by the dockerfile linter to validate a generated image end-to-end.

Two strategies are attempted in order:
1. Wrapper introspection — reads the generated wrapper script and parses its
   argparse flags so the command uses --flag value style arguments.
2. Placeholder substitution — falls back to substituting <param.name> tokens
   in planning_data.command_line (original behaviour).
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agents.logger import Logger
from wrapper.parser import parse_wrapper_flags


def build_runtime_command(
    planning_data,
    example_data,
    gpunit_params: Dict[str, Any],
    module_path: Optional[Path],
    logger: Logger,
) -> Tuple[Optional[str], List[str]]:
    """Build a docker runtime command and volume list for Dockerfile runtime testing.

    Args:
        planning_data:  A ``ModulePlan`` instance.
        example_data:   List of ``ExampleDataItem`` objects (may be empty).
        gpunit_params:  Parameter values read from the generated test.yml.
        module_path:    Directory containing the generated module artifacts.
        logger:         Logger instance for status messages.

    Returns:
        ``(command_str, volume_list)`` where ``volume_list`` entries are
        ``"host_path:container_path"`` strings.
        Returns ``(None, [])`` when no substitution is possible.
    """
    # Import here to avoid a top-level circular dependency
    from agents.models import ParameterType

    parameters = {p.name: p for p in planning_data.parameters}

    # Build extension → item mapping for file matching (first match wins)
    ext_to_item = {}
    positional_files = []
    for item in (example_data or []):
        if item.has_local:
            if item.extension and item.extension not in ext_to_item:
                ext_to_item[item.extension] = item
            positional_files.append(item)

    volume_list: List[str] = []

    # ------------------------------------------------------------------ #
    # Strategy 1: introspect the wrapper script for argparse flag names  #
    # ------------------------------------------------------------------ #
    wrapper_flags = None
    if module_path is not None:
        wrapper_script = planning_data.wrapper_script or 'wrapper.py'
        wrapper_path = module_path / wrapper_script
        if wrapper_path.exists():
            try:
                wrapper_flags = parse_wrapper_flags(wrapper_path)
                logger.print_status(
                    f"Introspected {len(wrapper_flags)} argument(s) from {wrapper_script}"
                )
            except Exception as e:
                logger.print_status(
                    f"Could not introspect wrapper flags, falling back to placeholder substitution: {e}",
                    "WARNING"
                )

    if wrapper_flags is not None:
        wrapper_script = planning_data.wrapper_script or 'wrapper.py'
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
                    logger.print_status(
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
                logger.print_status(
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

