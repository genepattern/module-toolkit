import re
from typing import List
from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv
from .models import ModulePlan, configured_llm_model


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

**GenePattern Naming Conventions:**
- **Module Names**: Must be in CamelCase (starting with a capital letter). Only alphanumeric characters 
  and periods are allowed. Periods are used exclusively for module suites (e.g., Salmon.Indexer, Salmon.Quant).
  Examples: Kallisto, Trimmomatic, DESeq2.Normalize
- **Parameter Names**: Must be lowercase with words separated by periods. Only alphanumeric characters 
  and periods are allowed. Examples: input.file, fragment.length, max.threads
- **Version Format**: Major versions (1, 2, 3) are production releases. Minor versions (1.1, 1.2, 5.2) 
  are beta releases.
- **LSID Format**: urn:lsid:broad.mit.edu:cancer.software.genepattern.module.analysis:<5-digit-id>:<version>
  Example: urn:lsid:broad.mit.edu:cancer.software.genepattern.module.analysis:00123:1

**Planning Methodology:**
1. Research the tool thoroughly using available resources
2. Analyze command-line interface and configuration options
3. Identify common use cases and workflows
4. Design intuitive parameter groupings following GenePattern conventions
5. Plan comprehensive testing and validation
6. Create detailed implementation roadmap

**Primary Output Format:**
Your main planning function should return structured data as a ModulePlan Pydantic model containing:
- Module metadata (name, description, author, language)
- Input file formats and categories
- Resource requirements (CPU cores, memory)
- Full unstructured plan text alongside structured data
- Wrapper script name and example command line
- Detailed parameter specifications with types, prefixes, constraints

Always prioritize comprehensive parameter analysis, accurate technical specifications, and strict 
adherence to GenePattern naming conventions.
"""

# Create agent with structured output support
planner_agent = Agent(configured_llm_model(), system_prompt=system_prompt, output_type=ModulePlan)


@planner_agent.tool
def create_structured_plan(context: RunContext[ModulePlan], tool_name: str, research_data: str = None) -> ModulePlan:
    """
    Create a comprehensive structured plan for a GenePattern module based on tool analysis.

    Args:
        tool_name: Name of the bioinformatics tool to create a module for
        research_data: Optional research data from the researcher agent

    Returns:
        ModulePlan object with all structured information about the module
    """
    print(f"🎯 STRUCTURED PLANNING: Starting comprehensive planning for {tool_name}")

    # Use the analysis tools to gather structured information
    if research_data:
        parameter_analysis = analyze_parameter_structure(context, research_data, "")
        print("✅ STRUCTURED PLANNING: Parameter analysis completed")

    print("✅ STRUCTURED PLANNING: Analysis completed, creating structured plan...")

    # This function will be implemented by the LLM to return structured data
    # The LLM will analyze all available information and return a properly structured ModulePlan object

    # Placeholder return - the LLM will replace this with actual structured data
    return ModulePlan(
        module_name=tool_name,
        description="Comprehensive plan in progress - this will be populated by the LLM",
        author="Unknown",
        input_file_formats=["unknown"],
        language="unknown",
        categories=["unknown"],
        cpu_cores=1,
        memory="1GB",
        plan="Detailed planning findings will be compiled into a comprehensive plan",
        wrapper_script=f"{tool_name.lower()}_wrapper.py",
        command_line=f"python {tool_name.lower()}_wrapper.py --help",
        parameters=[]
    )


@planner_agent.tool
def analyze_parameter_structure(context: RunContext[ModulePlan], tool_help_text: str, command_examples: str = None) -> str:
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
def create_parameter_group_schema(context: RunContext[ModulePlan], parameters: List[str], group_strategy: str = "functional") -> str:
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
def validate_parameter_definition(context: RunContext[ModulePlan], param_name: str, param_type: str, constraints: str = None, default_value: str = None) -> str:
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


@planner_agent.tool
def validate_module_name(context: RunContext[ModulePlan], module_name: str) -> str:
    """
    Validate a GenePattern module name against naming conventions.

    Args:
        module_name: The proposed module name

    Returns:
        Validation report with pass/fail status and recommendations
    """
    print(f"🔍 PLANNER TOOL: Running validate_module_name for '{module_name}'")

    report = f"Module Name Validation Report: {module_name}\n"
    report += "=" * 50 + "\n\n"

    issues = []
    warnings = []

    # Check if name is empty
    if not module_name:
        issues.append("Module name cannot be empty")
        report += "❌ **Status: INVALID**\n\n"
        report += "**Issues:**\n"
        for issue in issues:
            report += f"  - {issue}\n"
        return report

    # Check CamelCase (must start with capital letter)
    if not module_name[0].isupper():
        issues.append("Module name must start with a capital letter (CamelCase)")

    # Check for valid characters (alphanumeric and periods only)
    if not re.match(r'^[A-Za-z0-9.]+$', module_name):
        issues.append("Module name may only contain alphanumeric characters and periods")
        invalid_chars = set(re.findall(r'[^A-Za-z0-9.]', module_name))
        if invalid_chars:
            issues.append(f"  Invalid characters found: {', '.join(sorted(invalid_chars))}")

    # Check period usage (should be for suite modules only)
    if '.' in module_name:
        parts = module_name.split('.')
        if len(parts) > 2:
            warnings.append("Module name has multiple periods - typically only one period is used for suite modules")

        # Each part should follow CamelCase
        for part in parts:
            if part and not part[0].isupper():
                issues.append(f"Each component of a suite module should start with capital letter: '{part}' in '{module_name}'")
            if not part:
                issues.append("Module name contains consecutive periods or starts/ends with a period")

        if len(parts) == 2:
            warnings.append(f"Module appears to be part of a suite: {parts[0]} suite with {parts[1]} functionality")

    # Check for common issues
    if '_' in module_name:
        issues.append("Module name should use CamelCase, not underscores (use 'MyModule' not 'My_Module')")

    if '-' in module_name:
        issues.append("Module name should not contain hyphens (use 'MyModule' not 'My-Module')")

    if module_name.islower():
        issues.append("Module name should be in CamelCase (e.g., 'Salmon' not 'salmon')")

    if module_name.isupper() and len(module_name) > 1:
        warnings.append("Module name is all uppercase - consider using CamelCase for readability")

    # Generate report
    if not issues:
        report += "✅ **Status: VALID**\n\n"
        report += f"Module name '{module_name}' follows GenePattern naming conventions.\n\n"
    else:
        report += "❌ **Status: INVALID**\n\n"
        report += "**Issues to Fix:**\n"
        for issue in issues:
            report += f"  - {issue}\n"
        report += "\n"

    if warnings:
        report += "⚠️  **Warnings:**\n"
        for warning in warnings:
            report += f"  - {warning}\n"
        report += "\n"

    report += "**Convention Reference:**\n"
    report += "  - Must start with a capital letter (CamelCase)\n"
    report += "  - Only alphanumeric characters and periods allowed\n"
    report += "  - Periods used exclusively for suite modules (e.g., Salmon.Indexer, Salmon.Quant)\n"
    report += "  - Examples: Kallisto, Trimmomatic, DESeq2.Normalize\n"

    print(f"✅ PLANNER TOOL: validate_module_name completed - {'VALID' if not issues else 'INVALID'}")
    return report


@planner_agent.tool
def validate_parameter_name(context: RunContext[ModulePlan], param_name: str) -> str:
    """
    Validate a GenePattern parameter name against naming conventions.

    Args:
        param_name: The proposed parameter name

    Returns:
        Validation report with pass/fail status and recommendations
    """
    print(f"🔍 PLANNER TOOL: Running validate_parameter_name for '{param_name}'")

    report = f"Parameter Name Validation Report: {param_name}\n"
    report += "=" * 50 + "\n\n"

    issues = []
    warnings = []

    # Check if name is empty
    if not param_name:
        issues.append("Parameter name cannot be empty")
        report += "❌ **Status: INVALID**\n\n"
        report += "**Issues:**\n"
        for issue in issues:
            report += f"  - {issue}\n"
        return report

    # Check for lowercase
    if not param_name.islower() or any(c.isupper() for c in param_name):
        # Allow exceptions for periods
        if not all(c.islower() or c == '.' or c.isdigit() for c in param_name):
            issues.append("Parameter name must be all lowercase")

    # Check for valid characters (alphanumeric and periods only)
    if not re.match(r'^[a-z0-9.]+$', param_name):
        issues.append("Parameter name may only contain lowercase alphanumeric characters and periods")
        invalid_chars = set(re.findall(r'[^a-z0-9.]', param_name))
        if invalid_chars:
            issues.append(f"  Invalid characters found: {', '.join(sorted(invalid_chars))}")

    # Check period usage (should separate words)
    if '.' in param_name:
        if param_name.startswith('.') or param_name.endswith('.'):
            issues.append("Parameter name should not start or end with a period")

        if '..' in param_name:
            issues.append("Parameter name should not contain consecutive periods")

        parts = param_name.split('.')
        for part in parts:
            if part and not part[0].isalpha():
                warnings.append(f"Word component '{part}' starts with a number - consider starting with a letter")

    # Check for common issues
    if '_' in param_name:
        issues.append("Parameter name should use periods to separate words, not underscores (use 'input.file' not 'input_file')")

    if '-' in param_name:
        issues.append("Parameter name should use periods to separate words, not hyphens (use 'max.threads' not 'max-threads')")

    if ' ' in param_name:
        issues.append("Parameter name should not contain spaces (use 'input.file' not 'input file')")

    # Check length
    if len(param_name) > 50:
        warnings.append(f"Parameter name is quite long ({len(param_name)} characters) - consider abbreviating")

    if len(param_name) < 2:
        warnings.append("Parameter name is very short - consider using a more descriptive name")

    # Generate report
    if not issues:
        report += "✅ **Status: VALID**\n\n"
        report += f"Parameter name '{param_name}' follows GenePattern naming conventions.\n\n"
    else:
        report += "❌ **Status: INVALID**\n\n"
        report += "**Issues to Fix:**\n"
        for issue in issues:
            report += f"  - {issue}\n"
        report += "\n"

    if warnings:
        report += "⚠️  **Warnings:**\n"
        for warning in warnings:
            report += f"  - {warning}\n"
        report += "\n"

    report += "**Convention Reference:**\n"
    report += "  - Must be all lowercase\n"
    report += "  - Only alphanumeric characters and periods allowed\n"
    report += "  - Use periods to separate words\n"
    report += "  - Examples: input.file, fragment.length, max.threads, output.dir\n"

    print(f"✅ PLANNER TOOL: validate_parameter_name completed - {'VALID' if not issues else 'INVALID'}")
    return report


@planner_agent.tool
def validate_version_format(context: RunContext[ModulePlan], version: str) -> str:
    """
    Validate a GenePattern module version format.

    Args:
        version: The proposed version string

    Returns:
        Validation report with version type (production/beta) and recommendations
    """
    print(f"🔍 PLANNER TOOL: Running validate_version_format for '{version}'")

    report = f"Version Format Validation Report: {version}\n"
    report += "=" * 50 + "\n\n"

    issues = []
    warnings = []
    version_type = None

    # Check if version is empty
    if not version:
        issues.append("Version cannot be empty")
        report += "❌ **Status: INVALID**\n\n"
        report += "**Issues:**\n"
        for issue in issues:
            report += f"  - {issue}\n"
        return report

    # Check version format (should be digits with optional decimal point)
    version_pattern = r'^\d+(\.\d+)?$'
    if not re.match(version_pattern, version):
        issues.append(f"Version must be in format 'X' or 'X.Y' where X and Y are integers")
        issues.append(f"  Examples: '1', '2', '1.1', '5.2'")
    else:
        # Determine version type
        if '.' in version:
            version_type = "beta"
            parts = version.split('.')
            major = int(parts[0])
            minor = int(parts[1])
            report += f"📦 **Version Type: BETA (Minor Release)**\n"
            report += f"   Major: {major}, Minor: {minor}\n\n"

            if minor == 0:
                warnings.append("Minor version is 0 - consider using major version format (e.g., '2' instead of '2.0')")
        else:
            version_type = "production"
            report += f"🚀 **Version Type: PRODUCTION (Major Release)**\n"
            report += f"   Version: {version}\n\n"

    # Additional checks
    if version.startswith('0') and len(version) > 1 and version[1] != '.':
        warnings.append("Version starts with leading zero (e.g., '01') - consider using '1' instead")

    if '.' in version and version.count('.') > 1:
        issues.append("Version should have at most one decimal point (e.g., '1.2' not '1.2.3')")

    # Generate report
    if not issues:
        report += "✅ **Status: VALID**\n\n"
        report += f"Version '{version}' follows GenePattern version format.\n\n"
    else:
        report += "❌ **Status: INVALID**\n\n"
        report += "**Issues to Fix:**\n"
        for issue in issues:
            report += f"  - {issue}\n"
        report += "\n"

    if warnings:
        report += "⚠️  **Warnings:**\n"
        for warning in warnings:
            report += f"  - {warning}\n"
        report += "\n"

    report += "**Convention Reference:**\n"
    report += "  - Major versions (1, 2, 3, etc.) are PRODUCTION releases\n"
    report += "  - Minor versions (1.1, 1.2, 5.2, etc.) are BETA releases\n"
    report += "  - Format: Single integer or integer.integer\n"

    print(f"✅ PLANNER TOOL: validate_version_format completed - {'VALID' if not issues else 'INVALID'}")
    return report


@planner_agent.tool
def validate_lsid_format(context: RunContext[ModulePlan], lsid: str) -> str:
    """
    Validate a GenePattern LSID (Life Science Identifier) format.

    Args:
        lsid: The proposed LSID string

    Returns:
        Validation report with parsed components and recommendations
    """
    print(f"🔍 PLANNER TOOL: Running validate_lsid_format for '{lsid}'")

    report = f"LSID Format Validation Report\n"
    report += "=" * 50 + "\n\n"

    issues = []
    warnings = []

    # Check if LSID is empty
    if not lsid:
        issues.append("LSID cannot be empty")
        report += "❌ **Status: INVALID**\n\n"
        report += "**Issues:**\n"
        for issue in issues:
            report += f"  - {issue}\n"
        return report

    # Expected format: urn:lsid:broad.mit.edu:cancer.software.genepattern.module.analysis:XXXXX:V
    lsid_pattern = r'^urn:lsid:broad\.mit\.edu:cancer\.software\.genepattern\.module\.analysis:(\d{5}):(\d+(?:\.\d+)?)$'
    match = re.match(lsid_pattern, lsid)

    if not match:
        issues.append("LSID does not match required format")
        report += "❌ **Status: INVALID**\n\n"

        # Provide detailed feedback on what's wrong
        if not lsid.startswith('urn:lsid:'):
            issues.append("  LSID must start with 'urn:lsid:'")

        if 'broad.mit.edu' not in lsid:
            issues.append("  LSID must include 'broad.mit.edu' authority")

        if 'cancer.software.genepattern.module.analysis' not in lsid:
            issues.append("  LSID must include 'cancer.software.genepattern.module.analysis' namespace")

        # Check module ID format
        parts = lsid.split(':')
        if len(parts) >= 5:
            module_id = parts[4] if len(parts) > 4 else ""
            if module_id and not re.match(r'^\d{5}$', module_id):
                issues.append(f"  Module ID must be exactly 5 digits (found: '{module_id}')")

        if len(parts) >= 6:
            version = parts[5] if len(parts) > 5 else ""
            if version and not re.match(r'^\d+(\.\d+)?$', version):
                issues.append(f"  Version must be in format 'X' or 'X.Y' (found: '{version}')")

        report += "**Issues to Fix:**\n"
        for issue in issues:
            report += f"  {issue}\n"
        report += "\n"
    else:
        # Parse components
        module_id = match.group(1)
        version = match.group(2)

        report += "✅ **Status: VALID**\n\n"
        report += f"**Parsed Components:**\n"
        report += f"  - Authority: broad.mit.edu\n"
        report += f"  - Namespace: cancer.software.genepattern.module.analysis\n"
        report += f"  - Module ID: {module_id}\n"
        report += f"  - Version: {version}\n\n"

        # Determine version type
        if '.' in version:
            report += f"  - Version Type: Beta (Minor Release)\n"
        else:
            report += f"  - Version Type: Production (Major Release)\n"
        report += "\n"

        # Check for warnings
        if module_id == "00000":
            warnings.append("Module ID is 00000 - this is typically a placeholder. Use actual assigned ID.")

        if int(module_id) > 99999:
            issues.append("Module ID exceeds 5 digits")

    if warnings:
        report += "⚠️  **Warnings:**\n"
        for warning in warnings:
            report += f"  - {warning}\n"
        report += "\n"

    report += "**LSID Format Reference:**\n"
    report += "  Format: urn:lsid:broad.mit.edu:cancer.software.genepattern.module.analysis:<5-digit-id>:<version>\n"
    report += "  - Module ID: Exactly 5 digits (e.g., 00123, 01234)\n"
    report += "  - Version: Integer or integer.integer (e.g., 1, 1.1, 5.2)\n"
    report += "  Example: urn:lsid:broad.mit.edu:cancer.software.genepattern.module.analysis:00123:1\n"

    print(f"✅ PLANNER TOOL: validate_lsid_format completed - {'VALID' if not issues else 'INVALID'}")
    return report


@planner_agent.tool
def validate_module_plan(context: RunContext[ModulePlan], plan: ModulePlan) -> str:
    """
    Validate a complete ModulePlan against all GenePattern conventions.

    Args:
        plan: The ModulePlan object to validate

    Returns:
        Comprehensive validation report covering all aspects of the plan
    """
    print(f"🔍 PLANNER TOOL: Running validate_module_plan for '{plan.module_name}'")

    report = f"Module Plan Validation Report: {plan.module_name}\n"
    report += "=" * 60 + "\n\n"

    all_issues = []
    all_warnings = []

    # Validate module name
    module_name_result = validate_module_name(context, plan.module_name)
    if "INVALID" in module_name_result:
        all_issues.append("Module name validation failed")

    # Validate all parameter names
    param_issues = []
    for param in plan.parameters:
        param_result = validate_parameter_name(context, param.name)
        if "INVALID" in param_result:
            param_issues.append(param.name)

    if param_issues:
        all_issues.append(f"Invalid parameter names: {', '.join(param_issues)}")

    # Check for other potential issues
    if not plan.description or len(plan.description) < 10:
        all_warnings.append("Module description is too short - provide detailed description")

    if not plan.author or plan.author == "Unknown":
        all_warnings.append("Module author should be specified")

    if plan.cpu_cores < 1:
        all_issues.append("CPU cores must be at least 1")

    if not plan.categories or plan.categories == ["unknown"]:
        all_warnings.append("Module categories should be specified")

    if not plan.parameters:
        all_warnings.append("Module has no parameters defined")

    # Generate summary report
    if not all_issues:
        report += "✅ **Overall Status: VALID**\n\n"
        report += f"Module plan '{plan.module_name}' passes all validation checks.\n\n"
    else:
        report += "❌ **Overall Status: ISSUES FOUND**\n\n"
        report += "**Critical Issues:**\n"
        for issue in all_issues:
            report += f"  - {issue}\n"
        report += "\n"

    if all_warnings:
        report += "⚠️  **Warnings:**\n"
        for warning in all_warnings:
            report += f"  - {warning}\n"
        report += "\n"

    report += "**Plan Summary:**\n"
    report += f"  - Module Name: {plan.module_name}\n"
    report += f"  - Parameters: {len(plan.parameters)}\n"
    report += f"  - Language: {plan.language}\n"
    report += f"  - CPU Cores: {plan.cpu_cores}\n"
    report += f"  - Memory: {plan.memory}\n"
    report += f"  - Categories: {', '.join(plan.categories)}\n\n"

    report += "**Detailed Validation Results:**\n"
    report += f"  - Module name: {'✅ Valid' if 'INVALID' not in module_name_result else '❌ Invalid'}\n"
    report += f"  - Parameter names: {'✅ All valid' if not param_issues else f'❌ {len(param_issues)} invalid'}\n"
    report += f"  - Description: {'✅ Present' if plan.description and len(plan.description) >= 10 else '⚠️  Needs improvement'}\n"
    report += f"  - Author: {'✅ Specified' if plan.author and plan.author != 'Unknown' else '⚠️  Not specified'}\n"

    print(f"✅ PLANNER TOOL: validate_module_plan completed - {'VALID' if not all_issues else 'ISSUES FOUND'}")
    return report

