import yaml
from typing import Dict, Any, List
from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv
from agents.models import configured_llm_model


# Load environment variables from .env file
load_dotenv()


system_prompt = """
You are an expert software testing specialist and GenePattern platform developer with deep 
expertise in automated testing, test-driven development, and quality assurance for 
bioinformatics modules. Your task is to create comprehensive GPUnit test definitions that 
ensure module reliability and correctness.

Key requirements for GenePattern GPUnit tests:
- Design tests that validate module functionality with realistic data
- Create comprehensive parameter combinations to test edge cases
- Define clear test assertions that verify expected outputs
- Structure tests for maintainability and debugging ease
- Include both positive and negative test scenarios
- Follow GPUnit YAML specification and conventions
- Ensure tests are reproducible with deterministic inputs

GPUnit Test Structure:
- name: Descriptive test name explaining what is being tested
- module: Module name or LSID being tested
- params: Dictionary of parameter values for the test execution
- assertions: Test validation rules and expected outcome checks

Test Design Principles:
- Test one specific functionality per GPUnit file
- Use representative input data that exercises module features
- Include boundary conditions and edge cases
- Verify both successful execution and error handling
- Test parameter validation and input constraints
- Check output format and content correctness
- Ensure tests complete in reasonable time

Parameter Testing Strategy:
- Test required parameters with valid values
- Test optional parameters with default and custom values
- Validate parameter type checking and constraints
- Test parameter combinations and dependencies
- Include invalid parameter scenarios where appropriate
- Verify parameter validation error messages

Assertion Strategies:
- Compare output files with expected reference files
- Check output file existence and basic properties
- Validate output format and structure
- Test specific content patterns in outputs
- Verify error messages for invalid inputs
- Check execution time and resource usage where relevant

Always generate complete, valid GPUnit test files that provide thorough validation
of module functionality and can be executed reliably in automated testing environments.
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
def analyze_test_requirements(context: RunContext[str], tool_info: Dict[str, Any], parameters: List[Dict[str, Any]] = None, test_scenarios: List[str] = None) -> str:
    """
    Analyze module information to determine comprehensive GPUnit test requirements and strategy.
    
    Args:
        tool_info: Dictionary with tool information (name, description, language, etc.)
        parameters: List of parameter definitions for the module
        test_scenarios: List of specific test scenarios to include (optional)
    
    Returns:
        Analysis of test requirements with suggested test cases and coverage strategy
    """
    print(f"🧪 GPUNIT TOOL: Running analyze_test_requirements for '{tool_info.get('name', 'unknown')}' with {len(parameters or [])} parameters")
    
    tool_name = tool_info.get('name', 'Unknown Tool')
    description = tool_info.get('description', '')
    language = tool_info.get('language', 'unknown')
    
    analysis = f"GPUnit Test Requirements Analysis for {tool_name}:\n"
    analysis += "=" * 55 + "\n\n"
    
    # Analyze module complexity for test design
    complexity_factors = []
    if parameters:
        param_count = len(parameters)
        required_params = [p for p in parameters if p.get('required', False)]
        optional_params = [p for p in parameters if not p.get('required', False)]
        file_params = [p for p in parameters if p.get('type') == 'File']
        choice_params = [p for p in parameters if p.get('type') == 'Choice']
        
        if param_count > 8:
            complexity_factors.append("Many parameters (>8)")
        if len(choice_params) > 2:
            complexity_factors.append("Multiple choice parameters")
        if len(file_params) > 3:
            complexity_factors.append("Complex file handling")
        
        analysis += f"**Module Characteristics:**\n"
        analysis += f"- Total parameters: {param_count}\n"
        analysis += f"- Required parameters: {len(required_params)}\n"
        analysis += f"- Optional parameters: {len(optional_params)}\n"
        analysis += f"- File parameters: {len(file_params)}\n"
        analysis += f"- Choice parameters: {len(choice_params)}\n"
        
        if complexity_factors:
            analysis += f"- Complexity factors: {', '.join(complexity_factors)}\n"
        analysis += "\n"
    
    # Determine test coverage strategy
    if complexity_factors:
        if len(complexity_factors) >= 3:
            test_complexity = "High"
            recommended_tests = 5
        elif len(complexity_factors) >= 1:
            test_complexity = "Medium"
            recommended_tests = 3
        else:
            test_complexity = "Low"
            recommended_tests = 2
    else:
        test_complexity = "Low"
        recommended_tests = 2
    
    analysis += f"**Test Strategy Recommendations:**\n"
    analysis += f"- Test complexity level: {test_complexity}\n"
    analysis += f"- Recommended test cases: {recommended_tests}\n"
    analysis += f"- Test focus areas:\n"
    
    # Suggest specific test categories
    test_categories = []
    if parameters:
        # Basic functionality test
        test_categories.append("Basic functionality with required parameters")
        
        # Parameter combination tests
        if optional_params:
            test_categories.append("Optional parameter combinations")
        
        # File format tests
        if file_params:
            test_categories.append("Input file format validation")
        
        # Choice parameter tests
        if choice_params:
            test_categories.append("Choice parameter options testing")
        
        # Edge case tests
        if any('threshold' in p.get('name', '').lower() for p in parameters):
            test_categories.append("Boundary value testing for thresholds")
        
        # Error condition tests
        test_categories.append("Error handling and validation")
    
    for category in test_categories[:recommended_tests]:
        analysis += f"  - {category}\n"
    
    # Analyze parameter test requirements
    if parameters:
        analysis += f"\n**Parameter Test Coverage:**\n"
        
        # Group parameters by test priority
        high_priority = required_params
        medium_priority = [p for p in optional_params if p.get('type') in ['File', 'Choice']]
        low_priority = [p for p in optional_params if p not in medium_priority]
        
        if high_priority:
            analysis += f"- High priority (required): {', '.join([p.get('name', 'unknown') for p in high_priority[:3]])}{'...' if len(high_priority) > 3 else ''}\n"
        
        if medium_priority:
            analysis += f"- Medium priority (key optional): {', '.join([p.get('name', 'unknown') for p in medium_priority[:3]])}{'...' if len(medium_priority) > 3 else ''}\n"
        
        if low_priority:
            analysis += f"- Low priority (other optional): {len(low_priority)} parameters\n"
        
        # Suggest parameter combinations
        analysis += f"\n**Suggested Parameter Combinations:**\n"
        analysis += "1. Minimal valid configuration (required parameters only)\n"
        
        if optional_params:
            analysis += "2. Standard configuration (required + common optional)\n"
            analysis += "3. Full configuration (all parameters with non-default values)\n"
        
        if choice_params:
            analysis += "4. Alternative choice selections (test different options)\n"
    
    # Test data requirements
    analysis += f"\n**Test Data Requirements:**\n"
    if file_params:
        analysis += "- Sample input files for each supported format\n"
        analysis += "- Reference output files for comparison\n"
        analysis += "- Invalid input files for error testing\n"
    
    analysis += "- Reproducible test data (avoid random/time-dependent inputs)\n"
    analysis += "- Appropriate data size for quick test execution\n"
    analysis += "- Edge case data (empty files, boundary values, etc.)\n"
    
    # Assertion strategy
    analysis += f"\n**Assertion Strategy:**\n"
    analysis += "- File existence and basic properties\n"
    analysis += "- Content comparison with reference files\n"
    
    if 'statistical' in description.lower() or 'analysis' in description.lower():
        analysis += "- Statistical output validation (within tolerance)\n"
    
    if file_params:
        analysis += "- Output format validation\n"
    
    analysis += "- Error message validation for invalid inputs\n"
    analysis += "- Execution time bounds (performance regression testing)\n"
    
    # Special considerations
    if test_scenarios:
        analysis += f"\n**Custom Test Scenarios:**\n"
        for scenario in test_scenarios[:5]:
            analysis += f"- {scenario}\n"
    
    analysis += f"\n**Testing Best Practices:**\n"
    analysis += "- Keep test execution time under 2 minutes per test\n"
    analysis += "- Use descriptive test names that explain what is being validated\n"
    analysis += "- Include both positive and negative test cases\n"
    analysis += "- Test parameter validation and error handling\n"
    analysis += "- Ensure tests are independent and can run in any order\n"
    analysis += "- Document test data sources and expected outcomes\n"
    
    print("✅ GPUNIT TOOL: analyze_test_requirements completed successfully")
    return analysis


@gpunit_agent.tool
def generate_test_cases(context: RunContext[str], module_info: Dict[str, Any], test_scenarios: List[Dict[str, Any]]) -> str:
    """
    Generate specific GPUnit test case definitions based on module information and scenarios.
    
    Args:
        module_info: Dictionary with module name, LSID, and other metadata
        test_scenarios: List of test scenario definitions with parameters and expected outcomes
    
    Returns:
        Complete GPUnit test cases in YAML format with proper structure and assertions
    """
    print(f"📝 GPUNIT TOOL: Running generate_test_cases for '{module_info.get('name', 'unknown')}' with {len(test_scenarios)} scenarios")
    
    if not test_scenarios:
        print("❌ GPUNIT TOOL: generate_test_cases failed - no test scenarios provided")
        return "Error: No test scenarios provided for GPUnit generation"
    
    module_name = module_info.get('name', 'UnknownModule')
    module_lsid = module_info.get('lsid', f"urn:lsid:genepattern.org:module.analysis:{module_name.lower()}")
    
    result = f"Generated GPUnit Test Cases for {module_name}:\n"
    result += "=" * 50 + "\n\n"
    
    test_cases = []
    
    for i, scenario in enumerate(test_scenarios, 1):
        scenario_name = scenario.get('name', f'Test Case {i}')
        params = scenario.get('params', {})
        description = scenario.get('description', 'Basic functionality test')
        expected_outputs = scenario.get('expected_outputs', [])
        
        # Generate test case YAML
        test_case = {
            'name': f"{module_name} - {scenario_name}",
            'module': module_lsid,
            'params': params,
            'assertions': {}
        }
        
        # Build assertions based on expected outputs
        if expected_outputs:
            test_case['assertions']['files'] = {}
            
            for output in expected_outputs:
                if isinstance(output, str):
                    # Simple file comparison
                    test_case['assertions']['files'][output] = {
                        'diff': f"data/expected_{output}"
                    }
                elif isinstance(output, dict):
                    # Detailed output specification
                    filename = output.get('filename')
                    if filename:
                        assertion = {}
                        if output.get('reference_file'):
                            assertion['diff'] = output['reference_file']
                        if output.get('exists'):
                            assertion['exists'] = True
                        if output.get('size_min'):
                            assertion['size'] = f">={output['size_min']}"
                        test_case['assertions']['files'][filename] = assertion
        
        # Add default diff command if not specified
        if 'diffCmd' not in test_case['assertions']:
            test_case['assertions']['diffCmd'] = "diff <%gpunit.diffStripTrailingCR%> -q"
        
        test_cases.append(test_case)
    
    # Format as YAML and add to result
    for i, test_case in enumerate(test_cases, 1):
        result += f"**Test Case {i}: {test_case['name']}**\n\n"
        result += "```yaml\n"
        try:
            # Convert to YAML format
            yaml_content = yaml.dump(test_case, default_flow_style=False, sort_keys=False)
            result += yaml_content
        except Exception as e:
            # Fallback to manual formatting if yaml module issues
            result += f"name: \"{test_case['name']}\"\n"
            result += f"module: {test_case['module']}\n"
            result += "params:\n"
            for key, value in test_case['params'].items():
                if isinstance(value, str):
                    result += f"  {key}: \"{value}\"\n"
                else:
                    result += f"  {key}: {value}\n"
            result += "assertions:\n"
            for key, value in test_case['assertions'].items():
                if key == 'diffCmd':
                    result += f"  {key}: {value}\n"
                elif key == 'files':
                    result += f"  {key}:\n"
                    for filename, assertion in value.items():
                        result += f"    \"{filename}\":\n"
                        for assert_key, assert_value in assertion.items():
                            result += f"      {assert_key}: \"{assert_value}\"\n"
        
        result += "```\n\n"
    
    # Summary information
    result += f"**Summary:**\n"
    result += f"- Generated test cases: {len(test_cases)}\n"
    result += f"- Module under test: {module_name}\n"
    result += f"- Module LSID: {module_lsid}\n"
    result += f"- Total parameters tested: {len(set().union(*[tc['params'].keys() for tc in test_cases]))}\n"
    
    # Recommendations
    result += f"\n**Implementation Notes:**\n"
    result += "- Ensure test data files are available in the specified paths\n"
    result += "- Verify reference output files match expected results\n"
    result += "- Test files should be placed in GPUnit test directory\n"
    result += "- Run tests individually to verify they pass before integration\n"
    result += "- Consider adding performance benchmarks for long-running modules\n"
    
    print("✅ GPUNIT TOOL: generate_test_cases completed successfully")
    return result


@gpunit_agent.tool
def optimize_test_coverage(context: RunContext[str], existing_tests: List[Dict[str, Any]], module_parameters: List[Dict[str, Any]]) -> str:
    """
    Analyze existing test coverage and suggest optimizations for better parameter and scenario coverage.
    
    Args:
        existing_tests: List of existing GPUnit test definitions
        module_parameters: List of module parameter definitions
    
    Returns:
        Analysis of test coverage gaps and recommendations for additional test cases
    """
    print(f"⚡ GPUNIT TOOL: Running optimize_test_coverage with {len(existing_tests)} tests and {len(module_parameters)} parameters")
    
    if not existing_tests and not module_parameters:
        print("❌ GPUNIT TOOL: optimize_test_coverage failed - no tests or parameters provided")
        return "Error: No existing tests or module parameters provided for coverage analysis"
    
    analysis = "GPUnit Test Coverage Optimization:\n"
    analysis += "=" * 40 + "\n\n"
    
    # Analyze current test coverage
    tested_params = set()
    test_scenarios = []
    
    for test in existing_tests:
        test_name = test.get('name', 'Unnamed Test')
        params = test.get('params', {})
        tested_params.update(params.keys())
        test_scenarios.append({
            'name': test_name,
            'param_count': len(params),
            'params': list(params.keys())
        })
    
    analysis += f"**Current Test Coverage:**\n"
    analysis += f"- Total test cases: {len(existing_tests)}\n"
    analysis += f"- Parameters tested: {len(tested_params)}\n"
    analysis += f"- Module parameters: {len(module_parameters)}\n"
    
    if existing_tests:
        avg_params_per_test = sum(len(test.get('params', {})) for test in existing_tests) / len(existing_tests)
        analysis += f"- Average parameters per test: {avg_params_per_test:.1f}\n"
    
    # Analyze parameter coverage gaps
    all_param_names = set(param.get('name', '') for param in module_parameters)
    untested_params = all_param_names - tested_params
    
    if untested_params:
        analysis += f"\n**Coverage Gaps:**\n"
        analysis += f"- Untested parameters ({len(untested_params)}): {', '.join(sorted(list(untested_params)))}\n"
        
        # Categorize untested parameters by importance
        untested_required = []
        untested_optional = []
        untested_choice = []
        
        for param in module_parameters:
            param_name = param.get('name', '')
            if param_name in untested_params:
                if param.get('required', False):
                    untested_required.append(param_name)
                elif param.get('type') == 'Choice':
                    untested_choice.append(param_name)
                else:
                    untested_optional.append(param_name)
        
        if untested_required:
            analysis += f"- Untested REQUIRED parameters: {', '.join(untested_required)}\n"
        if untested_choice:
            analysis += f"- Untested CHOICE parameters: {', '.join(untested_choice)}\n"
        if untested_optional:
            analysis += f"- Untested optional parameters: {len(untested_optional)} total\n"
    else:
        analysis += f"\n**Coverage Status:** ✅ All module parameters are tested\n"
    
    # Analyze test scenario coverage
    analysis += f"\n**Test Scenario Analysis:**\n"
    
    scenario_coverage = {
        'minimal': False,  # Only required parameters
        'standard': False,  # Required + some optional
        'comprehensive': False,  # Most/all parameters
        'edge_cases': False,  # Boundary values, error conditions
        'choice_variants': False  # Different choice options
    }
    
    for test in existing_tests:
        params = test.get('params', {})
        param_count = len(params)
        
        # Check for different scenario types
        required_params = [p for p in module_parameters if p.get('required', False)]
        
        if param_count <= len(required_params) + 1:
            scenario_coverage['minimal'] = True
        elif param_count <= len(module_parameters) * 0.6:
            scenario_coverage['standard'] = True
        elif param_count >= len(module_parameters) * 0.8:
            scenario_coverage['comprehensive'] = True
        
        # Check for choice parameter variations
        choice_params_in_test = [p for p in params.keys() 
                               if any(mp.get('name') == p and mp.get('type') == 'Choice' 
                                     for mp in module_parameters)]
        if choice_params_in_test:
            scenario_coverage['choice_variants'] = True
    
    # Report scenario coverage
    for scenario_type, covered in scenario_coverage.items():
        status = "✅" if covered else "❌"
        analysis += f"- {scenario_type.replace('_', ' ').title()}: {status}\n"
    
    # Generate recommendations
    recommendations = []
    
    if untested_required:
        recommendations.append(f"HIGH PRIORITY: Add tests for required parameters: {', '.join(untested_required)}")
    
    if not scenario_coverage['minimal']:
        recommendations.append("Add minimal test case with only required parameters")
    
    if not scenario_coverage['comprehensive'] and len(module_parameters) > 5:
        recommendations.append("Add comprehensive test case exercising most parameters")
    
    if untested_choice and not scenario_coverage['choice_variants']:
        recommendations.append(f"Add tests for choice parameter options: {', '.join(untested_choice)}")
    
    if not scenario_coverage['edge_cases']:
        recommendations.append("Add edge case tests (boundary values, error conditions)")
    
    # Parameter combination recommendations
    if len(existing_tests) < 3 and len(module_parameters) > 6:
        recommendations.append("Consider adding more parameter combination tests")
    
    # Suggest specific test improvements
    if existing_tests:
        # Find tests with very few parameters
        minimal_tests = [t for t in existing_tests if len(t.get('params', {})) <= 2]
        if len(minimal_tests) == len(existing_tests):
            recommendations.append("Expand test parameter coverage - current tests use very few parameters")
    
    if recommendations:
        analysis += f"\n**Optimization Recommendations:**\n"
        for i, rec in enumerate(recommendations, 1):
            analysis += f"{i}. {rec}\n"
    else:
        analysis += f"\n**Result:** Test coverage appears comprehensive!\n"
    
    # Coverage metrics
    coverage_percentage = (len(tested_params) / len(all_param_names) * 100) if all_param_names else 0
    analysis += f"\n**Coverage Metrics:**\n"
    analysis += f"- Parameter coverage: {coverage_percentage:.1f}% ({len(tested_params)}/{len(all_param_names)})\n"
    analysis += f"- Scenario diversity: {sum(scenario_coverage.values())}/5 types covered\n"
    
    if coverage_percentage >= 80:
        analysis += "- Assessment: Good parameter coverage\n"
    elif coverage_percentage >= 60:
        analysis += "- Assessment: Moderate parameter coverage - room for improvement\n"
    else:
        analysis += "- Assessment: Low parameter coverage - significant gaps\n"
    
    analysis += f"\n**Next Steps:**\n"
    analysis += "- Prioritize testing untested required parameters\n"
    analysis += "- Add scenario diversity for comprehensive validation\n"
    analysis += "- Include error condition testing\n"
    analysis += "- Verify test data availability for new test cases\n"
    analysis += "- Run existing tests to ensure they pass before expanding\n"
    
    print("✅ GPUNIT TOOL: optimize_test_coverage completed successfully")
    return analysis


@gpunit_agent.tool
def create_gpunit(context: RunContext[str], tool_info: Dict[str, Any], planning_data: Dict[str, Any], error_report: str = "", attempt: int = 1) -> str:
    """
    Generate a comprehensive GPUnit test definition (test.yml) for the GenePattern module.
    
    Args:
        tool_info: Dictionary with tool information (name, version, language, description)
        planning_data: Planning phase results with parameters and context
        error_report: Optional error feedback from previous validation attempts
        attempt: Attempt number for retry logic
    
    Returns:
        Complete GPUnit YAML content ready for validation
    """
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
            print(f"⚠️  Retry attempt {attempt} - previous error: {error_report[:100]}")

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
