# Assumptions

| ID | Assumption | Consequence | Validation and status |
|---|---|---|---|
| A-001 | The supplied pack contains public blank forms and one published article, not patient data. | Development fixtures may be committed, subject to the licences in `data/SOURCES.md`. | Stated by the provider in `data/README.md`; accepted for this evaluation. |
| A-002 | Evaluators can provide `OPENAI_API_KEY` and access `gpt-5.6-terra`. | Live extraction and translation cannot run without both. | Environment diagnostics check only key presence; model access remains unverified until the model adapter milestone. |
| A-003 | Evaluators can install LibreOffice on macOS or Linux. | Publication requires an independent LibreOffice render. | The publication gate renders every candidate and fails when LibreOffice is unavailable. |
| A-004 | A translated page must retain the Source Page's size, orientation, and page count while remaining legible at 5 pt or larger. | Text that cannot fit fails instead of clipping or creating a continuation page. | Covered by font-floor, dense-layout, page-count, and page-dimension checks. |
| A-005 | Paths in the supplied manifest are relative to the manifest file. | Moving the pack under `data/` preserves its internal references without editing the supplied manifest. | Verified by resolving every manifest path after the move. |
| A-006 | A standalone image without usable physical-resolution metadata is treated as 200 DPI. | Its inferred physical page size may differ from the scanner's intent, so the normalized page records `dpi_assumed=True`. | Covered by a synthetic no-DPI image test. JPEG density without physical units is treated as missing even when Pillow reports a nominal 72 DPI. |
