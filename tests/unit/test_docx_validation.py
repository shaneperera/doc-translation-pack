from __future__ import annotations

from pathlib import Path

from doc_translation.adapters.docx import render_text_docx
from doc_translation.adapters.docx_validation import find_libreoffice, inspect_docx
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
    assert inspection.page_sized_raster_count == 0


def test_find_libreoffice_returns_path_or_none() -> None:
    assert find_libreoffice() is None or isinstance(find_libreoffice(), str)
