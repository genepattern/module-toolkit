"""
Status tracking for the module generation pipeline.

ModuleGenerationStatus is the central state object threaded through the
entire pipeline.  It holds research/planning results, per-artifact progress,
token usage, and escalation history, and can be serialised to / from JSON
for resume support.

ArtifactResult is the structured return value from artifact_creation_loop.
"""
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agents.example_data import ExampleDataItem

# Token cost configuration (cost per 1000 tokens)
INPUT_TOKEN_COST_PER_1000 = float(os.getenv('INPUT_TOKEN_COST_PER_1000', '0.003'))
OUTPUT_TOKEN_COST_PER_1000 = float(os.getenv('OUTPUT_TOKEN_COST_PER_1000', '0.015'))


@dataclass
class ArtifactResult:
    """Structured result from an artifact_creation_loop call."""
    success: bool
    artifact_name: str
    error_text: str = ""
    # populated when classification is available; imported lazily to avoid circular deps
    root_cause: Optional[Any] = None


@dataclass
class ModuleGenerationStatus:
    """Track the status of module generation process."""
    tool_name: str
    module_directory: str
    research_data: Dict[str, Any] = None
    # ModulePlan is set at runtime; typed as Any to avoid a hard import cycle
    planning_data: Any = None
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
        """Return True if research data is present."""
        return bool(self.research_data)

    @property
    def planning_complete(self) -> bool:
        """Return True if planning data is present."""
        return self.planning_data is not None

    @property
    def parameters(self):
        """Return parameters from planning_data if available."""
        return self.planning_data.parameters if self.planning_data else []

    def add_usage(self, result) -> None:
        """Add token usage from an agent result to the running totals."""
        try:
            usage = result.usage()
            if usage:
                self.input_tokens += usage.input_tokens or 0
                self.output_tokens += usage.output_tokens or 0
        except Exception:
            pass

    def get_estimated_cost(self) -> float:
        """Calculate estimated cost based on token usage."""
        input_cost = (self.input_tokens / 1000) * INPUT_TOKEN_COST_PER_1000
        output_cost = (self.output_tokens / 1000) * OUTPUT_TOKEN_COST_PER_1000
        return input_cost + output_cost

    def to_dict(self) -> Dict[str, Any]:
        """Convert status to a JSON-serialisable dictionary."""
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


