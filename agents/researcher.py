import os
import re
import json
import requests
from typing import List, Dict, Any, Optional
from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


system_prompt = """
You are a PhD-level bioinformatician and research specialist with deep expertise in genetics, 
genomics, computational biology, machine learning, and data analysis. Your primary role is to 
conduct comprehensive research on bioinformatics tools and methodologies for GenePattern module 
development.

**Research Objectives:**

1. **Tool Discovery & Analysis**: Identify and analyze bioinformatics tools, their capabilities, 
   limitations, and use cases in genomic research workflows

2. **Technical Specification**: Document technical requirements including dependencies, system 
   requirements, input/output formats, and computational resources

3. **Parameter Documentation**: Catalog all configurable parameters with their types, ranges, 
   defaults, and biological significance

4. **Usage Patterns**: Research common usage patterns, best practices, and typical workflows 
   where the tool is applied

5. **Comparative Analysis**: Compare tools with similar functionality, highlighting strengths, 
   weaknesses, and appropriate use cases

6. **Literature Review**: Survey scientific literature to understand the tool's validation, 
   performance characteristics, and adoption in the research community

**Research Standards:**
- Always cite authoritative sources (official documentation, peer-reviewed papers, repositories)
- Provide specific version information when available
- Document known issues, limitations, or caveats
- Include installation and usage examples where relevant
- Note licensing and distribution constraints
- Consider compatibility with common bioinformatics file formats and workflows

**Output Format:**
Provide structured, detailed reports with clear sections for different aspects of the research. 
Include references and maintain scientific rigor in all analyses.
"""

# Use DEFAULT_LLM_MODEL from environment, fallback to a reasonable default
DEFAULT_LLM_MODEL = os.getenv('DEFAULT_LLM_MODEL', 'bedrock:us.anthropic.claude-sonnet-4-20250514-v1:0')

# Create agent with MCP tools access
researcher_agent = Agent(DEFAULT_LLM_MODEL, system_prompt=system_prompt)


@researcher_agent.tool
def web_search(context: RunContext[str], query: str, num_results: int = 5) -> str:
    """
    Search the web using Brave Search API and extract content from relevant pages.
    
    Args:
        query: Search query string
        num_results: Number of search results to process (default: 5)
    
    Returns:
        Formatted search results with page content extracted from top results
    """
    print(f"🔍 RESEARCH TOOL: Running web_search for query: '{query}' (requesting {num_results} results)")
    
    brave_api_key = os.getenv('BRAVE_API_KEY')
    if not brave_api_key:
        print("⚠️  RESEARCH TOOL: web_search failed - BRAVE_API_KEY not configured")
        return "Error: BRAVE_API_KEY environment variable not set. Please configure Brave Search API access."
    
    try:
        # Brave Search API endpoint
        search_url = "https://api.search.brave.com/res/v1/web/search"
        
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": brave_api_key
        }
        
        params = {
            "q": query,
            "count": min(num_results, 10),  # Brave API typically allows up to 20 results
            "search_lang": "en",
            "country": "US",
            "safesearch": "moderate",
            "freshness": "all"
        }
        
        # Make the search request
        response = requests.get(search_url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        search_data = response.json()
        
        if not search_data.get('web', {}).get('results'):
            return f"No search results found for query: '{query}'"
        
        results = search_data['web']['results']
        
        # Format the search results
        formatted_results = f"Web Search Results for: '{query}'\n"
        formatted_results += "=" * (30 + len(query)) + "\n\n"
        
        for i, result in enumerate(results[:num_results], 1):
            title = result.get('title', 'No Title')
            url = result.get('url', 'No URL')
            description = result.get('description', 'No description available')
            
            formatted_results += f"**Result {i}: {title}**\n"
            formatted_results += f"URL: {url}\n"
            formatted_results += f"Description: {description}\n"
            
            # Try to extract additional content from the page
            try:
                page_content = _extract_page_content(url)
                if page_content:
                    formatted_results += f"Content Preview: {page_content[:300]}{'...' if len(page_content) > 300 else ''}\n"
            except Exception as e:
                formatted_results += f"Content extraction failed: {str(e)[:100]}\n"
            
            formatted_results += "\n" + "-" * 50 + "\n\n"
        
        # Add search metadata
        total_results = search_data.get('web', {}).get('totalCount', 'Unknown')
        formatted_results += f"**Search Metadata:**\n"
        formatted_results += f"Total results available: {total_results}\n"
        formatted_results += f"Results displayed: {len(results[:num_results])}\n"
        formatted_results += f"Query processed: {query}\n"
        
        print(f"✅ RESEARCH TOOL: web_search completed successfully - found {len(results)} results")
        return formatted_results
        
    except requests.RequestException as e:
        print(f"❌ RESEARCH TOOL: web_search failed with RequestException: {str(e)}")
        return f"Error making search request: {str(e)}"
    except json.JSONDecodeError:
        print(f"❌ RESEARCH TOOL: web_search failed with JSON decode error for query: '{query}'")
        return f"Error parsing search response for query: '{query}'"
    except Exception as e:
        print(f"❌ RESEARCH TOOL: web_search failed with unexpected error: {str(e)}")
        return f"Unexpected error during web search: {str(e)}"


def _extract_page_content(url: str) -> str:
    """
    Extract readable content from a web page.
    
    Args:
        url: URL of the page to extract content from
    
    Returns:
        Extracted text content, cleaned and truncated
    """
    try:
        # Set headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        
        # Basic HTML content extraction
        content = response.text
        
        # Remove HTML tags using regex (basic approach)
        # Remove script and style elements
        content = re.sub(r'<script[^>]*?>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<style[^>]*?>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags
        content = re.sub(r'<[^>]+>', '', content)
        
        # Clean up whitespace
        content = re.sub(r'\s+', ' ', content)
        content = content.strip()
        
        # Extract meaningful content (skip very short extracts)
        if len(content) < 50:
            return ""
        
        # Return first meaningful portion
        return content[:1000]  # Limit to 1000 characters
        
    except Exception:
        # If page extraction fails, return empty string
        return ""


@researcher_agent.tool
def analyze_tool_documentation(context: RunContext[str], documentation_text: str, source_type: str = "help") -> str:
    """
    Analyze tool documentation to extract structured information about capabilities and usage.
    
    Args:
        documentation_text: Raw documentation text (help output, README, manual, etc.)
        source_type: Type of documentation (help, readme, manual, man_page, website)
    
    Returns:
        Structured analysis of tool capabilities, parameters, and usage patterns
    """
    print(f"📖 RESEARCH TOOL: Running analyze_tool_documentation (source: {source_type}, text length: {len(documentation_text)} chars)")
    
    analysis = f"Tool Documentation Analysis (Source: {source_type})\n"
    analysis += "=" * 50 + "\n\n"
    
    # Extract tool name and version
    tool_info = {}
    
    # Look for version information
    version_patterns = [
        r'version\s+(\d+\.\d+\.\d+)',
        r'v(\d+\.\d+\.\d+)',
        r'(\d+\.\d+\.\d+)',
        r'Version:\s*([^\n\r]+)'
    ]
    
    for pattern in version_patterns:
        match = re.search(pattern, documentation_text, re.IGNORECASE)
        if match:
            tool_info['version'] = match.group(1)
            break
    
    # Extract tool name from common patterns
    name_patterns = [
        r'^([A-Z][a-zA-Z0-9]+)\s+[-\w\s]*(?:Usage|USAGE|Description)',
        r'NAME\s*\n\s*([^\n]+)',
        r'^#\s*([^\n]+)',
        r'(\w+)\s+--?\s*help'
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, documentation_text, re.MULTILINE | re.IGNORECASE)
        if match:
            tool_info['name'] = match.group(1).strip()
            break
    
    # Extract description
    desc_patterns = [
        r'DESCRIPTION\s*\n\s*([^\n]+(?:\n\s*[^\n]+)*)',
        r'Description:\s*([^\n]+(?:\n\s*[^\n]+)*)',
        r'^([A-Z][^.!?]*[.!?])',  # First sentence
    ]
    
    for pattern in desc_patterns:
        match = re.search(pattern, documentation_text, re.MULTILINE | re.IGNORECASE)
        if match:
            tool_info['description'] = match.group(1).strip()
            break
    
    # Analyze parameter structure
    param_analysis = {}
    
    # Find option sections
    option_sections = re.findall(r'(OPTIONS?|ARGUMENTS?|PARAMETERS?)\s*\n(.*?)(?=\n[A-Z]|\Z)', 
                                documentation_text, re.DOTALL | re.IGNORECASE)
    
    if option_sections:
        for section_name, section_content in option_sections:
            # Extract individual options
            options = re.findall(r'(-\w|--[\w-]+)(?:\s+([^\n]+))?', section_content)
            param_analysis[section_name.lower()] = options
    
    # Look for usage patterns
    usage_patterns = re.findall(r'(Usage|USAGE|Example):\s*([^\n]+(?:\n\s*[^\n]+)*)', 
                               documentation_text, re.IGNORECASE)
    
    # Analyze file format mentions
    file_formats = set()
    format_patterns = [
        r'\.(bam|sam|vcf|bed|gtf|gff|gff3|fasta|fa|fastq|fq|txt|csv|tsv|json|xml|yaml|yml)',
        r'(FASTQ|FASTA|VCF|BAM|SAM|BED|GTF|GFF)',
        r'format:\s*([A-Z]+)'
    ]
    
    for pattern in format_patterns:
        matches = re.findall(pattern, documentation_text, re.IGNORECASE)
        file_formats.update([m.lower() if isinstance(m, str) else m[0].lower() for m in matches])
    
    # Generate analysis report
    if tool_info:
        analysis += "**Tool Information:**\n"
        for key, value in tool_info.items():
            analysis += f"  - {key.title()}: {value}\n"
        analysis += "\n"
    
    if param_analysis:
        analysis += "**Parameter Structure:**\n"
        for section, params in param_analysis.items():
            analysis += f"  {section.title()} ({len(params)} found):\n"
            for param, desc in params[:5]:  # Show first 5
                analysis += f"    - {param}"
                if desc:
                    analysis += f": {desc[:50]}{'...' if len(desc) > 50 else ''}"
                analysis += "\n"
            if len(params) > 5:
                analysis += f"    ... and {len(params) - 5} more\n"
        analysis += "\n"
    
    if file_formats:
        analysis += "**Supported File Formats:**\n"
        for fmt in sorted(file_formats):
            analysis += f"  - {fmt.upper()}\n"
        analysis += "\n"
    
    if usage_patterns:
        analysis += "**Usage Examples Found:**\n"
        for usage_type, usage_text in usage_patterns[:3]:
            analysis += f"  {usage_type}: {usage_text.strip()[:100]}{'...' if len(usage_text) > 100 else ''}\n"
        analysis += "\n"
    
    # Research recommendations
    analysis += "**Research Recommendations:**\n"
    analysis += "- Verify version compatibility and system requirements\n"
    analysis += "- Test parameter combinations and validation rules\n"
    analysis += "- Document input/output file format specifications\n"
    analysis += "- Research typical use cases and workflows\n"
    analysis += "- Check for known issues or limitations\n"
    
    print("✅ RESEARCH TOOL: analyze_tool_documentation completed successfully")
    return analysis


@researcher_agent.tool
def parse_repository_info(context: RunContext[str], repo_url: str, readme_content: str = None) -> str:
    """
    Parse software repository information to extract development and usage details.
    
    Args:
        repo_url: Repository URL (GitHub, GitLab, Bitbucket, etc.)
        readme_content: Optional README file content
    
    Returns:
        Structured analysis of repository metadata and development information
    """
    print(f"🗂️  RESEARCH TOOL: Running parse_repository_info for URL: {repo_url}")
    
    analysis = f"Repository Analysis\n"
    analysis += "=" * 30 + "\n\n"
    
    analysis += f"**Repository URL:** {repo_url}\n\n"
    
    # Extract repository metadata from URL
    repo_info = {}
    
    # Parse different repository hosting services
    github_match = re.search(r'github\.com/([^/]+)/([^/]+)', repo_url, re.IGNORECASE)
    gitlab_match = re.search(r'gitlab\.com/([^/]+)/([^/]+)', repo_url, re.IGNORECASE)
    bitbucket_match = re.search(r'bitbucket\.org/([^/]+)/([^/]+)', repo_url, re.IGNORECASE)
    
    if github_match:
        repo_info['platform'] = 'GitHub'
        repo_info['owner'] = github_match.group(1)
        repo_info['name'] = github_match.group(2)
    elif gitlab_match:
        repo_info['platform'] = 'GitLab'
        repo_info['owner'] = gitlab_match.group(1)
        repo_info['name'] = gitlab_match.group(2)
    elif bitbucket_match:
        repo_info['platform'] = 'Bitbucket'
        repo_info['owner'] = bitbucket_match.group(1)
        repo_info['name'] = bitbucket_match.group(2)
    
    if repo_info:
        analysis += "**Repository Metadata:**\n"
        for key, value in repo_info.items():
            analysis += f"  - {key.title()}: {value}\n"
        analysis += "\n"
    
    # Analyze README content if provided
    if readme_content:
        analysis += "**README Analysis:**\n"
        
        # Extract installation instructions
        install_patterns = [
            r'(Installation|Install|Setup):\s*([^\n]+(?:\n\s*[^\n]+)*)',
            r'```(?:bash|shell|sh)?\s*((?:pip install|conda install|git clone|make install)[^\n]*)',
            r'(pip install [^\n]+)',
            r'(conda install [^\n]+)'
        ]
        
        installations = []
        for pattern in install_patterns:
            matches = re.findall(pattern, readme_content, re.IGNORECASE | re.MULTILINE)
            installations.extend(matches)
        
        if installations:
            analysis += "  Installation Methods Found:\n"
            for install in installations[:3]:
                if isinstance(install, tuple):
                    install = install[1] if len(install) > 1 else install[0]
                analysis += f"    - {install.strip()[:80]}{'...' if len(install) > 80 else ''}\n"
        
        # Extract dependencies
        dep_patterns = [
            r'(Requirements?|Dependencies?|Depends?):\s*([^\n]+(?:\n\s*[^\n]+)*)',
            r'requirements\.txt',
            r'environment\.yml',
            r'(Python \d+\.\d+)',
            r'(R \d+\.\d+)'
        ]
        
        dependencies = []
        for pattern in dep_patterns:
            matches = re.findall(pattern, readme_content, re.IGNORECASE)
            dependencies.extend(matches)
        
        if dependencies:
            analysis += "  Dependencies Mentioned:\n"
            for dep in set([str(d) for d in dependencies[:5]]):
                analysis += f"    - {dep}\n"
        
        # Extract usage examples
        example_blocks = re.findall(r'```(?:bash|shell|sh|python|r)?\s*\n(.*?)\n```', 
                                   readme_content, re.DOTALL)
        
        if example_blocks:
            analysis += "  Code Examples Found:\n"
            for i, example in enumerate(example_blocks[:2]):
                analysis += f"    Example {i+1}: {example.strip()[:60]}{'...' if len(example) > 60 else ''}\n"
        
        # Look for badges/status indicators
        badges = re.findall(r'!\[([^\]]+)\]\(([^)]+)\)', readme_content)
        if badges:
            analysis += "  Status Badges:\n"
            for badge_name, badge_url in badges[:3]:
                if any(term in badge_name.lower() for term in ['build', 'test', 'coverage', 'version']):
                    analysis += f"    - {badge_name}: {badge_url}\n"
        
        analysis += "\n"
    
    # Research suggestions
    analysis += "**Research Action Items:**\n"
    analysis += "- Check repository activity and maintenance status\n"
    analysis += "- Review issue tracker for known problems\n"
    analysis += "- Examine release history and versioning\n"
    analysis += "- Look for documentation and wiki pages\n"
    analysis += "- Check for continuous integration setup\n"
    analysis += "- Review licensing and distribution terms\n"
    
    print("✅ RESEARCH TOOL: parse_repository_info completed successfully")
    return analysis


@researcher_agent.tool
def create_tool_research_report(context: RunContext[str], tool_name: str, research_findings: List[Dict[str, Any]]) -> str:
    """
    Create a comprehensive research report combining multiple research findings.
    
    Args:
        tool_name: Name of the tool being researched
        research_findings: List of research data dictionaries with keys like 'source', 'type', 'data'
    
    Returns:
        Comprehensive formatted research report
    """
    print(f"📊 RESEARCH TOOL: Running create_tool_research_report for {tool_name} with {len(research_findings)} findings")
    
    report = f"Comprehensive Research Report: {tool_name}\n"
    report += "=" * (35 + len(tool_name)) + "\n\n"
    
    # Executive Summary
    report += "## Executive Summary\n\n"
    report += f"This report provides a comprehensive analysis of {tool_name} for potential "
    report += "integration into the GenePattern platform. The analysis covers technical "
    report += "specifications, usage patterns, parameter analysis, and implementation considerations.\n\n"
    
    # Tool Overview
    report += "## Tool Overview\n\n"
    
    # Extract basic info from findings
    tool_info = {}
    for finding in research_findings:
        if finding.get('type') == 'basic_info':
            tool_info.update(finding.get('data', {}))
    
    if tool_info:
        for key, value in tool_info.items():
            report += f"**{key.title()}:** {value}\n"
        report += "\n"
    
    # Technical Specifications
    report += "## Technical Specifications\n\n"
    
    tech_specs = {}
    for finding in research_findings:
        if finding.get('type') == 'technical':
            tech_specs.update(finding.get('data', {}))
    
    if tech_specs:
        report += "| Specification | Details |\n"
        report += "|---------------|----------|\n"
        for spec, detail in tech_specs.items():
            report += f"| {spec.title()} | {detail} |\n"
        report += "\n"
    
    # Parameter Analysis
    report += "## Parameter Analysis\n\n"
    
    parameters = []
    for finding in research_findings:
        if finding.get('type') == 'parameters':
            parameters.extend(finding.get('data', []))
    
    if parameters:
        report += "### Identified Parameters\n\n"
        report += "| Parameter | Type | Description | GenePattern Mapping |\n"
        report += "|-----------|------|-------------|--------------------|\n"
        
        for param in parameters[:20]:  # Limit to 20 for readability
            param_name = param.get('name', 'Unknown')
            param_type = param.get('type', 'Unknown')
            param_desc = param.get('description', 'No description')[:50]
            gp_mapping = param.get('genepattern_type', 'TBD')
            
            report += f"| {param_name} | {param_type} | {param_desc}... | {gp_mapping} |\n"
        
        if len(parameters) > 20:
            report += f"\n*Note: {len(parameters) - 20} additional parameters identified but not shown for brevity.*\n"
        report += "\n"
    
    # Usage Patterns
    report += "## Usage Patterns & Examples\n\n"
    
    usage_examples = []
    for finding in research_findings:
        if finding.get('type') == 'usage':
            usage_examples.extend(finding.get('data', []))
    
    if usage_examples:
        for i, example in enumerate(usage_examples[:3]):
            report += f"### Example {i+1}: {example.get('name', 'Usage Example')}\n\n"
            report += f"**Command:** `{example.get('command', 'Not specified')}`\n\n"
            report += f"**Description:** {example.get('description', 'No description provided')}\n\n"
            
            if example.get('input_files'):
                report += f"**Input Files:** {', '.join(example['input_files'])}\n\n"
            
            if example.get('output_files'):
                report += f"**Output Files:** {', '.join(example['output_files'])}\n\n"
    
    # Implementation Considerations
    report += "## Implementation Considerations\n\n"
    
    considerations = []
    for finding in research_findings:
        if finding.get('type') == 'considerations':
            considerations.extend(finding.get('data', []))
    
    if considerations:
        report += "### Key Considerations for GenePattern Integration\n\n"
        for consideration in considerations:
            report += f"- **{consideration.get('category', 'General')}**: {consideration.get('detail', 'No detail provided')}\n"
        report += "\n"
    else:
        report += "### Standard Implementation Considerations\n\n"
        report += "- **Docker Container**: Create optimized container with all dependencies\n"
        report += "- **Parameter Validation**: Implement comprehensive input validation\n"
        report += "- **Error Handling**: Robust error handling and user feedback\n"
        report += "- **Output Processing**: Standardize output formats for GenePattern\n"
        report += "- **Documentation**: Create comprehensive user documentation\n"
        report += "- **Testing**: Develop comprehensive test suite\n\n"
    
    # Recommendations
    report += "## Recommendations\n\n"
    
    recommendations = []
    for finding in research_findings:
        if finding.get('type') == 'recommendations':
            recommendations.extend(finding.get('data', []))
    
    if recommendations:
        for rec in recommendations:
            priority = rec.get('priority', 'Medium')
            action = rec.get('action', 'No action specified')
            reason = rec.get('reason', 'No reason provided')
            
            report += f"**{priority} Priority**: {action}\n"
            report += f"  *Rationale*: {reason}\n\n"
    else:
        report += "**High Priority**: Conduct parameter mapping analysis\n"
        report += "  *Rationale*: Essential for proper GenePattern integration\n\n"
        report += "**Medium Priority**: Performance benchmarking\n"
        report += "  *Rationale*: Optimize resource requirements for typical workflows\n\n"
        report += "**Low Priority**: Advanced feature exploration\n"
        report += "  *Rationale*: Identify opportunities for enhanced functionality\n\n"
    
    # Research Sources
    report += "## Research Sources\n\n"
    
    sources = set()
    for finding in research_findings:
        source = finding.get('source')
        if source:
            sources.add(source)
    
    if sources:
        for i, source in enumerate(sorted(sources), 1):
            report += f"{i}. {source}\n"
        report += "\n"
    
    # Metadata
    report += "---\n"
    report += f"*Report generated for {tool_name} - {len(research_findings)} research findings analyzed*\n"
    
    print("✅ RESEARCH TOOL: create_tool_research_report completed successfully")
    return report


@researcher_agent.tool
def analyze_parameter_patterns(context: RunContext[str], parameter_list: List[str], usage_examples: str = None) -> str:
    """
    Analyze parameter usage patterns to identify groupings and relationships.
    
    Args:
        parameter_list: List of parameter names/flags
        usage_examples: Optional usage examples showing parameter combinations
    
    Returns:
        Analysis of parameter patterns, dependencies, and groupings
    """
    print(f"🔧 RESEARCH TOOL: Running analyze_parameter_patterns with {len(parameter_list)} parameters")
    
    analysis = "Parameter Pattern Analysis\n"
    analysis += "=" * 30 + "\n\n"
    
    if not parameter_list:
        return "Error: No parameters provided for analysis"
    
    analysis += f"**Total Parameters Analyzed:** {len(parameter_list)}\n\n"
    
    # Categorize parameters by common patterns
    categories = {
        'Input/Output': [],
        'Processing Options': [],
        'Quality Control': [],
        'Output Format': [],
        'System/Performance': [],
        'Debug/Verbose': [],
        'Other': []
    }
    
    # Classification patterns
    io_patterns = ['input', 'output', 'file', 'read', 'write', 'data']
    processing_patterns = ['algorithm', 'method', 'mode', 'process', 'analyze', 'filter']
    qc_patterns = ['quality', 'qc', 'trim', 'filter', 'threshold', 'cutoff']
    format_patterns = ['format', 'type', 'extension', 'delimiter', 'separator']
    system_patterns = ['thread', 'cpu', 'memory', 'temp', 'cache', 'parallel']
    debug_patterns = ['verbose', 'debug', 'quiet', 'silent', 'log']
    
    for param in parameter_list:
        param_lower = param.lower()
        categorized = False
        
        for pattern in io_patterns:
            if pattern in param_lower:
                categories['Input/Output'].append(param)
                categorized = True
                break
        
        if not categorized:
            for pattern in processing_patterns:
                if pattern in param_lower:
                    categories['Processing Options'].append(param)
                    categorized = True
                    break
        
        if not categorized:
            for pattern in qc_patterns:
                if pattern in param_lower:
                    categories['Quality Control'].append(param)
                    categorized = True
                    break
        
        if not categorized:
            for pattern in format_patterns:
                if pattern in param_lower:
                    categories['Output Format'].append(param)
                    categorized = True
                    break
        
        if not categorized:
            for pattern in system_patterns:
                if pattern in param_lower:
                    categories['System/Performance'].append(param)
                    categorized = True
                    break
        
        if not categorized:
            for pattern in debug_patterns:
                if pattern in param_lower:
                    categories['Debug/Verbose'].append(param)
                    categorized = True
                    break
        
        if not categorized:
            categories['Other'].append(param)
    
    # Display categorization
    analysis += "**Parameter Categorization:**\n\n"
    for category, params in categories.items():
        if params:
            analysis += f"*{category}* ({len(params)} parameters):\n"
            for param in params[:8]:  # Show up to 8 per category
                analysis += f"  - {param}\n"
            if len(params) > 8:
                analysis += f"  ... and {len(params) - 8} more\n"
            analysis += "\n"
    
    # Analyze naming patterns
    analysis += "**Naming Patterns:**\n\n"
    
    # Common prefixes
    prefixes = {}
    for param in parameter_list:
        clean_param = param.lstrip('-')
        if len(clean_param) > 2:
            prefix = clean_param[:3]
            prefixes[prefix] = prefixes.get(prefix, 0) + 1
    
    common_prefixes = [(p, c) for p, c in prefixes.items() if c > 1]
    if common_prefixes:
        analysis += "Common prefixes (indicating parameter families):\n"
        for prefix, count in sorted(common_prefixes, key=lambda x: x[1], reverse=True)[:5]:
            analysis += f"  - '{prefix}*': {count} parameters\n"
        analysis += "\n"
    
    # Boolean vs value parameters
    boolean_like = [p for p in parameter_list if not any(char in p.lower() for char in ['=', ':', '<', '>'])]
    value_like = [p for p in parameter_list if p not in boolean_like]
    
    analysis += f"Parameter Types (by pattern):\n"
    analysis += f"  - Boolean-like flags: {len(boolean_like)} ({(len(boolean_like)/len(parameter_list)*100):.1f}%)\n"
    analysis += f"  - Value-taking parameters: {len(value_like)} ({(len(value_like)/len(parameter_list)*100):.1f}%)\n\n"
    
    # Usage pattern analysis
    if usage_examples:
        analysis += "**Usage Pattern Analysis:**\n\n"
        
        # Extract parameter combinations from examples
        example_params = re.findall(r'(-\w+|--[\w-]+)', usage_examples)
        if example_params:
            param_freq = {}
            for param in example_params:
                param_freq[param] = param_freq.get(param, 0) + 1
            
            analysis += "Most frequently used parameters in examples:\n"
            sorted_params = sorted(param_freq.items(), key=lambda x: x[1], reverse=True)
            for param, freq in sorted_params[:10]:
                analysis += f"  - {param}: {freq} times\n"
            analysis += "\n"
    
    # Recommendations
    analysis += "**GenePattern Grouping Recommendations:**\n\n"
    analysis += "Based on the parameter analysis, suggested parameter groups:\n\n"
    
    for category, params in categories.items():
        if params and len(params) >= 2:
            analysis += f"**{category} Group:**\n"
            analysis += f"  Description: Parameters controlling {category.lower()}\n"
            analysis += f"  Parameters: {len(params)} total\n"
            analysis += f"  Priority: {'High' if category in ['Input/Output', 'Processing Options'] else 'Medium'}\n\n"
    
    print("✅ RESEARCH TOOL: analyze_parameter_patterns completed successfully")
    return analysis


@researcher_agent.tool
def compare_similar_tools(context: RunContext[str], target_tool: str, similar_tools: List[Dict[str, str]]) -> str:
    """
    Compare the target tool with similar tools to highlight unique features and positioning.
    
    Args:
        target_tool: Name of the main tool being researched
        similar_tools: List of similar tools with 'name', 'description', and 'key_features' keys
    
    Returns:
        Comparative analysis highlighting strengths, weaknesses, and unique positioning
    """
    print(f"⚖️  RESEARCH TOOL: Running compare_similar_tools for {target_tool} vs {len(similar_tools)} similar tools")
    
    comparison = f"Comparative Analysis: {target_tool}\n"
    comparison += "=" * (25 + len(target_tool)) + "\n\n"
    
    if not similar_tools:
        return f"Error: No similar tools provided for comparison with {target_tool}"
    
    comparison += f"**Target Tool:** {target_tool}\n"
    comparison += f"**Compared Against:** {len(similar_tools)} similar tools\n\n"
    
    # Create comparison table
    comparison += "## Tool Comparison Matrix\n\n"
    comparison += "| Tool | Primary Use Case | Key Strengths | Limitations |\n"
    comparison += "|------|------------------|---------------|-------------|\n"
    
    # Add target tool first
    comparison += f"| **{target_tool}** | *Target for analysis* | TBD | TBD |\n"
    
    # Add similar tools
    for tool in similar_tools:
        name = tool.get('name', 'Unknown')
        use_case = tool.get('description', 'No description')[:40] + "..."
        strengths = tool.get('key_features', 'Not specified')[:30] + "..."
        limitations = tool.get('limitations', 'Unknown')[:30] + "..."
        
        comparison += f"| {name} | {use_case} | {strengths} | {limitations} |\n"
    
    comparison += "\n"
    
    # Detailed analysis sections
    comparison += "## Detailed Comparison\n\n"
    
    # Feature comparison
    comparison += "### Feature Analysis\n\n"
    
    all_features = set()
    for tool in similar_tools:
        features = tool.get('key_features', '').split(',')
        all_features.update([f.strip().lower() for f in features if f.strip()])
    
    if all_features:
        comparison += f"**Common feature categories identified across {len(similar_tools)} tools:**\n"
        for feature in sorted(list(all_features))[:10]:
            if feature:
                comparison += f"  - {feature.title()}\n"
        comparison += "\n"
    
    # Market positioning analysis
    comparison += "### Market Positioning\n\n"
    
    # Categorize tools by complexity/target audience
    academic_tools = [t for t in similar_tools if any(term in t.get('description', '').lower() 
                                                    for term in ['research', 'academic', 'publication'])]
    commercial_tools = [t for t in similar_tools if any(term in t.get('description', '').lower() 
                                                       for term in ['commercial', 'enterprise', 'business'])]
    cli_tools = [t for t in similar_tools if any(term in t.get('description', '').lower() 
                                                for term in ['command', 'cli', 'terminal'])]
    gui_tools = [t for t in similar_tools if any(term in t.get('description', '').lower() 
                                                for term in ['gui', 'interface', 'desktop'])]
    
    comparison += f"**Tool Categories:**\n"
    comparison += f"  - Academic/Research focus: {len(academic_tools)} tools\n"
    comparison += f"  - Commercial/Enterprise: {len(commercial_tools)} tools\n"
    comparison += f"  - Command-line interface: {len(cli_tools)} tools\n"
    comparison += f"  - Graphical interface: {len(gui_tools)} tools\n\n"
    
    # Competitive advantages analysis
    comparison += "### Competitive Analysis for GenePattern Integration\n\n"
    
    comparison += f"**Advantages of choosing {target_tool}:**\n"
    comparison += "  - (To be determined based on detailed research)\n"
    comparison += "  - Integration feasibility with GenePattern architecture\n"
    comparison += "  - Parameter exposure and customization capabilities\n"
    comparison += "  - Docker containerization compatibility\n\n"
    
    comparison += "**Potential concerns:**\n"
    comparison += "  - Competition from established alternatives\n"
    comparison += "  - User familiarity with existing tools\n"
    comparison += "  - Documentation and support quality\n"
    comparison += "  - Performance characteristics vs alternatives\n\n"
    
    # Integration recommendations
    comparison += "### Integration Recommendations\n\n"
    
    comparison += f"**Priority Assessment:**\n"
    if len(similar_tools) <= 2:
        comparison += f"  - **High Priority**: Limited competition suggests {target_tool} fills important niche\n"
    elif len(similar_tools) <= 5:
        comparison += f"  - **Medium Priority**: Moderate competition requires differentiation strategy\n"
    else:
        comparison += f"  - **Low Priority**: High competition requires strong justification\n"
    
    comparison += f"\n**Differentiation Strategy:**\n"
    comparison += f"  - Emphasize {target_tool}'s unique capabilities\n"
    comparison += "  - Focus on GenePattern-specific optimizations\n"
    comparison += "  - Provide superior parameter organization and validation\n"
    comparison += "  - Ensure robust error handling and user feedback\n\n"
    
    comparison += f"**User Adoption Considerations:**\n"
    comparison += "  - Provide migration guides from popular alternatives\n"
    comparison += "  - Document performance comparisons\n"
    comparison += "  - Create tutorial content highlighting advantages\n"
    comparison += "  - Consider parameter naming consistency with similar tools\n\n"
    
    # Research recommendations
    comparison += "### Further Research Needed\n\n"
    comparison += "1. **Performance Benchmarking**: Compare execution speed and resource usage\n"
    comparison += "2. **Feature Gap Analysis**: Identify missing features vs competitors\n"
    comparison += "3. **User Community Analysis**: Assess adoption rates and user satisfaction\n"
    comparison += "4. **Documentation Quality**: Compare ease of use and learning curve\n"
    comparison += "5. **Maintenance Status**: Evaluate ongoing development and support\n"
    
    print("✅ RESEARCH TOOL: compare_similar_tools completed successfully")
    return comparison
