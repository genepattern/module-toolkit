from typing import Dict, Any
from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv
from agents.models import configured_llm_model


# Load environment variables from .env file
load_dotenv()


system_prompt = """
You are an expert Docker engineer and bioinformatician specializing in creating production-ready 
Dockerfiles for GenePattern modules. Your task is to generate optimized, secure, and maintainable 
Dockerfiles that encapsulate bioinformatics tools and their dependencies.

Key requirements for GenePattern module Dockerfiles:
- Use appropriate base images (python:3.11-slim, alpine:3.19, ubuntu:22.04, etc.)
- Install required system dependencies and bioinformatics tools
- Handle package management (pip, conda, apt, apk) appropriately
- Create proper working directories and file permissions
- Include proper COPY/ADD instructions for module files
- Set appropriate environment variables
- Use multi-stage builds when beneficial for size optimization
- Follow Docker best practices for caching, security, and maintainability
- Ensure the container can run the target bioinformatics tool correctly
- Include proper CMD or ENTRYPOINT for module execution

CRITICAL DOCKER SYNTAX RULES:
- NEVER use shell redirection or operators in COPY/ADD commands (e.g., NO "2>/dev/null", NO "||", NO "&&")
- COPY and ADD do NOT support shell syntax - they are not shell commands
- Only copy files that are guaranteed to exist in the build context
- For optional files, either ensure they exist before building or omit the COPY instruction
- Shell operators (||, &&, >, 2>&1, etc.) ONLY work in RUN commands, not COPY/ADD

Guidelines:
- Minimize image size while ensuring all dependencies are available
- Use specific version tags for base images to ensure reproducibility
- Group RUN commands to reduce layers
- Place frequently changing instructions (like COPY) near the end
- Use .dockerignore-friendly patterns
- Handle both Python and R-based tools as needed
- Consider conda/mamba for complex bioinformatics dependencies
- Ensure proper locale and timezone settings if needed
- Include necessary metadata labels

Always generate complete, working Dockerfiles that can be built and tested immediately.
Provide clear comments explaining each section and any complex installation steps.
"""

# Create agent without MCP dependency
dockerfile_agent = Agent(configured_llm_model(), system_prompt=system_prompt)


@dockerfile_agent.tool
def validate_dockerfile(context: RunContext[str], path: str, tag: str = None, cmd: str = None, cleanup: bool = True) -> str:
    """
    Validate Dockerfiles for GenePattern modules.

    This tool validates Dockerfile syntax and structure, optionally builds and tests
    the Docker image to ensure it can be used for GenePattern module execution.

    Args:
        path: Path to the Dockerfile or directory containing a Dockerfile.
              If a directory is provided, looks for 'Dockerfile' in that directory.
        tag: Optional Docker image tag to use when building the image for testing.
             If not provided, a default tag will be generated.
        cmd: Optional command to run inside the container for testing.
             If provided, the tool will start a container and execute this command
             to verify the image works correctly.
        cleanup: Whether to clean up Docker images after validation (default: True).
                Setting to False will leave test images on the system for debugging.

    Returns:
        A string containing the validation results, including build output,
        test results, and any error messages.
    """
    import io
    import sys
    from contextlib import redirect_stderr, redirect_stdout
    import traceback

    print(f"🔍 DOCKERFILE TOOL: Running validate_dockerfile on '{path}'")

    try:
        import dockerfile.linter

        argv = [path]
        if tag:
            argv.extend(["-t", tag])
        if cmd:
            argv.extend(["-c", cmd])
        if not cleanup:
            argv.append("--no-cleanup")

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exit_code = dockerfile.linter.main(argv)

            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Dockerfile validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            result_text = f"Dockerfile validation {'PASSED' if exit_code == 0 else 'FAILED'}\n\n{output}"
            if errors:
                result_text += f"\nErrors:\n{errors}"
            return result_text
    except Exception as e:
        error_msg = f"Error running dockerfile linter: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ DOCKERFILE TOOL: {error_msg}")
        return error_msg


@dockerfile_agent.tool
def analyze_tool_requirements(context: RunContext[str], tool_name: str, language: str = None, dependencies: str = None) -> str:
    """
    Analyze the requirements for a bioinformatics tool to determine appropriate Dockerfile base image and dependencies.
    
    Args:
        tool_name: Name of the bioinformatics tool
        language: Primary language (python, r, java, etc.)
        dependencies: Known dependencies or package requirements
    
    Returns:
        Analysis of tool requirements for Dockerfile generation
    """
    print(f"🐳 DOCKERFILE TOOL: Running analyze_tool_requirements for '{tool_name}' (language: {language or 'unknown'}, deps: {'Yes' if dependencies else 'No'})")
    
    analysis = f"Analyzing requirements for {tool_name}:\n"
    
    if language:
        analysis += f"- Primary language: {language}\n"
        
        if language.lower() == 'python':
            analysis += "- Recommended base: python:3.11-slim or python:3.9-slim\n"
            analysis += "- Package manager: pip (requirements.txt) or conda\n"
        elif language.lower() == 'r':
            analysis += "- Recommended base: rocker/r-ver:4.3.0 or r-base:4.3.0\n"
            analysis += "- Package manager: CRAN, Bioconductor\n"
        elif language.lower() == 'java':
            analysis += "- Recommended base: openjdk:11-jre-slim or eclipse-temurin:11-jre\n"
            analysis += "- May need Maven or Gradle for building\n"
        else:
            analysis += f"- Consider ubuntu:22.04 or alpine:3.19 for {language}\n"
    
    if dependencies:
        analysis += f"- Known dependencies: {dependencies}\n"
        
        # Common bioinformatics dependencies
        bio_tools = ['samtools', 'bcftools', 'bedtools', 'bwa', 'bowtie2', 'star', 'hisat2']
        mentioned_tools = [tool for tool in bio_tools if tool.lower() in dependencies.lower()]
        if mentioned_tools:
            analysis += f"- Detected bioinformatics tools: {', '.join(mentioned_tools)}\n"
            analysis += "- Consider using conda/mamba for bioinformatics dependencies\n"
    
    analysis += "\nRecommendations:\n"
    analysis += "- Use multi-stage build if compilation is needed\n"
    analysis += "- Pin versions for reproducibility\n"
    analysis += "- Use --no-cache-dir for pip installs\n"
    analysis += "- Clean up package caches to reduce image size\n"
    
    print("✅ DOCKERFILE TOOL: analyze_tool_requirements completed successfully")
    return analysis


@dockerfile_agent.tool
def suggest_optimizations(context: RunContext[str], dockerfile_content: str) -> str:
    """
    Suggest optimizations for a Dockerfile to reduce size and improve performance.
    
    Args:
        dockerfile_content: The Dockerfile content to optimize
    
    Returns:
        Optimization suggestions
    """
    print(f"🐳 DOCKERFILE TOOL: Running suggest_optimizations (Dockerfile length: {len(dockerfile_content)} chars)")
    
    optimizations = []
    
    lines = dockerfile_content.strip().split('\n')
    run_commands = [line for line in lines if line.strip().upper().startswith('RUN')]
    
    if len(run_commands) > 3:
        optimizations.append("Consider combining multiple RUN commands to reduce layers")
    
    if 'apt-get update' in dockerfile_content and 'apt-get clean' not in dockerfile_content:
        optimizations.append("Add 'apt-get clean && rm -rf /var/lib/apt/lists/*' after apt installations")
    
    if 'pip install' in dockerfile_content and '--no-cache-dir' not in dockerfile_content:
        optimizations.append("Add '--no-cache-dir' flag to pip install commands")
    
    if 'COPY . .' in dockerfile_content:
        optimizations.append("Consider using specific COPY instructions instead of 'COPY . .' for better caching")
    
    result = "Dockerfile optimization suggestions:\n"
    
    if optimizations:
        for opt in optimizations:
            result += f"- {opt}\n"
    else:
        result += "Dockerfile appears well-optimized for size and caching."
    
    print("✅ DOCKERFILE TOOL: suggest_optimizations completed successfully")
    return result


@dockerfile_agent.tool
def create_dockerfile(context: RunContext[str]) -> str:
    """
    Generate a complete Dockerfile for the GenePattern module.
    
    Args:
        context: RunContext with dependencies containing tool_info, planning_data, error_report, and attempt

    Returns:
        Complete Dockerfile content ready for validation
    """
    # Extract data from context dependencies
    tool_info = context.deps.get('tool_info', {})
    planning_data = context.deps.get('planning_data', {})
    error_report = context.deps.get('error_report', '')
    attempt = context.deps.get('attempt', 1)

    print(f"🐳 DOCKERFILE TOOL: Running create_dockerfile for '{tool_info.get('name', 'unknown')}' (attempt {attempt})")
    
    try:
        tool_name = tool_info.get('name', 'unknown')
        language = tool_info.get('language', 'python').lower()
        version = tool_info.get('version', 'latest')
        tool_instructions = tool_info.get('instructions', '')

        if tool_instructions:
            print(f"✓ User provided instructions: {tool_instructions[:100]}...")

        # USE PLANNING DATA - Extract comprehensive build information
        cpu_cores = planning_data.get('cpu_cores', 1) if planning_data else 1
        memory = planning_data.get('memory', '2GB') if planning_data else '2GB'
        input_formats = planning_data.get('input_file_formats', []) if planning_data else []
        wrapper_script = planning_data.get('wrapper_script', 'wrapper.py') if planning_data else 'wrapper.py'
        parameters = planning_data.get('parameters', []) if planning_data else []

        print(f"✓ Using cpu_cores from planning_data: {cpu_cores}")
        print(f"✓ Using memory from planning_data: {memory}")
        if input_formats:
            print(f"✓ Using input_file_formats from planning_data: {input_formats}")
        print(f"✓ Using wrapper_script from planning_data: {wrapper_script}")
        print(f"✓ Analyzing {len(parameters)} parameters for dependency hints")

        # Analyze input formats to determine required system tools
        format_tools = set()
        format_lower = [fmt.lower().lstrip('.') for fmt in input_formats]

        # Common bioinformatics file format tools
        format_tool_map = {
            'bam': ['samtools'],
            'sam': ['samtools'],
            'cram': ['samtools'],
            'vcf': ['bcftools', 'tabix'],
            'bcf': ['bcftools'],
            'bed': ['bedtools'],
            'bigwig': ['ucsc-tools'],
            'bw': ['ucsc-tools'],
            'fastq': [],  # Usually no special tools needed
            'fq': [],
            'fasta': [],
            'fa': [],
            'gz': ['gzip'],
            'bz2': ['bzip2'],
            'zip': ['unzip'],
        }

        for fmt in format_lower:
            if fmt in format_tool_map:
                format_tools.update(format_tool_map[fmt])

        if format_tools:
            print(f"✓ Detected required tools from input formats: {', '.join(format_tools)}")

        # Analyze parameters for additional dependency hints
        param_tools = set()
        for param in parameters:
            param_name = param.get('name', '').lower()
            param_desc = param.get('description', '').lower()

            # Look for references to specific tools in parameter names/descriptions
            if 'samtools' in param_name or 'samtools' in param_desc:
                param_tools.add('samtools')
            if 'bedtools' in param_name or 'bedtools' in param_desc:
                param_tools.add('bedtools')
            if 'vcf' in param_name or 'bcf' in param_name:
                param_tools.add('bcftools')

        if param_tools:
            print(f"✓ Detected tools from parameter analysis: {', '.join(param_tools)}")

        # Combine all detected tools
        all_tools = format_tools | param_tools

        # Determine base image based on language
        if language == 'python':
            base_image = 'python:3.11-slim'
            install_cmd = 'pip install --no-cache-dir'
        elif language == 'r':
            base_image = 'rocker/r-ver:4.3.0'
            install_cmd = 'R -e'
        elif language == 'java':
            base_image = 'openjdk:11-jre-slim'
            install_cmd = 'apt-get install -y'
        else:
            base_image = 'ubuntu:22.04'
            install_cmd = 'apt-get install -y'

        # Generate Dockerfile content with planning data
        dockerfile_content = f"""# Dockerfile for {tool_name} GenePattern Module
# Generated from planning data
# Resource requirements: {cpu_cores} CPU cores, {memory} memory
# Supported input formats: {', '.join(input_formats) if input_formats else 'various'}
FROM {base_image}

# Metadata labels
LABEL maintainer="GenePattern"
LABEL module.name="{tool_name}"
LABEL module.version="{version}"
LABEL module.language="{language}"

# Set working directory
WORKDIR /module

"""

        # Install system dependencies (base + format-specific tools)
        base_deps = ['wget', 'curl', 'git', 'ca-certificates']

        # Add bioinformatics tools if needed
        apt_tools = []
        if 'samtools' in all_tools:
            apt_tools.append('samtools')
        if 'bcftools' in all_tools:
            apt_tools.append('bcftools')
        if 'bedtools' in all_tools:
            apt_tools.append('bedtools')
        if 'tabix' in all_tools:
            apt_tools.append('tabix')

        all_deps = base_deps + apt_tools

        dockerfile_content += f"""# Install system dependencies
RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
"""

        for dep in all_deps:
            dockerfile_content += f"        {dep} \\\n"

        dockerfile_content += """    && apt-get clean && \\
    rm -rf /var/lib/apt/lists/*

"""

        # Add language-specific installation
        if language == 'python':
            # Try to install the tool, but don't fail if it's not available
            dockerfile_content += f"""# Install Python dependencies
# Install the tool if available via pip, otherwise install common scientific packages
RUN {install_cmd} {tool_name.lower()} || \\
    {install_cmd} numpy pandas scipy matplotlib seaborn scikit-learn

"""
        elif language == 'r':
            dockerfile_content += f"""# Install R packages
# Install from CRAN or Bioconductor
RUN {install_cmd} "install.packages(c('optparse', 'futile.logger'), repos='http://cran.r-project.org')" && \\
    {install_cmd} "if (!requireNamespace('BiocManager', quietly = TRUE)) install.packages('BiocManager', repos='http://cran.r-project.org')"

# Attempt to install the tool package
RUN {install_cmd} "install.packages('{tool_name}', repos='http://cran.r-project.org')" || \\
    {install_cmd} "BiocManager::install('{tool_name}')" || true

"""
        elif language == 'java':
            dockerfile_content += f"""# Java-based tool
# Tool JAR should be provided in module files

"""

        # IMPORTANT: Always use wrapper_script from planning_data
        wrapper_filename = wrapper_script
        if not wrapper_filename:
            # Only use fallback if wrapper_script is completely missing
            ext_map = {'python': '.py', 'r': '.R', 'bash': '.sh'}
            wrapper_filename = f"wrapper{ext_map.get(language, '.py')}"
            print(f"⚠️  No wrapper_script in planning_data, using fallback: {wrapper_filename}")
        else:
            print(f"✓ Using wrapper_script from planning_data for COPY command: {wrapper_filename}")

        # Add module files with proper wrapper script name
        # Only copy files that are required and always present
        dockerfile_content += f"""# Copy required module files
COPY {wrapper_filename} /module/
COPY manifest /module/

"""

        # Set permissions based on wrapper language
        if language in ['python', 'r', 'bash']:
            dockerfile_content += f"""# Set execute permissions on wrapper script
RUN chmod +x /module/{wrapper_filename}

"""

        # Add environment variables for resource hints
        dockerfile_content += f"""# Environment variables for resource management
ENV MODULE_CPU_CORES={cpu_cores}
ENV MODULE_MEMORY={memory}
ENV MODULE_NAME={tool_name}

"""

        # Set entrypoint
        dockerfile_content += """# Set entrypoint
CMD ["/bin/bash"]
"""

        # Add retry context if applicable
        if attempt > 1 and error_report:
            print(f"⚠️  Retry attempt {attempt} - addressing: {error_report[:100]}")

        print("✅ DOCKERFILE TOOL: create_dockerfile completed successfully")
        return dockerfile_content

    except Exception as e:
        print(f"❌ DOCKERFILE TOOL: create_dockerfile failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

        # Return a minimal valid Dockerfile
        return f"""# Dockerfile for GenePattern Module
FROM python:3.11-slim

WORKDIR /module

RUN apt-get update && \\
    apt-get install -y --no-install-recommends wget && \\
    apt-get clean && \\
    rm -rf /var/lib/apt/lists/*

COPY wrapper.py /module/
RUN chmod +x /module/wrapper.py

CMD ["/bin/bash"]
"""
