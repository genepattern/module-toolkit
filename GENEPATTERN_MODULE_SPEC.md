# GenePattern Module Specification

This document defines the exact format and rules for the two primary artifacts in a GenePattern module: the **manifest file** and the **wrapper script**. It is derived from the linters, agents, examples, and generated outputs in this toolkit.

---

## 1. Module Manifest File

### Format

- **Filename**: Exactly `manifest` (no extension, lowercase)
- **Format**: Java `.properties` key=value text file
- **Encoding**: UTF-8 (fallback: ISO-8859-1)
- **Comments**: Lines starting with `#` or `!`
- **Colons in values**: Must be escaped with a backslash (e.g., `urn\:lsid\:...`, `genepattern/tool\:1.0`)
- **Non-ASCII characters**: Forbidden (codepoints > 127). The GenePattern database does not support Unicode. Replace:
  - `—` → `--`, `–` → `-`
  - `'` `'` → `'`, `"` `"` → `"`
  - `…` → `...`
  - Accented letters → ASCII equivalents

---

### Required Fields

#### Core Fields

| Key | Format / Example | Notes |
|-----|-----------------|-------|
| `LSID` | `urn:lsid:genepattern.org:module.analysis:00001:1` | Colons may be escaped with `\` |
| `name` | `Samtools.SamToBam` | Module display name in UI |
| `commandLine` | `python wrapper.py <input.file> <output.name>` | See Command Line Template section |

#### Required Metadata Fields

| Key | Format / Example | Notes |
|-----|-----------------|-------|
| `author` | `Jane Smith` | ASCII only — no accented characters |
| `description` | `Converts SAM to BAM format` | ASCII only |
| `categories` | `RNA-seq;Alignment` | Semicolon-separated |
| `language` | `Python` | `Python`, `R`, `Java`, `any` |
| `os` | `any` | `any`, `linux`, `windows` |
| `taskType` | `RNA-seq` | Free-form task category |
| `quality` | `production` | `production`, `preproduction`, `development` |
| `privacy` | `public` | `public`, `private` |

---

### Optional Metadata Fields

| Key | Format / Example | Notes                                                                                                       |
|-----|-----------------|-------------------------------------------------------------------------------------------------------------|
| `version` | `1.0.0` | Semantic version preferred                                                                                  |
| `cpuType` | `any` | `any` or specific type                                                                                      |
| `fileFormat` | `txt;bam;sam` | Semicolon-separated extensions (no leading `.`).  Used to  indicate formats of files this module generates. |
| `documentationUrl` | `https://...` | External documentation URL.  Either documentationUrl or taskDoc must be defined.                            |
| `taskDoc` | `doc.html` | Local documentation file. Either documentationUrl or taskDoc must be defined.                                                                                  |
| `publicationDate` | `MM/DD/YYYY HH\:MM` | Colon in time must be escaped                                                                               |
| `userid` | `username` | Module owner                                                                                                |
| `JVMLevel` | (blank or JVM version) | Leave blank if not Java                                                                                     |
| `src.repo` | `https://github.com/...` | Source repository                                                                                           |

---

### Job Resource Fields

| Key | Format / Example | Notes |
|-----|-----------------|-------|
| `job.cpuCount` | `4` | Number of CPUs |
| `job.memory` | `8Gb` | Memory allocation |
| `job.walltime` | `24h` | Maximum runtime |
| `job.docker.image` | `genepattern/samtools\:1.0` | **Colon MUST be escaped with `\`** |

---

### Command Line Template

The `commandLine` value is a template with parameter placeholders:

```
commandLine=python wrapper.py --input.file <input.file> --output.name <output.name>
```

- Placeholders use angle brackets: `<parameter.name>`
- The placeholder name must match the parameter's `p<N>_name` value exactly
- All defined parameters must appear in the command line
- The command references the wrapper script (e.g., `python wrapper.py`) or tool executable
- Placeholders may also be keys for any entries in genepattern.properties

---

### Parameter Definition

Parameters are numbered sequentially starting at `p1` with **no gaps**.
If `p1`, `p2`, `p3` exist, `p2` must exist (no skipping).

**Complete parameter field set:**

```properties
p<N>_name=input.file
p<N>_description=Human-readable description of this parameter
p<N>_optional=
p<N>_TYPE=FILE
p<N>_type=java.io.File
p<N>_MODE=IN
p<N>_fileFormat=txt;bam;sam
p<N>_numValues=1..1
p<N>_prefix_when_specified=--input.file
p<N>_default_value=
p<N>_value=
p<N>_range=
```

#### Parameter Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `p<N>_name` | **Required** | Parameter name using **dots** as separators (e.g., `input.file`, `quality.threshold`) |
| `p<N>_description` | **Required** | Clear explanation of the parameter |
| `p<N>_optional` | **Required** | Empty string = required; `on` = optional |
| `p<N>_TYPE` | Recommended | GenePattern shorthand: `FILE`, `TEXT`, `Integer`, `Float`, `Floating Point` |
| `p<N>_type` | **Required** | Java class: `java.io.File`, `java.lang.String`, `java.lang.Integer`, `java.lang.Float` |
| `p<N>_MODE` | **Required** | `IN` (input file), `OUT` (output file), or empty for non-file parameters |
| `p<N>_fileFormat` | For FILE type | Semicolon-separated accepted extensions, e.g., `txt;csv;bam` |
| `p<N>_numValues` | **Required** | Cardinality: `0..1`, `1..1`, `0+`, `1+`, `N..M`, or exact integer |
| `p<N>_prefix_when_specified` | Recommended | CLI flag added only when parameter is provided (e.g., `--input.file`). **Must use dots matching `p<N>_name`** |
| `p<N>_prefix` | Rarely used | CLI flag added unconditionally |
| `p<N>_default_value` | Optional | Default value when parameter is not specified |
| `p<N>_value` | For choices | Semicolon-separated choices: `Display\=value;Display2\=value2` |
| `p<N>_range` | For numeric | Allowed range, e.g., `0..255` |
| `p<N>_choiceDir` | Optional | URL to directory for file choices |
| `p<N>_choiceDirFilter` | Optional | Glob filter for `choiceDir`, e.g., `*.fa;*.fasta` |

#### Parameter Type Mapping

| GenePattern TYPE | Java type | Use case |
|-----------------|-----------|----------|
| `FILE` | `java.io.File` | Input or output file |
| `TEXT` | `java.lang.String` | Free-form text, enumerations |
| `Integer` | `java.lang.Integer` | Whole numbers |
| `Float` / `Floating Point` | `java.lang.Float` | Decimal numbers |

#### numValues Format

| Value | Meaning |
|-------|---------|
| `0..1` | Optional single value |
| `1..1` | Required single value |
| `0+` | Zero or more values |
| `1+` | One or more values |
| `N..M` | Between N and M values |
| `N` | Exactly N values |

#### Choice Parameter Format

```properties
p3_value=Human\=Human (Gencode v37);Mouse\=Mouse (Gencode M26);Yes\=true;No\=false
```

The format is `DisplayLabel\=commandLineValue` pairs separated by `;`. The equals sign in each pair must be escaped with `\`.

---

### Validation Rules (Manifest Linter)

1. Filename must be exactly `manifest`
2. Each line is `key=value`; keys have no whitespace or special characters
3. No duplicate keys
4. `LSID` must start with `urn:lsid:` or `urn\:lsid\:`
5. `name` and `commandLine` must be non-empty
6. `author`, `description`, `categories`, `language`, `os`, `taskType`, `quality`, and `privacy` are required metadata fields
7. Parameters numbered sequentially from `p1` with no gaps
8. Each parameter must have `description`, `optional`, `type`, `MODE`, and `numValues` fields
9. FILE-type parameters must have `MODE` set to `IN` or `OUT`
10. `prefix_when_specified` must use dots matching the parameter name (not dashes)
11. `job.docker.image` must have the colon before the tag escaped: `image\:tag`
12. `quality` must be `production`, `preproduction`, or `development`
13. `privacy` must be `public` or `private`
14. `os` must be `any`, `linux`, `windows`, or similar known value
15. No non-ASCII characters (> codepoint 127) anywhere in the file
16. `author` must be ASCII-only (no accented characters)
17. `version` should follow semantic versioning

---

### Complete Manifest Example

```properties
# GenePattern Module Manifest

LSID=urn:lsid:genepattern.org:module.analysis:00001:1
name=Samtools.SamToBam
commandLine=python wrapper.py --input.sam.file <input.sam.file> --output.file.name <output.file.name> --num.threads <num.threads>
author=GenePattern Team
version=1.0
description=Converts SAM files to BAM format using samtools view
taskType=RNA-seq
quality=production
privacy=public
cpuType=any
os=any
language=Python
JVMLevel=
job.docker.image=genepattern/samtools\:1.0
job.memory=4Gb
job.cpuCount=4
src.repo=https://github.com/genepattern/samtools
fileFormat=sam

p1_name=input.sam.file
p1_description=Input SAM file to convert to BAM format
p1_optional=
p1_TYPE=FILE
p1_type=java.io.File
p1_MODE=IN
p1_fileFormat=sam
p1_numValues=1..1
p1_prefix_when_specified=--input.sam.file

p2_name=output.file.name
p2_description=Name for the output BAM file (default derived from input filename)
p2_optional=on
p2_TYPE=TEXT
p2_type=java.lang.String
p2_numValues=0..1
p2_prefix_when_specified=--output.file.name
p2_default_value=

p3_name=num.threads
p3_description=Number of compression threads to use
p3_optional=on
p3_TYPE=Integer
p3_type=java.lang.Integer
p3_numValues=0..1
p3_prefix_when_specified=--num.threads
p3_default_value=1
p3_range=1..64
```

---

## 2. Wrapper Script

### Supported Languages

| Language | Extension | Shebang |
|----------|-----------|---------|
| Python | `.py` | `#!/usr/bin/env python3` |
| R | `.R` or `.r` | `#!/usr/bin/env Rscript` |
| Bash | `.sh` | `#!/bin/bash` |

Python wrappers are preferred for complex tools. R wrappers are used when the tool is R-based.

---

### Critical Convention: Dot-Based Parameter Names

**The single most important rule:** argument flags in the wrapper must use **dots**, matching the manifest `p<N>_name` and `p<N>_prefix_when_specified` exactly.

| Location | Format | Example |
|----------|--------|---------|
| Manifest `p<N>_name` | dots | `input.sam.file` |
| Manifest `commandLine` placeholder | dots | `<input.sam.file>` |
| Manifest `p<N>_prefix_when_specified` | dots | `--input.sam.file` |
| Wrapper argparse flag | **dots** | `--input.sam.file` |

**Wrong** (causes runtime failure):
```python
parser.add_argument('--input-sam-file', ...)   # dashes instead of dots
parser.add_argument('--input_sam_file', ...)   # underscores instead of dots
```

**Correct:**
```python
parser.add_argument('--input.sam.file', dest='input_sam_file', ...)
```

Python's `argparse` accepts dot-notation flags; the `dest` parameter maps the dotted flag to a Python-valid attribute name using underscores.

---

### Python Wrapper Structure

```python
#!/usr/bin/env python3
"""
Wrapper script for [Module Name] GenePattern module.

[One-paragraph description of what this module does.]
"""

import argparse
import logging
import os
import subprocess
import sys


TOOL_NAME = "module.name"
EXECUTABLE = "tool-binary"   # or full path if not on PATH


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format="%(levelname)s: %(message)s",
    )


def parse_arguments():
    """Parse GenePattern-style command-line arguments.

    Flag names use dots (e.g. --input.file) to match manifest parameter names.
    """
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="[Description]",
    )

    # Required FILE parameter
    parser.add_argument(
        "--input.file",
        dest="input_file",
        required=True,
        help="Input file",
    )

    # Optional TEXT parameter with default
    parser.add_argument(
        "--output.prefix",
        dest="output_prefix",
        default="output",
        help="Prefix for output files",
    )

    # Optional Integer parameter
    parser.add_argument(
        "--num.threads",
        dest="num_threads",
        type=int,
        default=1,
        help="Number of threads",
    )

    return parser.parse_args()


def validate_inputs(args):
    if not os.path.exists(args.input_file):
        raise FileNotFoundError(f"Input file not found: {args.input_file}")
    # Add additional validation as needed


def run_tool(args):
    cmd = [
        EXECUTABLE,
        "--input", args.input_file,
        "--output", args.output_prefix,
        "--threads", str(args.num_threads),
    ]

    logging.info(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            logging.info(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Tool failed with exit code {e.returncode}")
        if e.stderr:
            logging.error(e.stderr)
        return False


def main():
    args = parse_arguments()
    setup_logging()

    try:
        validate_inputs(args)
        success = run_tool(args)
        sys.exit(0 if success else 1)
    except Exception as e:
        logging.error(f"Wrapper execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

---

### R Wrapper Structure

```r
#!/usr/bin/env Rscript

# Wrapper for [Module Name] GenePattern module
# [Description]

suppressPackageStartupMessages({
    library(optparse)
})

option_list <- list(
    make_option("--input.file",   type="character", default=NULL,
                help="Input file path"),
    make_option("--output.prefix", type="character", default="output",
                help="Prefix for output files"),
    make_option("--num.threads",  type="integer",   default=1,
                help="Number of threads")
)

parser <- OptionParser(option_list=option_list)
args   <- parse_args(parser)

# Validate
if (is.null(args$input.file) || !file.exists(args$input.file)) {
    stop(paste("Input file not found:", args$input.file))
}

# Execute
tryCatch({
    # ... tool logic here ...
    message("Completed successfully")
}, error = function(e) {
    message("ERROR: ", conditionMessage(e))
    quit(status=1)
})
```

---

### Bash Wrapper Structure

```bash
#!/bin/bash
set -euo pipefail

# Wrapper for [Module Name] GenePattern module

INPUT_FILE=""
OUTPUT_PREFIX="output"
NUM_THREADS=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --input.file)    INPUT_FILE="$2";    shift 2 ;;
        --output.prefix) OUTPUT_PREFIX="$2"; shift 2 ;;
        --num.threads)   NUM_THREADS="$2";   shift 2 ;;
        *) echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
    esac
done

# Validate
if [[ ! -f "$INPUT_FILE" ]]; then
    echo "ERROR: Input file not found: $INPUT_FILE" >&2
    exit 1
fi

# Execute
tool-binary \
    --input "$INPUT_FILE" \
    --output "$OUTPUT_PREFIX" \
    --threads "$NUM_THREADS"
```

---

### Wrapper Validation Rules (Wrapper Linter)

1. File must exist and be readable
2. Must have a valid shebang line for the detected language
3. **Python**: Full AST parse must succeed (no syntax errors)
4. **Bash**: `bash -n` must pass
5. **R**: `Rscript --parse` must pass
6. All parameter names defined in the manifest must appear in the wrapper
7. Must include error handling (try/except in Python, tryCatch in R, set -e in Bash)
8. Must use appropriate exit codes (0 = success, non-zero = failure)
9. Input files must be validated before use
10. subprocess calls must use `check=True` or equivalent to propagate errors

---

## 3. Cross-Artifact Consistency Rules

These rules apply across manifest and wrapper together:

1. **Every** parameter `p<N>_name` in the manifest must appear as a `--dot.notation` flag in the wrapper.
2. **Every** parameter in the manifest must appear in `commandLine` as `<parameter.name>`.
3. `p<N>_prefix_when_specified` must exactly equal `--` + `p<N>_name` (dots, not dashes).
4. The wrapper filename referenced in `commandLine` must match the actual wrapper file (e.g., `wrapper.py`).
5. The `job.docker.image` must include all Python packages and tool binaries required by the wrapper.
6. Parameter cardinality (`p<N>_numValues`) must be consistent with whether the wrapper argument is `required=True` or has a `default`.

---

## 4. LSID Assignment

LSIDs uniquely identify modules and must follow this format:

```
urn:lsid:<authority>:<namespace>:<object>:<revision>
```

| Component | Common Values |
|-----------|--------------|
| authority | `genepattern.org`, `broad.mit.edu` |
| namespace | `module.analysis` |
| object | Numeric ID (assigned by GenePattern server) or placeholder |
| revision | Starts at `1`, increments on each version update |

For new modules during development, use a placeholder like `00000` for the object ID. The GenePattern server assigns the permanent LSID upon first installation.
