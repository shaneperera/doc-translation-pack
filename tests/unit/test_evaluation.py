from __future__ import annotations

from pathlib import Path

from doc_translation.adapters.docx import render_text_docx
from doc_translation.domain.critical_validation import CriticalToken
from doc_translation.domain.document import DocumentIR, PageGeometry, PageIR
from doc_translation.domain.region import BoundingBox, RegionIR
from doc_translation.evaluation import (
    ReviewedAnchors,
    ReviewedRegion,
    content_retention,
    critical_token_precision,
    critical_token_recall,
    editability_metrics,
    translation_anchor_accuracy,
)


def test_content_retention_uses_editable_text_and_region_bookmarks(tmp_path: Path) -> None:
    region = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=0, y=0, width=100, height=20),
        source_text="Hallo",
    )
    document = DocumentIR(
        source_sha256="abc123",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=100, height_points=100),
                regions=[region],
                reading_order=[region.region_id],
            )
        ],
    )
    output = tmp_path / "output.docx"
    render_text_docx(document, {region.region_id: "Hello"}, output)
    anchors = ReviewedAnchors(
        version=1,
        regions=[ReviewedRegion(region_id=region.region_id, expected_text="Hello")],
    )

    assert content_retention(output, anchors) == 1.0


def test_critical_token_recall_checks_region_value_and_unit(tmp_path: Path) -> None:
    region = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=0, y=0, width=100, height=20),
        source_text="Gewicht 5 mg",
    )
    document = DocumentIR(
        source_sha256="abc123",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=100, height_points=100),
                regions=[region],
                reading_order=[region.region_id],
            )
        ],
    )
    output = tmp_path / "output.docx"
    render_text_docx(document, {region.region_id: "Weight 5 mg"}, output)

    tokens = [
        CriticalToken(
            region_id=region.region_id,
            value="5",
            kind="number",
            unit="mg",
        ),
        CriticalToken(
            region_id=region.region_id,
            value="7",
            kind="number",
            unit="mg",
        ),
    ]

    assert critical_token_recall(output, tokens) == 0.5


def test_critical_token_precision_detects_an_unreviewed_number(tmp_path: Path) -> None:
    region = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=0, y=0, width=180, height=20),
        source_text="Gewicht 5 mg",
    )
    document = DocumentIR(
        source_sha256="abc123",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=200, height_points=100),
                regions=[region],
                reading_order=[region.region_id],
            )
        ],
    )
    output = tmp_path / "output.docx"
    render_text_docx(document, {region.region_id: "Weight 5 mg and 99 mg"}, output)

    tokens = [
        CriticalToken(
            region_id=region.region_id,
            value="5",
            kind="number",
            unit="mg",
        )
    ]

    assert critical_token_precision(output, tokens) == 0.5


def test_editability_metrics_reports_text_and_raster_counts(tmp_path: Path) -> None:
    region = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=0, y=0, width=100, height=20),
        source_text="Source",
    )
    document = DocumentIR(
        source_sha256="abc123",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=100, height_points=100),
                regions=[region],
                reading_order=[region.region_id],
            )
        ],
    )
    output = tmp_path / "output.docx"
    render_text_docx(document, {region.region_id: "Translated"}, output)

    assert editability_metrics(output).model_dump() == {
        "editable_text_count": 1,
        "page_sized_raster_count": 0,
    }


def test_translation_anchor_accuracy_compares_reviewed_text(tmp_path: Path) -> None:
    regions = [
        RegionIR(
            region_id="p0001-r0001",
            kind="text",
            box=BoundingBox(x=0, y=0, width=100, height=20),
            source_text="Hallo",
        ),
        RegionIR(
            region_id="p0001-r0002",
            kind="text",
            box=BoundingBox(x=0, y=20, width=100, height=20),
            source_text="Welt",
        ),
    ]
    document = DocumentIR(
        source_sha256="abc123",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=100, height_points=100),
                regions=regions,
                reading_order=[region.region_id for region in regions],
            )
        ],
    )
    output = tmp_path / "output.docx"
    render_text_docx(
        document,
        {"p0001-r0001": "Hello", "p0001-r0002": "World"},
        output,
    )
    anchors = ReviewedAnchors(
        version=1,
        regions=[
            ReviewedRegion(region_id="p0001-r0001", expected_text="Hello"),
            ReviewedRegion(region_id="p0001-r0002", expected_text="Earth"),
        ],
    )

    assert translation_anchor_accuracy(output, anchors) == 0.5
