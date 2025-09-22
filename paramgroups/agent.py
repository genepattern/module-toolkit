import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerStdio
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


system_prompt = """
You are an expert UX designer and bioinformatician specializing in creating intuitive parameter 
organization for GenePattern modules. Your task is to generate well-structured paramgroups.json 
files that provide optimal user experience by logically grouping related parameters.

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

Always generate complete, valid paramgroups.json files that enhance user experience
and follow GenePattern UI conventions.
"""

# Use DEFAULT_LLM_MODEL from environment, fallback to a reasonable default
DEFAULT_LLM_MODEL = os.getenv('DEFAULT_LLM_MODEL', 'bedrock:us.anthropic.claude-sonnet-4-20250514-v1:0')

mcp_tools = MCPServerStdio('python', args=['mcp/server.py'], timeout=10)

# Create agent 
paramgroups_agent = Agent(DEFAULT_LLM_MODEL, system_prompt=system_prompt, toolsets=[mcp_tools])


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
    analysis += f"- Total parameters distributed: {total_params}/{len(parameters)}\n"
    
    if total_params < len(parameters):
        analysis += f"- WARNING: {len(parameters) - total_params} parameters not categorized\n"
    
    # Group size analysis
    non_empty_groups = [g for g in groups.values() if g]
    if non_empty_groups:
        avg_size = sum(len(g) for g in non_empty_groups) / len(non_empty_groups)
        analysis += f"- Average group size: {avg_size:.1f} parameters\n"
        
        large_groups = [name for name, params in groups.items() if len(params) > 8]
        if large_groups:
            analysis += f"- Consider splitting large groups: {', '.join(large_groups)}\n"
        
        small_groups = [name for name, params in groups.items() if 1 <= len(params) <= 2]
        if small_groups:
            analysis += f"- Consider merging small groups: {', '.join(small_groups)}\n"
    
    analysis += "- Ensure all parameters appear in exactly one group\n"
    analysis += "- Consider workflow sequence when ordering groups\n"
    
    print("✅ PARAMGROUPS TOOL: analyze_parameter_groupings completed successfully")
    return analysis


@paramgroups_agent.tool
def generate_paramgroups_structure(context: RunContext[str], groups: List[Dict[str, Any]]) -> str:
    """
    Generate a complete paramgroups.json structure from group definitions.
    
    Args:
        groups: List of group dictionaries with 'name', 'description', 'parameters', 'hidden' fields
    
    Returns:
        Complete paramgroups.json content as formatted JSON string
    """
    print(f"🏗️ PARAMGROUPS TOOL: Running generate_paramgroups_structure with {len(groups)} groups")
    
    if not groups:
        print("❌ PARAMGROUPS TOOL: generate_paramgroups_structure failed - no groups provided")
        return "Error: No groups provided for paramgroups generation"
    
    try:
        # Validate and clean group data
        paramgroups = []
        
        for i, group in enumerate(groups):
            if not isinstance(group, dict):
                print(f"❌ PARAMGROUPS TOOL: generate_paramgroups_structure failed - group {i} is not a dictionary")
                return f"Error: Group {i} must be a dictionary"
            
            # Required fields
            if 'name' not in group:
                print(f"❌ PARAMGROUPS TOOL: generate_paramgroups_structure failed - group {i} missing 'name'")
                return f"Error: Group {i} missing required field 'name'"
            
            if 'parameters' not in group:
                print(f"❌ PARAMGROUPS TOOL: generate_paramgroups_structure failed - group {i} missing 'parameters'")
                return f"Error: Group {i} missing required field 'parameters'"
            
            # Build clean group object
            clean_group = {
                "name": str(group['name']),
                "parameters": list(group['parameters']) if isinstance(group['parameters'], list) else []
            }
            
            # Optional fields
            if 'description' in group and group['description']:
                clean_group['description'] = str(group['description'])
            
            if 'hidden' in group:
                clean_group['hidden'] = bool(group['hidden'])
            
            paramgroups.append(clean_group)
        
        # Generate formatted JSON
        json_output = json.dumps(paramgroups, indent=4, ensure_ascii=False)
        
        # Add summary information
        total_parameters = sum(len(group.get('parameters', [])) for group in paramgroups)
        result = f"Generated paramgroups.json structure:\n"
        result += "=" * 40 + "\n\n"
        result += json_output + "\n\n"
        result += f"**Summary:**\n"
        result += f"- Groups: {len(paramgroups)}\n"
        result += f"- Total parameters: {total_parameters}\n"
        result += f"- Hidden groups: {sum(1 for g in paramgroups if g.get('hidden', False))}\n"
        
        # Validation notes
        result += f"\n**Notes:**\n"
        result += "- Ensure all parameters in your module are included\n"
        result += "- Verify parameter names match exactly with module definition\n"
        result += "- Consider group ordering for optimal user workflow\n"
        result += "- Test UI layout with actual parameter widgets\n"
        
        print("✅ PARAMGROUPS TOOL: generate_paramgroups_structure completed successfully")
        return result
        
    except Exception as e:
        error_msg = f"Error generating paramgroups structure: {str(e)}"
        print(f"❌ PARAMGROUPS TOOL: generate_paramgroups_structure failed - {error_msg}")
        return error_msg


@paramgroups_agent.tool
def optimize_group_organization(context: RunContext[str], paramgroups_content: str, optimization_goals: List[str] = None) -> str:
    """
    Analyze and suggest optimizations for an existing paramgroups.json structure.
    
    Args:
        paramgroups_content: Current paramgroups.json content as string
        optimization_goals: List of optimization goals ('user_experience', 'group_balance', 'workflow_order', 'complexity_separation')
    
    Returns:
        Analysis with optimization suggestions and improved structure
    """
    print(f"⚡ PARAMGROUPS TOOL: Running optimize_group_organization (content length: {len(paramgroups_content)} chars)")
    
    if optimization_goals is None:
        optimization_goals = ['user_experience', 'group_balance']
    
    try:
        # Parse existing paramgroups
        paramgroups = json.loads(paramgroups_content)
        
        if not isinstance(paramgroups, list):
            print("❌ PARAMGROUPS TOOL: optimize_group_organization failed - invalid structure")
            return "Error: Paramgroups must be an array of group objects"
        
        analysis = "Paramgroups Optimization Analysis:\n"
        analysis += "=" * 40 + "\n\n"
        
        # Current structure analysis
        total_groups = len(paramgroups)
        total_params = sum(len(group.get('parameters', [])) for group in paramgroups)
        hidden_groups = sum(1 for group in paramgroups if group.get('hidden', False))
        
        analysis += f"**Current Structure:**\n"
        analysis += f"- Groups: {total_groups}\n"
        analysis += f"- Total parameters: {total_params}\n"
        analysis += f"- Hidden groups: {hidden_groups}\n"
        analysis += f"- Average group size: {total_params/total_groups:.1f} parameters\n\n"
        
        # Optimization analysis
        suggestions = []
        
        if 'group_balance' in optimization_goals:
            # Check group size balance
            group_sizes = [len(group.get('parameters', [])) for group in paramgroups]
            large_groups = [i for i, size in enumerate(group_sizes) if size > 8]
            small_groups = [i for i, size in enumerate(group_sizes) if 1 <= size <= 2]
            
            if large_groups:
                suggestions.append(f"Consider splitting large groups (groups {[i+1 for i in large_groups]} have >8 parameters)")
            
            if small_groups:
                suggestions.append(f"Consider merging small groups (groups {[i+1 for i in small_groups]} have ≤2 parameters)")
        
        if 'workflow_order' in optimization_goals:
            # Check workflow ordering
            group_names = [group.get('name', '').lower() for group in paramgroups]
            workflow_order = ['input', 'basic', 'required', 'analysis', 'processing', 'output', 'advanced', 'system']
            
            out_of_order = []
            for i, name in enumerate(group_names):
                for j, pattern in enumerate(workflow_order):
                    if pattern in name:
                        # Check if there are later workflow groups before this one
                        for k in range(i):
                            prev_name = group_names[k]
                            for l, later_pattern in enumerate(workflow_order[j+1:], j+1):
                                if later_pattern in prev_name:
                                    out_of_order.append(f"'{paramgroups[i]['name']}' should come before '{paramgroups[k]['name']}'")
                        break
            
            if out_of_order:
                suggestions.append(f"Workflow ordering issues: {'; '.join(out_of_order[:3])}")
        
        if 'complexity_separation' in optimization_goals:
            # Check complexity separation
            basic_terms = ['basic', 'required', 'essential', 'input', 'output']
            advanced_terms = ['advanced', 'expert', 'debug', 'system', 'optional']
            
            mixed_complexity = []
            for group in paramgroups:
                name = group.get('name', '').lower()
                is_basic = any(term in name for term in basic_terms)
                is_advanced = any(term in name for term in advanced_terms)
                is_hidden = group.get('hidden', False)
                
                if is_advanced and not is_hidden:
                    mixed_complexity.append(f"'{group['name']}' appears advanced but not hidden")
                elif is_basic and is_hidden:
                    mixed_complexity.append(f"'{group['name']}' appears basic but is hidden")
            
            if mixed_complexity:
                suggestions.append(f"Complexity/visibility mismatches: {'; '.join(mixed_complexity[:2])}")
        
        if 'user_experience' in optimization_goals:
            # Check UX factors
            ux_issues = []
            
            # Check for descriptive group names
            vague_names = [group['name'] for group in paramgroups 
                          if group.get('name', '').lower() in ['other', 'misc', 'additional', 'more']]
            if vague_names:
                ux_issues.append(f"Vague group names: {', '.join(vague_names)}")
            
            # Check for missing descriptions
            no_description = [group['name'] for group in paramgroups 
                            if not group.get('description') and len(group.get('parameters', [])) > 3]
            if no_description:
                ux_issues.append(f"Large groups missing descriptions: {', '.join(no_description[:2])}")
            
            if ux_issues:
                suggestions.append(f"UX improvements needed: {'; '.join(ux_issues)}")
        
        # Generate suggestions
        if suggestions:
            analysis += "**Optimization Suggestions:**\n"
            for i, suggestion in enumerate(suggestions, 1):
                analysis += f"{i}. {suggestion}\n"
        else:
            analysis += "**Result:** Paramgroups structure appears well-optimized!\n"
        
        analysis += f"\n**Optimization Goals Applied:** {', '.join(optimization_goals)}\n"
        
        # Quick wins
        analysis += f"\n**Quick Wins:**\n"
        analysis += "- Add descriptions to groups with >3 parameters\n"
        analysis += "- Hide groups with 'advanced', 'expert', or 'debug' in the name\n"
        analysis += "- Ensure 'Required' or 'Basic' groups come first\n"
        analysis += "- Use descriptive names instead of 'Other' or 'Miscellaneous'\n"
        
        print("✅ PARAMGROUPS TOOL: optimize_group_organization completed successfully")
        return analysis
        
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in paramgroups content: {str(e)}"
        print(f"❌ PARAMGROUPS TOOL: optimize_group_organization failed - {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Error optimizing paramgroups: {str(e)}"
        print(f"❌ PARAMGROUPS TOOL: optimize_group_organization failed - {error_msg}")
        return error_msg
