import re
from typing import Dict, Any, List
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerStdio
from dotenv import load_dotenv
from agents.models import configured_llm_model

# Load environment variables from .env file
load_dotenv()


system_prompt = """
You are an expert technical writer and documentation specialist with deep expertise in 
bioinformatics and GenePattern platform documentation. Your task is to create comprehensive, 
user-friendly documentation that helps researchers effectively use GenePattern modules.

Key requirements for GenePattern module documentation:
- Write clear, accessible explanations for both novice and expert users
- Include comprehensive parameter descriptions with biological context
- Provide practical usage examples and common workflows
- Structure content logically with proper headings and sections
- Address common user questions and troubleshooting scenarios
- Include relevant citations and references where appropriate
- Follow consistent formatting and style conventions

Documentation Structure Guidelines:
- Start with clear module overview and purpose
- Include installation/access instructions if needed
- Organize parameters by logical groups (required, optional, advanced)
- Provide parameter descriptions with:
  - Purpose and biological significance
  - Expected data types and formats
  - Default values and valid ranges
  - Dependencies on other parameters
- Include practical examples with real-world use cases
- Add troubleshooting section for common issues
- Provide references to related modules and methods

Writing Best Practices:
- Use active voice and clear, concise language
- Define technical terms and acronyms on first use
- Include visual aids descriptions where helpful
- Structure for easy scanning with bullets and headings
- Provide context for parameter choices and defaults
- Include example data sources and formats
- Address computational requirements and runtime expectations

Always generate complete, well-structured documentation that enables users to 
successfully apply the module to their research with confidence and understanding.
"""

mcp_tools = MCPServerStdio('python', args=['mcp/server.py'], timeout=10)

# Create agent 
documentation_agent = Agent(configured_llm_model(), system_prompt=system_prompt, toolsets=[mcp_tools])


@documentation_agent.tool
def analyze_documentation_requirements(context: RunContext[str], tool_info: Dict[str, Any], parameters: List[Dict[str, Any]] = None, target_audience: str = "mixed") -> str:
    """
    Analyze module information to determine documentation structure and content requirements.
    
    Args:
        tool_info: Dictionary with tool information (name, description, language, etc.)
        parameters: List of parameter definitions for the module
        target_audience: Target audience level ('novice', 'expert', 'mixed')
    
    Returns:
        Analysis of documentation requirements with suggested structure and content
    """
    print(f"📚 DOCUMENTATION TOOL: Running analyze_documentation_requirements for '{tool_info.get('name', 'unknown')}' with {len(parameters or [])} parameters (audience: {target_audience})")
    
    tool_name = tool_info.get('name', 'Unknown Tool')
    description = tool_info.get('description', 'No description provided')
    language = tool_info.get('language', 'unknown')
    version = tool_info.get('version', 'latest')
    repository = tool_info.get('repository_url', '')
    
    analysis = f"Documentation Requirements Analysis for {tool_name}:\n"
    analysis += "=" * 55 + "\n\n"
    
    # Analyze tool complexity and documentation needs
    complexity_indicators = []
    if parameters and len(parameters) > 10:
        complexity_indicators.append("Many parameters (>10)")
    if any(p.get('type') == 'Choice' for p in (parameters or [])):
        complexity_indicators.append("Multiple choice parameters")
    if any('advanced' in p.get('description', '').lower() for p in (parameters or [])):
        complexity_indicators.append("Advanced configuration options")
    if language.lower() in ['r', 'python', 'java']:
        complexity_indicators.append("Programming language based")
    
    # Determine documentation complexity level
    if len(complexity_indicators) >= 3:
        complexity_level = "High"
        doc_sections = 8
    elif len(complexity_indicators) >= 1:
        complexity_level = "Medium"
        doc_sections = 6
    else:
        complexity_level = "Low"
        doc_sections = 4
    
    analysis += f"**Tool Characteristics:**\n"
    analysis += f"- Complexity level: {complexity_level}\n"
    analysis += f"- Parameter count: {len(parameters or [])}\n"
    analysis += f"- Target audience: {target_audience.title()}\n"
    analysis += f"- Recommended sections: {doc_sections}\n"
    
    if complexity_indicators:
        analysis += f"- Complexity factors: {', '.join(complexity_indicators)}\n"
    analysis += "\n"
    
    # Analyze parameter documentation needs
    if parameters:
        param_analysis = {
            'required': [p for p in parameters if p.get('required', False)],
            'optional': [p for p in parameters if not p.get('required', False)],
            'file_params': [p for p in parameters if p.get('type') == 'File'],
            'choice_params': [p for p in parameters if p.get('type') == 'Choice'],
            'numeric_params': [p for p in parameters if p.get('type') in ['Integer', 'Float']],
        }
        
        analysis += f"**Parameter Documentation Needs:**\n"
        analysis += f"- Required parameters: {len(param_analysis['required'])} (high priority)\n"
        analysis += f"- Optional parameters: {len(param_analysis['optional'])} (medium priority)\n"
        analysis += f"- File parameters: {len(param_analysis['file_params'])} (need format details)\n"
        analysis += f"- Choice parameters: {len(param_analysis['choice_params'])} (need option explanations)\n"
        analysis += f"- Numeric parameters: {len(param_analysis['numeric_params'])} (need range/unit info)\n\n"
        
        # Special documentation needs
        special_needs = []
        if param_analysis['file_params']:
            special_needs.append("File format specifications and examples")
        if param_analysis['choice_params']:
            special_needs.append("Detailed choice option descriptions")
        if any('threshold' in p.get('name', '').lower() for p in parameters):
            special_needs.append("Threshold parameter guidance and defaults")
        if any('seed' in p.get('name', '').lower() for p in parameters):
            special_needs.append("Reproducibility instructions")
        
        if special_needs:
            analysis += f"**Special Documentation Needs:**\n"
            for need in special_needs:
                analysis += f"- {need}\n"
            analysis += "\n"
    
    # Suggest documentation structure
    analysis += f"**Recommended Documentation Structure:**\n\n"
    
    sections = [
        ("Overview", "Purpose, scope, and key capabilities"),
        ("Quick Start", "Minimal example to get users started"),
        ("Parameters", "Detailed parameter descriptions by category"),
        ("Examples", "Practical use cases with sample data"),
    ]
    
    if complexity_level in ["Medium", "High"]:
        sections.extend([
            ("Advanced Usage", "Complex workflows and parameter combinations"),
            ("Troubleshooting", "Common issues and solutions"),
        ])
    
    if target_audience in ["mixed", "novice"]:
        sections.extend([
            ("Background", "Scientific context and methodology"),
            ("Interpretation", "Understanding and interpreting results"),
        ])
    
    sections.append(("References", "Citations and related resources"))
    
    for i, (section, description) in enumerate(sections, 1):
        analysis += f"{i}. **{section}**: {description}\n"
    
    # Content recommendations by audience
    analysis += f"\n**Audience-Specific Recommendations:**\n\n"
    
    if target_audience == "novice":
        analysis += "For novice users:\n"
        analysis += "- Include extensive background and context\n"
        analysis += "- Provide step-by-step workflows\n"
        analysis += "- Explain biological significance of parameters\n"
        analysis += "- Include glossary of technical terms\n"
        analysis += "- Add troubleshooting for common beginner mistakes\n"
    
    elif target_audience == "expert":
        analysis += "For expert users:\n"
        analysis += "- Focus on technical specifications and algorithms\n"
        analysis += "- Provide detailed parameter relationships\n"
        analysis += "- Include performance considerations\n"
        analysis += "- Reference primary literature and methods\n"
        analysis += "- Emphasize advanced configuration options\n"
    
    else:  # mixed
        analysis += "For mixed audience:\n"
        analysis += "- Structure with progressive complexity levels\n"
        analysis += "- Use expandable sections for advanced details\n"
        analysis += "- Provide both basic and detailed examples\n"
        analysis += "- Include 'beginner' and 'advanced' usage paths\n"
        analysis += "- Balance accessibility with comprehensiveness\n"
    
    analysis += f"\n**Quality Assurance Recommendations:**\n"
    analysis += "- Include example datasets and expected outputs\n"
    analysis += "- Validate all parameter combinations in examples\n"
    analysis += "- Test documentation with actual users\n"
    analysis += "- Keep examples current with tool versions\n"
    analysis += "- Ensure consistent terminology throughout\n"
    
    print("✅ DOCUMENTATION TOOL: analyze_documentation_requirements completed successfully")
    return analysis


@documentation_agent.tool
def generate_documentation_outline(context: RunContext[str], tool_info: Dict[str, Any], sections: List[str], parameters: List[Dict[str, Any]] = None) -> str:
    """
    Generate a detailed documentation outline with section structure and content guidelines.
    
    Args:
        tool_info: Dictionary with tool information
        sections: List of documentation sections to include
        parameters: List of parameter definitions for detailed planning
    
    Returns:
        Detailed documentation outline with section descriptions and content guidelines
    """
    print(f"📋 DOCUMENTATION TOOL: Running generate_documentation_outline for '{tool_info.get('name', 'unknown')}' with {len(sections)} sections")
    
    if not sections:
        print("❌ DOCUMENTATION TOOL: generate_documentation_outline failed - no sections provided")
        return "Error: No documentation sections provided for outline generation"
    
    tool_name = tool_info.get('name', 'Unknown Tool')
    description = tool_info.get('description', '')
    
    outline = f"Documentation Outline for {tool_name}:\n"
    outline += "=" * 40 + "\n\n"
    
    # Generate detailed outline for each section
    section_templates = {
        'overview': {
            'content': [
                "Brief description of tool purpose and capabilities",
                "Key scientific applications and use cases",
                "Input data types and requirements",
                "Output data and analysis results",
                "Comparison with similar tools (if relevant)"
            ],
            'estimated_length': "200-400 words"
        },
        'quick start': {
            'content': [
                "Minimal working example",
                "Required input files and formats",
                "Basic parameter configuration",
                "Expected runtime and output",
                "Link to detailed examples"
            ],
            'estimated_length': "150-300 words"
        },
        'parameters': {
            'content': [
                "Required parameters with detailed descriptions",
                "Optional parameters organized by function",
                "Advanced/expert parameters section",
                "Parameter dependencies and interactions",
                "Default values and recommended ranges"
            ],
            'estimated_length': f"{len(parameters or []) * 50}-{len(parameters or []) * 100} words"
        },
        'examples': {
            'content': [
                "Basic usage example with sample data",
                "Advanced workflow example",
                "Parameter combination examples",
                "Real-world use case scenarios",
                "Expected outputs and interpretation"
            ],
            'estimated_length': "400-800 words"
        },
        'advanced usage': {
            'content': [
                "Complex parameter combinations",
                "Integration with other tools",
                "Batch processing workflows",
                "Performance optimization tips",
                "Custom configuration scenarios"
            ],
            'estimated_length': "300-600 words"
        },
        'troubleshooting': {
            'content': [
                "Common error messages and solutions",
                "Data format issues and fixes",
                "Performance problems and optimization",
                "Parameter validation errors",
                "Support and contact information"
            ],
            'estimated_length': "250-500 words"
        },
        'background': {
            'content': [
                "Scientific methodology and algorithms",
                "Statistical approaches used",
                "Biological or computational context",
                "Assumptions and limitations",
                "Theoretical foundation"
            ],
            'estimated_length': "300-600 words"
        },
        'interpretation': {
            'content': [
                "Understanding output formats",
                "Statistical significance interpretation",
                "Visualization and plotting guidance",
                "Results validation approaches",
                "Common interpretation pitfalls"
            ],
            'estimated_length': "250-500 words"
        },
        'references': {
            'content': [
                "Primary tool citation",
                "Methodology references",
                "Related tools and alternatives",
                "Example datasets and databases",
                "Further reading and resources"
            ],
            'estimated_length': "100-200 words"
        }
    }
    
    total_estimated_words = 0
    
    for i, section in enumerate(sections, 1):
        section_key = section.lower().replace(' ', ' ')
        template = section_templates.get(section_key, {
            'content': [f"Content guidelines for {section} section"],
            'estimated_length': "200-400 words"
        })
        
        outline += f"## {i}. {section.title()}\n\n"
        outline += f"**Purpose**: {template.get('purpose', f'Provide comprehensive information about {section.lower()}')}\n\n"
        outline += f"**Content Guidelines**:\n"
        
        for content_item in template['content']:
            outline += f"- {content_item}\n"
        
        outline += f"\n**Estimated Length**: {template['estimated_length']}\n"
        
        # Add parameter-specific guidance for parameters section
        if section_key == 'parameters' and parameters:
            outline += f"\n**Parameter Organization**:\n"
            
            required_params = [p for p in parameters if p.get('required', False)]
            optional_params = [p for p in parameters if not p.get('required', False)]
            
            if required_params:
                outline += f"- Required Parameters ({len(required_params)}): {', '.join([p.get('name', 'unknown') for p in required_params[:3]])}{'...' if len(required_params) > 3 else ''}\n"
            
            if optional_params:
                outline += f"- Optional Parameters ({len(optional_params)}): Organize by functional groups\n"
            
            # Suggest parameter groupings
            param_groups = {}
            for param in parameters:
                param_name = param.get('name', '').lower()
                if any(term in param_name for term in ['input', 'file', 'data']):
                    param_groups.setdefault('Input Parameters', []).append(param)
                elif any(term in param_name for term in ['output', 'result', 'save']):
                    param_groups.setdefault('Output Parameters', []).append(param)
                elif any(term in param_name for term in ['threshold', 'cutoff', 'limit']):
                    param_groups.setdefault('Reproducibility', []).append(param)
                elif any(term in param_name for term in ['seed', 'random', 'iteration']):
                    param_groups.setdefault('Analysis Options', []).append(param)
                else:
                    param_groups.setdefault('Miscellaneous', []).append(param)

            if len(param_groups) > 1:
                outline += f"- Suggested groupings: {', '.join(param_groups.keys())}\n"
        
        outline += f"\n**Writing Guidelines**:\n"
        if section_key in ['overview', 'background']:
            outline += "- Use clear, accessible language for broad audience\n"
            outline += "- Include relevant scientific context\n"
            outline += "- Define technical terms on first use\n"
        elif section_key == 'parameters':
            outline += "- Provide biological/scientific rationale for each parameter\n"
            outline += "- Include examples of appropriate values\n"
            outline += "- Explain parameter interactions and dependencies\n"
        elif section_key == 'examples':
            outline += "- Use realistic, representative datasets\n"
            outline += "- Show complete workflows from input to output\n"
            outline += "- Include command lines and expected results\n"
        
        outline += "\n" + "-" * 50 + "\n\n"
        
        # Estimate word count
        length_range = template['estimated_length']
        try:
            if '-' in length_range:
                min_words = int(length_range.split('-')[0])
                total_estimated_words += min_words
        except:
            total_estimated_words += 200  # Default estimate
    
    # Summary
    outline += f"**Documentation Summary**:\n"
    outline += f"- Total sections: {len(sections)}\n"
    outline += f"- Estimated total length: {total_estimated_words}-{int(total_estimated_words * 1.5)} words\n"
    outline += f"- Target reading time: {total_estimated_words // 200}-{int(total_estimated_words * 1.5) // 200} minutes\n"
    
    outline += f"\n**Production Notes**:\n"
    outline += "- Validate all examples before publication\n"
    outline += "- Include version information and last updated date\n"
    outline += "- Ensure consistent formatting and style\n"
    outline += "- Test with actual users from target audience\n"
    outline += "- Include contact information for questions\n"
    
    print("✅ DOCUMENTATION TOOL: generate_documentation_outline completed successfully")
    return outline


@documentation_agent.tool
def optimize_documentation_structure(context: RunContext[str], existing_content: str, improvement_goals: List[str] = None) -> str:
    """
    Analyze existing documentation and suggest structural and content improvements.
    
    Args:
        existing_content: Current documentation content to analyze
        improvement_goals: List of improvement goals ('clarity', 'completeness', 'accessibility', 'examples')
    
    Returns:
        Analysis with specific improvement recommendations and restructuring suggestions
    """
    print(f"⚡ DOCUMENTATION TOOL: Running optimize_documentation_structure (content length: {len(existing_content)} chars)")
    
    if improvement_goals is None:
        improvement_goals = ['clarity', 'completeness']
    
    if not existing_content.strip():
        print("❌ DOCUMENTATION TOOL: optimize_documentation_structure failed - no content provided")
        return "Error: No documentation content provided for analysis"
    
    analysis = "Documentation Structure Optimization:\n"
    analysis += "=" * 40 + "\n\n"
    
    # Analyze current content structure
    content_lines = existing_content.split('\n')
    content_stats = {
        'total_lines': len(content_lines),
        'non_empty_lines': len([line for line in content_lines if line.strip()]),
        'headings': len([line for line in content_lines if line.strip().startswith('#')]),
        'bullet_points': len([line for line in content_lines if line.strip().startswith(('-', '*', '+'))]),
        'code_blocks': len(re.findall(r'```', existing_content)),
        'parameters_mentioned': len(re.findall(r'\b\w+\.\w+\b|\b\w+_\w+\b', existing_content)),
        'word_count': len(existing_content.split())
    }
    
    analysis += f"**Current Structure Analysis:**\n"
    analysis += f"- Total lines: {content_stats['total_lines']}\n"
    analysis += f"- Content lines: {content_stats['non_empty_lines']}\n"
    analysis += f"- Headings: {content_stats['headings']}\n"
    analysis += f"- Lists/bullets: {content_stats['bullet_points']}\n"
    analysis += f"- Code examples: {content_stats['code_blocks'] // 2} blocks\n"
    analysis += f"- Parameters mentioned: {content_stats['parameters_mentioned']}\n"
    analysis += f"- Estimated word count: {content_stats['word_count']}\n\n"
    
    # Analyze by improvement goals
    suggestions = []
    
    if 'clarity' in improvement_goals:
        clarity_issues = []
        
        # Check for unclear headings
        headings = [line.strip() for line in content_lines if line.strip().startswith('#')]
        vague_headings = [h for h in headings if any(word in h.lower() for word in ['other', 'misc', 'additional', 'more'])]
        if vague_headings:
            clarity_issues.append(f"Vague headings found: {', '.join(vague_headings[:2])}")
        
        # Check paragraph length
        paragraphs = existing_content.split('\n\n')
        long_paragraphs = [p for p in paragraphs if len(p.split()) > 100]
        if long_paragraphs:
            clarity_issues.append(f"Found {len(long_paragraphs)} paragraphs >100 words (consider breaking up)")
        
        # Check for technical terms without explanation
        technical_terms = re.findall(r'\b[A-Z]{2,}\b', existing_content)
        if len(set(technical_terms)) > 5:
            clarity_issues.append(f"Many technical acronyms ({len(set(technical_terms))}) - consider adding glossary")
        
        if clarity_issues:
            suggestions.append(f"**Clarity improvements**: {'; '.join(clarity_issues)}")
    
    if 'completeness' in improvement_goals:
        completeness_issues = []
        
        # Check for missing sections
        content_lower = existing_content.lower()
        expected_sections = ['overview', 'parameter', 'example', 'usage']
        missing_sections = [section for section in expected_sections if section not in content_lower]
        if missing_sections:
            completeness_issues.append(f"Missing sections: {', '.join(missing_sections)}")
        
        # Check for examples
        if content_stats['code_blocks'] == 0:
            completeness_issues.append("No code examples found")
        
        # Check parameter documentation depth
        if content_stats['parameters_mentioned'] < 3:
            completeness_issues.append("Few parameters documented")
        
        if completeness_issues:
            suggestions.append(f"**Completeness improvements**: {'; '.join(completeness_issues)}")
    
    if 'accessibility' in improvement_goals:
        accessibility_issues = []
        
        # Check heading hierarchy
        heading_levels = [len(line) - len(line.lstrip('#')) for line in content_lines if line.strip().startswith('#')]
        if heading_levels and max(heading_levels) > 3:
            accessibility_issues.append("Deep heading nesting (>3 levels) may confuse readers")
        
        # Check for bullet point usage
        if content_stats['bullet_points'] < content_stats['non_empty_lines'] * 0.1:
            accessibility_issues.append("Consider adding more bullet points for scannability")
        
        # Check sentence length (simplified)
        sentences = re.split(r'[.!?]+', existing_content)
        long_sentences = [s for s in sentences if len(s.split()) > 25]
        if len(long_sentences) > len(sentences) * 0.2:
            accessibility_issues.append("Many long sentences (>25 words) - consider simplifying")
        
        if accessibility_issues:
            suggestions.append(f"**Accessibility improvements**: {'; '.join(accessibility_issues)}")
    
    if 'examples' in improvement_goals:
        example_issues = []
        
        # Check example quality
        if '```' in existing_content:
            code_blocks = re.findall(r'```[^`]*```', existing_content, re.DOTALL)
            short_examples = [block for block in code_blocks if len(block) < 50]
            if short_examples:
                example_issues.append(f"Found {len(short_examples)} very short code examples")
        
        # Check for placeholder values
        if '<' in existing_content and '>' in existing_content:
            placeholders = re.findall(r'<[^>]+>', existing_content)
            if len(placeholders) > 5:
                example_issues.append("Many placeholder values - consider providing concrete examples")
        
        # Check for output examples
        if 'output' in existing_content.lower() and 'result' not in existing_content.lower():
            example_issues.append("Mentions output but no result examples shown")
        
        if example_issues:
            suggestions.append(f"**Example improvements**: {'; '.join(example_issues)}")
    
    # Generate specific recommendations
    if suggestions:
        analysis += f"**Improvement Opportunities:**\n"
        for suggestion in suggestions:
            analysis += f"- {suggestion}\n"
        analysis += "\n"
    else:
        analysis += f"**Result**: Documentation structure appears well-optimized for specified goals!\n\n"
    
    # Structural recommendations
    analysis += f"**Structural Recommendations:**\n"
    
    if content_stats['word_count'] < 500:
        analysis += "- Content is quite brief - consider expanding key sections\n"
    elif content_stats['word_count'] > 2000:
        analysis += "- Content is extensive - consider adding table of contents\n"
    
    if content_stats['headings'] < 3:
        analysis += "- Add more section headings for better organization\n"
    elif content_stats['headings'] > 10:
        analysis += "- Consider consolidating some sections\n"
    
    if content_stats['code_blocks'] == 0:
        analysis += "- Add code examples to illustrate usage\n"
    
    analysis += f"\n**Quick Wins:**\n"
    analysis += "- Add table of contents for documents >1000 words\n"
    analysis += "- Include 'Quick Start' section for immediate value\n"
    analysis += "- Use consistent heading hierarchy (H1->H2->H3)\n"
    analysis += "- Add cross-references between related sections\n"
    analysis += "- Include last-updated date and version information\n"
    
    print("✅ DOCUMENTATION TOOL: optimize_documentation_structure completed successfully")
    return analysis


@documentation_agent.tool
def create_documentation(context: RunContext[str], tool_info: Dict[str, Any], planning_data: Dict[str, Any], attempt: int = 1) -> str:
    """
    Generate comprehensive user documentation (README.md) for the GenePattern module.
    
    Args:
        tool_info: Dictionary with tool information (name, version, language, description)
        planning_data: Planning phase results with parameters and context
        attempt: Attempt number for retry logic
    
    Returns:
        Complete README.md content ready for validation
    """
    print(f"📚 DOCUMENTATION TOOL: Running create_documentation for '{tool_info.get('name', 'unknown')}' (attempt {attempt})")
    
    try:
        # Extract parameter information from planning data
        parameters = planning_data.get('parameters', [])
        tool_name = tool_info.get('name', 'UnknownTool')
        description = tool_info.get('description', 'Bioinformatics analysis tool')
        version = tool_info.get('version', '1.0')
        language = tool_info.get('language', 'Python')

        # Generate README.md content
        readme_content = f"""# {tool_name}

## Overview

{description}

**Version:** {version}  
**Language:** {language}

## Description

{tool_name} is a GenePattern module that provides {description.lower() if description else 'bioinformatics analysis capabilities'}.

## Parameters

"""

        # Add parameter documentation
        if parameters:
            # Group parameters by required/optional
            required_params = [p for p in parameters if p.get('required', False)]
            optional_params = [p for p in parameters if not p.get('required', False)]

            if required_params:
                readme_content += "### Required Parameters\n\n"
                for param in required_params:
                    param_name = param.get('name', 'unknown')
                    param_type = param.get('type', 'Text')
                    param_desc = param.get('description', 'No description available')
                    readme_content += f"**{param_name}** ({param_type})\n"
                    readme_content += f"- {param_desc}\n\n"

            if optional_params:
                readme_content += "### Optional Parameters\n\n"
                for param in optional_params:
                    param_name = param.get('name', 'unknown')
                    param_type = param.get('type', 'Text')
                    param_desc = param.get('description', 'No description available')
                    default_val = param.get('default_value', 'None')
                    readme_content += f"**{param_name}** ({param_type})\n"
                    readme_content += f"- {param_desc}\n"
                    readme_content += f"- Default: {default_val}\n\n"
        else:
            readme_content += "No parameters documented.\n\n"

        # Add usage section
        readme_content += """## Usage

### Basic Example

1. Select your input file(s)
2. Configure the required parameters
3. Adjust optional parameters as needed for your analysis
4. Run the module

### Output Files

The module generates the following output files:
- `output.txt` - Main analysis results

## Troubleshooting

**Common Issues:**

- **Error: Missing input file** - Ensure your input file path is correct and the file exists
- **Error: Invalid parameters** - Check that all required parameters are provided with valid values

## References

For more information about this tool, please refer to the official documentation.

## License

This module is provided as-is for research purposes.

## Version History

- **{version}** - Initial release
"""

        print("✅ DOCUMENTATION TOOL: create_documentation completed successfully")
        return readme_content

    except Exception as e:
        print(f"❌ DOCUMENTATION TOOL: create_documentation failed: {e}")
        # Return a minimal valid README
        return f"""# {tool_info.get('name', 'GenePattern Module')}

## Overview

{tool_info.get('description', 'A GenePattern bioinformatics module.')}

## Parameters

Please refer to the module interface for parameter details.

## Usage

1. Configure your input parameters
2. Run the module
3. Review the output files

## License

Provided as-is for research purposes.
"""
