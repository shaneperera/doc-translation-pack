from __future__ import annotations

from pathlib import Path

import pytest

from doc_translation.adapters.docx import render_text_docx
from doc_translation.domain.document import DocumentIR, PageGeometry, PageIR
from doc_translation.domain.region import BoundingBox, RegionIR
from doc_translation.eval_cli import main


def test_evaluate_docs_prints_metric_definitions_and_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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
    anchors = tmp_path / "anchors.json"
    anchors.write_text(
        '{"version": 1, "regions": '
        '[{"region_id": "p0001-r0001", "expected_text": "Hello"}]}'
    )

    assert main(["--anchors", str(anchors), str(output)]) == 0
    captured = capsys.readouterr()
    assert "content_retention: represented reviewed regions" in captured.out
    assert "content_retention=1.000" in captured.out
    assert "translation_anchor_accuracy=1.000" in captured.out
    assert "critical_token_precision=1.000" in captured.out
    assert "critical_token_recall=1.000" in captured.out
    assert "median_anchor_iou=unavailable" in captured.out
    assert "libreoffice_roundtrip=unavailable" in captured.out
    assert "mean_content_retention=1.000" in captured.out


def test_evaluate_docs_accepts_anchor_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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
    output = tmp_path / "sample.docx"
    render_text_docx(document, {region.region_id: "Hello"}, output)
    anchors = tmp_path / "anchors"
    anchors.mkdir()
    (anchors / "sample.json").write_text(
        '{"version": 1, "regions": '
        '[{"region_id": "p0001-r0001", "expected_text": "Hello"}]}'
    )

    assert main(["--anchors", str(anchors), str(output)]) == 0
    assert "content_retention=1.000" in capsys.readouterr().out
