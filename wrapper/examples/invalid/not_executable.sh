#!/bin/bash
# This bash script is valid but will not have execute permissions

echo "This script exists but is not executable"
echo "The linter should warn about missing execute permissions"

input="$1"
output="$2"

if [[ -z "$input" ]]; then
    echo "No input provided"
    exit 1
fi

echo "Processing $input -> $output"
