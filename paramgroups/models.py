"""
Pydantic models for GenePattern parameter groups (paramgroups.json).

Parameter groups organize module parameters into logical sections for better UX.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
import json


class ParameterGroup(BaseModel):
    """Represents a single parameter group in the paramgroups.json file."""

    name: str = Field(..., description="Name of the parameter group (e.g., 'Basic parameters', 'Advanced parameters')")
    description: str = Field(..., description="Description of what parameters in this group control")
    parameters: List[str] = Field(..., description="List of parameter names included in this group")
    hidden: Optional[bool] = Field(False, description="Whether this parameter group should be hidden by default in the UI")

    class Config:
        populate_by_name = True


class ParamgroupsModel(BaseModel):
    """
    Represents a GenePattern paramgroups.json file.

    Parameter groups organize module parameters into logical sections,
    making complex modules easier to understand and use.

    Based on analysis of multiple GenePattern paramgroups.json files.
    """

    groups: List[ParameterGroup] = Field(..., description="List of parameter groups")

    # Artifact generation metadata (for compatibility with ArtifactModel)
    artifact_report: Optional[str] = Field(None, description="Report on the generated paramgroups implementation")
    artifact_status: Optional[str] = Field(None, description="Status of paramgroups generation (success/failure)")

    class Config:
        populate_by_name = True

    def to_json_string(self, indent: int = 4) -> str:
        """
        Convert the model to a JSON string for the paramgroups.json file.

        Args:
            indent: Number of spaces for JSON indentation (default: 4)

        Returns:
            JSON string representation of the paramgroups
        """
        # Convert groups to list of dicts, excluding artifact metadata
        groups_data = [group.model_dump(exclude_none=True) for group in self.groups]

        # Return formatted JSON
        return json.dumps(groups_data, indent=indent)

    @classmethod
    def from_json_string(cls, json_content: str) -> 'ParamgroupsModel':
        """
        Parse a paramgroups.json string and create a ParamgroupsModel instance.

        Args:
            json_content: String content of a paramgroups.json file

        Returns:
            ParamgroupsModel instance
        """
        try:
            groups_data = json.loads(json_content)

            # Convert list of dicts to ParameterGroup objects
            groups = [ParameterGroup(**group_data) for group_data in groups_data]

            return cls(groups=groups)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in paramgroups file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse paramgroups.json: {e}")

    def add_group(self, name: str, description: str, parameters: List[str], hidden: bool = False) -> None:
        """
        Add a new parameter group to the model.

        Args:
            name: Name of the parameter group
            description: Description of the group
            parameters: List of parameter names
            hidden: Whether the group should be hidden by default
        """
        new_group = ParameterGroup(
            name=name,
            description=description,
            parameters=parameters,
            hidden=hidden
        )
        self.groups.append(new_group)

    def get_group_by_name(self, name: str) -> Optional[ParameterGroup]:
        """
        Get a parameter group by name.

        Args:
            name: Name of the parameter group to find

        Returns:
            ParameterGroup if found, None otherwise
        """
        for group in self.groups:
            if group.name == name:
                return group
        return None

    def get_all_parameters(self) -> List[str]:
        """
        Get a flat list of all parameters across all groups.

        Returns:
            List of all parameter names
        """
        all_params = []
        for group in self.groups:
            all_params.extend(group.parameters)
        return all_params

    def validate_against_parameters(self, parameter_names: List[str]) -> dict:
        """
        Validate that all parameters in groups exist in the provided parameter list.

        Args:
            parameter_names: List of valid parameter names from the manifest

        Returns:
            Dictionary with validation results
        """
        all_group_params = self.get_all_parameters()
        missing_params = [p for p in all_group_params if p not in parameter_names]
        extra_params = [p for p in parameter_names if p not in all_group_params]

        return {
            'valid': len(missing_params) == 0,
            'missing_from_manifest': missing_params,
            'not_in_groups': extra_params,
            'total_grouped_params': len(all_group_params),
            'total_manifest_params': len(parameter_names)
        }

