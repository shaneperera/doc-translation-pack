# Clinical Document Translation

This Python 3.11 CLI turns scanned clinical PDFs into editable Word documents. It extracts and translates page regions, checks protected content, and publishes only after the generated DOCX passes structural and LibreOffice page checks. It is an evaluation prototype, not a clinical translation system.

## Setup

Install Python 3.11 and LibreOffice. For live extraction and translation, set the OpenAI key in the shell that runs the CLI:

```sh
export OPENAI_API_KEY="your-key"
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .
.venv/bin/translate-doc --check-system
.venv/bin/translate-doc --help
```

## Checks

```sh
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
```

## Repository layout

- `src/doc_translation/` contains the CLI, pipeline, domain models, and adapters.
- `data/` is the immutable supplied document pack.
- `outputs/` contains generated DOCX deliverables and audit sidecars.
- `eval/` contains the example reviewed-anchor format and offline evaluation harness.
- `report/` records architecture, evidence, assumptions, and results.
- `tests/` contains offline tests.

The supplied pack contains public blank forms and a published article, not patient data. Results on these files do not establish accuracy on patient records or suitability for clinical decisions.
