from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest
from lxml import etree  # type: ignore[import-untyped]
from PIL import Image

from doc_translation.adapters.docx import render_text_docx
from doc_translation.domain.document import DocumentIR, PageGeometry, PageIR
from doc_translation.domain.region import BoundingBox, RegionIR

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _document() -> DocumentIR:
    return DocumentIR(
        source_sha256="abc123",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=300, height_points=500),
                regions=[
                    RegionIR(
                        region_id="p0001-r0001",
                        kind="text",
                        box=BoundingBox(x=10, y=10, width=100, height=20),
                        source_text="Original ✓",
                    )
                ],
                reading_order=["p0001-r0001"],
            ),
            PageIR(
                page_number=2,
                geometry=PageGeometry(width_points=600, height_points=400),
                regions=[],
                reading_order=[],
            ),
        ],
    )


def test_renders_editable_text_and_source_page_sizes(tmp_path: Path) -> None:
    output = tmp_path / "result.docx"

    render_text_docx(_document(), {"p0001-r0001": "Translated ✓"}, output)

    with ZipFile(output) as package:
        document_xml = etree.fromstring(package.read("word/document.xml"))
        text_nodes = document_xml.findall(f".//{WORD_NS}t")
        page_sizes = document_xml.findall(f".//{WORD_NS}pgSz")
        assert [node.text for node in text_nodes] == ["Translated ✓"]
        assert 'cx="1270000"' in etree.tostring(document_xml).decode()
        assert [(node.get(f"{WORD_NS}w"), node.get(f"{WORD_NS}h")) for node in page_sizes] == [
            ("6000", "10000"),
            ("12000", "8000"),
        ]
        assert "word/media/" not in " ".join(package.namelist())


def test_rejects_missing_translation_and_unsupported_region(tmp_path: Path) -> None:
    region = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=0, y=0, width=10, height=10),
        source_text="Original",
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

    with pytest.raises(ValueError, match="missing translated text"):
        render_text_docx(document, {}, tmp_path / "missing.docx")


def test_renders_table_cells_checkbox_and_region_bookmarks(tmp_path: Path) -> None:
    table = RegionIR(
        region_id="p0001-r0001",
        kind="table",
        box=BoundingBox(x=0, y=0, width=100, height=50),
        translation_eligible=False,
    )
    first_cell = RegionIR(
        region_id="p0001-r0002",
        kind="cell",
        box=BoundingBox(x=0, y=0, width=50, height=25),
        parent_region_id=table.region_id,
    )
    second_cell = RegionIR(
        region_id="p0001-r0003",
        kind="cell",
        box=BoundingBox(x=50, y=0, width=50, height=25),
        source_text="",
        parent_region_id=table.region_id,
    )
    checkbox = RegionIR(
        region_id="p0001-r0004",
        kind="checkbox",
        box=BoundingBox(x=0, y=60, width=10, height=10),
        translation_eligible=False,
        checked=True,
    )
    document = DocumentIR(
        source_sha256="abc123",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=100, height_points=100),
                regions=[table, first_cell, second_cell, checkbox],
                reading_order=[
                    table.region_id,
                    first_cell.region_id,
                    second_cell.region_id,
                    checkbox.region_id,
                ],
            )
        ],
    )
    output = tmp_path / "controls.docx"

    render_text_docx(document, {first_cell.region_id: "Name", second_cell.region_id: ""}, output)

    with ZipFile(output) as package:
        document_xml = etree.fromstring(package.read("word/document.xml"))
        xml_text = package.read("word/document.xml").decode()
        assert document_xml.find(f".//{WORD_NS}tbl") is not None
        assert "☑" in xml_text
        assert 'w:name="p0001_r0001"' in xml_text
        assert 'w:name="p0001_r0002"' in xml_text
        assert 'w:name="p0001_r0004"' in xml_text


def test_renders_rotated_text_as_editable_drawingml(tmp_path: Path) -> None:
    region = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=0, y=0, width=100, height=30),
        source_text="Header",
        rotation=47.5,
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

    output = tmp_path / "rotated.docx"
    render_text_docx(document, {region.region_id: "Translated"}, output)

    with ZipFile(output) as package:
        xml_text = package.read("word/document.xml").decode()
        assert "Translated" in xml_text
        assert 'rot="2850000"' in xml_text


def test_renders_image_mark_as_cropped_media(tmp_path: Path) -> None:
    raster = tmp_path / "page.png"
    Image.new("RGB", (200, 200), "red").save(raster)
    region = RegionIR(
        region_id="p0001-r0001",
        kind="image_mark",
        box=BoundingBox(x=25, y=25, width=50, height=50),
        translation_eligible=False,
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

    output = tmp_path / "image-mark.docx"
    render_text_docx(document, {}, output, {1: raster})

    with ZipFile(output) as package:
        assert "word/media/image1.png" in package.namelist()
        assert 'w:name="p0001_r0001"' in package.read("word/document.xml").decode()
