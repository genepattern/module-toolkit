import os
import sys
import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerStdio
from dotenv import load_dotenv


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

# Use DEFAULT_LLM_MODEL from environment, fallback to a reasonable default
DEFAULT_LLM_MODEL = os.getenv('DEFAULT_LLM_MODEL', 'bedrock:us.anthropic.claude-sonnet-4-20250514-v1:0')

mcp_tools = MCPServerStdio('python', args=['mcp/server.py'], timeout=10)

# Create agent 
gpunit_agent = Agent(DEFAULT_LLM_MODEL, system_prompt=system_prompt, toolsets=[mcp_tools])


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
