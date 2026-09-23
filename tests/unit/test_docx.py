from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest
from lxml import etree  # type: ignore[import-untyped]

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
