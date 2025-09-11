#!/usr/bin/env Rscript
# Sample R wrapper script for GenePattern module
#
# This script demonstrates a typical R wrapper that:
# - Parses command line arguments using optparse
# - Validates inputs
# - Calls analysis functions
# - Handles outputs and error checking

# Load required libraries
suppressPackageStartupMessages({
  library(optparse)
})

# Define command line options
option_list <- list(
  make_option(c("--input"), 
              type="character", 
              default=NULL,
              help="Input data file [required]"),
  
  make_option(c("--output"), 
              type="character", 
              default="output.txt",
              help="Output file name [default: output.txt]"),
  
  make_option(c("--method"), 
              type="character", 
              default="pearson",
              help="Correlation method (pearson, spearman, kendall) [default: pearson]"),
  
  make_option(c("--threshold"), 
              type="double", 
              default=0.05,
              help="P-value threshold [default: 0.05]"),
  
  make_option(c("--verbose"), 
              action="store_true", 
              default=FALSE,
              help="Enable verbose output")
)

# Parse arguments
parser <- OptionParser(
  usage = "%prog --input INPUT_FILE [options]",
  option_list = option_list,
  description = "Sample GenePattern R wrapper script"
)

args <- parse_args(parser)

# Validate required arguments
if (is.null(args$input)) {
  cat("Error: --input is required\n")
  print_help(parser)
  quit(status=1)
}

# Validate input file
if (!file.exists(args$input)) {
  cat("Error: Input file does not exist:", args$input, "\n")
  quit(status=1)
}

# Print parameters if verbose
if (args$verbose) {
  cat("Running analysis with parameters:\n")
  cat("  Input:", args$input, "\n")
  cat("  Output:", args$output, "\n") 
  cat("  Method:", args$method, "\n")
  cat("  Threshold:", args$threshold, "\n")
}

# Function to run analysis
run_analysis <- function(input_file, output_file, method, threshold, verbose=FALSE) {
  tryCatch({
    # Example analysis: read data and compute correlations
    if (verbose) cat("Reading input data...\n")
    
    # Read input data (assuming it's a matrix or data frame)
    data <- read.table(input_file, header=TRUE, sep="\t", row.names=1)
    
    if (verbose) cat("Computing correlations using method:", method, "\n")
    
    # Compute correlation matrix
    cor_matrix <- cor(data, method=method, use="complete.obs")
    
    # Apply threshold if specified
    if (!is.na(threshold)) {
      if (verbose) cat("Applying threshold:", threshold, "\n")
      cor_matrix[abs(cor_matrix) < threshold] <- 0
    }
    
    # Write output
    if (verbose) cat("Writing output to:", output_file, "\n")
    write.table(cor_matrix, file=output_file, sep="\t", quote=FALSE)
    
    if (verbose) cat("Analysis completed successfully\n")
    return(TRUE)
    
  }, error = function(e) {
    cat("Error during analysis:", e$message, "\n")
    return(FALSE)
  })
}

# Create output directory if needed
output_dir <- dirname(args$output)
if (!dir.exists(output_dir)) {
  dir.create(output_dir, recursive=TRUE)
}

# Run the analysis
cat("Starting analysis...\n")
success <- run_analysis(
  args$input,
  args$output,
  args$method, 
  args$threshold,
  args$verbose
)

# Check results
if (success) {
  cat("Analysis completed successfully\n")
  cat("Output written to:", args$output, "\n")
  
  # Verify output file was created
  if (!file.exists(args$output)) {
    cat("Warning: Expected output file was not created\n")
    quit(status=1)
  }
  
  quit(status=0)
} else {
  cat("Analysis failed\n")
  quit(status=1)
}
