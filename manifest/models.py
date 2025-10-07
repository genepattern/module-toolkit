from pydantic import BaseModel, Field
from typing import Optional, Dict
import re


class ManifestParameter(BaseModel):
    """Represents a single parameter in a GenePattern module manifest."""
    MODE: Optional[str] = Field(None, description="Parameter mode (IN for input files)")
    TYPE: Optional[str] = Field(None, description="Parameter type (FILE, TEXT, Integer, Floating Point)")
    name: str = Field(..., description="Parameter name")
    description: Optional[str] = Field(None, description="Parameter description")
    default_value: Optional[str] = Field(None, description="Default value for parameter")
    optional: Optional[str] = Field(None, description="Whether parameter is optional ('on' or empty)")
    type_class: Optional[str] = Field(None, alias='type',
                                      description="Java type class (e.g., java.io.File, java.lang.String)")
    fileFormat: Optional[str] = Field(None, description="Allowed file formats (semicolon-separated)")
    numValues: Optional[str] = Field(None, description="Number of values allowed (e.g., '1..1', '0+', '1+')")
    value: Optional[str] = Field(None, description="Parameter value or choice list")
    prefix: Optional[str] = Field(None, description="Prefix for parameter")
    prefix_when_specified: Optional[str] = Field(None, description="Prefix when parameter is specified")
    flag: Optional[str] = Field(None, description="Command line flag for parameter")
    range: Optional[str] = Field(None, description="Valid range for numeric parameters")
    choiceDir: Optional[str] = Field(None, description="URL for dynamic choice lists")
    choices: Optional[str] = Field(None, description="Static choice list")
    url: Optional[str] = Field(None, description="Whether parameter accepts URLs")

    class Config:
        populate_by_name = True


class ManifestModel(BaseModel):
    """
    Represents a GenePattern module manifest file.

    Based on analysis of multiple GenePattern module manifests including:
    - Single.Cell.ssGSEA
    - igv.js
    - STAR.aligner
    - Salmon.Quant
    - spatialGE.STgradient.Launcher
    """

    # Required fields
    LSID: str = Field(...,
                      description="Unique identifier in urn:lsid format (e.g., 'urn:lsid:genepattern.org:module.analysis:00437')")
    name: str = Field(..., description="Module name (e.g., 'Single.Cell.ssGSEA')")
    commandLine: str = Field(...,
                             description="Command line template with parameter placeholders (e.g., 'bash <libdir>script.sh <input.file>')")

    # Common metadata fields
    author: Optional[str] = Field(None, description="Module author(s)")
    version: Optional[str] = Field(None, description="Module version")
    description: Optional[str] = Field(None, description="Description of module functionality")
    categories: Optional[str] = Field(None,
                                      description="Semicolon-separated category list (e.g., 'gsea;pathway analysis')")

    # Documentation and quality
    taskDoc: Optional[str] = Field(None, description="Documentation file or URL")
    documentationUrl: Optional[str] = Field(None, description="URL to module documentation")
    quality: Optional[str] = Field(None,
                                   description="Quality level (e.g., 'production', 'preproduction', 'development')")
    privacy: Optional[str] = Field(None, description="Privacy setting (e.g., 'public', 'private')")

    # Technical specifications
    language: Optional[str] = Field(None, description="Programming language (e.g., 'Python', 'R', 'Javascript', 'any')")
    os: Optional[str] = Field(None, description="Operating system requirement (e.g., 'any', 'linux')")
    cpuType: Optional[str] = Field(None, description="CPU type requirement (e.g., 'any')")
    JVMLevel: Optional[str] = Field(None, description="JVM version requirement")

    # File and format specifications
    fileFormat: Optional[str] = Field(None, description="Supported file formats (semicolon-separated)")

    # Job resource requirements
    job_cpuCount: Optional[str] = Field(None, alias='job.cpuCount', description="Number of CPUs required")
    job_memory: Optional[str] = Field(None, alias='job.memory', description="Memory requirement (e.g., '8Gb')")
    job_walltime: Optional[str] = Field(None, alias='job.walltime', description="Maximum wall time")
    job_docker_image: Optional[str] = Field(None, alias='job.docker.image', description="Docker image to use")

    # Source and publication
    src_repo: Optional[str] = Field(None, alias='src.repo', description="Source code repository URL")
    publicationDate: Optional[str] = Field(None, description="Publication date")

    # Module type and classification
    taskType: Optional[str] = Field(None, description="Task type (e.g., 'gsea', 'rna-seq', 'javascript')")

    # Advanced settings
    requiredPatchLSIDs: Optional[str] = Field(None, description="Required patch LSIDs")
    requiredPatchURLs: Optional[str] = Field(None, description="Required patch URLs")
    pipelineModel: Optional[str] = Field(None, description="Pipeline model")
    serializedModel: Optional[str] = Field(None, description="Serialized model")

    # User information
    userid: Optional[str] = Field(None, description="User ID of module creator")

    # Parameters - stored as dictionary with parameter number as key
    parameters: Optional[Dict[int, ManifestParameter]] = Field(default_factory=dict,
                                                               description="Module parameters indexed by parameter number")

    # Additional properties not covered above
    additional_properties: Optional[Dict[str, str]] = Field(default_factory=dict,
                                                            description="Any additional key-value pairs")

    class Config:
        populate_by_name = True

    def to_manifest_string(self) -> str:
        """
        Convert the model to a manifest file string in key=value format.

        Returns:
            String representation of the manifest file
        """
        lines = []
        lines.append("# GenePattern Module Manifest")
        lines.append("")

        # Standard fields in recommended order
        field_order = [
            'LSID', 'name', 'version', 'author', 'description', 'categories',
            'commandLine', 'cpuType', 'os', 'language', 'JVMLevel',
            'fileFormat', 'taskType', 'taskDoc', 'documentationUrl',
            'quality', 'privacy', 'publicationDate', 'userid',
            'job.cpuCount', 'job.memory', 'job.walltime', 'job.docker.image',
            'src.repo', 'pipelineModel', 'serializedModel',
            'requiredPatchLSIDs', 'requiredPatchURLs'
        ]

        # Add standard fields
        model_dict = self.model_dump(by_alias=True, exclude={'parameters', 'additional_properties'})
        for field in field_order:
            if field in model_dict and model_dict[field] is not None and model_dict[field] != '':
                lines.append(f"{field}={model_dict[field]}")

        # Add parameters
        if self.parameters:
            lines.append("")
            lines.append("# Parameters")
            for param_num in sorted(self.parameters.keys()):
                param = self.parameters[param_num]
                param_dict = param.model_dump(by_alias=True, exclude_none=True)
                for key, value in sorted(param_dict.items()):
                    if value is not None and value != '':
                        lines.append(f"p{param_num}_{key}={value}")

        # Add additional properties
        if self.additional_properties:
            lines.append("")
            lines.append("# Additional Properties")
            for key, value in sorted(self.additional_properties.items()):
                if value is not None and value != '':
                    lines.append(f"{key}={value}")

        return "\n".join(lines)

    @classmethod
    def from_manifest_string(cls, manifest_content: str) -> 'ManifestModel':
        """
        Parse a manifest file string and create a ManifestModel instance.

        Args:
            manifest_content: String content of a manifest file

        Returns:
            ManifestModel instance
        """
        data = {}
        parameters = {}
        additional = {}

        for line in manifest_content.split('\n'):
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Parse key=value
            if '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()

                # Check if it's a parameter
                param_match = re.match(r'p(\d+)_(.+)', key)
                if param_match:
                    param_num = int(param_match.group(1))
                    param_key = param_match.group(2)

                    if param_num not in parameters:
                        parameters[param_num] = {}
                    parameters[param_num][param_key] = value
                else:
                    # Standard field
                    # Convert dot notation to underscore for Pydantic
                    pydantic_key = key.replace('.', '_')
                    data[pydantic_key] = value

        # Convert parameter dictionaries to ManifestParameter objects
        param_objects = {}
        for param_num, param_data in parameters.items():
            try:
                param_objects[param_num] = ManifestParameter(**param_data)
            except Exception as e:
                print(f"Warning: Could not parse parameter {param_num}: {e}")

        data['parameters'] = param_objects

        return cls(**data)
