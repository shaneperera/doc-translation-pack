"""Command-line entry point for offline DOCX evaluation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from doc_translation.evaluation import (
    ReviewedAnchors,
    content_retention,
    editability_metrics,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evaluate-docs",
        description="Evaluate completed DOCX files without network or model calls.",
    )
    parser.add_argument("--anchors", required=True, type=Path)
    parser.add_argument("docs", nargs="+", type=Path)
    args = parser.parse_args(argv)

    anchors = ReviewedAnchors.model_validate_json(args.anchors.read_text())
    print("metrics:")
    print("content_retention: represented reviewed regions / reviewed regions")
    print("editable_text_count: Word w:t nodes in the DOCX")
    print("page_sized_raster_count: full-page raster drawings in the DOCX")

    retention_values: list[float] = []
    print("documents:")
    for path in args.docs:
        retention = content_retention(path, anchors)
        editability = editability_metrics(path)
        retention_values.append(retention)
        print(
            f"{path}: content_retention={retention:.3f} "
            f"editable_text_count={editability.editable_text_count} "
            f"page_sized_raster_count={editability.page_sized_raster_count}"
        )
    print("aggregate:")
    print(f"mean_content_retention={sum(retention_values) / len(retention_values):.3f}")
    return 0
