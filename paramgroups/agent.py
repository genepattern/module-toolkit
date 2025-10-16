import json
from typing import List, Dict, Any
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerStdio
from dotenv import load_dotenv
from agents.models import configured_llm_model
from agents.planner import ModulePlan


# Load environment variables from .env file
load_dotenv()


system_prompt = """
You are an expert UX designer and bioinformatician specializing in creating intuitive parameter 
organization for GenePattern modules. Your task is to generate well-structured paramgroups.json 
files that provide optimal user experience by logically grouping related parameters.

CRITICAL: Your output must ALWAYS be valid JSON only - no markdown, no explanations, no text before or after the JSON.

Key requirements for GenePattern paramgroups:
- Group related parameters together for intuitive workflows
- Create clear, descriptive group names that users understand
- Organize from most essential to least essential parameters
- Balance group sizes (avoid too many small groups or overly large groups)
- Consider parameter dependencies and typical usage patterns
- Use appropriate group descriptions to guide users
- Mark advanced/expert groups as hidden when appropriate

Paramgroups Structure:
- JSON array of group objects
- Each group: {"name": "string", "description": "string", "hidden": boolean, "parameters": ["array"]}
- Required fields: name, parameters
- Optional fields: description, hidden

Best Practices:
- Start with "Required" or "Basic" parameters group
- Group by functional area (Input/Output, Analysis Options, Quality Control, etc.)
- Use clear, non-technical group names when possible
- Provide helpful descriptions that explain the group's purpose
- Hide complex/advanced groups by default (hidden: true)
- Ensure every parameter appears in exactly one group
- Order groups by typical workflow sequence

REMEMBER: Output ONLY valid JSON. No explanations, no markdown, no additional text.
"""

mcp_tools = MCPServerStdio('python', args=['mcp/server.py'], timeout=10)

# Create agent 
paramgroups_agent = Agent(configured_llm_model(), system_prompt=system_prompt, toolsets=[mcp_tools])


@paramgroups_agent.tool
def analyze_parameter_groupings(context: RunContext[str], parameters: List[Dict[str, Any]], group_strategy: str = "functional") -> str:
    """
    Analyze a list of parameters and suggest optimal groupings for paramgroups.json.
    
    Args:
        parameters: List of parameter dictionaries with 'name', 'type', 'required', 'description' fields
        group_strategy: Grouping strategy ('functional', 'workflow', 'complexity', 'alphabetical')
    
    Returns:
        Analysis of suggested parameter groupings with rationale
    """
    print(f"📋 PARAMGROUPS TOOL: Running analyze_parameter_groupings with {len(parameters)} parameters (strategy: {group_strategy})")
    
    if not parameters:
        print("❌ PARAMGROUPS TOOL: analyze_parameter_groupings failed - no parameters provided")
        return "Error: No parameters provided for grouping analysis"
    
    analysis = f"Parameter Grouping Analysis ({group_strategy} strategy):\n"
    analysis += "=" * 50 + "\n\n"
    
    # Categorize parameters based on strategy
    groups = {}
    
    if group_strategy == "functional":
        # Group by functional categories
        groups = {
            "Required Parameters": [],
            "Input/Output": [],
            "Analysis Options": [],
            "Quality Control": [],
            "Advanced Settings": [],
            "System Parameters": []
        }
        
        for param in parameters:
            name = param.get('name', '')
            param_type = param.get('type', '')
            required = param.get('required', False)
            description = param.get('description', '').lower()
            
            # Categorization logic
            if required or any(term in name.lower() for term in ['input', 'output'] if required):
                groups["Required Parameters"].append(param)
            elif any(term in name.lower() for term in ['input', 'file', 'data', 'output', 'result']):
                groups["Input/Output"].append(param)
            elif any(term in description for term in ['quality', 'filter', 'threshold', 'cutoff']):
                groups["Quality Control"].append(param)
            elif any(term in name.lower() for term in ['thread', 'memory', 'cpu', 'timeout', 'debug']):
                groups["System Parameters"].append(param)
            elif any(term in description for term in ['advanced', 'expert', 'optional']):
                groups["Advanced Settings"].append(param)
            else:
                groups["Analysis Options"].append(param)
    
    elif group_strategy == "workflow":
        # Group by typical workflow sequence
        groups = {
            "Data Input": [],
            "Processing Options": [],
            "Output Configuration": [],
            "Post-processing": []
        }
        
        for param in parameters:
            name = param.get('name', '').lower()
            if any(term in name for term in ['input', 'data', 'file', 'source']):
                groups["Data Input"].append(param)
            elif any(term in name for term in ['output', 'result', 'save', 'export']):
                groups["Output Configuration"].append(param)
            elif any(term in name for term in ['post', 'final', 'summary', 'report']):
                groups["Post-processing"].append(param)
            else:
                groups["Processing Options"].append(param)
    
    elif group_strategy == "complexity":
        # Group by complexity level
        groups = {
            "Basic Parameters": [],
            "Intermediate Options": [],
            "Advanced Configuration": []
        }
        
        for param in parameters:
            required = param.get('required', False)
            description = param.get('description', '').lower()
            name = param.get('name', '').lower()
            
            if required or any(term in name for term in ['input', 'output', 'method']):
                groups["Basic Parameters"].append(param)
            elif any(term in description for term in ['advanced', 'expert', 'complex']):
                groups["Advanced Configuration"].append(param)
            else:
                groups["Intermediate Options"].append(param)
    
    elif group_strategy == "alphabetical":
        # Simple alphabetical grouping
        groups = {
            "A-F": [],
            "G-M": [],
            "N-S": [],
            "T-Z": []
        }
        
        for param in parameters:
            name = param.get('name', '')
            if name:
                first_letter = name[0].upper()
                if first_letter <= 'F':
                    groups["A-F"].append(param)
                elif first_letter <= 'M':
                    groups["G-M"].append(param)
                elif first_letter <= 'S':
                    groups["N-S"].append(param)
                else:
                    groups["T-Z"].append(param)
    
    # Generate analysis output
    analysis += f"**Suggested Groups ({len([g for g in groups.values() if g])} groups):**\n\n"
    
    total_params = 0
    for group_name, group_params in groups.items():
        if group_params:
            total_params += len(group_params)
            analysis += f"**{group_name}** ({len(group_params)} parameters):\n"
            
            # Show parameter details
            for param in group_params[:5]:  # Limit to first 5 for readability
                name = param.get('name', 'Unknown')
                param_type = param.get('type', 'Unknown')
                required = param.get('required', False)
                status = "Required" if required else "Optional"
                analysis += f"  - {name} ({param_type}, {status})\n"
            
            if len(group_params) > 5:
                analysis += f"  ... and {len(group_params) - 5} more parameters\n"
            
            # Suggest group properties
            has_required = any(p.get('required', False) for p in group_params)
            should_hide = group_name in ["Advanced Settings", "System Parameters", "Advanced Configuration"]
            
            analysis += f"  → Suggested hidden: {should_hide}\n"
            analysis += f"  → Contains required parameters: {has_required}\n\n"
    
    # Grouping recommendations
    analysis += "**Recommendations:**\n"
    analysis += "- Use these groupings to structure your paramgroups.json file.\n"
    analysis += "- The 'Advanced' and 'System' groups are good candidates for `\"hidden\": true`.\n"
    analysis += "- Ensure all parameters from the plan are included in the final JSON.\n"

    print(f"✅ PARAMGROUPS TOOL: analyze_parameter_groupings completed successfully")
    return analysis


@paramgroups_agent.tool
def create_paramgroups(context: RunContext[str], tool_info: Dict[str, Any], planning_data: ModulePlan, error_report: str = "", attempt: int = 1) -> str:
    """
    Generate a valid paramgroups.json file based on the provided tool information and planning data.

    Args:
        tool_info: Dictionary containing tool metadata (name, version, etc.)
        planning_data: ModulePlan object containing the module plan and parameter definitions.
        error_report: Optional string containing error feedback from previous validation attempts.
        attempt: The current attempt number for generation.

    Returns:
        A string containing the complete and valid paramgroups.json content.
    """
    print(f"📋 PARAMGROUPS TOOL: Running create_paramgroups for {tool_info.get('name', 'Unknown Tool')} (attempt {attempt})")

    # Extract parameters from planning data (ModulePlan object)
    if not planning_data.parameters:
        print("⚠️ PARAMGROUPS TOOL: No parameters found in planning_data. Generating empty paramgroups.")
        return "[]"

    # Convert ModulePlan parameters to dictionary format for analysis
    parameters = [p.model_dump() for p in planning_data.parameters]

    # Use the analyze_parameter_groupings tool to get a suggested structure
    grouping_analysis = analyze_parameter_groupings(context, parameters)

    # Convert planning_data to dictionary format for the prompt
    planning_data_dict = planning_data.model_dump()

    # Build the generation prompt with all the necessary information
    generation_info = f"""
Tool Information:
- Name: {tool_info.get('name')}
- Version: {tool_info.get('version', 'unknown')}
- Description: {tool_info.get('description', 'No description provided')}

Parameters to Group ({len(parameters)} total):
{json.dumps(parameters, indent=2)}

Grouping Analysis:
{grouping_analysis}

Previous Error Report: {error_report if error_report else "None"}
Attempt Number: {attempt}

Generate a valid paramgroups.json file that groups these {len(parameters)} parameters logically.
Each parameter must appear in exactly one group. Output ONLY valid JSON - no markdown, no explanations.
"""

    print(f"✅ PARAMGROUPS TOOL: create_paramgroups completed successfully")
    return generation_info
