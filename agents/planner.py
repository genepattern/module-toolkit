import os
import re
from typing import List, Dict, Any
from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


system_prompt = """
You are a PhD-level bioinformatician and software architect, specializing in creating comprehensive 
plans for wrapping bioinformatics tools into GenePattern modules. Your expertise spans genetics, 
genomics, computational biology, machine learning, and data analysis.

Your primary task is to analyze bioinformatics tools and generate detailed implementation plans that include:

1. **Parameter Analysis**: Identify all configurable parameters, their types, constraints, and relationships
2. **Data Flow Design**: Map input/output relationships and data transformations
3. **Module Architecture**: Design the overall structure including wrapper scripts, dependencies, and configuration
4. **Parameter Groups**: Organize parameters into logical, user-friendly groups
5. **Validation Strategy**: Define input validation, error handling, and testing approaches
6. **Documentation Plan**: Outline user documentation, examples, and help text

**GenePattern Parameter Types:**
- Text: String values (single or multiple)
- Integer: Whole numbers with optional ranges
- Float: Decimal numbers with optional ranges  
- File: Input/output files with format constraints
- Choice: Predefined options (single or multiple selection)

**Parameter Properties:**
- Required vs Optional
- Default values
- Value constraints (min/max, patterns, file formats)
- Multiple value support
- Dependencies between parameters

**Planning Methodology:**
1. Research the tool thoroughly using available resources
2. Analyze command-line interface and configuration options
3. Identify common use cases and workflows
4. Design intuitive parameter groupings
5. Plan comprehensive testing and validation
6. Create detailed implementation roadmap

Always provide thorough, accurate, and actionable plans with clear implementation steps.
"""

# Use DEFAULT_LLM_MODEL from environment, fallback to a reasonable default
DEFAULT_LLM_MODEL = os.getenv('DEFAULT_LLM_MODEL', 'bedrock:us.anthropic.claude-sonnet-4-20250514-v1:0')

# Create agent with MCP tools access
planner_agent = Agent(DEFAULT_LLM_MODEL, system_prompt=system_prompt)


@planner_agent.tool
def analyze_parameter_structure(context: RunContext[str], tool_help_text: str, command_examples: str = None) -> str:
    """
    Analyze command-line help text and examples to extract parameter structure.
    
    Args:
        tool_help_text: Help text from the tool (e.g., tool --help output)
        command_examples: Optional example commands showing parameter usage
    
    Returns:
        Structured analysis of parameters with types and constraints
    """
    print(f"🔧 PLANNER TOOL: Running analyze_parameter_structure (text length: {len(tool_help_text)} chars, examples: {'Yes' if command_examples else 'No'})")
    
    analysis = "Parameter Structure Analysis:\n"
    analysis += "=" * 40 + "\n\n"
    
    # Extract common parameter patterns
    flag_patterns = [
        (r'(-\w|--\w+)', 'flags'),
        (r'<(\w+)>', 'required_args'),
        (r'\[([^\]]+)\]', 'optional_args'),
        (r'(\w+)\s*:\s*(int|integer|float|string|file|bool)', 'typed_params')
    ]
    
    found_params = {}
    for pattern, param_type in flag_patterns:
        matches = re.findall(pattern, tool_help_text, re.IGNORECASE)
        if matches:
            found_params[param_type] = matches
    
    if found_params:
        for param_type, params in found_params.items():
            analysis += f"**{param_type.replace('_', ' ').title()}:**\n"
            for param in params[:10]:  # Limit to first 10 to avoid overwhelming
                analysis += f"  - {param}\n"
            analysis += "\n"
    
    # Look for file format indicators
    file_formats = re.findall(r'\.(bam|sam|vcf|bed|gtf|gff|fasta|fastq|txt|csv|tsv|json|xml)', tool_help_text, re.IGNORECASE)
    if file_formats:
        analysis += "**Detected File Formats:**\n"
        for fmt in set(file_formats):
            analysis += f"  - .{fmt}\n"
        analysis += "\n"
    
    # Look for numeric ranges or constraints
    numeric_constraints = re.findall(r'(\d+)-(\d+)|range\s*\[(\d+),\s*(\d+)\]|min[:\s]*(\d+)|max[:\s]*(\d+)', tool_help_text, re.IGNORECASE)
    if numeric_constraints:
        analysis += "**Numeric Constraints Found:**\n"
        for constraint in set(numeric_constraints[:5]):
            non_empty = [x for x in constraint if x]
            if non_empty:
                analysis += f"  - {' to '.join(non_empty)}\n"
        analysis += "\n"
    
    if command_examples:
        analysis += "**Example Analysis:**\n"
        # Extract parameters from examples
        example_params = re.findall(r'(-\w+|--\w+)(?:\s+([^\s-][^\s]*)?)', command_examples)
        if example_params:
            analysis += "Parameters used in examples:\n"
            for param, value in example_params[:10]:
                analysis += f"  - {param}"
                if value:
                    analysis += f" = {value}"
                analysis += "\n"
        analysis += "\n"
    
    analysis += "**Recommendations:**\n"
    analysis += "- Review each parameter for GenePattern type mapping\n"
    analysis += "- Identify parameter dependencies and groupings\n"
    analysis += "- Define validation rules and constraints\n"
    analysis += "- Consider default values and required parameters\n"
    
    print("✅ PLANNER TOOL: analyze_parameter_structure completed successfully")
    return analysis


@planner_agent.tool
def create_parameter_group_schema(context: RunContext[str], parameters: List[str], group_strategy: str = "functional") -> str:
    """
    Create parameter grouping schema for GenePattern module organization.
    
    Args:
        parameters: List of parameter names to organize
        group_strategy: Strategy for grouping ('functional', 'alphabetical', 'complexity')
    
    Returns:
        JSON-like schema for parameter groups
    """
    print(f"📊 PLANNER TOOL: Running create_parameter_group_schema with {len(parameters)} parameters (strategy: {group_strategy})")
    
    if not parameters:
        print("❌ PLANNER TOOL: create_parameter_group_schema failed - no parameters provided")
        return "Error: No parameters provided for grouping"
    
    schema = "Parameter Group Schema:\n"
    schema += "=" * 30 + "\n\n"
    
    if group_strategy == "functional":
        # Group by functional categories
        groups = {
            "Input Files": [],
            "Output Options": [],
            "Analysis Parameters": [],
            "Quality Control": [],
            "Advanced Options": [],
            "System Settings": []
        }
        
        for param in parameters:
            param_lower = param.lower()
            if any(term in param_lower for term in ['input', 'file', 'read', 'data']):
                groups["Input Files"].append(param)
            elif any(term in param_lower for term in ['output', 'out', 'result', 'write']):
                groups["Output Options"].append(param)
            elif any(term in param_lower for term in ['quality', 'qc', 'filter', 'trim']):
                groups["Quality Control"].append(param)
            elif any(term in param_lower for term in ['thread', 'cpu', 'memory', 'temp', 'cache']):
                groups["System Settings"].append(param)
            elif any(term in param_lower for term in ['advanced', 'expert', 'debug', 'verbose']):
                groups["Advanced Options"].append(param)
            else:
                groups["Analysis Parameters"].append(param)
                
    elif group_strategy == "alphabetical":
        # Group alphabetically
        groups = {}
        for param in sorted(parameters):
            first_letter = param[0].upper()
            if first_letter not in groups:
                groups[first_letter] = []
            groups[first_letter].append(param)
            
    elif group_strategy == "complexity":
        # Group by complexity (basic vs advanced)
        groups = {
            "Essential Parameters": [],
            "Optional Parameters": [],
            "Advanced Configuration": []
        }
        
        # Simple heuristic based on parameter names
        for param in parameters:
            param_lower = param.lower()
            if any(term in param_lower for term in ['help', 'version', 'input', 'output']):
                groups["Essential Parameters"].append(param)
            elif any(term in param_lower for term in ['advanced', 'expert', 'debug', 'verbose', 'thread', 'memory']):
                groups["Advanced Configuration"].append(param)
            else:
                groups["Optional Parameters"].append(param)
    
    # Generate schema output
    for group_name, group_params in groups.items():
        if group_params:  # Only show groups with parameters
            schema += f'"{group_name}": {{\n'
            schema += f'  "description": "Parameters related to {group_name.lower()}",\n'
            schema += f'  "parameters": [\n'
            for i, param in enumerate(group_params):
                comma = "," if i < len(group_params) - 1 else ""
                schema += f'    "{param}"{comma}\n'
            schema += '  ]\n'
            schema += '},\n\n'
    
    schema += "\n**Grouping Strategy Used:** " + group_strategy.title() + "\n"
    schema += "**Total Parameters:** " + str(len(parameters)) + "\n"
    schema += "**Groups Created:** " + str(len([g for g in groups.values() if g])) + "\n"
    
    print("✅ PLANNER TOOL: create_parameter_group_schema completed successfully")
    return schema


@planner_agent.tool
def validate_parameter_definition(context: RunContext[str], param_name: str, param_type: str, constraints: str = None, default_value: str = None) -> str:
    """
    Validate a GenePattern parameter definition for correctness and completeness.
    
    Args:
        param_name: Name of the parameter
        param_type: GenePattern type (Text, Integer, Float, File, Choice)
        constraints: Optional constraints (ranges, formats, etc.)
        default_value: Optional default value
    
    Returns:
        Validation report with recommendations
    """
    print(f"✅ PLANNER TOOL: Running validate_parameter_definition for '{param_name}' (type: {param_type})")
    
    report = f"Parameter Validation Report: {param_name}\n"
    report += "=" * 50 + "\n\n"
    
    # Validate parameter name
    name_issues = []
    if not param_name:
        name_issues.append("Parameter name is required")
    elif not re.match(r'^[a-zA-Z][a-zA-Z0-9._-]*$', param_name):
        name_issues.append("Parameter name should start with a letter and contain only alphanumeric characters, dots, hyphens, or underscores")
    elif len(param_name) > 50:
        name_issues.append("Parameter name is too long (>50 characters)")
    
    # Validate parameter type
    valid_types = ['Text', 'Integer', 'Float', 'File', 'Choice']
    type_issues = []
    if param_type not in valid_types:
        type_issues.append(f"Invalid parameter type '{param_type}'. Must be one of: {', '.join(valid_types)}")
    
    # Validate constraints based on type
    constraint_issues = []
    if constraints:
        if param_type == 'Integer':
            if not re.search(r'min|max|range', constraints, re.IGNORECASE):
                constraint_issues.append("Integer constraints should specify min/max ranges")
        elif param_type == 'Float':
            if not re.search(r'min|max|range|precision', constraints, re.IGNORECASE):
                constraint_issues.append("Float constraints should specify ranges or precision")
        elif param_type == 'File':
            if not re.search(r'format|extension|\.', constraints, re.IGNORECASE):
                constraint_issues.append("File constraints should specify accepted formats/extensions")
        elif param_type == 'Choice':
            if not re.search(r'options|values|choices', constraints, re.IGNORECASE):
                constraint_issues.append("Choice constraints should specify available options")
    
    # Validate default value
    default_issues = []
    if default_value:
        if param_type == 'Integer':
            try:
                int(default_value)
            except ValueError:
                default_issues.append("Default value must be a valid integer")
        elif param_type == 'Float':
            try:
                float(default_value)
            except ValueError:
                default_issues.append("Default value must be a valid number")
        elif param_type == 'File':
            if not re.match(r'.*\.\w+$', default_value):
                default_issues.append("File default should include file extension")
    
    # Generate report
    all_issues = name_issues + type_issues + constraint_issues + default_issues
    
    if not all_issues:
        report += "✅ **Status: VALID**\n\n"
        report += "Parameter definition passes all validation checks.\n\n"
    else:
        report += "❌ **Status: ISSUES FOUND**\n\n"
        report += "**Issues to Address:**\n"
        for issue in all_issues:
            report += f"  - {issue}\n"
        report += "\n"
    
    report += "**Parameter Summary:**\n"
    report += f"  - Name: {param_name}\n"
    report += f"  - Type: {param_type}\n"
    report += f"  - Constraints: {constraints or 'None specified'}\n"
    report += f"  - Default: {default_value or 'None specified'}\n\n"
    
    report += "**Recommendations:**\n"
    if param_type == 'File':
        report += "  - Consider specifying input vs output file distinction\n"
        report += "  - Include expected file format documentation\n"
    elif param_type == 'Choice':
        report += "  - Provide clear descriptions for each choice option\n"
        report += "  - Consider if multiple selections should be allowed\n"
    elif param_type in ['Integer', 'Float']:
        report += "  - Define realistic min/max ranges based on tool requirements\n"
        report += "  - Consider if parameter affects performance or memory usage\n"
    
    print("✅ PLANNER TOOL: validate_parameter_definition completed successfully")
    return report
