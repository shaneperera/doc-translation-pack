from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest
from lxml import etree  # type: ignore[import-untyped]
from PIL import Image

from doc_translation.adapters.docx import expand_text_regions, render_text_docx
from doc_translation.domain.document import DocumentIR, PageGeometry, PageIR
from doc_translation.domain.region import BoundingBox, RegionIR

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DRAWING_NS = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"


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
        assert 'w:val="22"' in etree.tostring(document_xml).decode()
        assert 'cx="1270000"' in etree.tostring(document_xml).decode()
        assert document_xml.find(f".//{DRAWING_NS}anchor") is not None
        assert "<wp:posOffset>127000</wp:posOffset>" in etree.tostring(
            document_xml
        ).decode()
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
        assert document_xml.find(f".//{WORD_NS}tbl") is None
        assert "☑" in xml_text
        assert 'w:name="p0001_r0002"' in xml_text
        assert 'w:name="p0001_r0003"' in xml_text
        assert 'w:name="p0001_r0004"' in xml_text
        assert xml_text.count("<a:ln w=\"12700\">") == 3


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


def test_long_text_fails_below_five_point_floor(tmp_path: Path) -> None:
    region = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=0, y=0, width=20, height=10),
    )
    blocker = RegionIR(
        region_id="p0001-r0002",
        kind="text",
        box=BoundingBox(x=30, y=0, width=20, height=10),
        translation_eligible=False,
    )
    document = DocumentIR(
        source_sha256="abc123",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=100, height_points=100),
                regions=[region, blocker],
                reading_order=[region.region_id, blocker.region_id],
            )
        ],
    )

    with pytest.raises(ValueError, match="does not fit at 5 pt"):
        render_text_docx(
            document,
            {region.region_id: "A very long translated label"},
            tmp_path / "small-box.docx",
        )


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


def test_skips_image_mark_under_overlapping_editable_text(tmp_path: Path) -> None:
    raster = tmp_path / "page.png"
    Image.new("RGB", (200, 200), "red").save(raster)
    image_mark = RegionIR(
        region_id="p0001-r0001",
        kind="image_mark",
        box=BoundingBox(x=25, y=25, width=50, height=50),
        translation_eligible=False,
    )
    text = RegionIR(
        region_id="p0001-r0002",
        kind="text",
        box=BoundingBox(x=30, y=30, width=45, height=15),
        source_text="Original wording",
    )
    document = DocumentIR(
        source_sha256="abc123",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=100, height_points=100),
                regions=[image_mark, text],
                reading_order=[image_mark.region_id, text.region_id],
            )
        ],
    )
    output = tmp_path / "overlap.docx"

    render_text_docx(document, {text.region_id: "Translated wording"}, output, {1: raster})

    with ZipFile(output) as package:
        assert not any(name.startswith("word/media/") for name in package.namelist())
        xml = package.read("word/document.xml").decode()
        assert "Translated wording" in xml
        assert 'w:name="p0001_r0001"' in xml


def test_many_positioned_regions_share_one_page_host(tmp_path: Path) -> None:
    regions = [
        RegionIR(
            region_id=f"p0001-r{index:04d}",
            kind="cell",
            box=BoundingBox(
                x=((index - 1) % 5) * 55,
                y=((index - 1) // 5) * 25,
                width=50,
                height=20,
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
                geometry=PageGeometry(width_points=300, height_points=500),
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

    with ZipFile(output) as package:
        document_xml = etree.fromstring(package.read("word/document.xml"))
        assert len(document_xml.findall(f".//{WORD_NS}p")) == 41
        assert len(document_xml.findall(f".//{DRAWING_NS}anchor")) == 40
        body = document_xml.find(f"{WORD_NS}body")
        assert len(body.findall(f"{WORD_NS}p")) == 1


def test_expands_overflowing_text_to_nearest_horizontal_region(tmp_path: Path) -> None:
    label = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=10, y=10, width=20, height=10),
        source_text="Label",
    )
    neighbor = RegionIR(
        region_id="p0001-r0002",
        kind="text",
        box=BoundingBox(x=100, y=10, width=50, height=10),
        source_text="Neighbor",
    )
    document = DocumentIR(
        source_sha256="abc123",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=200, height_points=100),
                regions=[label, neighbor],
                reading_order=[label.region_id, neighbor.region_id],
            )
        ],
    )

    rendered = render_text_docx(
        document,
        {label.region_id: "Expanded section label", neighbor.region_id: "Neighbor"},
        tmp_path / "expanded.docx",
    )

    assert rendered.pages[0].regions[0].box.width == 90


def test_does_not_expand_text_into_an_overlapping_region(tmp_path: Path) -> None:
    label = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=10, y=10, width=20, height=10),
        source_text="Label",
    )
    overlapping = RegionIR(
        region_id="p0001-r0002",
        kind="text",
        box=BoundingBox(x=15, y=10, width=60, height=10),
        source_text="Other",
        translation_eligible=False,
    )
    document = DocumentIR(
        source_sha256="abc123",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=200, height_points=100),
                regions=[label, overlapping],
                reading_order=[label.region_id, overlapping.region_id],
            )
        ],
    )

    rendered = expand_text_regions(
        document, {label.region_id: "Expanded section label"}
    )

    assert rendered.pages[0].regions[0].box.width == label.box.width


def test_renders_lines_and_skips_watermarks(tmp_path: Path) -> None:
    line = RegionIR(
        region_id="p0001-r0001",
        kind="line",
        box=BoundingBox(x=10, y=20, width=80, height=3),
        translation_eligible=False,
    )
    watermark = RegionIR(
        region_id="p0001-r0002",
        kind="watermark",
        box=BoundingBox(x=10, y=30, width=80, height=20),
        source_text="COPY",
        translation_eligible=False,
    )
    document = DocumentIR(
        source_sha256="abc123",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=100, height_points=100),
                regions=[line, watermark],
                reading_order=[line.region_id, watermark.region_id],
            )
        ],
    )
    output = tmp_path / "line.docx"

    render_text_docx(document, {}, output)

    with ZipFile(output) as package:
        xml = package.read("word/document.xml").decode()
        assert '<a:srgbClr val="000000"/>' in xml
        assert 'w:name="p0001_r0001"' in xml
        assert 'w:name="p0001_r0002"' not in xml
