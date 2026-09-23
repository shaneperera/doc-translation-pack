# Architecture

The scaffold reserves three package layers behind a thin CLI:

- `domain` owns document concepts and validation policy and performs no external I/O.
- `pipeline` coordinates translation Runs and depends on `domain`.
- `adapters` integrate file formats, models, rendering tools, and the filesystem through seams required by `pipeline`.
- The CLI will call `pipeline`; it does not contain translation logic.

Dependencies point toward `domain`. A seam is introduced only when behavior actually varies or must be replaced in an offline test. This keeps the public translation interface small while external-tool complexity stays local to its adapter.

Milestone 1 implements only package scaffolding, environment diagnostics, and command help. The three layers contain no speculative interfaces yet. Extraction, translation, rendering, evaluation, and publication are absent.

## Repository boundaries

- `data/` is immutable input and source metadata.
- `outputs/` accepts only validated, atomically published deliverables and comparisons.
- Work in progress and failed Runs stay in temporary directories.
- `eval/` operates offline on committed references and outputs.
- `report/` accumulates the evidence used by the final report.
