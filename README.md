# Clinical Document Translation Pipeline

This project converts image-only clinical PDFs and images into validated, editable DOCX files while preserving source content and page geometry. Development is incremental; Milestone 1 establishes the reproducible project and environment checks but does not yet translate documents.

## Setup

Install Python 3.11 and [uv](https://docs.astral.sh/uv/), then run:

```bash
uv sync --all-extras --dev
uv run translate-doc --help
uv run translate-doc --check-system
```

LibreOffice is a system dependency used by later milestones for independent DOCX rendering and text recovery. Install it separately with Homebrew on macOS or the system package manager on Linux. `OPENAI_API_KEY` is required only for live extraction and translation calls; offline tests do not require it.

## Project structure

```text
data/       immutable supplied document pack
src/        translation package
eval/       evaluation harness, references, fixtures, and results
outputs/    validated deliverables and comparison renders
app/        Streamlit entry point
report/     architecture, assumptions, evidence, and final report
tests/      unit, integration, and synthetic tests
```

The supplied pack is preserved under `data/`. Paths in `data/manifest.json` are resolved relative to that manifest.

## Development commands

```bash
uv run pytest
uv run ruff check .
uv run mypy
```

## Safety scope

The provided files contain blank public forms and a published article, not patient data. The planned pipeline is an evaluation system, not evidence that handwriting or real patient documents can be translated safely.
