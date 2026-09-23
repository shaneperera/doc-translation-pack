# Final report

## Setup and reproduction

Use Python 3.11 and LibreOffice. Before a live translation run, set `OPENAI_API_KEY` in the shell where you will run the CLI: `export OPENAI_API_KEY="your-key"`. Replace the placeholder with your key; do not add the key to the repository. Live calls also need access to `gpt-5.6-terra`.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
.venv/bin/translate-doc data/documents/DEU_child_checkup.pdf -t en -o outputs/DEU_child_checkup.docx
.venv/bin/translate-doc data/documents/KOR_case_report.pdf -t en -o outputs/KOR_case_report.docx
.venv/bin/translate-doc data/documents/JPN_referral.pdf -t en -o outputs/JPN_referral.docx
```

The final run produced 69 passing tests; Ruff and strict Mypy passed. A LibreOffice stress test kept 40 positioned cells on one source-sized page. Successful translations publish a DOCX and its `.audit.json`. The Japanese run exits at the fit check and publishes neither file.

The German and Korean output files are already present in the repository, so add `--force` to those two commands when regenerating them here.

To reproduce the editable-text and raster counts without model calls:

```sh
PYTHONPATH=src .venv/bin/python -c 'from doc_translation.eval_cli import main; raise SystemExit(main(["--anchors", "eval/anchors.example.json", "outputs/DEU_child_checkup.docx", "outputs/KOR_case_report.docx"]))'
```

The example anchor is a placeholder. Use only `editable_text_count`, `page_sized_raster_count`, and LibreOffice round-trip status from this command. Ignore its anchor-based scores. Source page counts come from `data/manifest.json`.

## Architecture and rejected alternatives

The pipeline normalizes each page, extracts editable regions, translates eligible text in batches of 10, then places DrawingML text boxes over one host paragraph per page. It checks immutable tokens and retries missing or oversized translations. Regions can widen into clear space; text shrinks to a 5 pt floor. An image-mark crop overlapping editable text is omitted to prevent duplicate source lettering; its background may be lost. LibreOffice checks editability, bookmarks, page count, and physical dimensions before publication.

I rejected full-page image backgrounds because they are not editable, normal Word flow because it loses the source coordinates, continuation pages because they break page parity, and text below 5 pt because it becomes too small. The renderer uses the same rules for every document. If a region still does not fit, the run fails rather than clipping text.

## Results

I narrowed the five-document pack to the first three for this effort: Japanese, German, and Korean. Only the German and Korean documents produced validated DOCX files. The Japanese document failed because region `p0001-r0019` still would not fit after safe widening and two shorter-translation attempts at 5 pt. The Italian form and German maternity record were not run.

| Document | Pages: source/output | Dimensions *(within 1 pt)* | Editable `w:t` nodes *(Word text nodes)* | Full-page rasters *(must be 0)* | Result |
|---|---:|---|---:|---:|---|
| Japanese referral | 1 / N/A | N/A | N/A | N/A | Fit check failed; no output |
| German child check-up | 2 / 2 | Pass | 65 | 0 | Published; both pages reviewed |
| Korean case report | 1 / 1 | Pass | 20 | 0 | Published; page reviewed |
| Italian adverse-reaction form | 1 / N/A | N/A | N/A | N/A | Not run; cut for time |
| German maternity record | 1 / N/A | N/A | N/A | N/A | Not run; cut for time |

## Measurement choice and limits

The pack had no reviewed labels or translations. I used the scans and manifest to check page count and size, checked immutable tokens and already-English spans, and compared the two rendered outputs with their source pages. The bundled anchor file is only an example, so this report makes no claim about translation accuracy. These checks cannot catch every omission, reading-order error, overlap, clipping issue, or clinical mistake.

## Failures encountered

- Japanese, page 1, region `p0001-r0019`: remained too long at the 5 pt floor after widening and two shorter-translation retries. The publication check stopped the run.
- German check-up, page 2, region `p0002-r0049`: failed the earlier 7 pt fit check. Widening and the 5 pt floor let a later run pass.
- German check-up, page 1, instruction banner: the cropped image mark contained `Zutreffendes bitte ankreuzen!` beneath the editable “Please check as applicable!” text. The renderer now skips an image-mark crop when its box overlaps editable text; the banner fill is lost, but the lettering no longer overlaps.
- Korean report, page 1: an earlier translation changed immutable tokens `제6` and `제3`. A later run passed after smaller batches and token checks with retries.

## What I would tell the customer

Do not use this pipeline for clinical decisions or unattended patient documents. Two documents passed structural checks and visual review, one failed, and two were not attempted. We also lack reviewed reference translations. Before clinical use, we need bilingual review and clinician sign-off, plus broader checks for content and layout across every page and document type.
