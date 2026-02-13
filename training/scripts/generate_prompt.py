#!/usr/bin/env python
"""
GenePattern Module Prompt Generator

Reverse engineers a prompt from an existing GenePattern manifest file.
This prompt can be used as input to the generate-module.py pipeline.
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Optional

# Add the project root to the path so we can import from manifest.models
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from manifest.models import ManifestModel


def extract_tool_info(manifest: ManifestModel) -> dict:
    """Extract tool information from a manifest model."""
    tool_info = {
        'name': manifest.name or 'Unknown',
        'version': manifest.version or 'latest',
        'language': manifest.language or 'unknown',
        'description': manifest.description or '',
        'repository_url': manifest.src_repo or '',
        'documentation_url': manifest.documentationUrl or '',
    }
    return tool_info


def extract_parameters_summary(manifest: ManifestModel) -> list:
    """Extract a summary of parameters from the manifest."""
    params_summary = []

    if not manifest.parameters:
        return params_summary

    for param_num in sorted(manifest.parameters.keys()):
        param = manifest.parameters[param_num]

        param_info = {
            'name': param.name,
            'description': param.description or '',
            'type': param.TYPE or param.type_class or 'unknown',
            'required': param.optional != 'on',
            'default_value': param.default_value or '',
            'file_format': param.fileFormat or '',
            'choices': param.value or '',
            'prefix': param.prefix_when_specified or param.prefix or '',
            'num_values': param.numValues or '',
        }
        params_summary.append(param_info)

    return params_summary


def extract_planning_data(manifest: ManifestModel) -> dict:
    """Extract planning data from the manifest in the format expected by generate-module.py."""
    params_summary = extract_parameters_summary(manifest)

    # Build parameters in the planning data format
    parameters = []
    for param in params_summary:
        param_entry = {
            'name': param['name'],
            'type': param['type'],
            'description': param['description'],
            'required': param['required'],
            'default_value': param['default_value'],
        }
        if param['file_format']:
            param_entry['file_format'] = param['file_format']
        if param['choices']:
            param_entry['choices'] = param['choices']
        if param['prefix']:
            param_entry['prefix'] = param['prefix']
        if param['num_values']:
            param_entry['num_values'] = param['num_values']
        parameters.append(param_entry)

    planning_data = {
        'module_name': manifest.name or 'Unknown',
        'parameters': parameters,
        'docker_image_tag': manifest.job_docker_image or '',
        'categories': manifest.categories or '',
        'task_type': manifest.taskType or '',
        'author': manifest.author or 'GenePattern Team',
        'command_line': manifest.commandLine or '',
    }

    return planning_data


def generate_prompt(manifest: ManifestModel, include_instructions: str = '') -> str:
    """Generate a prompt in the exact same format as generate-module.py uses for manifest generation."""
    tool_info = extract_tool_info(manifest)
    planning_data = extract_planning_data(manifest)

    # Build the instructions section if provided
    instructions_section = ""
    if include_instructions:
        instructions_section = f"\n\nAdditional Instructions (IMPORTANT):\n{include_instructions}\n"

    # Build the prompt in the exact same format as generate-module.py
    prompt = f"""Generate a complete GenePattern module manifest for {tool_info['name']}.

Tool Information:
- Name: {tool_info['name']}
- Version: {tool_info.get('version', '1.0')}
- Language: {tool_info.get('language', 'unknown')}
- Description: {tool_info.get('description', 'Bioinformatics analysis tool')}
- Repository: {tool_info.get('repository_url', '')}{instructions_section}

Planning Data:
{planning_data}

Generate a complete, valid manifest file in key=value format."""

    return prompt


def process_single_file(input_path: Path, output_path: Optional[Path], instructions: str) -> int:
    """Process a single manifest file and write the prompt."""
    try:
        with open(input_path, 'r') as f:
            manifest_content = f.read()

        manifest = ManifestModel.from_manifest_string(manifest_content)
    except Exception as e:
        print(f"Error parsing manifest file {input_path}: {e}", file=sys.stderr)
        return 1

    # Generate the prompt
    prompt = generate_prompt(manifest, instructions)

    # Output the prompt
    if output_path:
        try:
            with open(output_path, 'w') as f:
                f.write(prompt)
            print(f"Prompt written to: {output_path}")
        except Exception as e:
            print(f"Error writing output file {output_path}: {e}", file=sys.stderr)
            return 1
    else:
        print(prompt)

    return 0


def process_directory(input_dir: Path, output_dir: Path, instructions: str) -> int:
    """Process all manifest files in a directory."""
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all manifest files (files without extension or named 'manifest')
    manifest_files = []
    for item in input_dir.iterdir():
        if item.is_file():
            # Include files named 'manifest' or files without an extension
            # Also include common manifest-like files
            if item.name == 'manifest' or item.suffix == '' or item.name.endswith('.properties'):
                manifest_files.append(item)

    if not manifest_files:
        print(f"No manifest files found in {input_dir}", file=sys.stderr)
        return 1

    print(f"Found {len(manifest_files)} manifest file(s) in {input_dir}")

    errors = 0
    for manifest_file in manifest_files:
        try:
            with open(manifest_file, 'r') as f:
                manifest_content = f.read()

            manifest = ManifestModel.from_manifest_string(manifest_content)

            # Use the module name for the output filename
            module_name = manifest.name or manifest_file.stem or 'unknown'
            # Sanitize the module name for use as a filename
            safe_name = module_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
            output_file = output_dir / f"{safe_name}.txt"

            prompt = generate_prompt(manifest, instructions)

            with open(output_file, 'w') as f:
                f.write(prompt)

            print(f"  Processed: {manifest_file.name} -> {output_file.name}")

        except Exception as e:
            print(f"  Error processing {manifest_file.name}: {e}", file=sys.stderr)
            errors += 1

    print(f"\nCompleted: {len(manifest_files) - errors} succeeded, {errors} failed")
    return 0 if errors == 0 else 1


def main(args=None):
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Reverse engineer a prompt from an existing GenePattern manifest file or directory of manifests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate prompt from a single file and print to stdout
  python generate_prompt.py --input manifest
  
  # Generate prompt from a single file and save to file
  python generate_prompt.py --input manifest --output prompt.txt
  
  # Process all manifests in a directory
  python generate_prompt.py --input ../manifests --output ../prompts
  
  # Include additional instructions in the prompt
  python generate_prompt.py --input manifest --instructions "Focus on RNA-seq analysis"
        """
    )

    parser.add_argument('--input', '-i', required=True, type=str,
                        help='Path to a manifest file or directory of manifest files')
    parser.add_argument('--output', '-o', type=str,
                        help='Output file path (for single file) or directory (for directory input). If not specified, prints to stdout (single file only)')
    parser.add_argument('--instructions', type=str, default='',
                        help='Additional instructions to include in the prompt')

    parsed_args = parser.parse_args(args)

    input_path = Path(parsed_args.input)

    if not input_path.exists():
        print(f"Error: Input path not found: {input_path}", file=sys.stderr)
        return 1

    if input_path.is_dir():
        # Directory mode
        if not parsed_args.output:
            print("Error: --output directory is required when processing a directory", file=sys.stderr)
            return 1
        output_path = Path(parsed_args.output)
        return process_directory(input_path, output_path, parsed_args.instructions)
    else:
        # Single file mode
        output_path = Path(parsed_args.output) if parsed_args.output else None
        return process_single_file(input_path, output_path, parsed_args.instructions)


if __name__ == "__main__":
    sys.exit(main())
