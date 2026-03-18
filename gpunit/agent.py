import yaml
from typing import Dict, Any, List
from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv
from agents.models import configured_llm_model


# Load environment variables from .env file
load_dotenv()


system_prompt = """
You are an expert GenePattern platform developer specializing in automated module testing.
Your sole task is to generate EXACTLY ONE GPUnit test file (test.yml) for a GenePattern module.

Key rules:
- Generate ONE and ONLY ONE test — not a suite, not multiple files, not multiple YAML documents
- The single test should cover the most important basic functionality using required parameters only
- Do NOT call create_gpunit more than once
- Do NOT use optional parameters unless they are needed to make the test run
- Do NOT generate error-condition or edge-case tests — basic happy-path only

GPUnit Test Structure:
- name: Descriptive test name explaining what is being tested
- module: Module name being tested
- params: Dictionary of REQUIRED parameter values only
- assertions: diffCmd and file existence checks

Always call the create_gpunit tool once to produce the single test.yml content, then
call validate_gpunit to check it. If validation fails, call create_gpunit once more with
the corrected values. Do not loop further.
"""

# Create agent without MCP dependency
gpunit_agent = Agent(configured_llm_model(), system_prompt=system_prompt)


@gpunit_agent.tool
def validate_gpunit(context: RunContext[str], path: str, module: str = None, parameters: List[str] = None) -> str:
    """
    Validate GPUnit test definition YAML files.

    This tool validates GPUnit YAML files that define automated tests for GenePattern
    modules. GPUnit tests ensure modules work correctly by running them with known
    inputs and verifying expected outputs.

    Args:
        path: Path to the GPUnit YAML file to validate. The file should contain
              test definitions with input parameters, expected outputs, and
              validation criteria.
        module: Optional expected module name that the GPUnit test should target.
               If provided, validates that the test file correctly references
               this module and its interface.
        parameters: Optional list of parameter names that should be tested.
                   If provided, validates that the GPUnit test covers all
                   specified parameters with appropriate test cases.

    Returns:
        A string containing the validation results, indicating whether the GPUnit
        test file is properly structured and contains valid test definitions,
        along with any syntax or logic errors.
    """
    import io
    import sys
    from contextlib import redirect_stderr, redirect_stdout
    import traceback

    print(f"🔍 GPUNIT TOOL: Running validate_gpunit on '{path}'")

    try:
        import gpunit.linter

        argv = [path]
        if module:
            argv.extend(["--module", module])
        if parameters and isinstance(parameters, list):
            argv.extend(["--parameters"] + parameters)

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exit_code = gpunit.linter.main(argv)

            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"GPUnit validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"GPUnit validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
    except Exception as e:
        error_msg = f"Error running gpunit linter: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ GPUNIT TOOL: {error_msg}")
        return error_msg


@gpunit_agent.tool
def create_gpunit(context: RunContext[str]) -> str:
    """
    Generate a comprehensive GPUnit test definition (test.yml) for the GenePattern module.
    
    Args:
        context: RunContext with dependencies containing tool_info, planning_data, error_report, and attempt

    Returns:
        Complete GPUnit YAML content ready for validation

    Note: This tool is configured to generate exactly one GPUnit test file. It will not create
    multiple tests or test suites. The generated test will focus on basic functionality using
    required parameters only.
    """
    # Extract data from context dependencies
    tool_info = context.deps.get('tool_info', {})
    planning_data = context.deps.get('planning_data', {})
    error_report = context.deps.get('error_report', '')
    attempt = context.deps.get('attempt', 1)

    print(f"🧪 GPUNIT TOOL: Running create_gpunit for '{tool_info.get('name', 'unknown')}' (attempt {attempt})")
    
    try:
        # Extract tool information including instructions
        tool_name = tool_info.get('name', 'unknown')
        tool_instructions = tool_info.get('instructions', '')

        if tool_instructions:
            print(f"✓ User provided instructions: {tool_instructions[:100]}...")

        # USE PLANNING DATA - Extract comprehensive test information
        parameters = planning_data.get('parameters', []) if planning_data else []
        input_formats = planning_data.get('input_file_formats', []) if planning_data else []
        description = planning_data.get('description', '') if planning_data else ''
        cpu_cores = planning_data.get('cpu_cores', 1) if planning_data else 1
        memory = planning_data.get('memory', '2GB') if planning_data else '2GB'
        wrapper_script = planning_data.get('wrapper_script', 'wrapper.py') if planning_data else 'wrapper.py'
        module_name = planning_data.get('module_name', tool_name) if planning_data else tool_name

        # IMPORTANT: Use LSID from planning_data
        module_lsid = planning_data.get('lsid', f"urn:lsid:genepattern.org:module.analysis:{tool_name.lower().replace(' ', '').replace('-', '')}:1") if planning_data else f"urn:lsid:genepattern.org:module.analysis:{tool_name.lower().replace(' ', '').replace('-', '')}:1"

        # Log planning data usage
        print(f"✓ Using {len(parameters)} parameters from planning_data")
        print(f"✓ Using module LSID from planning_data: {module_lsid}")
        if input_formats:
            print(f"✓ Using input_file_formats from planning_data: {input_formats}")
        if description:
            print(f"✓ Using description from planning_data for test naming")
        print(f"✓ Using resource requirements: {cpu_cores} cores, {memory}")
        print(f"✓ Using wrapper_script: {wrapper_script}")

        # Determine primary file extension from input_file_formats
        primary_extension = 'txt'  # Default
        if input_formats:
            # Use first format, strip leading dot if present
            primary_extension = input_formats[0].lstrip('.')
            print(f"✓ Using primary file extension for test data: .{primary_extension}")

        # Build test parameters ONLY for REQUIRED parameters
        test_params = {}
        test_description_hints = []

        # Filter to only required parameters
        required_params = [p for p in parameters if p.get('required', False)]
        print(f"✓ Including only {len(required_params)} required parameters (out of {len(parameters)} total)")

        for param in required_params:
            param_name = param.get('name', 'unknown')
            param_type = param.get('type', 'text')
            # Normalize param_type to lowercase for case-insensitive comparison
            param_type_lower = param_type.lower() if isinstance(param_type, str) else 'text'
            param_desc = param.get('description', '')

            # Generate sample values based on parameter type with format awareness
            if param_type_lower == 'file':
                # Use input_file_formats for file parameters
                if 'input' in param_name.lower():
                    test_params[param_name] = f"test_data/sample_input.{primary_extension}"
                    test_description_hints.append(f"input format: {primary_extension}")
                elif 'output' in param_name.lower():
                    # Output files - try to infer format from parameter name
                    if 'prefix' in param_name.lower() or 'name' in param_name.lower():
                        test_params[param_name] = "test_output"
                    else:
                        test_params[param_name] = f"test_data/output.{primary_extension}"
                elif 'index' in param_name.lower() or 'reference' in param_name.lower():
                    test_params[param_name] = f"test_data/reference_index"
                else:
                    test_params[param_name] = f"test_data/sample.{primary_extension}"

            elif param_type_lower == 'choice':
                choices = param.get('choices', ['default'])
                # Extract actual choice values if they're ChoiceOption objects
                if choices and isinstance(choices[0], dict):
                    test_params[param_name] = choices[0].get('value', 'default')
                else:
                    test_params[param_name] = choices[0] if choices else 'default'
                test_description_hints.append(f"choice: {test_params[param_name]}")

            elif param_type_lower == 'integer':
                # Use cpu_cores for thread/core related parameters
                if any(keyword in param_name.lower() for keyword in ['thread', 'core', 'cpu', 'proc']):
                    test_params[param_name] = str(min(cpu_cores, 2))  # Use planning cores but cap for tests
                    test_description_hints.append(f"threads: {test_params[param_name]}")
                else:
                    test_params[param_name] = param.get('default_value', '10')

            elif param_type_lower == 'float':
                test_params[param_name] = param.get('default_value', '0.05')

            else:  # Text/String or any other type
                test_params[param_name] = param.get('default_value', 'test_value')

        # Ensure params is never empty - add a default parameter if needed
        if not test_params:
            print("⚠️  No required parameters found, adding default input.file parameter")
            test_params['input.file'] = f"test_data/sample.{primary_extension}"

        # Generate test name from description or tool name
        test_scenario = "Basic Functionality Test"
        if description:
            # Extract key terms from description for test name
            desc_lower = description.lower()
            if 'alignment' in desc_lower:
                test_scenario = "Alignment Test"
            elif 'quantif' in desc_lower:
                test_scenario = "Quantification Test"
            elif 'quality' in desc_lower or 'qc' in desc_lower:
                test_scenario = "Quality Control Test"
            elif 'expression' in desc_lower:
                test_scenario = "Expression Analysis Test"
            elif 'variant' in desc_lower:
                test_scenario = "Variant Calling Test"

        # Generate GPUnit YAML content - SINGLE TEST ONLY
        gpunit_content = f"""# GPUnit test for {module_name}
# Generated from planning data - {', '.join(test_description_hints[:3]) if test_description_hints else 'basic test'}
# Resource requirements: {cpu_cores} CPU cores, {memory} memory
# NOTE: This is a single test with required parameters only
name: "{module_name} - {test_scenario}"
module: {module_name}
params:
"""

        # Add parameters
        for param_name, param_value in test_params.items():
            gpunit_content += f"  {param_name}: \"{param_value}\"\n"

        # Generate assertions based on expected outputs
        # Try to identify output file parameters
        output_files = []
        for param in required_params:
            param_name = param.get('name', 'unknown')
            param_type = param.get('type', 'Text')

            if 'output' in param_name.lower():
                if param_type == 'File':
                    output_files.append(test_params.get(param_name, 'output.txt'))
                elif 'prefix' in param_name.lower():
                    # If it's an output prefix, add common output extensions
                    prefix = test_params.get(param_name, 'output')
                    output_files.append(f"{prefix}.txt")

        # Add assertions
        gpunit_content += """
assertions:
  diffCmd: diff <%gpunit.diffStripTrailingCR%> -q
"""

        # Add file assertions based on detected outputs
        if output_files:
            gpunit_content += "  files:\n"
            for output_file in output_files[:3]:  # Limit to first 3 to avoid overly complex tests
                # Clean up the filename
                filename = output_file.replace('test_data/', '')
                gpunit_content += f"""    "{filename}":
      diff: "expected/{filename}"
"""
        else:
            # Default output assertion
            gpunit_content += """  files:
    "output.txt":
      diff: "expected/output.txt"
"""

        # Add retry context if applicable
        if attempt > 1 and error_report:
            print(f"⚠️  Retry attempt {attempt} - previous error: {error_report[:2000]}")

        print("✅ GPUNIT TOOL: create_gpunit completed successfully")
        return gpunit_content

    except Exception as e:
        print(f"❌ GPUNIT TOOL: create_gpunit failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

        # Return a minimal valid GPUnit test
        return f"""# GPUnit test
name: "{tool_info.get('name', 'UnknownTool')} - Basic Test"
module: urn:lsid:genepattern.org:module.analysis:test:1
params:
  input.file: "test_data/sample.txt"
assertions:
  diffCmd: diff <%gpunit.diffStripTrailingCR%> -q
  files:
    "output.txt":
      diff: "expected/output.txt"
"""
