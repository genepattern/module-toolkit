import re
from typing import Dict, Any, List
from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv
from agents.models import configured_llm_model


# Load environment variables from .env file
load_dotenv()


system_prompt = """
You are an expert GenePattern platform specialist with deep knowledge of module development 
and metadata management. Your task is to generate accurate, compliant manifest data that 
properly defines GenePattern modules according to platform specifications.

CRITICAL: When asked to generate a manifest, you MUST call the create_manifest tool and return 
its result directly. Do not add explanations or additional text after calling the tool.

Key requirements for GenePattern module manifests:
- Include all required keys: LSID, name, commandLine
- Generate valid LSIDs following urn:lsid format
- Create clear, descriptive module names and descriptions
- Design proper command line templates with parameter placeholders
- Set appropriate module categories and properties
- Follow GenePattern naming conventions and best practices

Manifest Key Guidelines:
- LSID: Must follow format urn:lsid:authority:namespace:object:revision
- name: Clear, descriptive module name (use dots/underscores as needed)
- description: Concise explanation of module purpose and functionality
- commandLine: Template with parameter placeholders like <input.file>
- version: Semantic version (e.g., 1.0.0)
- author: Module author information
- categories: Semicolon-separated category list

Command Line Template Rules:
- Use angle brackets for parameters: <parameter.name>
- Include proper file extensions and paths
- Handle input/output file routing correctly
- Support both required and optional parameters
- Follow platform execution patterns

When generating manifests, use the create_manifest tool which will handle all the formatting
and structure requirements. Always return structured data that can be validated.
"""

# Create agent without MCP toolsets - validation happens separately via generate-module.py
manifest_agent = Agent(configured_llm_model(), system_prompt=system_prompt)


@manifest_agent.tool
def validate_manifest(context: RunContext[str], path: str) -> str:
    """
    Validate GenePattern manifest files.

    This tool validates GenePattern module manifest files to ensure they conform
    to the required format and contain all necessary metadata for module execution.

    Args:
        path: Path to the manifest file or directory containing a manifest file.
              Can be a specific manifest.json file or a directory that contains one.

    Returns:
        A string containing the validation results, indicating whether the manifest
        passed or failed validation along with detailed error messages if applicable.
    """
    import io
    import sys
    from contextlib import redirect_stderr, redirect_stdout
    import traceback

    print(f"🔍 MANIFEST TOOL: Running validate_manifest on '{path}'")

    try:
        import manifest.linter

        argv = [path]
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exit_code = manifest.linter.main(argv)

            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Manifest validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Manifest validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
    except Exception as e:
        error_msg = f"Error running manifest linter: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ MANIFEST TOOL: {error_msg}")
        return error_msg


@manifest_agent.tool
def analyze_module_metadata(context: RunContext[str], tool_name: str, tool_info: Dict[str, Any], parameters: List[Dict[str, Any]] = None) -> str:
    """
    Analyze module information to determine appropriate manifest metadata and structure.
    
    Args:
        tool_name: Name of the bioinformatics tool being wrapped
        tool_info: Dictionary with tool information (description, language, version, etc.)
        parameters: List of parameter definitions for the module
    
    Returns:
        Analysis of manifest requirements with suggested key-value pairs
    """
    print(f"📋 MANIFEST TOOL: Running analyze_module_metadata for '{tool_name}' with {len(parameters or [])} parameters")
    
    analysis = f"Manifest Metadata Analysis for {tool_name}:\n"
    analysis += "=" * 50 + "\n\n"
    
    # Extract tool information
    description = tool_info.get('description', f'GenePattern module for {tool_name}')
    language = tool_info.get('language', 'unknown')
    version = tool_info.get('version', '1.0.0')
    repository = tool_info.get('repository_url', '')
    
    # Analyze module categorization
    categories = []
    tool_lower = tool_name.lower()
    desc_lower = description.lower()
    
    # Common bioinformatics categories
    if any(term in tool_lower or term in desc_lower for term in ['align', 'mapping', 'bwa', 'bowtie', 'star']):
        categories.append('Sequence.Alignment')
    elif any(term in tool_lower or term in desc_lower for term in ['variant', 'snp', 'mutation', 'gatk']):
        categories.append('Sequence.VariantCalling')
    elif any(term in tool_lower or term in desc_lower for term in ['rna', 'expression', 'deseq', 'edger']):
        categories.append('Expression.Analysis')
    elif any(term in tool_lower or term in desc_lower for term in ['quality', 'qc', 'fastqc', 'trim']):
        categories.append('Sequence.QualityControl')
    elif any(term in tool_lower or term in desc_lower for term in ['assembly', 'contig', 'scaffold']):
        categories.append('Sequence.Assembly')
    elif any(term in tool_lower or term in desc_lower for term in ['annotation', 'predict', 'gene']):
        categories.append('Sequence.Annotation')
    else:
        categories.append('Utilities')
    
    # Suggest LSID format
    lsid_object = re.sub(r'[^a-zA-Z0-9]', '', tool_name.lower())
    suggested_lsid = f"urn:lsid:genepattern.org:module.analysis:{lsid_object}:1"
    
    # Suggest module name format
    suggested_name = re.sub(r'[^a-zA-Z0-9._-]', '', tool_name.replace(' ', '_'))
    
    # Analyze command line structure
    command_line_analysis = ""
    if parameters:
        # Categorize parameters
        input_files = [p for p in parameters if p.get('type') == 'File' and 'input' in p.get('name', '').lower()]
        output_params = [p for p in parameters if 'output' in p.get('name', '').lower()]
        required_params = [p for p in parameters if p.get('required', False)]
        optional_params = [p for p in parameters if not p.get('required', False)]
        
        command_line_analysis = f"""
**Command Line Structure Analysis:**
- Input files: {len(input_files)} parameters
- Output parameters: {len(output_params)} parameters  
- Required parameters: {len(required_params)} total
- Optional parameters: {len(optional_params)} total

**Suggested Command Template Pattern:**
"""
        
        # Build basic command structure
        if language.lower() == 'python':
            command_line_analysis += "python <wrapper_script> "
        elif language.lower() == 'r':
            command_line_analysis += "Rscript <wrapper_script> "
        elif language.lower() == 'java':
            command_line_analysis += "java -jar <tool_jar> "
        else:
            command_line_analysis += f"{tool_name} "
        
        # Add parameter placeholders
        for param in required_params[:5]:  # Show first 5 required
            param_name = param.get('name', 'param')
            command_line_analysis += f"<{param_name}> "
        
        if len(required_params) > 5:
            command_line_analysis += f"... (+{len(required_params) - 5} more required) "
        
        if optional_params:
            command_line_analysis += f"[optional parameters]"
    
    # Generate analysis output
    analysis += f"**Suggested Manifest Keys:**\n\n"
    analysis += f"LSID: {suggested_lsid}\n"
    analysis += f"name: {suggested_name}\n"
    analysis += f"description: {description}\n"
    analysis += f"version: {version}\n"
    analysis += f"categories: {';'.join(categories)}\n"
    
    if repository:
        analysis += f"documentationUrl: {repository}\n"
    
    analysis += f"\n**Module Classification:**\n"
    analysis += f"- Primary category: {categories[0] if categories else 'Utilities'}\n"
    analysis += f"- Additional categories: {';'.join(categories[1:]) if len(categories) > 1 else 'None'}\n"
    analysis += f"- Language/Platform: {language.title()}\n"
    
    if command_line_analysis:
        analysis += f"\n{command_line_analysis}\n"
    
    analysis += f"\n**LSID Guidelines:**\n"
    analysis += f"- Authority: genepattern.org (standard)\n"
    analysis += f"- Namespace: module.analysis (for analysis modules)\n"
    analysis += f"- Object: {lsid_object} (derived from tool name)\n"
    analysis += f"- Revision: 1 (initial version)\n"
    
    analysis += f"\n**Recommendations:**\n"
    analysis += f"- Ensure module name follows GenePattern conventions\n"
    analysis += f"- Verify command line template includes all required parameters\n"
    analysis += f"- Test command line substitution with sample values\n"
    analysis += f"- Consider adding optional author and contact information\n"
    
    print("✅ MANIFEST TOOL: analyze_module_metadata completed successfully")
    return analysis


@manifest_agent.tool
def generate_manifest_content(context: RunContext[str], manifest_data: Dict[str, str]) -> str:
    """
    Generate a complete manifest file content from provided key-value data.
    
    Args:
        manifest_data: Dictionary of manifest keys and values
    
    Returns:
        Complete manifest file content in proper key=value format
    """
    print(f"📝 MANIFEST TOOL: Running generate_manifest_content with {len(manifest_data)} key-value pairs")
    
    if not manifest_data:
        print("❌ MANIFEST TOOL: generate_manifest_content failed - no manifest data provided")
        return "Error: No manifest data provided for generation"
    
    # Required keys for validation
    required_keys = ['LSID', 'name', 'commandLine']
    missing_required = [key for key in required_keys if key not in manifest_data]
    
    if missing_required:
        error_msg = f"Missing required keys: {', '.join(missing_required)}"
        print(f"❌ MANIFEST TOOL: generate_manifest_content failed - {error_msg}")
        return f"Error: {error_msg}"
    
    # Standard key order for better readability
    key_order = [
        'LSID',
        'name', 
        'description',
        'version',
        'author',
        'commandLine',
        'categories',
        'documentationUrl',
        'publicationUrl',
        'requiredGenePatternVersion',
        'cpuType',
        'os',
        'language'
    ]
    
    # Generate manifest content
    manifest_lines = []
    manifest_lines.append("# GenePattern Module Manifest")
    manifest_lines.append("# Generated automatically - do not edit manually")
    manifest_lines.append("")
    
    # Add keys in preferred order
    used_keys = set()
    for key in key_order:
        if key in manifest_data:
            value = str(manifest_data[key]).strip()
            if value:  # Only add non-empty values
                manifest_lines.append(f"{key}={value}")
                used_keys.add(key)
    
    # Add any remaining keys not in the standard order
    remaining_keys = sorted(set(manifest_data.keys()) - used_keys)
    if remaining_keys:
        manifest_lines.append("")
        manifest_lines.append("# Additional properties")
        for key in remaining_keys:
            value = str(manifest_data[key]).strip()
            if value:
                manifest_lines.append(f"{key}={value}")
    
    manifest_content = "\n".join(manifest_lines)
    
    # Generate summary
    result = f"Generated manifest content:\n"
    result += "=" * 30 + "\n\n"
    result += manifest_content + "\n\n"
    result += f"**Summary:**\n"
    result += f"- Total properties: {len([k for k, v in manifest_data.items() if str(v).strip()])}\n"
    result += f"- Required keys: {', '.join(required_keys)} ✓\n"
    result += f"- Optional keys: {len(manifest_data) - len(required_keys)}\n"
    
    # Validation reminders
    result += f"\n**Notes:**\n"
    result += "- Verify LSID format follows urn:lsid convention\n"
    result += "- Test command line template with actual parameter values\n"
    result += "- Ensure module name follows GenePattern naming rules\n"
    result += "- Validate manifest using the manifest linter\n"
    
    print("✅ MANIFEST TOOL: generate_manifest_content completed successfully")
    return result


@manifest_agent.tool
def optimize_command_line_template(context: RunContext[str], current_command: str, parameters: List[Dict[str, Any]], tool_info: Dict[str, Any] = None) -> str:
    """
    Analyze and optimize a command line template for better GenePattern integration.
    
    Args:
        current_command: Current command line template
        parameters: List of parameter definitions
        tool_info: Optional tool information for context
    
    Returns:
        Analysis and optimized command line template suggestions
    """
    print(f"⚡ MANIFEST TOOL: Running optimize_command_line_template (command length: {len(current_command)} chars, {len(parameters)} parameters)")
    
    if not current_command.strip():
        print("❌ MANIFEST TOOL: optimize_command_line_template failed - empty command provided")
        return "Error: No command line template provided"
    
    analysis = "Command Line Template Optimization:\n"
    analysis += "=" * 40 + "\n\n"
    
    analysis += f"**Current Command:**\n{current_command}\n\n"
    
    # Analyze current command structure
    param_placeholders = re.findall(r'<([^>]+)>', current_command)
    analysis += f"**Current Analysis:**\n"
    analysis += f"- Parameter placeholders found: {len(param_placeholders)}\n"
    analysis += f"- Total parameters defined: {len(parameters)}\n"
    
    if param_placeholders:
        analysis += f"- Placeholders: {', '.join(param_placeholders[:5])}"
        if len(param_placeholders) > 5:
            analysis += f" (+{len(param_placeholders) - 5} more)"
        analysis += "\n"
    
    # Check parameter coverage
    param_names = [p.get('name', '') for p in parameters]
    missing_params = [name for name in param_names if name not in param_placeholders]
    extra_placeholders = [ph for ph in param_placeholders if ph not in param_names]
    
    issues = []
    suggestions = []
    
    if missing_params:
        issues.append(f"Missing parameter placeholders: {', '.join(missing_params[:5])}")
        suggestions.append("Add missing parameter placeholders to command line")
    
    if extra_placeholders:
        issues.append(f"Undefined placeholders: {', '.join(extra_placeholders[:5])}")
        suggestions.append("Remove undefined placeholders or add corresponding parameters")
    
    # Check for common patterns and best practices
    if not re.search(r'<[^>]*input[^>]*>', current_command, re.IGNORECASE):
        suggestions.append("Consider adding explicit input file parameter")
    
    if not re.search(r'<[^>]*output[^>]*>', current_command, re.IGNORECASE):
        suggestions.append("Consider adding explicit output parameter")
    
    # Language-specific optimizations
    if tool_info:
        language = tool_info.get('language', '').lower()
        tool_name = tool_info.get('name', '')
        
        if language == 'python' and not current_command.strip().startswith('python'):
            suggestions.append("Consider starting command with 'python' for Python tools")
        elif language == 'r' and not current_command.strip().startswith('Rscript'):
            suggestions.append("Consider starting command with 'Rscript' for R tools")
        elif language == 'java' and 'java' not in current_command.lower():
            suggestions.append("Consider including Java execution for Java tools")
    
    # Generate optimized command suggestion
    if parameters:
        analysis += f"\n**Optimization Suggestions:**\n"
        
        if issues:
            analysis += "Issues found:\n"
            for issue in issues:
                analysis += f"  - {issue}\n"
            analysis += "\n"
        
        if suggestions:
            analysis += "Recommendations:\n"
            for suggestion in suggestions:
                analysis += f"  - {suggestion}\n"
            analysis += "\n"
        
        # Generate improved template
        analysis += "**Suggested Optimized Command:**\n"
        
        # Build improved command based on analysis
        optimized_parts = []
        
        # Add language-specific prefix if needed
        if tool_info:
            language = tool_info.get('language', '').lower()
            if language == 'python':
                optimized_parts.append("python <wrapper.script>")
            elif language == 'r':
                optimized_parts.append("Rscript <wrapper.script>")
            elif language == 'java':
                optimized_parts.append("java -jar <tool.jar>")
            else:
                optimized_parts.append(current_command.split()[0] if current_command.split() else tool_info.get('name', 'tool'))
        
        # Add parameter placeholders in logical order
        input_params = [p for p in parameters if 'input' in p.get('name', '').lower()]
        output_params = [p for p in parameters if 'output' in p.get('name', '').lower()]
        other_required = [p for p in parameters if p.get('required', False) and p not in input_params + output_params]
        optional_params = [p for p in parameters if not p.get('required', False)]
        
        # Add parameters in order: inputs, required, outputs, optional
        for param_group in [input_params, other_required, output_params]:
            for param in param_group:
                param_name = param.get('name', 'param')
                optimized_parts.append(f"<{param_name}>")
        
        # Add optional parameters with indication
        if optional_params:
            optimized_parts.append("[optional parameters]")
        
        optimized_command = " ".join(optimized_parts)
        analysis += f"{optimized_command}\n\n"
    
    # Best practices
    analysis += "**Best Practices:**\n"
    analysis += "- Use descriptive parameter names in placeholders\n"
    analysis += "- Order parameters logically (inputs, processing, outputs)\n"
    analysis += "- Include file extensions in parameter names when relevant\n"
    analysis += "- Test command line substitution before deployment\n"
    analysis += "- Consider platform-specific path handling\n"
    
    print("✅ MANIFEST TOOL: optimize_command_line_template completed successfully")
    return analysis


@manifest_agent.tool
def create_manifest(context: RunContext[str], tool_info: Dict[str, Any] = None, planning_data: Dict[str, Any] = None, error_report: str = "", attempt: int = 1) -> Dict[str, Any]:
    """
    Generate a complete manifest file for the GenePattern module.
    
    Args:
        tool_info: Dictionary with tool information (name, version, language, description)
        planning_data: Planning phase results with parameters and context
        error_report: Optional error feedback from previous validation attempts
        attempt: Attempt number for retry logic
    
    Returns:
        Dictionary with manifest fields ready to be converted to ManifestModel
    """
    print(f"📋 MANIFEST TOOL: Running create_manifest (attempt {attempt})")
    
    # Handle string inputs from agent calls and parse planning_data
    import re
    import json
    import ast

    try:
        # Extract tool information including instructions
        tool_name = tool_info.get('name', 'unknown') if tool_info else 'unknown'
        tool_instructions = tool_info.get('instructions', '') if tool_info else ''

        if tool_instructions:
            print(f"✓ User provided instructions: {tool_instructions[:100]}...")

        # Parse planning_data to extract structured information
        planning_dict = {}
        if planning_data:
            # Handle both dict and string inputs
            if isinstance(planning_data, dict):
                planning_dict = planning_data
                print("✓ Using planning_data as dict")
            elif isinstance(planning_data, str):
                # Try multiple parsing strategies
                try:
                    planning_dict = json.loads(planning_data)
                    print("✓ Parsed planning_data as JSON")
                except:
                    try:
                        planning_dict = ast.literal_eval(planning_data)
                        print("✓ Parsed planning_data as Python literal")
                    except:
                        try:
                            # More robust quote replacement
                            fixed = planning_data.replace("'", '"')
                            # Handle None, True, False
                            fixed = fixed.replace('None', 'null').replace('True', 'true').replace('False', 'false')
                            planning_dict = json.loads(fixed)
                            print("✓ Parsed planning_data as fixed JSON")
                        except Exception as e:
                            print(f"⚠️ MANIFEST TOOL: All parsing strategies failed: {str(e)[:100]}")
                            planning_dict = {}

        # Extract tool info - handle both dict and string
        if isinstance(tool_info, dict):
            tool_name = tool_info.get('name', 'UnknownTool')
            tool_version = tool_info.get('version', '1.0')
            tool_language = tool_info.get('language', 'unknown')
            tool_description = tool_info.get('description', 'Bioinformatics analysis tool')
        elif isinstance(tool_info, str):
            # Try to parse as dict first
            try:
                if tool_info.startswith('{'):
                    tool_info_dict = ast.literal_eval(tool_info)
                    tool_name = tool_info_dict.get('name', 'UnknownTool')
                    tool_version = tool_info_dict.get('version', '1.0')
                    tool_language = tool_info_dict.get('language', 'unknown')
                    tool_description = tool_info_dict.get('description', 'Bioinformatics analysis tool')
                else:
                    raise ValueError("Not a dict")
            except:
                # Fall back to regex
                tool_name = re.search(r"'name':\s*'([^']+)'", tool_info)
                tool_name = tool_name.group(1) if tool_name else "UnknownTool"

                tool_version = re.search(r"'version':\s*'([^']+)'", tool_info)
                tool_version = tool_version.group(1) if tool_version else "1.0"

                tool_language = re.search(r"'language':\s*'([^']+)'", tool_info)
                tool_language = tool_language.group(1) if tool_language else "unknown"

                tool_description = re.search(r"'description':\s*'([^']+)'", tool_info)
                tool_description = tool_description.group(1) if tool_description else "Bioinformatics analysis tool"
        else:
            tool_name = "UnknownTool"
            tool_version = "1.0"
            tool_language = "unknown"
            tool_description = "Bioinformatics analysis tool"
        
        # USE PLANNING DATA - Override with planning data if available
        if planning_dict:
            # Use module_name from planning_data if available
            if 'module_name' in planning_dict and planning_dict['module_name']:
                tool_name = planning_dict['module_name']
                print(f"✓ Using module_name from planning_data: {tool_name}")

            # Use description from planning_data if available
            if 'description' in planning_dict and planning_dict['description']:
                tool_description = planning_dict['description']
                print(f"✓ Using description from planning_data")

            # Use author from planning_data if available
            author = planning_dict.get('author', 'GenePattern Module Toolkit')
            print(f"✓ Using author from planning_data: {author}")

            # Use categories from planning_data if available
            categories = planning_dict.get('categories', ['Bioinformatics', 'Analysis'])
            if isinstance(categories, list):
                categories_str = ';'.join(categories)
            else:
                categories_str = str(categories)
            print(f"✓ Using categories from planning_data: {categories_str}")

            # Use wrapper_script from planning_data if available
            wrapper_script = planning_dict.get('wrapper_script', 'wrapper.R')
            print(f"✓ Using wrapper_script from planning_data: {wrapper_script}")

            # Use command_line from planning_dict if available
            if 'command_line' in planning_dict and planning_dict['command_line']:
                command_line_from_plan = planning_dict['command_line']
                # Convert example command line to use parameter placeholders
                # Example: "Rscript wrapper.R --geo.accession=GSE12345" -> "Rscript wrapper.R <geo.accession>"
                command_line = command_line_from_plan

                # Replace --param=value patterns with <param>
                if 'parameters' in planning_dict and planning_dict['parameters']:
                    for param in planning_dict['parameters']:
                        param_name = param.get('name', '')
                        if param_name:
                            # Match patterns like --geo.accession=GSE12345 or --geo.accession GSE12345
                            pattern1 = rf'--{re.escape(param_name)}=[^\s]+'
                            pattern2 = rf'--{re.escape(param_name)}\s+[^\s-]+'
                            command_line = re.sub(pattern1, f'<{param_name}>', command_line)
                            command_line = re.sub(pattern2, f'<{param_name}>', command_line)

                print(f"✓ Using command_line from planning_data (converted to placeholders): {command_line}")
            else:
                # Build command line from wrapper_script and parameters
                command_line = f"<{wrapper_script}>"

                # Add parameters to command line if available
                if 'parameters' in planning_dict and planning_dict['parameters']:
                    params = planning_dict['parameters']
                    for param in params[:10]:  # Limit to avoid overly long command lines
                        param_name = param.get('name', 'param')
                        command_line += f" <{param_name}>"
                    print(f"✓ Built command_line from parameters: {command_line}")
                else:
                    command_line = f"<{wrapper_script}> <input.file> <output.prefix>"
                    print(f"⚠️ No parameters in planning_data, using generic command_line")

            # Use cpu_cores from planning_data if available (as cpuType hint)
            cpu_cores = planning_dict.get('cpu_cores', 1)
            print(f"✓ Using cpu_cores from planning_data: {cpu_cores}")

            # Use memory from planning_data if available
            memory = planning_dict.get('memory', '1GB')
            print(f"✓ Using memory from planning_data: {memory}")
        else:
            # Fallback values when no planning_data
            author = "GenePattern Module Toolkit"
            categories_str = "Bioinformatics;Analysis"
            wrapper_script = "wrapper.R" if tool_language == 'r' else "wrapper.py"
            command_line = f"<{wrapper_script}> <input.file> <output.prefix>"
            cpu_cores = 1
            memory = "1GB"
            print(f"⚠️ No planning_data available, using fallback values")

        # Add retry context if applicable
        if attempt > 1 and error_report:
            print(f"⚠️ Retry attempt {attempt} - previous error: {error_report[:100]}")

        # Generate LSID
        lsid_object = tool_name.lower().replace(' ', '').replace('.', '').replace('_', '')
        lsid = f"urn:lsid:genepattern.org:module.analysis:{lsid_object}:1"

        # Return structured dictionary that can be converted to ManifestModel
        manifest_dict = {
            "name": tool_name,
            "LSID": lsid,
            "version": tool_version,
            "description": tool_description,
            "author": author,
            "categories": categories_str,
            "commandLine": command_line,
            "language": tool_language,
            "os": "any",
            "cpuType": "any",
            "taskDoc": "README.md",
            "fileFormat": "",
            "privacy": "public",
            "quality": "development",
            "job.cpuCount": str(cpu_cores),
            "job.memory": memory,
            "artifact_report": f"Generated manifest for {tool_name} module with {len(command_line.split())} command components",
            "artifact_status": "success"
        }

        print("✅ MANIFEST TOOL: create_manifest completed successfully")
        return manifest_dict

    except Exception as e:
        error_msg = f"Error in create_manifest: {str(e)}"
        print(f"❌ MANIFEST TOOL: create_manifest failed: {error_msg}")
        import traceback
        traceback_str = traceback.format_exc()
        print(f"Traceback: {traceback_str}")

        # Return a minimal valid manifest dict with error details
        return {
            "name": "UnknownTool",
            "LSID": "urn:lsid:genepattern.org:module.analysis:unknowntool:1",
            "version": "1.0",
            "description": "Bioinformatics analysis tool",
            "commandLine": "<wrapper.py> <input.file> <output.prefix>",
            "artifact_report": f"Error during manifest generation: {error_msg}\n\nTraceback:\n{traceback_str}",
            "artifact_status": "error"
        }
