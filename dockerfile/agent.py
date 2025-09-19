import os
import sys
from pathlib import Path
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerStdio


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

# Use DEFAULT_LLM_MODEL from environment, fallback to a reasonable default
DEFAULT_LLM_MODEL = os.getenv('DEFAULT_LLM_MODEL', 'bedrock:us.anthropic.claude-sonnet-4-20250514-v1:0')

mcp_tools = MCPServerStdio('python', args=['mcp/server.py'], timeout=10)

# Create agent 
dockerfile_agent = Agent(DEFAULT_LLM_MODEL, system_prompt=system_prompt, toolsets=[mcp_tools])


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
    
    return result
