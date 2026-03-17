"""
Dockerfile runtime command builder.

Constructs the docker runtime test command (and associated volume mounts)
used by the dockerfile linter to validate a generated image end-to-end.

Three strategies are attempted in order:
1. Manifest-based — parses the generated manifest file for the authoritative
   commandLine template plus per-parameter metadata (type, defaults, choices,
   file formats, required/optional).
2. Wrapper introspection — reads the generated wrapper script and parses its
   argparse flags so the command uses --flag value style arguments.
3. Placeholder substitution — falls back to substituting <param.name> tokens
   in planning_data.command_line (original behaviour).
"""
import re
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agents.logger import Logger
from wrapper.parser import parse_wrapper_flags


def _shell_quote(value: str) -> str:
    """Shell-quote a value if it contains spaces or shell metacharacters.

    Plain single-token values are returned unchanged so the resulting command
    string stays readable.  Values with spaces (e.g. ``best match``) are
    returned as ``'best match'`` so that ``sh -lc`` treats them as one token.
    """
    if " " in value or any(ch in value for ch in ("'", '"', ";", "&", "|", "(", ")", "$", "`", "\\", "\n")):
        return shlex.quote(value)
    return value


# ---------------------------------------------------------------------------
# Manifest parser (lightweight — only needs commandLine + pN_* keys)
# ---------------------------------------------------------------------------

def _parse_manifest(manifest_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a GenePattern manifest file into a dict.

    Returns a dict with keys:
        ``commandLine``  — the raw command template string
        ``parameters``   — dict mapping param name -> param metadata dict

    Each parameter metadata dict has:
        name, TYPE, type_class, optional, default_value, fileFormat,
        prefix_when_specified, numValues, value (choice list)

    Returns ``None`` if the file cannot be read or has no ``commandLine``.
    """
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    kv: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        eq = line.find("=")
        if eq < 1:
            continue
        kv[line[:eq]] = line[eq + 1:]

    command_line = kv.get("commandLine")
    if not command_line:
        return None

    # Collect per-parameter keys (p1_name, p1_TYPE, p2_name, ...)
    param_indices: Dict[int, Dict[str, str]] = {}
    pkey_re = re.compile(r"^p(\d+)_(.+)$")
    for key, val in kv.items():
        m = pkey_re.match(key)
        if m:
            idx = int(m.group(1))
            field = m.group(2)
            param_indices.setdefault(idx, {})[field] = val

    # Build a name-indexed parameter dict
    parameters: Dict[str, Dict[str, Any]] = {}
    for idx in sorted(param_indices):
        pdata = param_indices[idx]
        name = pdata.get("name")
        if not name:
            continue
        parameters[name] = {
            "name": name,
            "TYPE": pdata.get("TYPE", "TEXT"),
            "type_class": pdata.get("type", ""),
            "optional": pdata.get("optional", ""),
            "default_value": pdata.get("default_value"),
            "fileFormat": pdata.get("fileFormat", ""),
            "prefix_when_specified": pdata.get("prefix_when_specified", ""),
            "numValues": pdata.get("numValues", ""),
            "value": pdata.get("value", ""),  # choice list
        }

    return {"commandLine": command_line, "parameters": parameters}


def _is_file_param(p: Dict[str, Any]) -> bool:
    """Return True if the manifest parameter represents a file input."""
    return (
        p.get("TYPE", "").upper() == "FILE"
        or "java.io.File" in (p.get("type_class") or "")
    )


def _is_required(p: Dict[str, Any]) -> bool:
    """Return True if the manifest parameter is required."""
    return p.get("optional", "") != "on"


def _first_choice_value(p: Dict[str, Any]) -> Optional[str]:
    r"""Extract the first choice value from a manifest choice list.

    Choice lists look like:  ``val1\=label1;val2\=label2;...``
    or plain:                ``val1;val2;...``
    """
    raw = p.get("value", "")
    if not raw:
        return None
    first_entry = raw.split(";")[0]
    # Each entry may be value\=label — we want the value part.
    if "\\=" in first_entry:
        return first_entry.split("\\=")[0]
    if "=" in first_entry:
        return first_entry.split("=")[0]
    return first_entry


def _substitute_placeholder(
    result_cmd: str,
    placeholder: str,
    param: Dict[str, Any],
    value: Optional[str],
) -> str:
    """Replace ``<placeholder>`` in *result_cmd* with the parameter's value.

    If the parameter has a ``prefix_when_specified`` entry in the manifest,
    the prefix is prepended to the value (e.g. ``--mode 'best match'``).

    When *value* is ``None`` the placeholder is stripped from the command.

    Raises
    ------
    ValueError
        If the ``prefix_when_specified`` text already appears immediately
        before ``<placeholder>`` in the command template.  This indicates
        a bug in the manifest: the ``commandLine`` should use bare
        ``<placeholder>`` tokens and let ``prefix_when_specified`` supply
        the flag — embedding the flag in *both* places causes duplication.
    """
    prefix = (param.get("prefix_when_specified") or "").rstrip()
    token = f"<{placeholder}>"

    if prefix:
        # Detect manifest bug: prefix_when_specified is duplicated in the
        # commandLine template (e.g. "--mode <mode>" when prefix_when_specified
        # is already "--mode ").
        dup_pattern = re.compile(
            re.escape(prefix) + r"\s+" + re.escape(token)
        )
        if dup_pattern.search(result_cmd):
            raise ValueError(
                f"Manifest commandLine bug: parameter '{placeholder}' has "
                f"prefix_when_specified='{prefix}' but the commandLine "
                f"template already contains '{prefix} <{placeholder}>'. "
                f"The commandLine should use the bare placeholder "
                f"<{placeholder}> without the prefix — the prefix is "
                f"supplied automatically by prefix_when_specified."
            )

        if value is not None:
            replacement = f"{prefix} {value}"
        else:
            replacement = ""

        result_cmd = result_cmd.replace(token, replacement, 1)
    else:
        # No prefix_when_specified — plain substitution.
        result_cmd = result_cmd.replace(
            token, value if value is not None else "", 1
        )

    return result_cmd


def _default_for_param(p: Dict[str, Any], gpunit_params: Dict[str, Any], *, allow_fallback: bool = True) -> Optional[str]:
    """Return a sensible value for a non-file parameter.

    Priority: gpunit params -> manifest default_value -> first choice -> type-based fallback.
    When *allow_fallback* is False, the type-based fallback is skipped (returns None).
    """
    name = p["name"]
    val = gpunit_params.get(name)
    if val is not None:
        return str(val)
    val = p.get("default_value")
    if val is not None and val != "":
        return val
    choice = _first_choice_value(p)
    if choice is not None:
        return choice
    # Type-based fallback (only when allow_fallback is True)
    if not allow_fallback:
        return None
    ptype = (p.get("TYPE") or "").upper()
    if ptype == "INTEGER" or "Integer" in (p.get("type_class") or ""):
        return "1"
    if ptype == "FLOAT" or "Float" in (p.get("type_class") or ""):
        return "1.0"
    return "output"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

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
    # ------------------------------------------------------------------ #
    # Strategy 1 (preferred): use the generated manifest                 #
    # ------------------------------------------------------------------ #
    if module_path is not None:
        manifest_path = module_path / "manifest"
        if manifest_path.exists():
            result = _build_from_manifest(
                manifest_path, example_data, gpunit_params, logger,
                module_path=module_path,
                wrapper_script=planning_data.wrapper_script if planning_data else None,
            )
            if result is not None:
                return result
            # If manifest strategy returned None, fall through.

    # ------------------------------------------------------------------ #
    # Strategy 2: introspect the wrapper script for argparse flag names  #
    # ------------------------------------------------------------------ #
    result = _build_from_wrapper_introspection(
        planning_data, example_data, gpunit_params, module_path, logger,
    )
    if result is not None:
        return result

    # ------------------------------------------------------------------ #
    # Strategy 3: placeholder substitution in command_line (fallback)    #
    # ------------------------------------------------------------------ #
    return _build_from_planning_data(
        planning_data, example_data, gpunit_params, logger,
    )


# ---------------------------------------------------------------------------
# Strategy 1: manifest-based
# ---------------------------------------------------------------------------

def _build_from_manifest(
    manifest_path: Path,
    example_data,
    gpunit_params: Dict[str, Any],
    logger: Logger,
    module_path: Optional[Path] = None,
    wrapper_script: Optional[str] = None,
) -> Optional[Tuple[str, List[str]]]:
    """Build the runtime command from the generated manifest file.

    Returns ``(command, volumes)`` on success, ``None`` on failure so that
    callers can fall through to the next strategy.
    """
    parsed = _parse_manifest(manifest_path)
    if parsed is None:
        logger.print_status(
            "Manifest could not be parsed for runtime command — trying next strategy",
            "WARNING",
        )
        return None

    command_line: str = parsed["commandLine"]
    manifest_params: Dict[str, Dict[str, Any]] = parsed["parameters"]
    logger.print_status(f"Parsed manifest commandLine: {command_line[:120]}...")
    logger.print_status(f"Parsed {len(manifest_params)} parameters from manifest: {list(manifest_params.keys())}")

    # Build extension -> item mapping for file matching (first match wins)
    ext_to_item: Dict[str, Any] = {}
    positional_files: list = []
    for item in (example_data or []):
        if item.has_local:
            if item.extension and item.extension not in ext_to_item:
                ext_to_item[item.extension] = item
            positional_files.append(item)
    logger.print_status(f"Example data: {len(positional_files)} file(s) with local paths, ext_to_item keys: {list(ext_to_item.keys())}")

    volume_list: List[str] = []
    positional_file_idx = 0

    # Replace <libdir> — inside the container the module files live in the
    # working directory, so <libdir> is simply empty.
    result_cmd = command_line.replace("<libdir>", "")

    # Find all <placeholder> tokens in the command line
    placeholders = re.findall(r"<([^>]+)>", result_cmd)
    if not placeholders:
        # No placeholders to substitute — command is ready as-is
        logger.print_status(
            f"Manifest commandLine has no placeholders: {result_cmd}"
        )
        return result_cmd, volume_list

    for placeholder in placeholders:
        param = manifest_params.get(placeholder)
        if param is None:
            # Unknown placeholder — remove it
            logger.print_status(
                f"Manifest placeholder <{placeholder}> has no matching parameter — removing",
                "WARNING",
            )
            result_cmd = _substitute_placeholder(result_cmd, placeholder, {}, None)
            continue

        is_file = _is_file_param(param)
        is_req = _is_required(param)
        logger.print_status(f"Placeholder <{placeholder}>: TYPE={param.get('TYPE')}, is_file={is_file}, required={is_req}, default_value={param.get('default_value')!r}")

        if is_file:
            # Match example data to this file parameter by extension
            item = None
            file_formats = param.get("fileFormat", "")
            has_format_restriction = bool(file_formats.strip())
            if has_format_restriction:
                for fmt in file_formats.split(";"):
                    fmt = fmt.strip()
                    if not fmt:
                        continue
                    ext = fmt if fmt.startswith(".") else f".{fmt}"
                    if ext.lower() in ext_to_item:
                        item = ext_to_item[ext.lower()]
                        break
            # Only fall back to positional matching for required params,
            # or optional params with NO format restriction.  Optional params
            # with a specific format (e.g. .pkl) that didn't match any data
            # should be stripped rather than getting an unrelated file.
            if item is None and positional_file_idx < len(positional_files):
                if is_req or not has_format_restriction:
                    item = positional_files[positional_file_idx]
                    positional_file_idx += 1

            if item is None or not item.has_local:
                if _is_required(param):
                    logger.print_status(
                        f"No local example data for required FILE parameter "
                        f"'{placeholder}' — skipping runtime command",
                        "WARNING",
                    )
                    return None
                else:
                    # Optional file param with no data — remove placeholder
                    # and any prefix_when_specified that accompanies it.
                    result_cmd = _substitute_placeholder(result_cmd, placeholder, param, None)
                    continue

            container_path = f"/data/{item.filename}"
            volume_entry = f"{item.local_path}:{container_path}"
            if volume_entry not in volume_list:
                volume_list.append(volume_entry)
            logger.print_status(f"FILE param '{placeholder}' -> {container_path} (volume: {volume_entry})")
            result_cmd = _substitute_placeholder(result_cmd, placeholder, param, _shell_quote(container_path))

        else:
            # Non-file parameter
            if not is_req:
                # Optional: use value if available, otherwise strip
                val = _default_for_param(param, gpunit_params, allow_fallback=False)
                if val is not None:
                    logger.print_status(f"Optional param '{placeholder}' -> {val!r}")
                    result_cmd = _substitute_placeholder(result_cmd, placeholder, param, _shell_quote(val))
                else:
                    logger.print_status(f"Optional param '{placeholder}' -> (stripped, no value)")
                    result_cmd = _substitute_placeholder(result_cmd, placeholder, param, None)
            else:
                # Required non-file: must have a value
                val = _default_for_param(param, gpunit_params)
                if val is None:
                    logger.print_status(
                        f"No value for required parameter '{placeholder}' — skipping runtime command",
                        "WARNING",
                    )
                    return None
                logger.print_status(f"Required param '{placeholder}' -> {val!r}")
                result_cmd = _substitute_placeholder(result_cmd, placeholder, param, _shell_quote(val))

    # Clean up any double spaces left by removed optional params
    result_cmd = re.sub(r"  +", " ", result_cmd).strip()

    # ------------------------------------------------------------------
    # Cross-check flag names against the wrapper's actual argparse flags.
    # The manifest commandLine may use dashes (e.g. --input-file) while
    # the wrapper uses dots (e.g. --input.file) or vice versa.  If we
    # can introspect the wrapper, fix any mismatches so the runtime
    # command uses the exact flag names the wrapper expects.
    # ------------------------------------------------------------------
    if module_path is not None:
        ws = wrapper_script or "wrapper.py"
        wrapper_path = module_path / ws
        if wrapper_path.exists():
            try:
                wrapper_flags = parse_wrapper_flags(wrapper_path)
                # wrapper_flags maps canonical names to the actual flag string
                # e.g. {"input.file": "--input.file", "input_file": "--input.file", ...}
                # Collect all actual long-flags the wrapper accepts
                actual_flags = {v for v in wrapper_flags.values() if v and v.startswith("--")}

                # Find all --flag tokens in result_cmd and check them
                for token in re.findall(r"--[\w._-]+", result_cmd):
                    if token in actual_flags:
                        continue  # already correct
                    # Try to find the correct flag by canonical matching
                    canon = token.lstrip("-").replace("-", ".").replace("_", ".")
                    correct_flag = wrapper_flags.get(canon)
                    if correct_flag and correct_flag != token:
                        logger.print_status(
                            f"Flag correction: {token} → {correct_flag} "
                            f"(matched via canonical name '{canon}')"
                        )
                        result_cmd = result_cmd.replace(token, correct_flag)
            except Exception as e:
                logger.print_status(
                    f"Could not cross-check flags against wrapper: {e}",
                    "WARNING",
                )

    logger.print_status(f"Built runtime command from manifest: {result_cmd}")
    return result_cmd, volume_list


# ---------------------------------------------------------------------------
# Strategy 2: wrapper introspection
# ---------------------------------------------------------------------------

def _build_from_wrapper_introspection(
    planning_data,
    example_data,
    gpunit_params: Dict[str, Any],
    module_path: Optional[Path],
    logger: Logger,
) -> Optional[Tuple[str, List[str]]]:
    """Build the runtime command by introspecting the wrapper's argparse flags."""
    from agents.models import ParameterType

    if module_path is None:
        return None

    wrapper_script = planning_data.wrapper_script or "wrapper.py"
    wrapper_path = module_path / wrapper_script
    if not wrapper_path.exists():
        return None

    try:
        wrapper_flags = parse_wrapper_flags(wrapper_path)
        logger.print_status(
            f"Introspected {len(wrapper_flags)} argument(s) from {wrapper_script}"
        )
    except Exception as e:
        logger.print_status(
            f"Could not introspect wrapper flags: {e}",
            "WARNING",
        )
        return None

    ext_to_item: Dict[str, Any] = {}
    positional_files: list = []
    for item in (example_data or []):
        if item.has_local:
            if item.extension and item.extension not in ext_to_item:
                ext_to_item[item.extension] = item
            positional_files.append(item)

    volume_list: List[str] = []

    if wrapper_script.endswith(".py"):
        prefix = f"python {wrapper_script}"
    elif wrapper_script.endswith((".R", ".r")):
        prefix = f"Rscript {wrapper_script}"
    elif wrapper_script.endswith(".sh"):
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
                    ext = fmt if fmt.startswith(".") else f".{fmt}"
                    if ext.lower() in ext_to_item:
                        item = ext_to_item[ext.lower()]
                        break
            if item is None and positional_file_idx < len(positional_files):
                item = positional_files[positional_file_idx]
                positional_file_idx += 1

            if item is None or not item.has_local:
                logger.print_status(
                    f"No local example data for FILE parameter '{param.name}' — skipping runtime command",
                    "WARNING",
                )
                return None

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


# ---------------------------------------------------------------------------
# Strategy 3: placeholder substitution in planning_data.command_line
# ---------------------------------------------------------------------------

def _build_from_planning_data(
    planning_data,
    example_data,
    gpunit_params: Dict[str, Any],
    logger: Logger,
) -> Tuple[Optional[str], List[str]]:
    """Fall back to substituting <param.name> placeholders in the plan's command_line."""
    from agents.models import ParameterType

    command_line = planning_data.command_line
    placeholders = re.findall(r"<([^>]+)>", command_line)

    if not placeholders:
        return None, []

    parameters = {p.name: p for p in planning_data.parameters}
    ext_to_item: Dict[str, Any] = {}
    positional_files: list = []
    for item in (example_data or []):
        if item.has_local:
            if item.extension and item.extension not in ext_to_item:
                ext_to_item[item.extension] = item
            positional_files.append(item)

    volume_list: List[str] = []
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
                    ext = fmt if fmt.startswith(".") else f".{fmt}"
                    if ext.lower() in ext_to_item:
                        item = ext_to_item[ext.lower()]
                        break
            if item is None and positional_file_idx < len(positional_files):
                item = positional_files[positional_file_idx]
                positional_file_idx += 1

            if item is None or not item.has_local:
                logger.print_status(
                    f"No local example data for FILE parameter '{placeholder}' — skipping runtime command",
                    "WARNING",
                )
                return None, []

            container_path = f"/data/{item.filename}"
            volume_entry = f"{item.local_path}:{container_path}"
            if volume_entry not in volume_list:
                volume_list.append(volume_entry)
            result_cmd = result_cmd.replace(f"<{placeholder}>", _shell_quote(container_path), 1)

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
            result_cmd = result_cmd.replace(f"<{placeholder}>", _shell_quote(str(value)), 1)

    return result_cmd, volume_list

