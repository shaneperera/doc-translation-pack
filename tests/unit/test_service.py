from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from pydantic import BaseModel

from doc_translation.adapters.extraction import ExtractionResponse
from doc_translation.adapters.translation import TranslationResponse
from doc_translation.domain.document import PageGeometry, PageIR
from doc_translation.domain.region import BoundingBox, RegionIR
from doc_translation.pipeline.service import translate_input


def test_translate_input_publishes_validated_docx(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (200, 200), "white").save(source)
    output = tmp_path / "output.docx"
    region = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=0, y=0, width=100, height=20),
        source_text="Hallo",
    )
    extraction = ExtractionResponse(
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=100, height_points=100),
                regions=[region],
                reading_order=[region.region_id],
            )
        ],
        language="de",
    )

    def parse(*, text_format: type[BaseModel], **_: object) -> SimpleNamespace:
        if text_format is ExtractionResponse:
            return SimpleNamespace(output_parsed=extraction)
        return SimpleNamespace(
            output_parsed=TranslationResponse(translations={region.region_id: "Hello"})
        )

    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    translate_input(source, output, client=client)

    assert output.is_file()
    audit = json.loads(output.with_suffix(".audit.json").read_text())
    assert audit["source_sha256"]
    assert audit["model"] == "gpt-5.6-terra"
    assert audit["regions"][0]["translated_text"] == "Hello"


def test_translate_input_leaves_output_absent_when_extraction_fails(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (20, 20), "white").save(source)
    output = tmp_path / "output.docx"

    def parse(**_: object) -> SimpleNamespace:
        raise RuntimeError("model failure")

    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))

    try:
        translate_input(source, output, client=client)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected model failure")

    assert not output.exists()


def test_translate_input_refuses_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (20, 20), "white").save(source)
    output = tmp_path / "output.docx"
    output.write_text("old")

    try:
        translate_input(source, output)
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected existing-output refusal")

    assert output.read_text() == "old"


def test_translate_input_leaves_output_absent_when_translation_fails(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (20, 20), "white").save(source)
    output = tmp_path / "output.docx"
    region = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=0, y=0, width=100, height=20),
        source_text="Hallo",
    )
    extraction = ExtractionResponse(
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=100, height_points=100),
                regions=[region],
                reading_order=[region.region_id],
            )
        ]
    )

    def parse(*, text_format: type[BaseModel], **_: object) -> SimpleNamespace:
        if text_format is ExtractionResponse:
            return SimpleNamespace(output_parsed=extraction)
        return SimpleNamespace(output_parsed=TranslationResponse(translations={}))

    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    with pytest.raises(ValueError):
        translate_input(source, output, client=client)

    assert not output.exists()
