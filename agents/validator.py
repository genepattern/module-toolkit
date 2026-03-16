"""
Artifact validation dispatcher.

Calls each artifact package's linter directly (without spawning a subprocess),
captures stdout/stderr, and returns a normalised success/failure dict.
"""
import importlib
import io
import traceback
from contextlib import redirect_stdout, redirect_stderr
from typing import Any, Dict, List, Optional

from agents.logger import Logger

# Maps the validate_tool name used in artifact_agents config to the
# importable linter module path.
LINTER_MAP: Dict[str, str] = {
    'validate_manifest': 'manifest.linter',
    'validate_dockerfile': 'dockerfile.linter',
    'validate_documentation': 'documentation.linter',
    'validate_gpunit': 'gpunit.linter',
    'validate_paramgroups': 'paramgroups.linter',
    'validate_wrapper': 'wrapper.linter',
}


def validate_artifact(
    file_path: str,
    validate_tool: str,
    extra_args: Optional[List[str]],
    logger: Logger,
) -> Dict[str, Any]:
    """Validate an artifact using its linter directly.

    Args:
        file_path:     Path to the artifact file to validate.
        validate_tool: Key into LINTER_MAP (e.g. 'validate_dockerfile').
        extra_args:    Additional CLI arguments to forward to the linter.
        logger:        Logger instance for status messages.

    Returns:
        ``{'success': True, 'result': <output>}`` or
        ``{'success': False, 'error': <output>}``.
    """
    try:
        logger.print_status(f"Validating with {validate_tool}")

        if validate_tool not in LINTER_MAP:
            return {'success': False, 'error': f"Unknown validation tool: {validate_tool}"}

        linter_module = importlib.import_module(LINTER_MAP[validate_tool])

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            linter_args = [file_path]
            if extra_args:
                linter_args.extend(extra_args)

            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exit_code = linter_module.main(linter_args)

            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            full_output = output + (f"\nErrors:\n{errors}" if errors else "")

        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            full_output = output + (f"\nErrors:\n{errors}" if errors else "")

        output_lower = full_output.lower()

        if exit_code != 0 or any(indicator in output_lower for indicator in [
            "fail:", "failed", "error:", "invalid json", "validation failed"
        ]):
            logger.print_status("Validation failed. Full validation output:", "ERROR")
            print(full_output)
            return {'success': False, 'error': full_output}

        elif any(indicator in output_lower for indicator in [
            "pass:", "passed", "validation passed", "has passed", "**passed**",
            "successfully", "validation successful", "all checks passed"
        ]):
            logger.print_status("✅ Validation passed", "SUCCESS")
            return {'success': True, 'result': full_output}

        else:
            logger.print_status("Ambiguous validation result, defaulting to failure", "WARNING")
            logger.print_status("Full validation output:", "WARNING")
            print(full_output)
            return {'success': False, 'error': f"Ambiguous validation result: {full_output}"}

    except Exception as e:
        error_msg = f"Validation error: {str(e)}"
        logger.print_status(error_msg, "ERROR")
        logger.print_status(f"Traceback: {traceback.format_exc()}", "DEBUG")
        return {'success': False, 'error': error_msg}

