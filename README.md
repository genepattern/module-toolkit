<!-- BANNER: Replace the line below with your project banner image -->
<!-- ![GenePattern Module AI Toolkit Banner](docs/banner.png) -->

<div align="center">

# 🧬 GenePattern Module AI Toolkit

**Turn any bioinformatics command-line tool into a production-ready GenePattern module — automatically, in minutes.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: BSD-3](https://img.shields.io/badge/license-BSD--3--Clause-green)](LICENSE)
[![Powered by GenePattern](https://img.shields.io/badge/Powered%20by-GenePattern-blueviolet)](https://genepattern.ucsd.edu/)

</div>

---

## ✨ Why GenePattern Module AI Toolkit?

Packaging a bioinformatics tool for broad, reproducible use is genuinely hard. You need a Dockerfile, a wrapper script, a manifest, parameter groups, test definitions, and documentation — all correct, all consistent, all maintainable. We built the GenePattern Module AI Toolkit to eliminate that toil.

A multi-agent AI pipeline researches your tool, plans its architecture, generates every artifact, and validates each one — giving researchers a shareable, cloud-ready GenePattern module without writing a single line of boilerplate.

| | |
|---|---|
| 🧬 **Genomic Integration** | Natively targets the GenePattern ecosystem — supports Cloud, Notebook and the RESTful API. |
| 🤖 **AI/ML Workflows** | Six specialized LLM agents collaborate: Researcher → Planner → Generator → Validator, end-to-end. |
| ☁️ **Cloud Scalability** | Every generated module ships with a Dockerfile and is ready to deploy on GenePattern's cloud infrastructure. |
| 📊 **Reproducible Science** | Pinned dependencies, GPUnit test definitions, and versioned manifests mean your analysis runs the same way, every time. |

---

## 🚀 Quick Start

### 1 — Install

```bash
# Clone the repository
git clone https://github.com/genepattern/module-toolkit.git
cd module-toolkit

# Install dependencies (Python 3.10+ recommended)
pip install -r requirements.txt
```

> **Conda users:**
> ```bash
> conda create -n gp-toolkit python=3.11 && conda activate gp-toolkit
> pip install -r requirements.txt
> ```

### 2 — Configure (Optional)

The defaults work out of the box. To customise, copy the example env file:

```bash
cp .env.example .env   # then edit as needed
```

| Variable | Default | Description |
|---|---|---|
| `DEFAULT_LLM_MODEL` | `Qwen3` | LLM powering all agents |
| `BRAVE_API_KEY` | *(none)* | Enables web research (strongly recommended) |
| `MAX_ARTIFACT_LOOPS` | `5` | Max validation retries per artifact |
| `MAX_ESCALATIONS` | `2` | Max cross-artifact escalation attempts per artifact pair |
| `MODULE_OUTPUT_DIR` | `./generated-modules` | Where modules are written |
| `INPUT_TOKEN_COST_PER_1000` | `0.003` | Cost per 1 000 input tokens (for cost reporting) |
| `OUTPUT_TOKEN_COST_PER_1000` | `0.015` | Cost per 1 000 output tokens (for cost reporting) |

### 3 — Generate Your First Module

```bash
python generate-module.py
```

Follow the interactive prompts — the whole pipeline runs automatically:

```
Tool name: samtools
Tool version: 1.19
Primary language: C
Brief description: Tools for manipulating SAM/BAM files
Repository URL: https://github.com/samtools/samtools
Documentation URL: http://www.htslib.org/doc/samtools.html
```

That's it. In a few minutes you'll have a fully validated, ready-to-deploy GenePattern module.

---

## 🧠 How It Works

Six AI agents work in a coordinated pipeline, each with a focused domain of expertise:

```
┌──────────────┐    ┌──────────────┐    ┌───────────────────────────────────────────────┐
│  Researcher  │───▶│   Planner    │───▶│              Artifact Generators              │
│              │    │              │    │  Wrapper · Manifest · ParamGroups · GPUnit    │
│ Web search,  │    │ Map params,  │    │  Documentation · Dockerfile                   │
│ CLI analysis │    │ design arch  │    │  (each with built-in validation loop ✓)       │
└──────────────┘    └──────────────┘    └───────────────────────────────────────────────┘
                                                           │
                                              ┌────────────▼────────────┐
                                              │   Error Classifier      │
                                              │ Cross-artifact escalation│
                                              │ (e.g. Dockerfile failure │
                                              │  triggers wrapper regen) │
                                              └─────────────────────────┘
```

### Phase 1 · Research
The `researcher_agent` scours documentation, GitHub repositories, and published literature to build a comprehensive model of your tool — its CLI interface, parameters, dependencies, and common usage patterns.

### Phase 2 · Planning
The `planner_agent` translates raw research into a concrete implementation plan: GenePattern parameter type mappings, UI groupings, container strategy, and a validation checklist.

### Phase 3 · Artifact Generation & Validation
Six specialised agents generate each file in sequence. After every file is written, a dedicated linter validates it. If validation fails, the agent incorporates the feedback and retries — up to `MAX_ARTIFACT_LOOPS` times.

| Agent | Output File | Purpose |
|---|---|---|
| `wrapper_agent` | `wrapper.py` | Execution wrapper bridging GenePattern ↔ tool |
| `manifest_agent` | `manifest` | Module metadata, command line, parameter definitions |
| `paramgroups_agent` | `paramgroups.json` | UI parameter groupings & conditional visibility |
| `gpunit_agent` | `test.yml` | Automated GPUnit test definition |
| `documentation_agent` | `README.md` | End-user documentation |
| `dockerfile_agent` | `Dockerfile` | Reproducible, pinned container image |

### Cross-Artifact Escalation
When a downstream artifact fails validation and the root cause is traced to an upstream artifact (e.g. a `Dockerfile` runtime error caused by a wrong argparse flag in the wrapper), the pipeline automatically invalidates the upstream artifact, regenerates it with the downstream error injected as context, and retries the downstream artifact — up to `MAX_ESCALATIONS` times per pair.

---

## 📁 Output Structure

Every module lands in `{MODULE_OUTPUT_DIR}/{tool_name}_{timestamp}/`:

```
samtools_20260315_143022/
├── wrapper.py             # Python wrapper — GenePattern calls this at runtime
├── manifest               # Module metadata, command template & parameter schema
├── paramgroups.json       # UI groupings for the GenePattern Notebook interface
├── test.yml               # GPUnit test suite (run with gpunit validate .)
├── README.md              # Human-readable user documentation
├── Dockerfile             # Pinned, reproducible container definition
├── status.json            # Live pipeline state (resume support)
├── research.md            # Raw researcher output
└── plan.md                # Planner output
```

---

## 📡 Live Status & Final Report

The toolkit streams real-time progress to your terminal:

```
[14:30:22] INFO: Created module directory: ./generated-modules/samtools_20260315_143022
[14:30:22] INFO: Starting research on the bioinformatics tool
[14:30:25] INFO: Research phase completed successfully
[14:30:25] INFO: Starting module planning based on research findings
[14:30:28] INFO: Planning phase completed successfully
[14:30:31] INFO: Generating dockerfile (attempt 1/5)
[14:30:37] INFO: ✅ Validation passed
```

And delivers a full report at the end:

```
============================================================
 Final Report
============================================================
Tool: samtools   |   Directory: ./generated-modules/samtools_20260315_143022
Research ✓   Planning ✓   Parameters Identified: 23

  wrapper        Generated ✓   Validated ✓   Attempts: 1
  manifest       Generated ✓   Validated ✓   Attempts: 1
  paramgroups    Generated ✓   Validated ✓   Attempts: 1
  gpunit         Generated ✓   Validated ✓   Attempts: 1
  documentation  Generated ✓   Validated ✓   Attempts: 1
  dockerfile     Generated ✓   Validated ✓   Attempts: 2

Token Usage:
  Input tokens:  48,221
  Output tokens: 12,904
  Estimated cost: $0.3384

🎉 MODULE GENERATION SUCCESSFUL!
Your GenePattern module is ready in: ./generated-modules/samtools_20260315_143022
============================================================
```

---

## ⌨️ Command-Line Reference

### Non-interactive usage

Pass tool information directly on the command line to skip interactive prompts:

```bash
python generate-module.py \
  --name samtools \
  --version 1.19 \
  --language c \
  --description "Tools for manipulating SAM/BAM files" \
  --repository-url https://github.com/samtools/samtools \
  --documentation-url http://www.htslib.org/doc/samtools.html \
  --data /path/to/sample.bam
```

### Tool information flags

| Flag | Description |
|---|---|
| `--name NAME` | Tool name (e.g. `samtools`). When provided, skips interactive prompts. |
| `--version VERSION` | Tool version string (default: `latest`). |
| `--language LANG` | Primary implementation language — `python`, `r`, `bash`, `java`, etc. |
| `--description TEXT` | Short description of what the tool does. |
| `--repository-url URL` | Source code repository URL (used by the researcher agent). |
| `--documentation-url URL` | Tool documentation URL (used by the researcher agent). |
| `--instructions TEXT` | Free-form additional instructions passed to all agents — use this to specify which sub-command to expose, preferred parameter names, or any special requirements. |
| `--data PATH_OR_URL …` | One or more example data files (local paths or `http`/`https` URLs). URLs are downloaded before the pipeline starts. All files are bind-mounted into the container during the Dockerfile runtime test, and their formats inform the manifest's `fileFormat` field. Accepts multiple values: `--data file.bam file2.bai` |

### Artifact selection flags

By default all six artifacts are generated. Use these flags to generate only what you need.

| Flag | Description |
|---|---|
| `--artifacts ARTIFACT …` | Generate **only** the listed artifacts. Accepts one or more of: `wrapper`, `manifest`, `paramgroups`, `gpunit`, `documentation`, `dockerfile`, or `none` to skip all. |
| `--skip-wrapper` | Skip wrapper script generation. |
| `--skip-manifest` | Skip manifest generation. |
| `--skip-paramgroups` | Skip `paramgroups.json` generation. |
| `--skip-gpunit` | Skip GPUnit test file generation. |
| `--skip-documentation` | Skip `README.md` documentation generation. |
| `--skip-dockerfile` | Skip `Dockerfile` generation. |

**Examples:**

```bash
# Fastest iteration — skip the slow Docker build step
python generate-module.py --name mytool --skip-dockerfile

# Regenerate only the wrapper and manifest after editing
python generate-module.py --name mytool --artifacts wrapper manifest

# Generate nothing except the Dockerfile (e.g. update container only)
python generate-module.py --resume ./generated-modules/mytool_20260315_143022 \
  --artifacts dockerfile
```

### Resume & output flags

| Flag | Description |
|---|---|
| `--resume MODULE_DIR` | Resume a previous run from its `status.json`. Already-validated artifacts are skipped; failed or missing ones are retried. Can be combined with `--data` to supply fresh example data, or with `--artifacts` / `--skip-*` to regenerate specific artifacts. |
| `--output-dir DIR` | Root directory where module subdirectories are created (default: `./generated-modules`, overrides `MODULE_OUTPUT_DIR`). |
| `--module-dir PATH` | Write output directly into this pre-created directory instead of generating a new timestamped name. Used by the web UI. |

### Retry & escalation flags

| Flag | Default | Description |
|---|---|---|
| `--max-loops X` | `5` | Maximum LLM generation + validation attempts per artifact before giving up. |
| `--max-escalations N` | `2` | Maximum cross-artifact escalation attempts per upstream/downstream pair (e.g. wrapper → dockerfile). |

### Output & packaging flags

| Flag | Description |
|---|---|
| `--no-zip` | Skip creating a `.zip` archive of the generated artifacts. |
| `--zip-only` | Create the `.zip` archive and then delete the individual artifact files, keeping only the zip. |
| `--docker-push` | After successfully building the Docker image, push it to Docker Hub using the tag in the module's `docker_image_tag` field. |

---

## 🌐 Web UI

The toolkit also ships a Django-based web interface in the `app/` directory, which wraps `generate-module.py` for browser-based use. To start it:

```bash
cd app
python manage.py runserver
```

The web UI provides the same generation pipeline as the CLI, with a form-based input, real-time log streaming, and per-user run history.

---

## 🏗️ Code Structure

```
module-toolkit/
├── generate-module.py       # CLI entry point (GenerationScript)
├── agents/
│   ├── module.py            # ModuleAgent — main pipeline orchestrator
│   ├── config.py            # Environment-driven constants
│   ├── error_classifier.py  # Root-cause classifier & escalation rules
│   ├── example_data.py      # ExampleDataItem / ExampleDataResolver
│   ├── logger.py            # Logger utility
│   ├── models.py            # Shared Pydantic AI model definitions
│   ├── planner.py           # planner_agent
│   ├── researcher.py        # researcher_agent
│   ├── status.py            # ModuleGenerationStatus / ArtifactResult
│   └── validator.py         # validate_artifact dispatcher
├── dockerfile/
│   ├── agent.py             # dockerfile_agent
│   ├── linter.py            # Dockerfile linter
│   └── runtime.py           # build_runtime_command (docker test helper)
├── wrapper/
│   ├── agent.py             # wrapper_agent
│   ├── linter.py            # Wrapper linter
│   └── parser.py            # parse_wrapper_flags (argparse introspection)
├── manifest/                # manifest_agent + linter + models
├── paramgroups/             # paramgroups_agent + linter + models
├── gpunit/                  # gpunit_agent + linter
├── documentation/           # documentation_agent + linter
└── app/                     # Django web UI
```

---

## 🔭 Observability

The toolkit emits OpenTelemetry traces via [Logfire](https://logfire.pydantic.dev/) for every agent run — giving you deep visibility into research queries, planning decisions, artifact generation attempts, and validation outcomes. Telemetry is enabled automatically when a compatible collector is reachable on `localhost:4318`.

### Viewing traces locally with Jaeger

Spin up a local [Jaeger](https://www.jaegertracing.io/) all-in-one container (no configuration required):

```bash
docker run --rm -it --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest
```

Open [http://localhost:16686](http://localhost:16686) in your browser, run a module generation, and you'll see the full agent pipeline traced — including retries, token usage, and per-artifact timings.

---

## 🤝 Contributing & Community

We actively welcome contributions from both researchers and engineers. Whether you're fixing a bug, adding support for a new artifact type, or improving the prompts — your input matters.

- 🐛 **Found a bug?** [Open an issue](https://github.com/genepattern/module-toolkit/issues/new?template=bug_report.md)
- 💡 **Have an idea?** [Start a discussion](https://github.com/genepattern/module-toolkit/discussions)
- 🔧 **Ready to contribute?** Fork the repo, create a feature branch, and submit a PR.
- 💬 **GenePattern Community Forum:** [groups.google.com/g/genepattern-help](https://groups.google.com/g/genepattern-help)

---

## 📄 License

Distributed under the **BSD 3-Clause License**. See [`LICENSE`](LICENSE) for details.

---

## 📖 Citing This Work

If you use the GenePattern Module AI Toolkit in your research, please cite:

Reich M, Liefeld T, Gould J, Lerner J, Tamayo P, Mesirov JP. [GenePattern 2.0](http://www.nature.com/ng/journal/v38/n5/full/ng0506-500.html) Nature Genetics 38 no. 5 (2006): pp500-501 [Google Scholar](http://scholar.google.com/citations?user=lREO6vMAAAAJ&hl=en)
