#!/bin/bash
# Sample Bash wrapper script for GenePattern module
#
# This script demonstrates a typical Bash wrapper that:
# - Parses command line arguments
# - Validates inputs
# - Calls the actual analysis tool
# - Handles outputs and error checking

set -e  # Exit on any error

# Default parameter values
input_file=""
output_file="output.txt"
method="default"
threshold=0.05
verbose=false

# Function to display usage
usage() {
    echo "Usage: $0 --input INPUT_FILE [OPTIONS]"
    echo ""
    echo "Required arguments:"
    echo "  --input FILE        Input data file"
    echo ""
    echo "Optional arguments:"
    echo "  --output FILE       Output file (default: output.txt)"
    echo "  --method METHOD     Analysis method (default: default)"
    echo "  --threshold FLOAT   Threshold value (default: 0.05)"
    echo "  --verbose           Enable verbose output"
    echo "  --help              Show this help message"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --input)
            input_file="$2"
            shift 2
            ;;
        --output)
            output_file="$2"
            shift 2
            ;;
        --method)
            method="$2"
            shift 2
            ;;
        --threshold)
            threshold="$2"
            shift 2
            ;;
        --verbose)
            verbose=true
            shift
            ;;
        --help)
            usage
            ;;
        *)
            echo "Error: Unknown option $1"
            usage
            ;;
    esac
done

# Validate required arguments
if [[ -z "$input_file" ]]; then
    echo "Error: --input is required"
    usage
fi

# Validate input file exists
if [[ ! -f "$input_file" ]]; then
    echo "Error: Input file does not exist: $input_file"
    exit 1
fi

# Validate input file is readable
if [[ ! -r "$input_file" ]]; then
    echo "Error: Cannot read input file: $input_file"
    exit 1
fi

# Print parameters if verbose
if [[ "$verbose" == true ]]; then
    echo "Running analysis with parameters:"
    echo "  Input: $input_file"
    echo "  Output: $output_file"
    echo "  Method: $method"
    echo "  Threshold: $threshold"
fi

# Create output directory if needed
output_dir=$(dirname "$output_file")
if [[ ! -d "$output_dir" ]]; then
    mkdir -p "$output_dir"
fi

# Run the actual analysis
echo "Starting analysis..."

# Example: call an R script, Python script, or other tool
if [[ "$verbose" == true ]]; then
    Rscript analysis.R \
        --input "$input_file" \
        --output "$output_file" \
        --method "$method" \
        --threshold "$threshold" \
        --verbose
else
    Rscript analysis.R \
        --input "$input_file" \
        --output "$output_file" \
        --method "$method" \
        --threshold "$threshold"
fi

# Check if analysis succeeded
if [[ $? -eq 0 ]]; then
    echo "Analysis completed successfully"
    echo "Output written to: $output_file"
else
    echo "Analysis failed"
    exit 1
fi

# Validate output was created
if [[ ! -f "$output_file" ]]; then
    echo "Warning: Expected output file was not created: $output_file"
    exit 1
fi

echo "Wrapper script completed successfully"
