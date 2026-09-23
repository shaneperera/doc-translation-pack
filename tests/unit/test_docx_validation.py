from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from docx import Document
from docx.shared import Inches
from PIL import Image

from doc_translation.adapters.docx import render_text_docx
from doc_translation.adapters.docx_validation import (
    find_libreoffice,
    inspect_docx,
    roundtrip_docx,
    validate_docx_for_publication,
)
from doc_translation.domain.document import DocumentIR, PageGeometry, PageIR
from doc_translation.domain.region import BoundingBox, RegionIR


def test_inspect_docx_finds_editable_text_and_no_full_page_raster(tmp_path: Path) -> None:
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

    inspection = inspect_docx(output)

    assert inspection.editable_text_count == 1
    assert inspection.bookmark_count == 1
    assert inspection.page_sized_raster_count == 0


@pytest.mark.skipif(find_libreoffice() is None, reason="LibreOffice is not installed")
def test_many_positioned_regions_render_as_one_source_sized_page(tmp_path: Path) -> None:
    regions = [
        RegionIR(
            region_id=f"p0001-r{index:04d}",
            kind="cell",
            box=BoundingBox(
                x=((index - 1) % 5) * 100 + 20,
                y=((index - 1) // 5) * 35 + 20,
                width=90,
                height=25,
            ),
            source_text="Field",
        )
        for index in range(1, 41)
    ]
    document = DocumentIR(
        source_sha256="abc123",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(
                    width_points=595.2756,
                    height_points=841.8898,
                ),
                regions=regions,
                reading_order=[region.region_id for region in regions],
            )
        ],
    )
    output = tmp_path / "dense.docx"
    render_text_docx(
        document,
        {region.region_id: "Field" for region in regions},
        output,
    )

    pdf = validate_docx_for_publication(output, document.pages, tmp_path / "rendered")

    with pymupdf.open(pdf) as rendered:  # type: ignore[no-untyped-call]
        assert len(rendered) == 1


def test_find_libreoffice_returns_path_or_none() -> None:
    assert find_libreoffice() is None or isinstance(find_libreoffice(), str)


def test_inspect_docx_rejects_a_full_page_raster(tmp_path: Path) -> None:
    raster = tmp_path / "page.png"
    Image.new("RGB", (100, 100), "white").save(raster)
    document = Document()
    section = document.sections[0]
    section.page_width = Inches(1)
    section.page_height = Inches(1)
    document.add_picture(str(raster), width=Inches(1), height=Inches(1))
    output = tmp_path / "raster.docx"
    document.save(str(output))

    assert inspect_docx(output).page_sized_raster_count == 1


def test_roundtrip_requires_libreoffice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "doc_translation.adapters.docx_validation.find_libreoffice", lambda: None
    )

    try:
        roundtrip_docx(tmp_path / "missing.docx", tmp_path / "roundtrip")
    except RuntimeError as error:
        assert "LibreOffice is required" in str(error)
    else:
        raise AssertionError("expected missing LibreOffice failure")
