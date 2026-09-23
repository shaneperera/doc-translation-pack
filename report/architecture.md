# Architecture

The `translate-doc` CLI delegates to one pipeline service. The service normalizes each source page, extracts generic positioned regions, translates eligible text in batches, validates protected content, and renders editable DrawingML text over a one-paragraph-per-page host. Tables group regions; cells, checkboxes, lines, and isolated image marks are rendered separately. An image-mark crop that overlaps editable text is omitted so embedded source lettering is not duplicated; its background or decoration may be lost. Text regions may widen into unused horizontal space and shrink to a 5 pt floor.

The service writes to a temporary workspace. Before publication, it checks editable text and bookmarks, rejects full-page raster backgrounds, renders with LibreOffice, and verifies output page count and dimensions against the source. A failure leaves the requested output unpublished. The offline evaluation harness checks document structure and only scores reviewed anchors supplied by the evaluator; the checked-in example anchors are placeholders.

## Repository boundaries

- `data/` is immutable input and source metadata.
- `outputs/` accepts only validated, atomically published deliverables and comparisons.
- Work in progress and failed runs stay in temporary directories.
- `eval/` operates offline on supplied references and outputs.
- `report/` records architecture, assumptions, evidence, and results.
