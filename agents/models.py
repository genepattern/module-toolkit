import os
from typing import Any, Dict, List, Optional, Literal
from enum import Enum
from pydantic import BaseModel, Field
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider


def configured_llm_model():
    DEFAULT_LLM_MODEL = os.getenv('DEFAULT_LLM_MODEL', 'ollama:qwen3:8b')
    if DEFAULT_LLM_MODEL.startswith('ollama:'):
        OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434/v1')
        OLLAMA_MODEL_NAME = DEFAULT_LLM_MODEL[7:]
        ollama_provider = OllamaProvider(base_url=OLLAMA_BASE_URL)
        ollama_model = OpenAIChatModel(model_name=OLLAMA_MODEL_NAME, provider=ollama_provider)
        return ollama_model
    else: return DEFAULT_LLM_MODEL

# Pydantic models for structured planning output
class ParameterType(str, Enum):
    FILE = "file"
    TEXT = "text"
    INTEGER = "integer"
    FLOAT = "float"
    CHOICE = "choice"


class ValueCount(str, Enum):
    ZERO_OR_ONE = "0..1"
    ONE = "1..1"
    ZERO_OR_MORE = "0+"
    ONE_OR_MORE = "1+"


class ChoiceOption(BaseModel):
    display: str = Field(description="Display value for the choice")
    value: str = Field(description="Actual value to use")


class Parameter(BaseModel):
    name: str = Field(description="Parameter name")
    description: str = Field(description="Parameter description")
    required: bool = Field(description="Whether the parameter is required")
    type: ParameterType = Field(description="Parameter type")
    value_count: ValueCount = Field(description="Number of values accepted")
    default_value: Optional[str] = Field(None, description="Default value if any")
    file_formats: Optional[List[str]] = Field(None, description="Accepted file formats for file parameters")
    choices: Optional[List[ChoiceOption]] = Field(None, description="Available choices for choice parameters")
    accept_user_values: Optional[bool] = Field(None, description="Whether to accept user supplied values for choice parameters")
    prefix: str = Field(description="Command line prefix")
    prefix_only_if_value: bool = Field(description="Only include prefix if a value is specified")


class ModulePlan(BaseModel):
    module_name: str = Field(description="Name of the module")
    description: str = Field(description="Description of what the module does")
    author: str = Field(description="Author or organization")
    input_file_formats: List[str] = Field(description="File formats accepted as input")
    language: str = Field(description="Programming language the tool is implemented in")
    categories: List[str] = Field(description="Categories for this module (preprocessing, clustering, etc.)")
    cpu_cores: int = Field(description="CPU core requirement for the tool")
    memory: str = Field(description="Memory requirement for the tool (e.g., '2GB')")
    lsid: str = Field(description="Life Science Identifier (LSID) for the module in format urn:lsid:broad.mit.edu:cancer.software.genepattern.module.generated:<5-digit-id>:<version>")
    plan: str = Field(description="The full unstructured text of the plan")
    wrapper_script: str = Field(description="The name of the wrapper script")
    command_line: str = Field(description="Example command line for calling the wrapper script")
    parameters: List[Parameter] = Field(description="List of parameters to expose")
    docker_image_tag: str = Field(description="Docker image tag in format genepattern/<module_name>:<version> where module_name is lowercase alphanumeric only")


class ArtifactModel(BaseModel):
    """Model representing a generated artifact result"""
    code: str  # The generated artifact code
    artifact_report: str  # A report on the generated artifact's implementation and use
    artifact_status: Literal["success", "failure"]  # Status of the artifact generation
    meta: Dict[str, Any]  # Additional metadata about the generated artifact
