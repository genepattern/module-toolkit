"""
Root-cause error classifier for cross-artifact error escalation.

When a downstream artifact (e.g. Dockerfile) fails validation, this module
inspects the error text and determines which *upstream* artifact is the most
likely root cause.  The orchestrator can then regenerate the responsible
artifact instead of blindly retrying the one that reported the error.

Design principles
-----------------
* **Missing packages / libraries are Dockerfile problems.**  If the wrapper
  correctly ``import``s pandas or calls ``library(DESeq2)``, the fix is to
  add ``pip install`` / ``install.packages()`` / ``apt-get install`` to the
  Dockerfile — *not* to rewrite the wrapper.

* **Wrapper escalation is reserved for structural / logic errors** in the
  wrapper itself: wrong argparse flags, syntax errors in the wrapper source,
  or R logic errors (``object not found``, ``unexpected symbol``) that
  indicate the generated code is buggy.

* **R and Python are treated equally.**  About half the generated wrappers
  are R scripts, so R-specific error patterns are first-class citizens.

Rules are evaluated in priority order; the first match wins.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import re


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Artifact dependency graph
# ---------------------------------------------------------------------------
# When a downstream artifact fails, these are the upstream artifacts that
# *could* be the root cause (in priority order).

ARTIFACT_DEPENDENCIES: Dict[str, List[str]] = {
    'dockerfile': ['wrapper', 'manifest', 'gpunit'],
    'gpunit': ['wrapper', 'manifest'],
    'manifest': ['wrapper'],
    'paramgroups': ['wrapper', 'manifest'],
    'documentation': [],
    'wrapper': [],
    'install': ['manifest', 'paramgroups'],
}


def get_upstream_dependencies(artifact_name: str) -> List[str]:
    """Return the list of upstream artifacts that could cause *artifact_name* to fail."""
    return ARTIFACT_DEPENDENCIES.get(artifact_name, [])


@dataclass(frozen=True)
class RootCause:
    """Result of root-cause classification."""
    target_artifact: str          # artifact that should be regenerated
    reason: str                   # human-readable explanation for logs / prompts
    original_artifact: str = ""   # the artifact whose validation surfaced the error


# ---------------------------------------------------------------------------
# Classification rules
# ---------------------------------------------------------------------------
# Each rule is (compiled_regex_pattern, target_artifact, reason_template).
# reason_template may contain ``{match}`` which is replaced with the first
# regex match group (or the full match if no groups).
#
# Rules are tried top-to-bottom; first match wins.

_RULES: List[tuple] = [

    # =====================================================================
    # WRAPPER ESCALATION — structural / logic errors in the wrapper itself
    # =====================================================================

    # -- Python wrapper syntax errors ----------------------------------------
    (
        re.compile(r"SyntaxError:", re.IGNORECASE),
        "wrapper",
        "Wrapper has a Python syntax error. "
        "The wrapper should be regenerated with valid syntax.",
    ),

    # -- Python / R argparse / optparse CLI mismatches -----------------------
    (
        re.compile(
            r"the following arguments are required:\s*(.+)",
            re.IGNORECASE,
        ),
        "wrapper",
        "Wrapper argparse requires arguments ({match}) that were not passed. "
        "The wrapper's argument parsing should be regenerated to match the "
        "module's command_line template.",
    ),
    (
        re.compile(
            r"unrecognized arguments?:\s*(.+)",
            re.IGNORECASE,
        ),
        "wrapper",
        "Wrapper does not recognise arguments ({match}). "
        "The wrapper's argument parsing should be regenerated to accept all "
        "parameters defined in the plan.",
    ),
    (
        re.compile(
            r"error: argument\s+(\S+):\s*(.+)",
            re.IGNORECASE,
        ),
        "wrapper",
        "Wrapper argparse error on argument {match}. "
        "The wrapper should be regenerated to fix argument handling.",
    ),

    # -- R wrapper logic / syntax errors (NOT missing-package errors) --------
    (
        re.compile(
            r"Error in .+:\s*object ['\"]?([^'\"]+?)['\"]?\s+not found",
            re.IGNORECASE,
        ),
        "wrapper",
        "R wrapper references undefined object '{match}'. "
        "The wrapper has a logic error and should be regenerated.",
    ),
    (
        re.compile(r"unexpected symbol", re.IGNORECASE),
        "wrapper",
        "R wrapper has a syntax error (unexpected symbol). "
        "The wrapper should be regenerated with valid R syntax.",
    ),
    (
        re.compile(r"unexpected string constant", re.IGNORECASE),
        "wrapper",
        "R wrapper has a syntax error (unexpected string constant). "
        "The wrapper should be regenerated with valid R syntax.",
    ),
    (
        re.compile(r"unexpected '[\)\}\]]'", re.IGNORECASE),
        "wrapper",
        "R wrapper has a syntax error (unmatched bracket/paren). "
        "The wrapper should be regenerated with valid R syntax.",
    ),
    (
        re.compile(
            r"could not find function ['\"]([^'\"]+)['\"]",
            re.IGNORECASE,
        ),
        "wrapper",
        "R wrapper calls undefined function '{match}'. "
        "The wrapper should be regenerated to call the correct function, "
        "or the Dockerfile needs to install the package that provides it.",
    ),
    # R optparse unknown flags (equivalent to Python's unrecognized arguments)
    (
        re.compile(
            r"Error in getopt.*?unknown flag",
            re.IGNORECASE,
        ),
        "wrapper",
        "R wrapper received an unknown command-line flag via optparse/getopt. "
        "The wrapper's option definitions should be regenerated to match "
        "the module's command_line template.",
    ),

    # -- Manifest / command_line mismatch errors -----------------------------
    (
        re.compile(
            r"parameter[s]?\s+(?:name[s]?\s+)?(?:not found|missing|unknown|undefined)"
            r".*?['\"]?(\S+?)['\"]?",
            re.IGNORECASE,
        ),
        "manifest",
        "Manifest references parameter '{match}' that does not match the wrapper. "
        "The manifest should be regenerated to align with the wrapper's arguments.",
    ),

    # =====================================================================
    # DOCKERFILE — package installation / build / environment errors
    # These should be fixed in the Dockerfile, NOT by rewriting the wrapper.
    # =====================================================================

    # -- Python missing package (pip install needed) -------------------------
    (
        re.compile(
            r"ModuleNotFoundError:\s*No module named ['\"]?([^\s'\"]+)",
            re.IGNORECASE,
        ),
        "dockerfile",
        "Python package '{match}' is not installed in the container. "
        "Add 'pip install {match}' (or the correct package name) to the Dockerfile.",
    ),
    (
        re.compile(
            r"ImportError:\s*cannot import name ['\"]?([^\s'\"]+)",
            re.IGNORECASE,
        ),
        "dockerfile",
        "Python cannot import name '{match}'. The package may be missing or "
        "the wrong version. Fix the pip install in the Dockerfile.",
    ),
    (
        re.compile(
            r"ImportError:\s*(.+)",
            re.IGNORECASE,
        ),
        "dockerfile",
        "Python import error: {match}. A system library or Python package "
        "is missing from the container. Fix the Dockerfile.",
    ),

    # -- R missing package (install.packages / BiocManager needed) -----------
    (
        re.compile(
            r"there is no package called ['\"]?([^\s'\"]+)",
            re.IGNORECASE,
        ),
        "dockerfile",
        "R package '{match}' is not installed in the container. "
        "Add install.packages('{match}') or BiocManager::install('{match}') "
        "to the Dockerfile.",
    ),
    (
        re.compile(
            r"Error in library\(([^)]+)\)",
            re.IGNORECASE,
        ),
        "dockerfile",
        "R library '{match}' failed to load. The package is likely not installed. "
        "Add install.packages('{match}') to the Dockerfile.",
    ),
    (
        re.compile(
            r"Error in loadNamespace\(.*?['\"]([^'\"]+)['\"]",
            re.IGNORECASE,
        ),
        "dockerfile",
        "R namespace '{match}' failed to load. The package is likely not installed. "
        "Add install.packages('{match}') to the Dockerfile.",
    ),
    (
        re.compile(
            r"Installation of package ['\"]([^'\"]+)['\"] had non-zero exit status",
            re.IGNORECASE,
        ),
        "dockerfile",
        "R package '{match}' failed to install. Check system dependencies "
        "or use a different installation method in the Dockerfile.",
    ),

    # -- R script / source file not found in container -----------------------
    (
        re.compile(
            r"Error in source\(",
            re.IGNORECASE,
        ),
        "dockerfile",
        "R source() could not find a script file. "
        "The Dockerfile COPY instruction may be incorrect.",
    ),
    (
        re.compile(
            r"cannot open connection.*No such file or directory",
            re.IGNORECASE | re.DOTALL,
        ),
        "dockerfile",
        "R cannot open a file in the container. "
        "A COPY instruction or working directory may be wrong in the Dockerfile.",
    ),

    # -- apt-get / system package errors -------------------------------------
    (
        re.compile(
            r"E: Unable to locate package\s+(\S+)",
            re.IGNORECASE,
        ),
        "dockerfile",
        "apt package '{match}' not found. Fix the package name in the Dockerfile.",
    ),
    (
        re.compile(
            r"E: Package ['\"]?([^\s'\"]+)['\"]? has no installation candidate",
            re.IGNORECASE,
        ),
        "dockerfile",
        "apt package '{match}' has no installation candidate. "
        "Fix the Dockerfile.",
    ),

    # -- pip-specific errors -------------------------------------------------
    (
        re.compile(
            r"pip.*?No matching distribution found for\s+(\S+)",
            re.IGNORECASE,
        ),
        "dockerfile",
        "pip cannot find package '{match}'. Fix the package name or version "
        "constraint in the Dockerfile.",
    ),

    # -- Shared-library / linker errors (missing apt package) ----------------
    (
        re.compile(
            r"error while loading shared libraries:\s*(\S+)",
            re.IGNORECASE,
        ),
        "dockerfile",
        "Shared library '{match}' is missing. Install the system package "
        "that provides it via apt-get in the Dockerfile.",
    ),
    (
        re.compile(
            r"cannot open shared object file.*No such file",
            re.IGNORECASE,
        ),
        "dockerfile",
        "A shared object (.so) file is missing from the container. "
        "Install the required system library via apt-get in the Dockerfile.",
    ),

    # -- Dockerfile build / syntax errors ------------------------------------
    (
        re.compile(
            r"unexpected end of statement",
            re.IGNORECASE,
        ),
        "dockerfile",
        "Dockerfile has a syntax error (unexpected end of statement).",
    ),
    (
        re.compile(
            r"failed to process\b",
            re.IGNORECASE,
        ),
        "dockerfile",
        "Dockerfile build processing error.",
    ),
    (
        re.compile(
            r"executor failed running",
            re.IGNORECASE,
        ),
        "dockerfile",
        "Dockerfile RUN instruction failed.",
    ),
    (
        re.compile(
            r"command not found",
            re.IGNORECASE,
        ),
        "dockerfile",
        "A command was not found inside the container. "
        "Install the tool or add it to PATH in the Dockerfile.",
    ),

    # -- File-not-found for wrapper script itself ----------------------------
    (
        re.compile(
            r"(?=.*(?:No such file or directory|cannot open file))(?=.*wrapper)",
            re.IGNORECASE,
        ),
        "dockerfile",
        "Wrapper script file not found in the container. "
        "The Dockerfile COPY instruction may be incorrect.",
    ),
]


def classify_error(
    error_text: str,
    failing_artifact: str,
) -> Optional[RootCause]:
    """Classify an error string and return the root-cause artifact.

    Parameters
    ----------
    error_text:
        The full validation error output (may be multi-line).
    failing_artifact:
        The artifact whose validation produced this error (e.g. ``"dockerfile"``).

    Returns
    -------
    A ``RootCause`` whose ``target_artifact`` may differ from *failing_artifact*
    (indicating escalation is needed), or ``None`` if no rule matched.
    """
    if not error_text:
        return None

    for pattern, target, reason_template in _RULES:
        m = pattern.search(error_text)
        if m:
            # Use first capture group if available, else the full match
            match_text = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)
            reason = reason_template.replace("{match}", match_text.strip())
            return RootCause(
                target_artifact=target,
                reason=reason,
                original_artifact=failing_artifact,
            )

    return None


def should_escalate(root_cause: Optional[RootCause]) -> bool:
    """Return True if the root cause points to a *different* artifact than
    the one that originally failed — meaning we should escalate.
    """
    if root_cause is None:
        return False
    return root_cause.target_artifact != root_cause.original_artifact


