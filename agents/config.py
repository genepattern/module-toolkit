"""
Central configuration for the module-generation pipeline.

All environment-driven constants live here so they can be imported by any
agent or the orchestrator without re-reading the environment in multiple
places.
"""
import os
import socket
import logfire

# ---------------------------------------------------------------------------
# Directory defaults
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT_DIR = os.getenv('MODULE_OUTPUT_DIR', './generated-modules')

# ---------------------------------------------------------------------------
# Retry / loop limits
# ---------------------------------------------------------------------------
MAX_ARTIFACT_LOOPS = int(os.getenv('MAX_ARTIFACT_LOOPS', '5'))
MAX_ESCALATIONS = int(os.getenv('MAX_ESCALATIONS', '2'))


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------

def enable_telemetry(host: str = "localhost", port: int = 4318) -> bool:
    """Return True if an OpenTelemetry collector is reachable at host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def configure_telemetry() -> None:
    """Configure Logfire telemetry if a collector is available."""
    if enable_telemetry():
        logfire.configure(send_to_logfire=False, service_name="module-toolkit")
        logfire.instrument_pydantic_ai()

