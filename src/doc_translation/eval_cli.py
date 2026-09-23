"""Command-line entry point for offline DOCX evaluation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from doc_translation.adapters.docx_validation import inspect_docx
from doc_translation.evaluation import (
    ReviewedAnchors,
    content_retention,
    critical_token_precision,
    critical_token_recall,
    libreoffice_roundtrip_status,
    median_anchor_iou,
    translation_anchor_accuracy,
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
    print("translation_anchor_accuracy: exact reviewed text matches / reviewed regions")
    print("critical_token_precision: numeric-like output tokens matching reviewed tokens")
    print("critical_token_recall: reviewed critical tokens preserved in their regions")
    print("editable_text_count: Word w:t nodes in the DOCX")
    print("page_sized_raster_count: full-page raster drawings in the DOCX")
    print("median_anchor_iou: median reviewed-box/output-box intersection-over-union")
    print("libreoffice_roundtrip: office reopen/render/text recovery status")

    retention_values: list[float] = []
    anchor_values: list[float] = []
    print("documents:")
    for path in args.docs:
        retention = content_retention(path, anchors)
        anchor_accuracy = translation_anchor_accuracy(path, anchors)
        token_precision = critical_token_precision(path, anchors.critical_tokens)
        token_recall = critical_token_recall(path, anchors.critical_tokens)
        editability = inspect_docx(path)
        audit_path = path.with_suffix(".audit.json")
        iou = median_anchor_iou(audit_path, anchors) if audit_path.exists() else None
        roundtrip = libreoffice_roundtrip_status(path)
        retention_values.append(retention)
        anchor_values.append(anchor_accuracy)
        print(
            f"{path}: content_retention={retention:.3f} "
            f"translation_anchor_accuracy={anchor_accuracy:.3f} "
            f"critical_token_precision={token_precision:.3f} "
            f"critical_token_recall={token_recall:.3f} "
            f"editable_text_count={editability.editable_text_count} "
            f"page_sized_raster_count={editability.page_sized_raster_count} "
            f"median_anchor_iou={iou if iou is not None else 'unavailable'} "
            f"libreoffice_roundtrip={roundtrip}"
        )
    print("aggregate:")
    print(f"mean_content_retention={sum(retention_values) / len(retention_values):.3f}")
    print(f"mean_translation_anchor_accuracy={sum(anchor_values) / len(anchor_values):.3f}")
    return 0
