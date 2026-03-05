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

| |                                                                                                                         |
|---|-------------------------------------------------------------------------------------------------------------------------|
| 🧬 **Genomic Integration** | Natively targets the GenePattern ecosystem — supports Cloud, Notebook and the RESTful API.                              |
| 🤖 **AI/ML Workflows** | Six specialized LLM agents collaborate: Researcher → Planner → Generator → Validator, end-to-end.                       |
| ☁️ **Cloud Scalability** | Every generated module ships with a Dockerfile and is ready to deploy on GenePattern's cloud infrastructure.            |
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
| `MODULE_OUTPUT_DIR` | `./generated-modules` | Where modules are written |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | *(none)* | OpenTelemetry collector endpoint (see [Observability](#-observability)) |

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

Five AI agents work in a coordinated pipeline, each with a focused domain of expertise:

```
┌──────────────┐    ┌──────────────┐    ┌───────────────────────────────────────────────┐
│  Researcher  │───▶│   Planner    │───▶│              Artifact Generators              │
│              │    │              │    │  Wrapper · Manifest · ParamGroups · GPUnit    │
│ Web search,  │    │ Map params,  │    │  Documentation · Dockerfile                   │
│ CLI analysis │    │ design arch  │    │  (each with built-in validation loop ✓)       │
└──────────────┘    └──────────────┘    └───────────────────────────────────────────────┘
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

---

## 📁 Output Structure

Every module lands in `{MODULE_OUTPUT_DIR}/{tool_name}_{timestamp}/`:

```
samtools_20241222_143022/
├── wrapper.py             # Python wrapper — GenePattern calls this at runtime
├── manifest               # Module metadata, command template & parameter schema
├── paramgroups.json       # UI groupings for the GenePattern Notebook interface
├── test.yml               # GPUnit test suite (run with gpunit validate .)
├── README.md              # Human-readable user documentation
└── Dockerfile             # Pinned, reproducible container definition
```

---

## 📡 Live Status & Final Report

The toolkit streams real-time progress to your terminal:

```
[14:30:22] INFO: Created module directory: ./generated-modules/samtools_20241222_143022
[14:30:22] INFO: Starting research on the bioinformatics tool
[14:30:25] INFO: Research phase completed successfully
[14:30:25] INFO: Starting module planning based on research findings
[14:30:28] INFO: Planning phase completed successfully
[14:30:31] INFO: Attempt 1/5 for dockerfile
[14:30:37] INFO: Validation passed for dockerfile ✓
```

And delivers a full report at the end:

```
============================================================
 Module Generation Report
============================================================
Tool: samtools   |   Directory: ./generated-modules/samtools_20241222_143022
Research ✓   Planning ✓   Parameters Identified: 23

  wrapper        Generated ✓   Validated ✓   Attempts: 1
  manifest       Generated ✓   Validated ✓   Attempts: 1
  paramgroups    Generated ✓   Validated ✓   Attempts: 1
  gpunit         Generated ✓   Validated ✓   Attempts: 1
  documentation  Generated ✓   Validated ✓   Attempts: 1
  dockerfile     Generated ✓   Validated ✓   Attempts: 1

🎉 MODULE GENERATION SUCCESSFUL!
Your GenePattern module is ready in: ./generated-modules/samtools_20241222_143022
============================================================
```

---

## 🔭 Observability

The toolkit emits OpenTelemetry traces via [Logfire](https://logfire.pydantic.dev/) for every agent run — giving you deep visibility into research queries, planning decisions, artifact generation attempts, and validation outcomes.

### Viewing traces locally with Jaeger

Spin up a local [Jaeger](https://www.jaegertracing.io/) all-in-one container (no configuration required):

```bash
docker run --rm -it --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest
```

Then point the toolkit at the collector by setting the following in your `.env`:

```dotenv
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4318/v1/traces
```

Open [http://localhost:16686](http://localhost:16686) in your browser, run a module generation, and you'll see the full agent pipeline traced — including retries, token usage, and per-artifact timings.

---

## 🏗️ Architecture

The toolkit is built on [Pydantic AI](https://ai.pydantic.dev/) multi-agent primitives and follows a clean separation of concerns:

- **Agent Specialisation** — Each agent owns a single, well-defined artifact domain.
- **Structured Communication** — Agents exchange typed Pydantic models, not raw text.
- **Validation-in-the-Loop** — Linters are invoked as MCP server tools, keeping generation and validation tightly coupled.
- **Retry with Context** — Every failed validation attempt feeds its error back into the next prompt, guiding the agent toward a correct solution.

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
