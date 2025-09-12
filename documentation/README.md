# GenePattern Documentation Linter

A production-ready linter for validating documentation files across multiple formats and sources.

## Overview

The documentation linter validates documentation files through comprehensive checks including content retrieval from files or URLs, format parsing, and optional module/parameter presence validation. It supports HTML, Markdown, PDF, and plain text formats from both local files and web URLs.

## Usage

```bash
python documentation/linter.py [PATH_OR_URL] [OPTIONS]
```

### Arguments

- `PATH_OR_URL` - Path to documentation file OR HTTP/HTTPS URL to documentation

### Options

- `--module MODULE` - Expected module name for validation (optional)
- `--parameters PARAM1 PARAM2 ...` - List of expected parameter names for validation (optional)

### Examples

```bash
# Basic documentation validation (local file)
python documentation/linter.py /path/to/docs.html

# Validate documentation from URL
python documentation/linter.py https://example.com/docs/module.html

# Include module validation
python documentation/linter.py docs.md --module CorrelationMatrix

# Include parameter validation
python documentation/linter.py docs.txt --parameters input output method threshold

# Full validation with module and parameters
python documentation/linter.py https://docs.site.com/api.html --module MyModule --parameters input.file gene.sets.database permutations

# Different format examples
python documentation/linter.py module_guide.pdf --module spatialGE.STenrich
python documentation/linter.py README.md --parameters dataset.file chip.platform
```

## Supported Formats

### Local File Formats
- **HTML** (`.html`, `.htm`) - Parsed with BeautifulSoup4 or fallback text extraction
- **Markdown** (`.md`, `.markdown`) - Treated as plain text with markdown syntax
- **PDF** (`.pdf`) - Text extraction using PyPDF2
- **Plain Text** (`.txt`) - Direct text parsing

### Remote Sources
- **HTTP/HTTPS URLs** - Any of the above formats served over web protocols
- **Content-Type Detection** - Automatic format detection from HTTP headers
- **Timeout Handling** - 30-second timeout for web requests

## Validation Tests

The linter runs the following modular tests:

### 1. Content Retrieval (`test_content_retrieval.py`)
- **Purpose**: Retrieves and parses documentation content
- **Checks**:
  - File/URL exists and is accessible
  - Content can be retrieved successfully
  - Format detection (HTML, Markdown, PDF, TXT)
  - Text extraction from formatted content
  - Content is not empty after processing
- **Dependencies**: 
  - `requests` for URL access
  - `beautifulsoup4` for HTML parsing (optional, has fallback)
  - `PyPDF2` for PDF text extraction

### 2. Module Validation (`test_module_validation.py`)
- **Purpose**: Validates module name presence (conditional)
- **Checks**:
  - Exact case-sensitive module name matching
  - Case-insensitive module name matching
  - Pattern matching for common module formats
  - LSID component matching for complex identifiers
  - Multiple search strategies to find module references
- **Requirements**: Requires `--module` argument

### 3. Parameter Validation (`test_parameter_validation.py`)
- **Purpose**: Validates parameter name presence (conditional)
- **Checks**:
  - Exact parameter name matching
  - Case-insensitive parameter matching
  - Pattern matching for parameter formats:
    - Command-line flags (`--parameter`, `-p`)
    - Variable assignments (`parameter=value`)
    - Dotted names (`parameter.file`)
    - Template variables (`<parameter>`, `${parameter}`)
  - Handles complex parameter naming conventions
- **Requirements**: Requires `--parameters` argument

## Exit Codes

- `0` - All validation checks passed
- `1` - One or more validation checks failed

## Output Examples

### Success (Basic Validation)
```
Running modular tests on documentation file: /path/to/docs.html
  Test 'Test Content Retrieval': 1 info message(s)
  Test 'Test Module Validation': 1 info message(s)
  Test 'Test Parameter Validation': 1 info message(s)
Ran 3 test module(s)

PASS: Documentation '/path/to/docs.html' passed all validation checks.
```

### Success (URL with Full Validation)
```
Running modular tests on documentation URL: https://example.com/docs/api.html
  Test 'Test Content Retrieval': 1 info message(s)
  Test 'Test Module Validation': 2 info message(s)
  Test 'Test Parameter Validation': 5 info message(s)
Ran 3 test module(s)

PASS: Documentation 'https://example.com/docs/api.html' passed all validation checks.
```

### Failure (Content Issues)
```
Running modular tests on documentation file: /path/to/docs.pdf
  Test 'Test Content Retrieval': 1 error(s) found
  Test 'Test Module Validation': 1 error(s) found
  Test 'Test Parameter Validation': 1 error(s) found
Ran 3 test module(s)

FAIL: Documentation '/path/to/docs.pdf' failed 3 checks:
ERROR: PyPDF2 library not available - cannot parse PDF files (Install with: pip install PyPDF2)
ERROR: Cannot validate module: document content not available
ERROR: Cannot validate parameters: document content not available
```

### Failure (Module/Parameter Not Found)
```
Running modular tests on documentation file: /path/to/docs.md
  Test 'Test Content Retrieval': 1 info message(s)
  Test 'Test Module Validation': 1 error(s) found
  Test 'Test Parameter Validation': 2 error(s) found
Ran 3 test module(s)

FAIL: Documentation '/path/to/docs.md' failed 3 checks:
INFO: Successfully retrieved 1250 characters from MARKDOWN document
ERROR: Module name 'ExpectedModule' not found in documentation
ERROR: Parameter 'missing.param' not found in documentation
ERROR: Parameter 'another.missing' not found in documentation
```

## Dependencies

### Required
- Python 3.7+

### Optional (Recommended)
- **requests** (≥2.25.0): Required for URL validation
- **beautifulsoup4** (≥4.9.0): Recommended for HTML parsing (has fallback)
- **PyPDF2** (≥3.0.0): Required for PDF parsing

Install dependencies:
```bash
pip install requests beautifulsoup4 PyPDF2
```

### Graceful Degradation
- **Missing requests**: URLs cannot be validated, local files work normally
- **Missing beautifulsoup4**: HTML parsing uses simple text extraction fallback
- **Missing PyPDF2**: PDF files cannot be parsed, other formats work normally

## Use Cases

### Documentation Quality Assurance
- Validate that documentation mentions the correct module name
- Ensure all module parameters are documented
- Check documentation accessibility and format validity

### CI/CD Integration
- Include in build pipelines to catch documentation issues
- Automated validation of documentation completeness
- Prevent deployment with incomplete or incorrect documentation

### Documentation Auditing
- Check documentation coverage across multiple sources
- Verify external documentation links are accessible
- Ensure parameter documentation matches module definitions

### Multi-Format Support
- Validate documentation regardless of format (HTML, PDF, Markdown, etc.)
- Support for both local files and web-hosted documentation
- Consistent validation across different documentation sources

## Architecture

The linter uses a modular architecture with intelligent content processing:

- Content retrieval handles multiple formats and sources with appropriate parsers
- Module validation uses multiple search strategies to find module references
- Parameter validation employs format-aware pattern matching
- Shared context allows content to be parsed once and used by all validation tests
- Conditional testing only runs module/parameter validation when requested

The design emphasizes flexibility and robustness, allowing validation of diverse documentation sources while providing detailed feedback about content coverage and accessibility.

## Format-Specific Features

### HTML Processing
- Extracts clean text from HTML tags
- Preserves semantic structure for better matching
- Handles malformed HTML gracefully

### PDF Processing
- Extracts text content from all pages
- Handles multi-page documents
- Preserves text layout where possible

### Markdown Processing
- Treats as structured plain text
- Preserves formatting indicators
- No special markdown parsing required

### URL Processing
- Automatic content-type detection
- Timeout protection for slow responses
- HTTP error handling with clear messages
