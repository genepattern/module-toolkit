# GenePattern Module AI Toolkit

A multi-agent system for automatically generating GenePattern modules.

## Overview

The `generate-module.py` script orchestrates multiple AI agents to:

1. **Research** bioinformatics tools using web search and analysis
2. **Plan** module structure, parameters, and architecture  
3. **Generate** module artifacts (Dockerfile, wrapper scripts, manifests, etc.)
4. **Validate** each artifact using the Module Toolkit linters
5. **Create** a complete, ready-to-use GenePattern module

## Prerequisites

1. **Environment Setup**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   The default values for the environment variables should be fine for most installations. However, if you wish to
   make changes, you may want to edit an .env with your API keys and preferences

4. **Environment Variables**:
   - `DEFAULT_LLM_MODEL`: LLM model for agents (default: Qwen3)
   - `BRAVE_API_KEY`: For web research (optional but recommended if you have one)
   - `MAX_ARTIFACT_LOOPS`: Max validation retry attempts (default: 5)
   - `MODULE_OUTPUT_DIR`: Output directory (default: ./generated-modules)

## Usage

### Interactive Mode

Run the script and follow the prompts:

```bash
python generate-module.py
```

You'll be prompted for:
- Tool name (required)
- Tool version (optional) 
- Primary language (optional)
- Brief description (optional)
- Repository URL (optional)
- Documentation URL (optional)

### Example Session

```
Tool name: samtools
Tool version: 1.19
Primary language: C
Brief description: Tools for manipulating SAM/BAM files
Repository URL: https://github.com/samtools/samtools
Documentation URL: http://www.htslib.org/doc/samtools.html
```

## Multi-Agent Process

### 1. Research Phase
- **Agent**: `researcher_agent`
- **Purpose**: Gather comprehensive information about the tool
- **Actions**: 
  - Web search for documentation and examples
  - Analyze command-line interface and parameters
  - Identify dependencies and requirements
  - Research common usage patterns

### 2. Planning Phase  
- **Agent**: `planner_agent`
- **Purpose**: Create implementation plan based on research
- **Actions**:
  - Map parameters to GenePattern types
  - Design parameter groupings for UI
  - Plan module architecture and dependencies
  - Define validation and testing strategy

### 3. Artifact Generation Phase
- **Agents**: Multiple artifact-specific agents
- **Current Artifacts** (in generation order):
  - `wrapper_agent`: Generates wrapper scripts for tool integration
  - `manifest_agent`: Creates module manifest with metadata and command line
  - `paramgroups_agent`: Creates parameter groupings for UI organization
  - `gpunit_agent`: Generates test definitions for automated testing
  - `documentation_agent`: Generates user documentation
  - `dockerfile_agent`: Creates Dockerfile

### 4. Validation Loop
For each artifact:
1. Generate content using specialized agent
2. Write to module directory
3. Validate using appropriate linter tool
4. If validation fails, retry up to `MAX_ARTIFACT_LOOPS` times
5. Include feedback from previous attempts in retry prompts

## Output Structure

Generated modules are saved to `{MODULE_OUTPUT_DIR}/{tool_name}_{timestamp}/`:

```
samtools_20241222_143022/
├── wrapper.py             # Execution wrapper script
├── manifest               # Module metadata and command line
├── paramgroups.json       # UI parameter groups
├── test.yml               # GPUnit test definition
├── README.md              # User documentation
└── Dockerfile             # Container definition
```

## Status Tracking

The script provides real-time status updates:

```
[14:30:22] INFO: Creating module directory for samtools
[14:30:22] INFO: Created module directory: ./generated-modules/samtools_20241222_143022
[14:30:22] INFO: Starting research on the bioinformatics tool
[14:30:25] INFO: Research phase completed successfully
[14:30:25] INFO: Starting module planning based on research findings
[14:30:28] INFO: Planning phase completed successfully
[14:30:28] INFO: Starting artifact generation
[14:30:28] INFO: Generating dockerfile...
[14:30:31] INFO: Attempt 1/5 for dockerfile
[14:30:34] INFO: Generated Dockerfile (1847 characters)
[14:30:34] INFO: Validating dockerfile...
[14:30:37] INFO: Validation passed for dockerfile
[14:30:37] INFO: Successfully generated and validated dockerfile
```

## Final Report

After completion, you'll receive a comprehensive report:

```
============================================================
 Module Generation Report
============================================================
Tool Name: samtools
Module Directory: ./generated-modules/samtools_20241222_143022
Research Complete: ✓
Planning Complete: ✓

Artifact Status:
  wrapper:
    Generated: ✓
    Validated: ✓
    Attempts: 1
  manifest:
    Generated: ✓
    Validated: ✓
    Attempts: 1
  paramgroups:
    Generated: ✓
    Validated: ✓
    Attempts: 1
  gpunit:
    Generated: ✓
    Validated: ✓
    Attempts: 1
  documentation:
    Generated: ✓
    Validated: ✓
    Attempts: 1
  dockerfile:
    Generated: ✓
    Validated: ✓
    Attempts: 1

Parameters Identified: 23
  - input_file: File (Required)
  - output_format: Choice (Optional)
  - quality_threshold: Integer (Optional)
  - threads: Integer (Optional)
  - memory_limit: Text (Optional)
  ... and 18 more parameters

============================================================
🎉 MODULE GENERATION SUCCESSFUL!
Your GenePattern module is ready in: ./generated-modules/samtools_20241222_143022
============================================================
```

## Architecture

The script follows Pydantic AI best practices for multi-agent systems:

- **Agent Specialization**: Each agent has a focused domain expertise
- **Structured Communication**: Agents pass structured data between phases
- **Error Handling**: Robust error handling with retry mechanisms
- **Validation Integration**: Built-in validation using MCP server tools
- **Status Tracking**: Comprehensive progress monitoring and reporting
