#!/usr/bin/env python
"""
Sample Python wrapper script for GenePattern module.

This script demonstrates a typical Python wrapper that:
- Parses command line arguments
- Processes input data  
- Calls the actual analysis module
- Handles output generation
"""

import argparse
import os
import sys
import subprocess


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Sample GenePattern Python wrapper")
    
    parser.add_argument('--input', 
                       required=True,
                       help='Input data file')
    
    parser.add_argument('--output',
                       default='output.txt', 
                       help='Output file name')
    
    parser.add_argument('--method',
                       choices=['pearson', 'spearman', 'kendall'],
                       default='pearson',
                       help='Correlation method')
    
    parser.add_argument('--threshold',
                       type=float,
                       default=0.05,
                       help='P-value threshold')
    
    parser.add_argument('--verbose',
                       action='store_true',
                       help='Enable verbose output')
    
    return parser.parse_args()


def validate_input(input_file):
    """Validate input file exists and is readable."""
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    if not os.access(input_file, os.R_OK):
        raise PermissionError(f"Cannot read input file: {input_file}")
    
    return True


def run_analysis(input_file, output_file, method, threshold, verbose=False):
    """Run the actual analysis module."""
    cmd = [
        'python', 'analysis_module.py',
        '--input', input_file,
        '--output', output_file, 
        '--method', method,
        '--threshold', str(threshold)
    ]
    
    if verbose:
        cmd.append('--verbose')
        print(f"Running command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        if verbose:
            print("Analysis completed successfully")
            if result.stdout:
                print("STDOUT:", result.stdout)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Analysis failed with exit code {e.returncode}")
        if e.stderr:
            print("STDERR:", e.stderr)
        return False


def main():
    """Main wrapper function."""
    try:
        # Parse arguments
        args = parse_arguments()
        
        # Validate input
        validate_input(args.input)
        
        # Run analysis
        success = run_analysis(
            args.input,
            args.output, 
            args.method,
            args.threshold,
            args.verbose
        )
        
        if success:
            print(f"Analysis completed. Output written to: {args.output}")
            sys.exit(0)
        else:
            print("Analysis failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
